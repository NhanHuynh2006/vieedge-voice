#!/usr/bin/env python3
"""Answer the held-out test questions twice: as typed (CLEAN) and as the STT delivered them (NOISY, data/qa/test_asr.jsonl).
The answer files keep the ORIGINAL question as `q`, so bench/judge.py scores correctness against what the user meant.

  eval_noisy_qa.py <gguf> [<gguf> ...]  ->  results/raw/answers_{CLEAN,NOISY}_<model>.jsonl  (then run bench/judge.py)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from common import ROOT, results_dir
from vieedge.llm.llamacpp_stream import LlamaClient, LlamaServer
from vieedge.llm.prompts import build_messages


def main() -> None:
    args = sys.argv[1:]
    asr_file, tag = "test_asr.jsonl", ""
    if args and args[0].startswith("--asr-file="):
        asr_file, tag = args.pop(0).split("=", 1)[1], "ZIP"
    rows = [json.loads(l) for l in open(ROOT / "data/qa" / asr_file, encoding="utf-8")]
    for model in args:
        srv = LlamaServer(str(ROOT / "third_party/llama.cpp/build/bin/llama-server"), str(ROOT / "models" / model), port=8137,
                          threads=6, cores=None, ctx=2048, batch=256, extra_args=["-ngl", "99"],
                          log_path=str(results_dir() / "llama-eval-noisy.log"))
        srv.start(180)
        try:
            cl = LlamaClient(srv.url, 160, 0.3, 0.9, True, {"enable_thinking": False})
            for cond, key in ((("CLEAN", "q_clean"), ("NOISY", "q")) if not tag else (("NOISYZIP", "q"),)):
                out = results_dir() / "raw" / f"answers_{cond}_{Path(model).stem}.jsonl"
                with open(out, "w", encoding="utf-8") as f:
                    for r in rows:
                        text, _ = cl.complete(build_messages(r[key]))
                        f.write(json.dumps({"id": r.get("id"), "q": r["q_clean"], "asked": r[key], "ref": r["a"], "kind": r.get("kind"),
                                            "answer": text}, ensure_ascii=False) + "\n")
                print("wrote", out)
        finally:
            srv.stop()


if __name__ == "__main__":
    main()
