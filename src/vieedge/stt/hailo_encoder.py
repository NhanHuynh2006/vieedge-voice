"""Whisper/PhoWhisper encoder on the Hailo-8L NPU (HEF compiled by hailo_compile/), plus an ONNX
Runtime stand-in with the identical interface (used on the laptop and to measure HEF-vs-ONNX drift).

Encoder input: log-mel of a fixed window (tiny 10 s -> 1000 frames, base 5 s -> 500 frames);
output: (1, frames/2, d_model) hidden states for the CPU decoder.
"""
from __future__ import annotations

import logging
import threading
import time

import numpy as np

log = logging.getLogger(__name__)


class HailoEncoder:
    where = "npu"

    def __init__(self, hef_path: str):
        from hailo_platform import HEF, FormatType, HailoSchedulingAlgorithm, VDevice

        self.hef_path = hef_path
        hef = HEF(hef_path)
        in_info = hef.get_input_vstream_infos()[0]
        out_info = hef.get_output_vstream_infos()[0]
        self.in_shape = tuple(in_info.shape)  # NHWC without batch, e.g. (1, 1000, 80)
        self.out_shape = tuple(out_info.shape)
        self.frames = int(np.prod(self.in_shape)) // 80
        self.window_s = self.frames / 100.0
        params = VDevice.create_params()
        params.scheduling_algorithm = HailoSchedulingAlgorithm.ROUND_ROBIN
        self.vdevice = VDevice(params)
        self.model = self.vdevice.create_infer_model(hef_path)
        self.model.input().set_format_type(FormatType.FLOAT32)
        self.model.output().set_format_type(FormatType.FLOAT32)
        self.cfg_ctx = self.model.configure()
        self.configured = self.cfg_ctx.__enter__()
        self.bindings = self.configured.create_bindings()
        self.out_buf = np.empty(self.model.output().shape, dtype=np.float32)
        self.lock = threading.Lock()
        self.busy_s = 0.0
        self.calls = 0
        log.info("Hailo encoder %s in=%s out=%s window=%.1fs", hef_path, self.in_shape, self.out_shape, self.window_s)

    def encode(self, mel: np.ndarray) -> np.ndarray:
        """mel (80, frames) -> (1, frames/2, d_model)"""
        x = np.ascontiguousarray(mel.T.reshape((1,) + self.in_shape).astype(np.float32))  # NHWC
        with self.lock:
            t0 = time.monotonic()
            self.bindings.input().set_buffer(x)
            self.bindings.output().set_buffer(self.out_buf)
            self.configured.run([self.bindings], 10_000)
            out = self.bindings.output().get_buffer().copy()
            self.busy_s += time.monotonic() - t0
            self.calls += 1
        return out.reshape(1, -1, out.shape[-1])

    def chip_temperature(self) -> float | None:
        try:
            dev = self.vdevice.get_physical_devices()[0]
            return float(dev.control.get_chip_temperature().ts0_temperature)
        except Exception:
            return None

    def close(self) -> None:
        try:
            self.cfg_ctx.__exit__(None, None, None)
            self.vdevice.release()
        except Exception:
            pass


class OnnxEncoder:
    """Same contract as HailoEncoder, FP32 ONNX (export from hailo_compile/export_phowhisper.py)."""

    where = "cpu-onnx"

    def __init__(self, onnx_path: str, threads: int = 2):
        import onnxruntime as ort

        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        self.sess = ort.InferenceSession(onnx_path, sess_options=so, providers=["CPUExecutionProvider"])
        inp = self.sess.get_inputs()[0]
        self.in_name = inp.name
        self.frames = int(inp.shape[-1])  # (1, 80, 1, frames)
        self.window_s = self.frames / 100.0
        self.busy_s = 0.0
        self.calls = 0

    def encode(self, mel: np.ndarray) -> np.ndarray:
        x = mel[None, :, None, :].astype(np.float32)
        t0 = time.monotonic()
        out = self.sess.run(None, {self.in_name: x})[0]
        self.busy_s += time.monotonic() - t0
        self.calls += 1
        return out.reshape(1, -1, out.shape[-1])

    def chip_temperature(self) -> float | None:
        return None

    def close(self) -> None: ...
