#!/usr/bin/env python3
"""Old vs new answer style of the phone assistant, same model (qwen3.5-2b-vi-voice Q4_0 imatrix, the file on the phone),
same retrieval (wiki_vi, 1 passage, 240 characters, as Rag.kt), same 345 held-out QA questions, typed (q_clean) and as
Zipformer heard them (q). Only the system prompt, the retrieval wording and the repetition penalty differ:

  A (old): the prompt shipped until 05/11/2026 ("if the passage is not relevant, say you are not sure"), no penalty.
  C: the old system prompt (honest about not knowing) with B's neutral passage wording and the repetition penalty.
  B (new): answer directly like a person talking, guess through ASR errors, ask back when unclear, say "I don't know" only
           for real-time facts or real ignorance; passage marked "use only if relevant"; repeat_penalty 1.1.

Writes results/raw/answers_STYLE{A,B}{CLEAN,ZIP}_<model>.jsonl for bench/judge.py, plus hedge/repetition counts.
  eval_answer_style.py [model.gguf]
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

from common import ROOT, results_dir
from vieedge.llm.llamacpp_stream import LlamaServer
from vieedge.rag import KnowledgeBase, build_prompt_context

OLD_SYSTEM = ("Bạn là VieEdge, trợ lý hỏi đáp bằng giọng nói tiếng Việt chạy hoàn toàn trên thiết bị, không có internet. "
              "Câu trả lời của bạn sẽ được đọc to bằng giọng nói, vì vậy hãy: trả lời ngắn gọn trong 1 đến 3 câu; dùng câu văn nói tự nhiên, thân thiện; "
              "không dùng markdown, không gạch đầu dòng, không ký hiệu, không biểu tượng cảm xúc; viết số và đơn vị sao cho dễ đọc. "
              "Nếu câu hỏi cần thông tin thời gian thực (thời tiết, tin tức, giá cả hôm nay, tỷ số) hoặc bạn không chắc chắn, "
              "hãy nói thật là mình không chắc hoặc không có thông tin đó, tuyệt đối không bịa.")
NEW_SYSTEM = ("Bạn là VieEdge, trợ lý trò chuyện bằng tiếng Việt trên điện thoại; câu trả lời sẽ được đọc to. "
              "Hãy nói như một người hiểu biết đang trò chuyện trực tiếp: nói ngay ý chính ở câu đầu, tự nhiên, ấm áp, 1 đến 3 câu ngắn. "
              "Không mở đầu bằng Dạ hay Vâng, không lặp lại câu hỏi, không dùng markdown, ký hiệu hay biểu tượng cảm xúc; viết số sao cho dễ đọc. "
              "Câu hỏi đến từ nhận dạng giọng nói nên có thể sai vài từ: hãy hiểu theo ý hợp lý nhất. Nếu không rõ người dùng hỏi gì, hãy hỏi lại một câu ngắn. "
              "Chỉ nói mình không biết khi câu hỏi cần tin tức, thời tiết, giá cả, tỷ số theo thời gian thực hoặc khi bạn thật sự không biết; "
              "khi đó nói gọn trong một câu và tuyệt đối không bịa.")


def user_msg(style: str, q: str, ctx: str | None) -> str:
    if not ctx:
        return q
    if style == "A":
        return f"Thông tin tham khảo: {ctx}\nCâu hỏi: {q}\nNếu thông tin không liên quan, hãy nói bạn không chắc."
    if style == "C":
        return f"Thông tin tham khảo, chỉ dùng nếu liên quan đến câu hỏi: {ctx}\nCâu hỏi: {q}"
    return f"Tài liệu tra cứu, chỉ dùng nếu liên quan đến câu hỏi: {ctx}\nCâu hỏi: {q}"


HEDGE = re.compile(r"không chắc|không có thông tin|không biết", re.I)


def chat(url: str, msgs: list, penalty: float) -> str:
    import urllib.request
    body = {"messages": msgs, "max_tokens": 160, "temperature": 0.3, "top_p": 0.9, "cache_prompt": True,
            "chat_template_kwargs": {"enable_thinking": False}}
    if penalty != 1.0:
        body["repeat_penalty"] = penalty
    req = urllib.request.Request(url + "/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()


def main() -> None:
    model = sys.argv[1] if len(sys.argv) > 1 else "llm/gguf/qwen3.5-2b-vi-voice-Q4_0.gguf"
    kb = KnowledgeBase(ROOT / "models/rag/wiki_vi.sqlite")
    rows = [json.loads(l) for l in open(ROOT / "data/qa/test_asr_zip.jsonl", encoding="utf-8")]
    srv = LlamaServer(str(ROOT / "third_party/llama.cpp/build/bin/llama-server"), str(ROOT / "models" / model), port=8141,
                      threads=6, cores=None, ctx=4096, batch=512, extra_args=["-ngl", "99"], log_path=str(results_dir() / "llama-eval-style.log"))
    srv.start(180)
    summary = {}
    try:
        want = (sys.argv[2] if len(sys.argv) > 2 else "AB")
        for style, system, pen in [s for s in (("A", OLD_SYSTEM, 1.0), ("B", NEW_SYSTEM, 1.1), ("C", OLD_SYSTEM, 1.1)) if s[0] in want]:
            for cond, key in (("CLEAN", "q_clean"), ("ZIP", "q")):
                tag = f"STYLE{style}{cond}"
                out = results_dir() / "raw" / f"answers_{tag}_{Path(model).stem}.jsonl"
                answers, t0 = [], time.time()
                with open(out, "w", encoding="utf-8") as f:
                    for r in rows:
                        ctx = build_prompt_context(kb.search(r[key], 6), 240, 0.0, 1)
                        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user_msg(style, r[key], ctx)}]
                        a = chat(srv.url, msgs, pen)
                        answers.append(a)
                        f.write(json.dumps({"id": r.get("id"), "q": r["q_clean"], "asked": r[key], "ref": r["a"], "kind": r.get("kind"),
                                            "answer": a, "ctx": ctx}, ensure_ascii=False) + "\n")
                starts = Counter(" ".join(a.split()[:3]).lower() for a in answers)
                summary[f"{tag}_{Path(model).stem}"] = {"n": len(answers), "hedge": sum(bool(HEDGE.search(a)) for a in answers),
                                "starts_with_khong_chac": sum(a.lower().startswith("mình không chắc") for a in answers),
                                "most_common_start": starts.most_common(3), "mean_words": round(sum(len(a.split()) for a in answers) / len(answers), 1),
                                "s": round(time.time() - t0)}
                print(tag, json.dumps(summary[f"{tag}_{Path(model).stem}"], ensure_ascii=False), flush=True)
    finally:
        srv.stop()
    f = ROOT / "results/answer_style.json"
    old = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    f.write_text(json.dumps({**old, **summary}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
