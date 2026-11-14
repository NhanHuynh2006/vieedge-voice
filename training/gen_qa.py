#!/usr/bin/env python3
"""Generate the spoken-style Vietnamese Q&A set for LoRA (PLAN §5.2) with a large "teacher" LLM.

Teacher: an OpenAI-compatible endpoint (default: llama-server on the laptop GPU serving
Qwen3.5-9B Q4_K_M, see scripts/run_teacher.sh). For every topic the teacher writes batches of
question/answer pairs in the target style (1-3 short spoken sentences, no markdown, admits
uncertainty). Automatic filters then drop malformed / too long / markdown / non-Vietnamese /
duplicate pairs, optionally a second teacher pass rates factual correctness, and 10 % (stratified
by topic) is held out as the test set.

  python training/gen_qa.py --target 3300 --out data/qa
  python training/gen_qa.py --verify --out data/qa      # optional fact-check pass + resplit
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import random
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TOPICS: dict[str, list[str]] = {
    "lịch sử Việt Nam": ["các triều đại phong kiến", "khởi nghĩa Hai Bà Trưng và Bà Triệu", "chiến thắng Bạch Đằng",
                         "nhà Trần chống quân Nguyên Mông", "Lê Lợi và khởi nghĩa Lam Sơn", "Quang Trung Nguyễn Huệ",
                         "Cách mạng tháng Tám và Quốc khánh 2/9", "chiến dịch Điện Biên Phủ", "thống nhất đất nước 1975",
                         "Đổi Mới 1986"],
    "địa lý Việt Nam": ["các tỉnh thành và vùng miền", "sông Hồng và sông Mê Kông", "núi Phan Xi Păng và địa hình",
                        "khí hậu ba miền", "biển đảo Việt Nam", "vịnh Hạ Long và di sản thiên nhiên", "đồng bằng sông Cửu Long",
                        "Tây Nguyên", "Hà Nội", "Thành phố Hồ Chí Minh", "Đà Nẵng và miền Trung"],
    "văn hóa và lễ hội": ["Tết Nguyên Đán", "Tết Trung Thu", "giỗ tổ Hùng Vương", "áo dài", "nhã nhạc cung đình Huế",
                          "ca trù và quan họ", "múa rối nước", "phong tục cưới hỏi", "chữ Nôm và chữ Quốc ngữ", "các dân tộc Việt Nam"],
    "ẩm thực": ["phở", "bánh mì", "bún chả và bún bò Huế", "bánh chưng bánh tét", "cà phê Việt Nam", "nước mắm",
                "món ăn miền Nam", "món chay", "nấu cơm và các món ăn gia đình", "trái cây nhiệt đới"],
    "khoa học tự nhiên": ["hệ Mặt Trời", "ánh sáng và màu sắc", "nước và vòng tuần hoàn", "điện và nam châm", "trọng lực",
                          "nguyên tử và phân tử", "phản ứng hóa học thường gặp", "thời tiết và khí hậu", "động đất và núi lửa",
                          "âm thanh", "nhiệt độ và nhiệt năng"],
    "sinh học và cơ thể người": ["tim và hệ tuần hoàn", "não bộ và giấc ngủ", "hệ tiêu hóa", "vi khuẩn và virus", "di truyền và ADN",
                                 "thực vật và quang hợp", "hệ miễn dịch", "các giác quan"],
    "động vật": ["voi và các loài thú lớn", "chim di cư", "cá heo và cá voi", "côn trùng có ích", "động vật quý hiếm ở Việt Nam",
                 "thú cưng chó mèo", "khủng long", "động vật dưới biển sâu"],
    "vũ trụ": ["Mặt Trăng", "sao Hỏa", "lỗ đen", "ngôi sao và thiên hà", "nhật thực nguyệt thực", "trạm vũ trụ và phi hành gia", "Trái Đất quay"],
    "sức khỏe phổ thông": ["ăn uống lành mạnh", "tập thể dục", "uống đủ nước", "giấc ngủ", "cảm cúm thông thường", "sơ cứu cơ bản",
                           "bảo vệ mắt khi dùng màn hình", "vệ sinh răng miệng", "sức khỏe tinh thần"],
    "công nghệ": ["máy tính hoạt động thế nào", "internet", "điện thoại thông minh", "trí tuệ nhân tạo", "robot", "pin và sạc",
                  "an toàn mật khẩu và lừa đảo trực tuyến", "lập trình cho người mới", "chip bán dẫn", "điện toán biên và thiết bị nhúng",
                  "nhận dạng giọng nói", "xe điện"],
    "toán và logic": ["phép tính nhẩm đơn giản", "phân số và phần trăm", "hình học cơ bản", "số nguyên tố", "đơn vị đo lường",
                      "đổi đơn vị thời gian", "câu đố logic ngắn"],
    "ngôn ngữ tiếng Việt": ["dấu thanh tiếng Việt", "thành ngữ tục ngữ", "từ đồng nghĩa trái nghĩa", "chính tả thường gặp",
                            "ca dao", "từ mượn"],
    "văn học": ["Truyện Kiều và Nguyễn Du", "Hồ Xuân Hương", "Nam Cao và Ngô Tất Tố", "truyện cổ tích Việt Nam",
                "Dế Mèn phiêu lưu ký", "thơ Tố Hữu và Xuân Diệu", "văn học thế giới nổi tiếng"],
    "thể thao": ["bóng đá Việt Nam", "SEA Games", "Thế vận hội Olympic", "cầu lông và bóng bàn", "võ thuật Vovinam", "cờ vua", "chạy bộ"],
    "đời sống và kỹ năng": ["tiết kiệm tiền", "quản lý thời gian", "học tập hiệu quả", "giao tiếp lịch sự", "nấu ăn an toàn",
                            "tiết kiệm điện nước", "phân loại rác", "chuẩn bị phỏng vấn xin việc", "an toàn giao thông", "phòng cháy chữa cháy"],
    "môi trường": ["biến đổi khí hậu", "ô nhiễm nhựa", "năng lượng mặt trời và gió", "trồng cây xanh", "ô nhiễm không khí", "bảo vệ rừng"],
    "thế giới": ["các châu lục và đại dương", "các nước láng giềng của Việt Nam", "kỳ quan thế giới", "Liên Hợp Quốc và ASEAN",
                 "các ngôn ngữ phổ biến", "các phát minh làm thay đổi thế giới"],
    "kinh tế cơ bản": ["tiền tệ và lạm phát", "ngân hàng và lãi suất", "xuất nhập khẩu của Việt Nam", "nông nghiệp lúa gạo", "khởi nghiệp"],
    "giáo dục": ["hệ thống giáo dục Việt Nam", "thi tốt nghiệp trung học phổ thông", "học ngoại ngữ", "nghiên cứu khoa học sinh viên", "học nghề"],
    "giao tiếp với trợ lý": ["chào hỏi và cảm ơn", "hỏi trợ lý là ai và làm được gì", "trò chuyện vui vẻ", "nhờ kể chuyện cười ngắn",
                             "nhờ động viên khi buồn", "hỏi về cách trợ lý hoạt động offline"],
}

UNKNOWN_KINDS = [
    "thông tin thời gian thực như thời tiết hôm nay, giá vàng, tỷ giá, tin tức mới nhất, kết quả trận đấu tối qua",
    "thông tin cá nhân của người hỏi mà trợ lý không thể biết (tên, tuổi, nhà ở đâu, hôm qua làm gì)",
    "dự đoán tương lai không thể biết chắc (xổ số, giá chứng khoán ngày mai, ai thắng giải)",
    "câu hỏi có tiền đề sai hoặc sự kiện không tồn tại",
    "chi tiết quá hiếm hoặc quá cụ thể mà một mô hình nhỏ không thể chắc chắn (số liệu chính xác, tên người ít nổi tiếng)",
    "yêu cầu chẩn đoán bệnh, kê đơn thuốc hoặc tư vấn pháp lý cụ thể cần chuyên gia",
]

STYLE = (
    "Phong cách trả lời bắt buộc: câu trả lời sẽ được ĐỌC TO bằng giọng nói nên phải ngắn (1 đến 3 câu, tối đa khoảng 60 từ), "
    "văn nói tự nhiên, thân thiện, xưng 'mình' và gọi người hỏi là 'bạn' khi cần; tuyệt đối không markdown, không gạch đầu dòng, "
    "không đánh số, không ký hiệu đặc biệt, không emoji; chính xác về sự thật; nếu không chắc chắn thì nói rõ là mình không chắc."
)

ANGLES = [
    "câu hỏi kiến thức cơ bản (cái gì, ở đâu, khi nào, ai)",
    "câu hỏi tại sao và như thế nào",
    "câu hỏi thực tế mà người bình thường hay hỏi trong đời sống",
]


def chat(url: str, messages: list[dict], max_tokens: int = 3000, temperature: float = 0.8, timeout: int = 600) -> str:
    body = json.dumps({"messages": messages, "max_tokens": max_tokens, "temperature": temperature, "top_p": 0.95,
                       "chat_template_kwargs": {"enable_thinking": False}}).encode()
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)["choices"][0]["message"]["content"]


def parse_pairs(text: str) -> list[dict]:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\[.*\]", text, flags=re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except json.JSONDecodeError:
        # salvage line-by-line objects
        arr = []
        for obj in re.findall(r"\{[^{}]*\}", m.group(0)):
            try:
                arr.append(json.loads(obj))
            except json.JSONDecodeError:
                pass
    out = []
    for x in arr:
        if isinstance(x, dict) and isinstance(x.get("q"), str) and isinstance(x.get("a"), str):
            out.append({"q": x["q"].strip(), "a": x["a"].strip()})
    return out


VI_CHARS = re.compile(r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]", re.I)


def norm_q(q: str) -> str:
    q = unicodedata.normalize("NFC", q.lower())
    return re.sub(r"[^\wÀ-ỹ ]+", "", q).strip()


def keep(p: dict) -> tuple[bool, str]:
    q, a = p["q"], p["a"]
    if not (8 <= len(q) <= 200):
        return False, "q_len"
    if not (12 <= len(a) <= 380):
        return False, "a_len"
    if re.search(r"(^|\n)\s*([-*•#]|\d+[.)])\s", a) or re.search(r"[*#`|_]{1,}|\n", a):
        return False, "markdown"
    if re.search(r"[\U0001F300-\U0001FAFF☀-➿]", a):
        return False, "emoji"
    if not VI_CHARS.search(a) or not VI_CHARS.search(q):
        return False, "not_vi"
    n_sent = len([s for s in re.split(r"(?<=[.!?…])\s+", a) if s.strip()])
    if n_sent > 4:
        return False, "too_many_sentences"
    if len(a.split()) > 75:
        return False, "too_many_words"
    return True, ""


def gen_topic(url: str, cat: str, sub: str, angle: str, n: int, seed: int) -> list[dict]:
    prompt = (
        f"Hãy viết {n} cặp hỏi đáp tiếng Việt đa dạng về chủ đề '{sub}' (lĩnh vực: {cat}), tập trung vào {angle}. "
        "Câu hỏi giống như người dùng nói với trợ lý giọng nói: tự nhiên, ngắn, đôi khi dùng văn nói (ví dụ 'cho mình hỏi', 'bạn ơi'). "
        f"{STYLE} Khoảng một trong mười câu hỏi nên là câu khó mà trợ lý nên trả lời thẳng thắn là không chắc. "
        'Chỉ xuất ra một mảng JSON hợp lệ dạng [{"q": "...", "a": "..."}], không có gì khác.'
    )
    random.seed(seed)
    txt = chat(url, [{"role": "system", "content": "Bạn là chuyên gia biên soạn dữ liệu hội thoại tiếng Việt chính xác."},
                     {"role": "user", "content": prompt}])
    return [dict(p, topic=cat, sub=sub, kind="normal") for p in parse_pairs(txt)]


def gen_unknown(url: str, kind: str, n: int) -> list[dict]:
    prompt = (
        f"Hãy viết {n} cặp hỏi đáp tiếng Việt trong đó người dùng hỏi trợ lý giọng nói OFFLINE (không có internet, không biết ngày giờ hiện tại) "
        f"về: {kind}. Câu trả lời phải thành thật nói rằng mình không biết, không có thông tin hoặc không chắc, giải thích ngắn lý do "
        f"và nếu hợp lý thì gợi ý người dùng có thể làm gì. {STYLE} "
        'Chỉ xuất ra một mảng JSON hợp lệ dạng [{"q": "...", "a": "..."}].'
    )
    txt = chat(url, [{"role": "user", "content": prompt}])
    return [dict(p, topic="không biết", sub=kind[:40], kind="unknown") for p in parse_pairs(txt)]


_GREET = re.compile(r"^(chào bạn|xin chào|dạ|vâng|à|ồ|ừm|à vâng|câu hỏi hay đấy|câu hỏi hay quá)[,!.]\s*", re.I)


def clean_answer(p: dict) -> dict:
    """Drop the teacher's habit of opening every answer with a greeting (unnatural when spoken each turn)."""
    a = p["a"]
    if p.get("topic") != "giao tiếp với trợ lý":
        for _ in range(2):
            a = _GREET.sub("", a).strip()
        if a:
            a = a[0].upper() + a[1:]
    return dict(p, a=a)


def verify(url: str, p: dict, think: bool = False) -> int:
    """Fact-check with the teacher: short explicit per-fact check, then a score (full reasoning mode
    produced >1500 tokens per item, ~19 h for the set, so a bounded written check is used instead)."""
    prompt = (
        "Bạn là giám khảo kiểm tra sự thật rất khắt khe. Hãy kiểm tra từng chi tiết (tên người, năm, số liệu, quan hệ) "
        "trong câu trả lời rồi chấm theo thang 1-5 về độ CHÍNH XÁC: 5 = hoàn toàn đúng; 4 = đúng nhưng hơi chung chung; "
        "3 = có chi tiết đáng ngờ; 2 = có chi tiết sai; 1 = sai hẳn. Câu trả lời thừa nhận không biết một cách hợp lý được 5.\n"
        f"Câu hỏi: {p['q']}\nCâu trả lời: {p['a']}\n"
        "Trước tiên liệt kê thật ngắn (tối đa 4 gạch) từng chi tiết kèm nhận xét đúng/sai/không chắc, "
        "rồi kết thúc bằng một dòng duy nhất dạng 'ĐIỂM: <số>'."
    )
    try:
        body = {"messages": [{"role": "user", "content": prompt}], "max_tokens": 1500 if think else 300,
                "temperature": 0.0, "chat_template_kwargs": {"enable_thinking": think}}
        req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:
            msg = json.load(r)["choices"][0]["message"]
        txt = re.sub(r"<think>.*?</think>", "", msg.get("content") or "", flags=re.S)
        m = re.findall(r"ĐIỂM\s*[:：]\s*([1-5])", txt) or re.findall(r"[1-5]", txt[-20:])
        return int(m[-1]) if m else 0
    except Exception:
        return 0


def split_write(pairs: list[dict], out: Path, test_frac: float = 0.1, seed: int = 13) -> None:
    rnd = random.Random(seed)
    by_topic: dict[str, list[dict]] = {}
    for p in pairs:
        by_topic.setdefault(p["topic"], []).append(p)
    train, test = [], []
    for _, ps in sorted(by_topic.items()):
        rnd.shuffle(ps)
        k = max(1, round(len(ps) * test_frac))
        test += ps[:k]
        train += ps[k:]
    rnd.shuffle(train)
    for name, rows in (("train", train), ("test", test)):
        with open(out / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for i, r in enumerate(rows):
                r = dict(r, id=hashlib.sha1(r["q"].encode()).hexdigest()[:10])
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"train={len(train)} test={len(test)} -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8090")
    ap.add_argument("--out", default=str(ROOT / "data" / "qa"))
    ap.add_argument("--target", type=int, default=3300, help="pairs to keep after filtering")
    ap.add_argument("--per-call", type=int, default=15)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--unknown-frac", type=float, default=0.08)
    ap.add_argument("--verify", action="store_true", help="fact-check raw pairs with the teacher and resplit")
    ap.add_argument("--min-score", type=int, default=4)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw_path = out / "raw.jsonl"

    if args.verify:
        rows = [json.loads(l) for l in open(raw_path, encoding="utf-8")]
        rows = [clean_answer(r) for r in rows if r.get("kept")]
        vpath = out / "verified.jsonl"
        done = {}
        if vpath.exists():  # resumable: keep scores from an interrupted run (0 = request failed -> retry)
            for l in open(vpath, encoding="utf-8"):
                r = json.loads(l)
                if r.get("fact_score"):
                    done[r["q"]] = r["fact_score"]
        todo = [r for r in rows if r["q"] not in done]
        print(f"verify: {len(done)} already scored, {len(todo)} to go", flush=True)
        lock = __import__("threading").Lock()
        with open(vpath, "a", encoding="utf-8") as f:
            def work(r):
                s = verify(args.url, r)
                with lock:
                    f.write(json.dumps(dict(r, fact_score=s), ensure_ascii=False) + "\n")
                    f.flush()
                return s
            with cf.ThreadPoolExecutor(args.workers) as ex:
                for i, s in enumerate(ex.map(work, todo)):
                    if i % 100 == 0:
                        print(f"  {i}/{len(todo)}", flush=True)
        latest = {}
        for l in open(vpath, encoding="utf-8"):
            r = json.loads(l)
            if r.get("fact_score") or r["q"] not in latest:
                latest[r["q"]] = r["fact_score"]
        for r in rows:
            r["fact_score"] = latest.get(r["q"], 0)
        scores = [r["fact_score"] for r in rows]
        good = [r for r in rows if r["fact_score"] >= args.min_score]
        hist = {s: scores.count(s) for s in range(6)}
        print(f"fact scores {hist}; keeping {len(good)}/{len(rows)}")
        (out / "stats_verify.json").write_text(json.dumps({"hist": hist, "kept": len(good), "total": len(rows)}, indent=1))
        split_write(good, out)
        return

    seen: set[str] = set()
    kept: list[dict] = []
    reasons: dict[str, int] = {}
    if raw_path.exists():  # resume
        for l in open(raw_path, encoding="utf-8"):
            r = json.loads(l)
            if r.get("kept"):
                seen.add(norm_q(r["q"]))
                kept.append(r)
    jobs = []
    rnd = random.Random(7)
    for cat, subs in TOPICS.items():
        for sub in subs:
            for angle in ANGLES:
                jobs.append(("topic", cat, sub, angle))
    rnd.shuffle(jobs)
    n_unknown_calls = max(1, int(args.target * args.unknown_frac / args.per_call) + 2)
    for i in range(n_unknown_calls):
        jobs.insert(rnd.randrange(len(jobs)), ("unknown", UNKNOWN_KINDS[i % len(UNKNOWN_KINDS)]))

    t0 = time.time()
    f = open(raw_path, "a", encoding="utf-8")

    def run(job, i):
        if job[0] == "topic":
            return gen_topic(args.url, job[1], job[2], job[3], args.per_call, i)
        return gen_unknown(args.url, job[1], args.per_call)

    with cf.ThreadPoolExecutor(args.workers) as ex:
        futs = {}
        it = iter(enumerate(jobs))
        for _ in range(args.workers * 2):
            try:
                i, j = next(it)
                futs[ex.submit(run, j, i)] = j
            except StopIteration:
                break
        while futs and len(kept) < args.target:
            done, _ = cf.wait(futs, return_when=cf.FIRST_COMPLETED)
            for fu in done:
                futs.pop(fu)
                try:
                    pairs = fu.result()
                except Exception as e:
                    print("  !!", e, file=sys.stderr)
                    pairs = []
                for p in pairs:
                    ok, why = keep(p)
                    k = norm_q(p["q"])
                    if ok and k in seen:
                        ok, why = False, "duplicate"
                    p["kept"] = ok
                    if ok:
                        seen.add(k)
                        kept.append(p)
                    else:
                        reasons[why] = reasons.get(why, 0) + 1
                    f.write(json.dumps(p, ensure_ascii=False) + "\n")
                f.flush()
                print(f"  kept {len(kept)}/{args.target}  rejected {reasons}  {time.time() - t0:.0f}s", flush=True)
                try:
                    i, j = next(it)
                    futs[ex.submit(run, j, i)] = j
                except StopIteration:
                    pass
        for fu in futs:
            fu.cancel()
    f.close()
    kept = [clean_answer(p) for p in kept]
    (out / "stats_gen.json").write_text(json.dumps({"kept": len(kept), "rejected": reasons,
                                                     "seconds": round(time.time() - t0)}, indent=1, ensure_ascii=False))
    split_write(kept, out)


if __name__ == "__main__":
    main()
