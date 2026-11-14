#!/usr/bin/env python3
"""Trains the second stage of the safety matcher: a small linear classifier that names a card when the keyword rules
find none, mainly for questions garbled by speech recognition ("rắn cắn" heard as "rắn cắng").

Data (never the held-out v3 set, never the v2 set used for validation):
  * typed: the dev set (cau_hoi_thu), held-out v1, template sentences built from each card's key phrases,
    general questions from the QA training set (label "khong" = no card);
  * spoken: every typed sentence synthesised with the Piper vivos voice (the v2/v3 test audio uses the 25hours voice),
    half of it mixed with DEMAND noise at 10 dB, then transcribed by Zipformer: the classifier sees real ASR errors.
Model: multinomial logistic regression on word unigrams/bigrams with and without diacritics (numpy, L2).
Threshold: chosen on v2 (typed + ASR) and the 345 QA test questions (typed + ASR) so that the cascade does not add a
single false trigger on those ordinary questions. Writes data/an_toan/phan_loai.json (sparse weights) and a report.

  train_safety_clf.py [--no-audio]
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
from common import ROOT, load_audio, mix_snr

from vieedge.safety import SafetyCards, norm_vi, strip_accents

A = ROOT / "data/an_toan"
OUT = ROOT / "results/an_toan"
CACHE = A / "huan_luyen_asr.jsonl"


def feats(text: str) -> list[str]:
    w = norm_vi(text).split()
    a = [strip_accents(x) for x in w]
    f = [f"w:{x}" for x in w] + [f"a:{x}" for x in a]
    f += [f"b:{x}_{y}" for x, y in zip(w, w[1:])] + [f"c:{x}_{y}" for x, y in zip(a, a[1:])]
    if CHARS:
        s = " " + " ".join(a) + " "
        f += [f"g:{s[i:i + 3]}" for i in range(len(s) - 2)]
    return sorted(set(f))


CHARS = __import__("os").environ.get("CLF_CHARS") == "1"

PRE = ["", "con tôi ", "bố tôi bị ", "mẹ tôi bị ", "tôi bị ", "có người ", "ở đây có người ", "cứu với ", "ông tôi bị ", "bạn tôi bị ",
       "nhà tôi có người ", "em bị ", "anh ơi ", "chị ơi "]
SUF = ["", " phải làm sao", " làm gì bây giờ", " xử lý thế nào", " thì sơ cứu ra sao", " giúp tôi với", " nguy hiểm không",
       " cần làm gì", " phải làm thế nào", " thì sao", " bây giờ phải làm gì", " cứu với"]


def templates(cards: SafetyCards, rnd: random.Random, per_card: int) -> list[dict]:
    out = []
    for c in cards.cards:
        phrases = list(c.keys)
        for combo in c.combos:
            for _ in range(6):
                phrases.append(" ".join(rnd.choice(g) for g in combo))
        for _ in range(per_card):
            out.append({"q": (rnd.choice(PRE) + rnd.choice(phrases) + rnd.choice(SUF)).strip(), "nhan": c.id, "src": "mau"})
    return out


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def label_of(r) -> str:
    n = r["nhan"][0] if isinstance(r["nhan"], list) else r["nhan"]
    return n if r["loai"] == "trong" else "khong"


def build_typed(cards, rnd, per_card):
    rows = [{"q": r["q"], "nhan": label_of(r), "src": "dev"} for r in load(A / "cau_hoi_thu.jsonl")]
    rows += [{"q": r["q"], "nhan": label_of(r), "src": "v1"} for r in load(A / "cau_hoi_doc_lap.jsonl")
             if not (r["loai"] == "trong" and label_of(r) not in cards.by_id)]
    rows += templates(cards, rnd, per_card)
    qa = load(ROOT / "data/qa/train.jsonl")
    rnd.shuffle(qa)
    relabel = {r["q"] for r in load(A / "qa_nhan_lai.jsonl")}
    rows += [{"q": r["q"], "nhan": "khong", "src": "qa"} for r in qa[:1500] if r["q"] not in relabel]
    return rows


def synthesize(rows, rnd):
    """Adds the ASR transcript of each typed row (vivos voice, half with noise); cached across runs."""
    cache = {(r["q"], r["snr"]): r["text"] for r in load(CACHE)} if CACHE.exists() else {}
    todo = [(r["q"], (10.0 if i % 2 else None)) for i, r in enumerate(rows)]
    need = [k for k in dict.fromkeys(todo) if k not in cache]
    if need:
        from vieedge.audio.resample import resample
        from vieedge.config import load_config
        from vieedge.stt.zipformer import ZipformerVi
        from vieedge.tts.piper_tts import PiperTTS
        cfg = load_config()
        tts = PiperTTS(cfg.model_path("tts/piper/vi_VN-vivos-x_low.onnx"), 2)
        stt = ZipformerVi(str(ROOT / "models/stt/zipformer-vi"), threads=3)
        noises = sorted((ROOT / "data/noise").rglob("ch01.wav"))
        nz = [load_audio(str(p)) for p in noises[:8]]
        t0 = time.time()
        with open(CACHE, "a", encoding="utf-8") as f:
            for i, (q, snr) in enumerate(need):
                r = tts.synthesize(q)
                x = resample(r.audio, r.sample_rate, 16000) * 0.7
                x = np.concatenate([np.zeros(4000), x, np.zeros(4000)]).astype(np.float32)
                if snr is not None and nz:
                    x = mix_snr(x, rnd.choice(nz), snr, rnd)
                text = stt.transcribe(x).text
                cache[(q, snr)] = text
                f.write(json.dumps({"q": q, "snr": snr, "text": text}, ensure_ascii=False) + "\n")
                if i % 500 == 0:
                    print(f"  asr {i}/{len(need)} {time.time() - t0:.0f}s", flush=True)
    return [{**r, "q": cache[k], "src": r["src"] + "_asr"} for r, k in zip(rows, todo)]


class Clf:
    def __init__(self, vocab, classes, W, b):
        self.vocab, self.classes, self.W, self.b = vocab, classes, W, b

    def proba(self, text):
        z = self.b.copy()
        for f in feats(text):
            j = self.vocab.get(f)
            if j is not None:
                z += self.W[j]
        z -= z.max()
        p = np.exp(z)
        return p / p.sum()


def train(rows, l2=1e-4, epochs=300, lr=0.5):
    classes = sorted({r["nhan"] for r in rows})
    ci = {c: i for i, c in enumerate(classes)}
    fs = [feats(r["q"]) for r in rows]
    cnt = {}
    for f in fs:
        for x in f:
            cnt[x] = cnt.get(x, 0) + 1
    vocab = {x: i for i, x in enumerate(sorted(k for k, v in cnt.items() if v >= 2))}
    import scipy.sparse as sp  # noqa: F401  (only for speed if present)
    rows_i, cols_i = [], []
    for i, f in enumerate(fs):
        for x in f:
            j = vocab.get(x)
            if j is not None:
                rows_i.append(i); cols_i.append(j)
    X = sp.csr_matrix((np.ones(len(rows_i), np.float32), (rows_i, cols_i)), shape=(len(rows), len(vocab)))
    y = np.array([ci[r["nhan"]] for r in rows])
    # class weights: the "khong" class is large
    cw = np.bincount(y, minlength=len(classes)).astype(np.float32)
    sw = (len(y) / (len(classes) * cw))[y] ** 0.5
    W = np.zeros((len(vocab), len(classes)), np.float32); b = np.zeros(len(classes), np.float32)
    Y = np.zeros((len(y), len(classes)), np.float32); Y[np.arange(len(y)), y] = 1
    mW = np.zeros_like(W); vW = np.zeros_like(W); mb = np.zeros_like(b); vb = np.zeros_like(b)
    for t in range(1, epochs + 1):
        Z = X @ W + b
        Z -= Z.max(1, keepdims=True)
        P = np.exp(Z); P /= P.sum(1, keepdims=True)
        G = (P - Y) * sw[:, None] / len(y)
        gW = X.T @ G + l2 * W; gb = G.sum(0)
        for g, m, v, p in ((gW, mW, vW, W), (gb, mb, vb, b)):
            m *= 0.9; m += 0.1 * g; v *= 0.999; v += 0.001 * g * g
            p -= lr * 0.05 * (m / (1 - 0.9 ** t)) / (np.sqrt(v / (1 - 0.999 ** t)) + 1e-8)
    return Clf(vocab, classes, W, b)


def cascade(cards, clf, text, tau, margin):
    """Rules first; the classifier only when the rules name no card and the question is not a knowledge question."""
    m = cards.match(text)
    if m is not None and m.card is not None:
        return m.card.id, "luat"
    t = norm_vi(text)
    ask = any(f" {a} " in f" {t} " for a in cards.ask)
    know = any(f" {k} " in f" {t} " for k in cards.knowledge) or bool(cards.year.search(t))
    if clf is not None and (ask or not know):
        p = clf.proba(text)
        o = np.argsort(-p)
        c = clf.classes[o[0]]
        if c != "khong" and p[o[0]] >= tau and p[o[0]] - p[o[1]] >= margin:
            card = cards.redirect(cards.by_id[c], t)
            return card.id, "phan_loai"
    return ("du_phong" if m is not None else "khong"), "luat"


def score(cards, clf, items, tau, margin):
    ok = {"trong": [0, 0], "ngoai": [0, 0], "am": [0, 0]}
    for it in items:
        got, _ = cascade(cards, clf, it["text"], tau, margin)
        want = it["nhan"] if isinstance(it["nhan"], list) else [it["nhan"]]
        k = it["loai"] if it["loai"] in ok else "am"
        ok[k][0] += got in want; ok[k][1] += 1
    return ok


def export(clf, path, tau, margin, prune=0.05):
    W = clf.W
    rows = {}
    for f, j in clf.vocab.items():
        nz = [(int(c), round(float(W[j, c]), 3)) for c in np.nonzero(np.abs(W[j]) >= prune)[0]]
        if nz:
            rows[f] = nz
    d = {"phien_ban": time.strftime("%Y-%m-%d"), "lop": clf.classes, "lech": [round(float(x), 4) for x in clf.b],
         "nguong": tau, "cach_biet": margin, "dac_trung": rows}
    Path(path).write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-card", type=int, default=40)
    ap.add_argument("--no-audio", action="store_true")
    a = ap.parse_args()
    rnd = random.Random(7)
    cards = SafetyCards(A / "the_an_toan.json")
    typed = build_typed(cards, rnd, a.per_card)
    rows = typed + ([] if a.no_audio else synthesize(typed, rnd))
    print(f"training rows: {len(typed)} typed + {len(rows) - len(typed)} ASR, {len({r['nhan'] for r in rows})} classes", flush=True)
    clf = train(rows)
    # validation: v2 typed + v2 ASR (25hours voice) + QA test typed/ASR as ordinary questions
    v2 = load(A / "cau_hoi_doc_lap_v2.jsonl")
    for r in v2:  # v2 labels predate the 18 new cards: an emergency without a card then may now have one
        r["text"] = r["q"]
    v2a = load(OUT / "asr_v2.jsonl")
    relabel = {r["q"]: r["nhan"] for r in load(A / "qa_nhan_lai.jsonl")}
    qa = [{"text": r["q"], "nhan": relabel.get(r["q"], "khong"), "loai": "am" if r["q"] not in relabel else "ngoai"} for r in load(ROOT / "data/qa/test.jsonl")]
    qa_asr = [{"text": r["q"], "nhan": relabel.get(r.get("q_clean", ""), "khong"), "loai": "am" if r.get("q_clean", "") not in relabel else "ngoai"}
              for r in load(ROOT / "data/qa/test_asr.jsonl")]
    sets = {"v2": v2, "v2_asr": v2a, "qa": qa, "qa_asr": qa_asr}
    base = {k: score(cards, None, v, 1, 1) for k, v in sets.items()}
    print("rules only:", json.dumps(base, ensure_ascii=False))
    grid = []
    for tau in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95):
        for margin in (0.0, 0.2, 0.4):
            s = {k: score(cards, clf, v, tau, margin) for k, v in sets.items()}
            fp = sum(s[k]["am"][1] - s[k]["am"][0] for k in sets) - sum(base[k]["am"][1] - base[k]["am"][0] for k in sets)
            hit = s["v2_asr"]["trong"][0] + s["v2"]["trong"][0]
            grid.append({"tau": tau, "margin": margin, "extra_false": fp, "v2_cards": hit, "s": s})
            print(f"  tau {tau} margin {margin}: extra false triggers {fp}, v2 typed+asr card hits {hit}", flush=True)
    ok = [g for g in grid if g["extra_false"] <= 0] or [min(grid, key=lambda g: g["extra_false"])]
    best = max(ok, key=lambda g: (g["v2_cards"], g["tau"]))
    n = export(clf, A / "phan_loai.json", best["tau"], best["margin"])
    rep = {"train_rows": len(rows), "typed": len(typed), "classes": len(clf.classes), "features_kept": n, "chosen": {k: best[k] for k in ("tau", "margin", "extra_false", "v2_cards")},
           "rules_only": base, "with_classifier": best["s"], "grid": [{k: g[k] for k in ("tau", "margin", "extra_false", "v2_cards")} for g in grid]}
    (OUT / "phan_loai_train.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("chosen", rep["chosen"], "features", n)


if __name__ == "__main__":
    main()
