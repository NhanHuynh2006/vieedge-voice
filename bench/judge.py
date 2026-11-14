#!/usr/bin/env python3
"""LLM-as-judge for spoken answers (PLAN §8): a large model on the laptop (scripts/run_teacher.sh)
scores each answer against the reference: correctness, concision, listenability (1-5) and flags
hallucination. Input: results/raw/answers_<exp>_<model>.jsonl from bench_llm.py --answers.

  python bench/judge.py results/raw/answers_M2_*.jsonl
Outputs results/raw/judged_<...>.jsonl and one experiments.csv row per file (answer_score = mean of
the three scores; hallucination rate in notes). 🧑 then reviews 100 answers with review_app --mode qa.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import urllib.request
from pathlib import Path
from statistics import mean

from common import append_experiment

PROMPT = """Bạn là giám khảo chấm câu trả lời của một trợ lý giọng nói tiếng Việt (câu trả lời sẽ được đọc to).
Câu hỏi: {q}
Đáp án tham khảo: {ref}
Câu trả lời cần chấm: {ans}

Chấm theo thang 1-5:
- DUNG: độ chính xác về nội dung (so với kiến thức chung và đáp án tham khảo; nếu câu hỏi không thể biết mà trợ lý thừa nhận không biết thì 5)
- NGAN: ngắn gọn, đúng trọng tâm (1-3 câu là lý tưởng)
- NGHE: dễ nghe khi đọc to (không markdown, không ký hiệu, câu tự nhiên)
- BIA: "co" nếu câu trả lời bịa thông tin sai một cách tự tin, ngược lại "khong"
Trả lời đúng 4 dòng: DUNG: <số>, NGAN: <số>, NGHE: <số>, BIA: <co|khong>"""


def judge(url: str, r: dict) -> dict:
    body = {"messages": [{"role": "user", "content": PROMPT.format(q=r["q"], ref=r.get("ref", ""), ans=r["answer"])}],
            "max_tokens": 60, "temperature": 0.0, "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            txt = json.load(resp)["choices"][0]["message"]["content"]
    except Exception as e:
        return {**r, "judge_error": str(e)}

    def num(key):
        m = re.search(key + r"\s*:\s*([1-5])", txt)
        return int(m.group(1)) if m else None

    bia = re.search(r"BIA\s*:\s*(co|có|khong|không)", txt, re.I)
    return {**r, "correct": num("DUNG"), "concise": num("NGAN"), "listen": num("NGHE"),
            "halluc": bool(bia and bia.group(1).lower() in ("co", "có")), "judge_raw": txt}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--url", default="http://127.0.0.1:8090")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    for f in a.files:
        rows = [json.loads(l) for l in open(f, encoding="utf-8")]
        with cf.ThreadPoolExecutor(a.workers) as ex:
            res = list(ex.map(lambda r: judge(a.url, r), rows))
        out = f.with_name(f.name.replace("answers_", "judged_"))
        with open(out, "w", encoding="utf-8") as fo:
            for r in res:
                fo.write(json.dumps(r, ensure_ascii=False) + "\n")
        ok = [r for r in res if r.get("correct")]
        sc = {k: round(mean(r[k] for r in ok if r.get(k)), 3) for k in ("correct", "concise", "listen")} if ok else {}
        hall = sum(r["halluc"] for r in ok) / len(ok) if ok else None
        unk = [r for r in ok if r.get("kind") == "unknown"]
        print(f.name, sc, f"halluc={hall}")
        exp, model = f.stem.replace("answers_", "").split("_", 1)
        append_experiment({"exp_id": exp, "llm_model": model + ".gguf", "lora": "yes" if "vi-voice" in model else "no",
                           "answer_score": round(mean(sc.values()), 3) if sc else "",
                           "notes": f"judge=teacher;correct={sc.get('correct')};concise={sc.get('concise')};listen={sc.get('listen')};"
                                    f"halluc_rate={hall:.3f};unknown_q_correct={mean(r['correct'] for r in unk) if unk else 'na'};n={len(ok)}"},
                          raw={"scores": sc, "halluc_rate": hall, "file": str(out)})


if __name__ == "__main__":
    main()
