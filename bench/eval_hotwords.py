#!/usr/bin/env python3
"""Does contextual biasing (sherpa-onnx hotwords, modified beam search) help Zipformer hear emergency words?

The Zipformer licence (CC BY-NC-ND) forbids derivatives, so the model is not fine-tuned; hotwords only rescore the beam
at decode time. Hotwords = every key phrase and combination word of the safety cards. Measured on the synthesised
held-out v2 safety questions (card accuracy + WER) and on real speech (VIVOS test subset, FLEURS) to check that biasing
does not hurt ordinary sentences.

  eval_hotwords.py [--n-real 300]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import sentencepiece as spm
from common import ROOT, load_audio, wer

from vieedge.safety import SafetyCards, norm_vi

D = ROOT / "models/stt/zipformer-vi"
OUT = ROOT / "results/an_toan"


def bpe_vocab() -> str:
    p = D / "bpe.vocab"
    if not p.exists():
        sp = spm.SentencePieceProcessor(model_file=str(D / "bpe.model"))
        p.write_text("".join(f"{sp.id_to_piece(i)}\t{sp.get_score(i)}\n" for i in range(sp.get_piece_size())), encoding="utf-8")
    return str(p)


def hotwords(cards: SafetyCards) -> list[str]:
    hw = set()
    for c in cards.cards:
        hw.update(c.keys)
        for combo in c.combos:
            for g in combo:
                hw.update(w for w in g if len(w.split()) >= 1 and len(w) >= 3)
    return sorted(hw, key=lambda s: (-len(s), s))


def recognizer(method: str, hw_file: str | None, score: float):
    import sherpa_onnx
    kw = dict(encoder=str(D / "encoder-epoch-20-avg-10.int8.onnx"), decoder=str(D / "decoder-epoch-20-avg-10.int8.onnx"),
              joiner=str(D / "joiner-epoch-20-avg-10.int8.onnx"), tokens=str(D / "tokens.txt"), num_threads=3, sample_rate=16000,
              feature_dim=80, decoding_method=method, modeling_unit="bpe", bpe_vocab=bpe_vocab())
    if method == "modified_beam_search":
        kw["max_active_paths"] = 4
    if hw_file:
        kw.update(hotwords_file=hw_file, hotwords_score=score)
    return sherpa_onnx.OfflineRecognizer.from_transducer(**kw)


def run(rec, items):
    hyps, t0 = [], time.perf_counter()
    for it in items:
        st = rec.create_stream()
        st.accept_waveform(16000, load_audio(str(ROOT / it["audio"])))
        rec.decode_stream(st)
        hyps.append(st.result.text.strip().lower())
    return hyps, (time.perf_counter() - t0) * 1000 / max(len(items), 1)


def card_acc(cards, labels, items, hyps):
    ok = {"trong": [0, 0], "ngoai": [0, 0], "am": [0, 0]}
    for it, h in zip(items, hyps):
        lab = labels[it["text"]]
        m = cards.match(h)
        got = "khong" if m is None else (m.card.id if m.card else "du_phong")
        want = lab["nhan"] if isinstance(lab["nhan"], list) else [lab["nhan"]]
        ok[lab["loai"]][0] += got in want
        ok[lab["loai"]][1] += 1
    return {k: f"{a}/{n}" for k, (a, n) in ok.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-real", type=int, default=300)
    ap.add_argument("--scores", default="1.0,1.5,2.0,3.0")
    ap.add_argument("--only-hw", action="store_true")
    ap.add_argument("--manifest", default="data/manifests/e2e_an_toan_v2.jsonl")
    ap.add_argument("--labels", default="data/an_toan/cau_hoi_doc_lap_v2.jsonl")
    ap.add_argument("--tag", default="v2")
    a = ap.parse_args()
    cards = SafetyCards(ROOT / "data/an_toan/the_an_toan.json")
    hw = hotwords(cards)
    hw_file = OUT / "hotwords.txt"
    hw_file.write_text("\n".join(h.upper() for h in hw) + "\n", encoding="utf-8")   # the BPE pieces are upper case
    labels = {json.loads(l)["q"]: json.loads(l) for l in open(ROOT / a.labels, encoding="utf-8") if l.strip()}
    safety = [json.loads(l) for l in open(ROOT / a.manifest, encoding="utf-8")]
    real = [json.loads(l) for l in open(ROOT / "data/manifests/vivos_test.jsonl", encoding="utf-8")][: a.n_real]
    refs_s = [norm_vi(x["text"]) for x in safety]
    refs_r = [norm_vi(x["text"]) for x in real]
    configs = ([("greedy", None, 0.0), ("beam4", None, 0.0)] if not a.only_hw else []) + [(f"beam4+hw{s}", str(hw_file), float(s)) for s in a.scores.split(",")]
    res = []
    for name, f, s in configs:
        rec = recognizer("greedy_search" if name == "greedy" else "modified_beam_search", f, s)
        hs, ms_s = run(rec, safety)
        hr, ms_r = run(rec, real)
        row = {"config": name, "hotwords": len(hw) if f else 0, "safety_wer": round(wer(refs_s, hs), 3), "safety_cards": card_acc(cards, labels, safety, hs),
               "vivos_wer": round(wer(refs_r, hr), 3), "ms_per_utt": round((ms_s + ms_r) / 2, 1)}
        res.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    (OUT / f"hotwords_eval_{a.tag}.json").write_text(json.dumps({"n_safety": len(safety), "n_vivos": len(real), "rows": res}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
