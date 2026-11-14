#!/usr/bin/env python3
"""TTS experiments T0-T2 (PLAN §6).

T0/T1  voices vi_VN-vais1000-medium vs vi_VN-25hours_single-low (vs vivos-x_low): time to first
       audio sample of a sentence, synthesis time, RTF; writes the 20 listening sentences as WAV +
       a scoring sheet for the 🧑 MOS (1-5) session (review_app --mode mos).
T2     30 sentences with numbers/dates/units, with and without vi_normalize:
       objective proxy = PhoWhisper reads the TTS audio back, WER against the normalised text;
       + WAVs and a sheet for the 🧑 30-sentence listening check (review_app --mode numbers).
"""
from __future__ import annotations

import argparse
import csv
import json
import wave
from pathlib import Path

import numpy as np

from common import append_experiment, pct, results_dir, wer
from vieedge.config import load_config
from vieedge.tts.piper_tts import PiperTTS
from vieedge.tts.vi_normalize import normalize

MOS_SENTENCES = [
    "Xin chào, mình là trợ lý giọng nói chạy hoàn toàn trên thiết bị.",
    "Hà Nội là thủ đô của Việt Nam, nằm ở đồng bằng sông Hồng.",
    "Bầu trời có màu xanh vì ánh sáng xanh bị không khí tán xạ mạnh hơn các màu khác.",
    "Bạn nên uống đủ nước mỗi ngày và ngủ đủ giấc để giữ sức khỏe.",
    "Mình không chắc về thông tin này, bạn nên kiểm tra lại từ nguồn đáng tin cậy.",
    "Phở là món ăn truyền thống nổi tiếng của người Việt.",
    "Trái Đất quay quanh Mặt Trời mất khoảng một năm.",
    "Vịnh Hạ Long được công nhận là di sản thiên nhiên thế giới.",
    "Muốn học tốt, bạn hãy chia nhỏ thời gian và ôn tập thường xuyên.",
    "Tết Nguyên Đán là dịp sum họp gia đình quan trọng nhất trong năm.",
    "Robot có thể giúp con người làm những công việc nặng nhọc và nguy hiểm.",
    "Mình là trợ lý offline nên không biết thời tiết hôm nay.",
    "Cà phê sữa đá là thức uống quen thuộc của nhiều người Việt Nam.",
    "Nước sôi ở một trăm độ xê khi ở áp suất bình thường.",
    "Bạn có thể hỏi mình về lịch sử, địa lý, khoa học hoặc đời sống.",
    "Đi xe máy thì nhớ đội mũ bảo hiểm và tuân thủ luật giao thông nhé.",
    "Cây xanh hấp thụ khí các bô níc và nhả ra khí ô xi.",
    "Truyện Kiều là tác phẩm nổi tiếng của đại thi hào Nguyễn Du.",
    "Mặt Trăng không tự phát sáng mà phản chiếu ánh sáng Mặt Trời.",
    "Cảm ơn bạn đã trò chuyện, chúc bạn một ngày vui vẻ.",
]

NUMBER_SENTENCES = [
    "Hôm nay là ngày 03/10/2026.", "Cuộc họp bắt đầu lúc 14:30.", "Giá vé là 25.000đ một người.",
    "Tỷ lệ đạt là 87,5%.", "Xe chạy với tốc độ 60 km/h.", "Nhiệt độ ngoài trời là 37°C.",
    "Dân số Việt Nam khoảng 100 triệu người.", "Năm 1945 là năm Cách mạng tháng Tám thành công.",
    "Đỉnh Phan Xi Păng cao 3.143 m.", "Sông Mê Kông dài khoảng 4.350 km.", "Hẹn gặp lúc 7h30 sáng thứ 2.",
    "Chiếc điện thoại nặng 185 g.", "Bạn cần 2 lít nước mỗi ngày.", "Pi xấp xỉ bằng 3,14.",
    "Diện tích Hà Nội là 3.359 km².", "Số điện thoại tổng đài là 1900 1234.", "Giảm giá 50% từ 1/6 đến 15/6.",
    "Ngày 30/4/1975 đất nước thống nhất.", "Thế kỷ XXI bắt đầu từ năm 2001.", "Lớp có 42 học sinh, 21 nam và 21 nữ.",
    "Chip Hailo-8L đạt 13 TOPS.", "Pin dung lượng 5.000 mAh.", "Một giờ có 3.600 giây.",
    "Lãi suất là 6,8% một năm.", "Từ 5-10 phút là xong.", "Bộ nhớ 8 GB và ổ cứng 256 GB.",
    "Giá 1 USD khoảng 25.000 đồng.", "Cao 1,75 m, nặng 68 kg.", "Lúc 23:59 ngày 31/12.", "Có 2/3 số người đồng ý.",
]


def save_wav(path: Path, audio: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config")
    ap.add_argument("--voices", nargs="+", default=["vi_VN-vais1000-medium", "vi_VN-25hours_single-low", "vi_VN-vivos-x_low"])
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--t2", action="store_true", help="run T2 (normalisation on/off) with ASR read-back")
    ap.add_argument("--asr-model", default="stt/ct2/phowhisper-base-int8")
    a = ap.parse_args()
    cfg = load_config(a.config)
    out = results_dir() / "audio"
    for v in a.voices:
        tts = PiperTTS(cfg.model_path(f"tts/piper/{v}.onnx"), a.threads)
        tts.warmup()
        synth, rtf, first = [], [], []
        for i, s in enumerate(MOS_SENTENCES):
            r = tts.synthesize(s)
            synth.append(r.synth_ms)
            rtf.append(r.rtf)
            save_wav(out / f"mos_{v}" / f"{i:02d}.wav", r.audio, r.sample_rate)
            # first-audio of a streamed answer = synthesis time of its first chunk (~first sentence)
            first.append(r.synth_ms)
        sheet = out / f"mos_{v}" / "sheet.csv"
        with open(sheet, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["file", "text", "rater", "score_1_5"])
            for i, s in enumerate(MOS_SENTENCES):
                w.writerow([f"{i:02d}.wav", s, "", ""])
        res = {"voice": v, "synth_ms": pct(synth), "rtf": pct(rtf, (50, 95)), "sample_rate": tts.sample_rate}
        print(json.dumps(res, ensure_ascii=False))
        append_experiment({"exp_id": "T0" if "medium" in v else "T1", "threads": a.threads,
                           "notes": f"tts={v};synth_p50_ms={res['synth_ms']['p50']};synth_p95_ms={res['synth_ms']['p95']};"
                                    f"rtf_p50={res['rtf']['p50']};mos=see review_app"}, raw=res)

    if a.t2:
        from vieedge.audio.resample import resample
        from vieedge.stt.cpu_ct2 import CT2Whisper

        asr = CT2Whisper(cfg.model_path(a.asr_model), "int8", 4, beam_size=3, window_s=30)
        v = a.voices[0]
        tts = PiperTTS(cfg.model_path(f"tts/piper/{v}.onnx"), a.threads)
        rows = {"norm": [], "raw": []}
        for i, s in enumerate(NUMBER_SENTENCES):
            target = normalize(s)  # what a listener should hear
            for mode, norm in (("norm", True), ("raw", False)):
                r = tts.synthesize(s, normalize_text=norm)
                save_wav(out / f"t2_{mode}" / f"{i:02d}.wav", r.audio, r.sample_rate)
                hyp = asr.transcribe(resample(r.audio, r.sample_rate, 16000)).text
                rows[mode].append({"i": i, "text": s, "target": target, "asr": hyp})
        res = {m: {"wer_vs_spoken_target": wer([x["target"] for x in rs], [x["asr"] for x in rs]), "items": rs} for m, rs in rows.items()}
        for mode in ("norm", "raw"):
            sheet = out / f"t2_{mode}" / "sheet.csv"
            with open(sheet, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["file", "text", "expected_reading", "rater", "read_correctly_y_n"])
                for x in rows[mode]:
                    w.writerow([f"{x['i']:02d}.wav", x["text"], x["target"], "", ""])
        print({m: round(r["wer_vs_spoken_target"], 3) for m, r in res.items()})
        append_experiment({"exp_id": "T2", "notes": f"tts={v};asr_readback_wer_norm={res['norm']['wer_vs_spoken_target']:.3f};"
                                                    f"asr_readback_wer_raw={res['raw']['wer_vs_spoken_target']:.3f};human=see review_app"},
                          raw=res)


if __name__ == "__main__":
    main()
