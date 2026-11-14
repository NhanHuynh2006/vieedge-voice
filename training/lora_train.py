#!/usr/bin/env python3
"""LoRA / QLoRA fine-tune for spoken Vietnamese Q&A style (PLAN §5.2, experiment M2).

Teaches: answers of 1-3 short spoken sentences, no markdown, natural Vietnamese, says "mình không
chắc" instead of inventing. The *runtime* system prompt (vieedge.llm.prompts.SYSTEM_PROMPT) is used in
training so train and inference prompts are identical; loss only on the assistant answer.

  python training/lora_train.py --base models/hf/Qwen__Qwen2.5-1.5B-Instruct --name qwen2.5-1.5b-vi-voice
  python training/lora_train.py --base models/hf/Qwen__Qwen2.5-0.5B-Instruct --name qwen2.5-0.5b-vi-voice   # draft (M3)
  python training/lora_train.py --base ... --qlora      # 4-bit base (QLoRA) when VRAM is short
Then: python training/merge_quantize.py --base <base> --lora training/runs/<name>/adapter --name <name>
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vieedge.llm.prompts import SYSTEM_PROMPT  # noqa: E402


def load_rows(split: str) -> list[dict]:
    return [json.loads(l) for l in open(ROOT / "data" / "qa" / f"{split}.jsonl", encoding="utf-8")]


def build_example(tok, q: str, a: str, max_len: int) -> dict | None:
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": q}]
    kw = {"enable_thinking": False}
    try:
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, **kw)
        full = tok.apply_chat_template(msgs + [{"role": "assistant", "content": a}], tokenize=False, **kw)
    except TypeError:
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        full = tok.apply_chat_template(msgs + [{"role": "assistant", "content": a}], tokenize=False)
    if not full.startswith(prompt):  # templates that re-render history (e.g. strip think) -> fall back
        full = prompt + a + (tok.eos_token or "")
    p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    f_ids = tok(full, add_special_tokens=False)["input_ids"]
    if len(f_ids) > max_len:
        return None
    labels = [-100] * len(p_ids) + f_ids[len(p_ids):]
    return {"input_ids": f_ids, "labels": labels}


class Collator:
    def __init__(self, pad_id: int):
        self.pad = pad_id

    def __call__(self, batch: list[dict]) -> dict:
        n = max(len(b["input_ids"]) for b in batch)
        ids = torch.full((len(batch), n), self.pad, dtype=torch.long)
        lab = torch.full((len(batch), n), -100, dtype=torch.long)
        att = torch.zeros((len(batch), n), dtype=torch.long)
        for i, b in enumerate(batch):
            k = len(b["input_ids"])
            ids[i, :k] = torch.tensor(b["input_ids"])
            lab[i, :k] = torch.tensor(b["labels"])
            att[i, :k] = 1
        return {"input_ids": ids, "labels": lab, "attention_mask": att}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--alpha", type=int, default=32)
    ap.add_argument("--dropout", type=float, default=0.05)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--micro", type=int, default=4)
    ap.add_argument("--max-len", type=int, default=384)
    ap.add_argument("--asr-aug", action="store_true",
                    help="also train on questions after TTS->noise->STT (data/qa/train_asr.jsonl), answer unchanged")
    ap.add_argument("--qlora", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

    random.seed(a.seed)
    torch.manual_seed(a.seed)
    out = ROOT / "training" / "runs" / a.name
    out.mkdir(parents=True, exist_ok=True)
    tok = AutoTokenizer.from_pretrained(a.base)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    kw: dict = {"dtype": torch.bfloat16, "device_map": "cuda", "low_cpu_mem_usage": True}
    if a.qlora:
        from transformers import BitsAndBytesConfig

        kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                                       bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(a.base, **kw)
    if a.qlora:
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    else:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
    targets = sorted({n.split(".")[-1] for n, m in model.named_modules() if isinstance(m, torch.nn.Linear)} -
                     {"lm_head", "embed_tokens"})
    model = get_peft_model(model, LoraConfig(r=a.rank, lora_alpha=a.alpha, lora_dropout=a.dropout, target_modules=targets,
                                             task_type="CAUSAL_LM"))
    model.print_trainable_parameters()

    def prep(rows):
        ex = [build_example(tok, r["q"], r["a"], a.max_len) for r in rows]
        return [e for e in ex if e]

    rows = load_rows("train")
    if a.asr_aug:
        # same answer for the clean question and for what the STT really delivered (typos, wrong words, dropped words)
        noisy = [r for r in load_rows("train_asr") if r["q"].strip() != r["q_clean"].strip()]
        print(f"ASR-noisy augmentation: +{len(noisy)} examples")
        rows = rows + [{"q": r["q"], "a": r["a"]} for r in noisy]
    train, test = prep(rows), prep(load_rows("test"))
    print(f"train {len(train)} / test {len(test)} examples; LoRA targets {targets}")
    steps = math.ceil(len(train) / a.batch) * a.epochs
    args = TrainingArguments(
        output_dir=str(out / "ckpt"), num_train_epochs=a.epochs, learning_rate=a.lr, lr_scheduler_type="cosine",
        warmup_steps=max(1, int(0.05 * steps)), per_device_train_batch_size=a.micro, per_device_eval_batch_size=a.micro,
        gradient_accumulation_steps=max(1, a.batch // a.micro), bf16=True, logging_steps=20, eval_strategy="epoch",
        save_strategy="epoch", save_total_limit=1, load_best_model_at_end=True, metric_for_best_model="eval_loss",
        report_to=[], seed=a.seed, dataloader_num_workers=0, remove_unused_columns=False,
    )
    trainer = Trainer(model=model, args=args, train_dataset=train, eval_dataset=test, data_collator=Collator(tok.pad_token_id))
    t0 = time.time()
    trainer.train()
    ev = trainer.evaluate()
    model.save_pretrained(out / "adapter")
    tok.save_pretrained(out / "adapter")
    log = {"base": str(a.base), "name": a.name, "train_examples": len(train), "test_examples": len(test),
           "eval_loss": ev.get("eval_loss"), "eval_ppl": math.exp(ev["eval_loss"]) if ev.get("eval_loss") else None,
           "minutes": round((time.time() - t0) / 60, 1), "args": vars(a) | {"base": str(a.base)},
           "history": trainer.state.log_history}
    (out / "train_log.json").write_text(json.dumps(log, indent=1, ensure_ascii=False, default=str))
    (ROOT / "results" / "training").mkdir(parents=True, exist_ok=True)
    (ROOT / "results" / "training" / f"{a.name}.json").write_text(json.dumps(log, indent=1, ensure_ascii=False, default=str))
    print(f"adapter -> {out / 'adapter'}  eval_loss={ev.get('eval_loss'):.4f}")


if __name__ == "__main__":
    main()
