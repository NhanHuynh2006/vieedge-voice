#!/usr/bin/env python3
"""LLM ladder M0-M5 (PLAN §6) with llama-server: speed (TTFT, tokens/s, RAM), knowledge accuracy
(Global-MMLU vi, Apache-2.0; VMLU validation mirror as a secondary signal) and spoken answers for judge.py.

  # M1 quantisation ladder (speed on the Pi; quality can run anywhere — same GGUF, same numbers)
  bench_llm.py --exp M1 --models llm/gguf/qwen2.5-1.5b-vi-voice-{Q8_0,Q6_K,Q5_K_M,Q4_K_M,Q3_K_M}.gguf --speed 30 --quality 400
  # M0 generic build + F16
  bench_llm.py --exp M0 --models llm/gguf/qwen2.5-1.5b-vi-voice-F16.gguf --server-bin /opt/llama-generic/bin/llama-server
  # M3 speculative decoding, M4 prompt cache off, M5 threads
  bench_llm.py --exp M3 --models llm/gguf/qwen2.5-1.5b-vi-voice-Q4_K_M.gguf --draft llm/gguf/qwen2.5-0.5b-vi-voice-Q8_0.gguf
  bench_llm.py --exp M4 --models ... --no-cache
  bench_llm.py --exp M5 --models ... --threads 2 3 4
  # answers for the judge (M2: small+LoRA vs bigger without LoRA)
  bench_llm.py --exp M2 --models a.gguf b.gguf --answers 0
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path

from common import ROOT, append_experiment, check_thermal, pct, results_dir, thermal_state
from vieedge.config import load_config, set_override
from vieedge.llm.llamacpp_stream import LlamaClient, LlamaServer, LLMStats
from vieedge.llm.prompts import build_messages
from vieedge.telemetry.sysmon import proc_rss_mb

MCQ_SYSTEM = "Bạn là trợ lý làm bài trắc nghiệm. Chỉ trả lời bằng một chữ cái A, B, C hoặc D."
MCQ_GRAMMAR = 'root ::= "A" | "B" | "C" | "D"'


def qa_questions(n: int | None, split: str = "test") -> list[dict]:
    for base in (ROOT / "data" / "qa", Path("/opt/vieedge/data/qa")):
        p = base / f"{split}.jsonl"
        if p.exists():
            rows = [json.loads(l) for l in open(p, encoding="utf-8")]
            return rows[:n] if n else rows
    return [{"q": q, "a": ""} for q in ["Thủ đô của Việt Nam là gì?", "Vì sao bầu trời có màu xanh?", "Một năm có bao nhiêu ngày?"]]


def mcq_items(n: int, source: str, seed: int = 0) -> list[dict]:
    rnd = random.Random(seed)
    items = []
    if source == "global_mmlu":
        import pandas as pd

        for base in (ROOT / "data" / "llm_bench", Path("/opt/vieedge/data/llm_bench")):
            p = base / "global_mmlu_vi_test.parquet"
            if p.exists():
                df = pd.read_parquet(p)
                # stratified by subject_category so the subset mirrors the full test set
                parts = [g.sample(max(1, round(n * len(g) / len(df))), random_state=seed) for _, g in df.groupby("subject_category")]
                for _, r in pd.concat(parts).iterrows():
                    items.append({"q": r["question"], "opts": [r["option_a"], r["option_b"], r["option_c"], r["option_d"]],
                                  "ans": r["answer"], "cat": r["subject_category"]})
                break
    else:
        for base in (ROOT / "data" / "llm_bench", Path("/opt/vieedge/data/llm_bench")):
            p = base / "vmlu_val" / "valid.jsonl"
            if p.exists():
                rows = [json.loads(l) for l in open(p, encoding="utf-8")]
                rows = [r for r in rows if len(r["choices"]) == 4]
                for r in rnd.sample(rows, min(n, len(rows))):
                    items.append({"q": r["question"], "opts": [re.sub(r"^[A-D]\.\s*", "", c) for c in r["choices"]],
                                  "ans": r["answer"], "cat": r["id"].split("-")[0]})
                break
    return items[:n]


def mcq_accuracy(cl: LlamaClient, items: list[dict]) -> tuple[float, list]:
    ok, log = 0, []
    for it in items:
        user = it["q"] + "\n" + "\n".join(f"{l}. {o}" for l, o in zip("ABCD", it["opts"])) + "\nĐáp án:"
        msgs = [{"role": "system", "content": MCQ_SYSTEM}, {"role": "user", "content": user}]
        # GBNF grammar forces a single letter: a style-tuned (LoRA) model would otherwise answer with a
        # spoken sentence and a regex would pick up the letters A-D inside ordinary words.
        text, _ = cl.complete(msgs, max_tokens=2, temperature=0.0, grammar=MCQ_GRAMMAR)
        m = re.match(r"\s*([ABCD])", text)
        pred = m.group(1) if m else "?"
        ok += pred == it["ans"]
        log.append({"pred": pred, "ans": it["ans"], "cat": it["cat"]})
    return ok / max(len(items), 1), log


def speed(cl: LlamaClient, questions: list[dict], cache: bool) -> dict:
    ttft, toks, cached, prompt_n = [], [], [], []
    if cache:
        cl.warmup(build_messages("Xin chào"))
    for q in questions:
        st = LLMStats()
        for _ in cl.stream_chat(build_messages(q["q"]), st, cache_prompt=cache):
            pass
        ttft.append(st.ttft_ms)
        toks.append(st.tok_s)
        cached.append(st.n_cached)
        prompt_n.append(st.n_prompt)
    return {"ttft_ms": pct(ttft), "tok_s": pct(toks, (50,)), "cached_tokens": pct(cached, (50,)), "prompt_tokens": pct(prompt_n, (50,))}


def quant_of(name: str) -> str:
    m = re.search(r"-(F16|BF16|Q\d_[0-9A-Z_]+|Q\d_\d|IQ\d_\w+)\.gguf$", name)
    return m.group(1) if m else ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--exp", required=True)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--draft")
    ap.add_argument("--threads", nargs="*", type=int)
    ap.add_argument("--server-bin")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--speed", type=int, default=30, help="questions for TTFT/tok-s (0 = skip)")
    ap.add_argument("--quality", type=int, default=0, help="Global-MMLU vi items (0 = skip)")
    ap.add_argument("--vmlu", type=int, default=0)
    ap.add_argument("--answers", type=int, default=-1, help="generate answers for N QA test questions (0 = all, -1 = skip)")
    ap.add_argument("--gpu", action="store_true", help="offload to GPU (laptop quality runs only; never for speed rows)")
    ap.add_argument("--notes", default="")
    a = ap.parse_args()
    over: dict = {}
    for kv in a.set:
        k, v = kv.split("=", 1)
        set_override(over, k, v)
    cfg = load_config(a.config, over)
    l = cfg["llm"]
    for model in a.models:
        for threads in a.threads or [l["threads"]]:
            extra = list(l.get("extra_args") or [])
            if a.gpu:
                extra = [x for x in extra if x not in ("-ngl", "0")] + ["-ngl", "99"]
            srv = LlamaServer(a.server_bin or l["server_bin"], cfg.model_path(model), port=l["port"] + 7, threads=threads,
                              cores=l.get("cores"), ctx=l["ctx"], batch=l["batch"], draft_model=cfg.model_path(a.draft),
                              draft_max=l.get("draft_max", 8), extra_args=extra,
                              log_path=str(results_dir() / "llama-bench-server.log"))
            th0 = thermal_state()
            t0 = time.monotonic()
            srv.start(l["startup_timeout_s"])
            load_s = time.monotonic() - t0
            cl = LlamaClient(srv.url, l["max_tokens"], l["temperature"], l["top_p"], not a.no_cache, l.get("chat_template_kwargs"))
            raw: dict = {"model": model, "threads": threads, "draft": a.draft, "load_s": round(load_s, 1)}
            row = {"exp_id": a.exp, "llm_model": Path(model).name, "llm_quant": quant_of(Path(model).name),
                   "lora": "yes" if "vi-voice" in model else "no", "spec_dec": Path(a.draft).name if a.draft else "no",
                   "threads": threads}
            try:
                if a.speed:
                    sp = speed(cl, qa_questions(a.speed), cache=not a.no_cache)
                    raw["speed"] = sp
                    row["ttft_ms"] = sp["ttft_ms"]["p50"]
                    row["tok_s"] = sp["tok_s"]["p50"]
                row["ram_mb"] = proc_rss_mb(srv.proc.pid)
                if a.quality:
                    acc, log = mcq_accuracy(cl, mcq_items(a.quality, "global_mmlu"))
                    raw["global_mmlu_vi"] = {"acc": acc, "n": len(log), "log": log}
                    row["llm_bench_acc"] = round(acc, 4)
                if a.vmlu:
                    acc, log = mcq_accuracy(cl, mcq_items(a.vmlu, "vmlu"))
                    raw["vmlu_val"] = {"acc": acc, "n": len(log)}
                if a.answers >= 0:
                    qs = qa_questions(a.answers or None)
                    out = results_dir() / "raw" / f"answers_{a.exp}_{Path(model).stem}.jsonl"
                    out.parent.mkdir(exist_ok=True)
                    with open(out, "w", encoding="utf-8") as f:
                        for q in qs:
                            text, st = cl.complete(build_messages(q["q"]))
                            f.write(json.dumps({"id": q.get("id"), "q": q["q"], "ref": q.get("a", ""), "kind": q.get("kind"),
                                                "answer": text, "tok_s": round(st.tok_s, 2)}, ensure_ascii=False) + "\n")
                    raw["answers_file"] = str(out)
            finally:
                srv.stop()
            th1 = thermal_state()
            row["temp_max"] = th1.get("temp_c")
            row["notes"] = ";".join(filter(None, [a.notes, "gpu-offload(quality only)" if a.gpu else "",
                                                  "no-prompt-cache" if a.no_cache else "", f"load_s={load_s:.1f}",
                                                  f"bin={Path(a.server_bin).parent.parent.name}" if a.server_bin else "",
                                                  check_thermal(th0, th1)]))
            if a.gpu:  # GPU numbers must never be mistaken for device speed
                row.pop("ttft_ms", None)
                row.pop("tok_s", None)
                row.pop("ram_mb", None)
            append_experiment(row, raw=raw)


if __name__ == "__main__":
    main()
