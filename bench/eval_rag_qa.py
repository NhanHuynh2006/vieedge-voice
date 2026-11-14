#!/usr/bin/env python3
"""Answer the held-out test questions WITH retrieval from the offline knowledge base, for the same inputs as before:
typed questions (RAGCLEAN) and questions as the Zipformer STT delivered them (RAGZIP). Compare with CLEAN / NOISYZIP
(no retrieval) using bench/judge.py. Also stores prompt size and retrieval time.

  eval_rag_qa.py [--min-score S] [--max-chars N] [--docs N] <gguf>
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from common import ROOT, results_dir
from vieedge.llm.llamacpp_stream import LlamaClient, LlamaServer, LLMStats
from vieedge.llm.prompts import build_messages
from vieedge.rag import KnowledgeBase, build_prompt_context


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--min-score", type=float, default=0.0)
    ap.add_argument("--max-chars", type=int, default=420)
    ap.add_argument("--docs", type=int, default=2)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    kb = KnowledgeBase(ROOT / "models/rag/wiki_vi.sqlite")
    kb.search("xin chào")
    zip_rows = [json.loads(l) for l in open(ROOT / "data/qa/test_asr_zip.jsonl", encoding="utf-8")]
    srv = LlamaServer(str(ROOT / "third_party/llama.cpp/build/bin/llama-server"), str(ROOT / "models" / a.model), port=8139,
                      threads=6, cores=None, ctx=3072, batch=512, extra_args=["-ngl", "99"],
                      log_path=str(results_dir() / "llama-eval-rag.log"))
    srv.start(180)
    try:
        cl = LlamaClient(srv.url, 160, 0.3, 0.9, True, {"enable_thinking": False})
        for cond, key in (("RAGCLEAN" + a.tag, "q_clean"), ("RAGZIP" + a.tag, "q")):
            out = results_dir() / "raw" / f"answers_{cond}_{Path(a.model).stem}.jsonl"
            used = 0
            t_ret = []
            with open(out, "w", encoding="utf-8") as f:
                for r in zip_rows:
                    t0 = time.monotonic()
                    hits = kb.search(r[key], 6)
                    ctx = build_prompt_context(hits, a.max_chars, a.min_score, a.docs)
                    t_ret.append((time.monotonic() - t0) * 1e3)
                    used += bool(ctx)
                    st = LLMStats()
                    text = "".join(cl.stream_chat(build_messages(r[key], context=ctx or None), st))
                    f.write(json.dumps({"id": r.get("id"), "q": r["q_clean"], "asked": r[key], "ref": r["a"], "kind": r.get("kind"),
                                        "answer": text.strip(), "ctx": ctx, "titles": [h["title"] for h in hits[:3]],
                                        "prompt_tokens": st.n_prompt + st.n_cached}, ensure_ascii=False) + "\n")
            print(f"{cond}: retrieval used on {used}/{len(zip_rows)} questions, retrieval ms p50 {sorted(t_ret)[len(t_ret) // 2]:.1f} -> {out}")
    finally:
        srv.stop()


if __name__ == "__main__":
    main()
