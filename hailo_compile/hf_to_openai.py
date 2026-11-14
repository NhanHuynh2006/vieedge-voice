#!/usr/bin/env python3
"""Convert a Hugging Face Whisper checkpoint (vinai/PhoWhisper-tiny/-base) into the openai-whisper
checkpoint format that hailo-whisper's export/convert scripts load (`whisper.load_model(<path.pt>)`).

PhoWhisper is a fine-tune of Whisper tiny/base with the same architecture, so the mapping is the
inverse of transformers' `convert_openai_to_hf.py`.

  python hailo_compile/hf_to_openai.py models/hf/vinai__PhoWhisper-tiny hailo_compile/work/phowhisper-tiny.pt
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import torch

RENAME = [
    (r"^model\.encoder\.layer_norm\.", "encoder.ln_post."),
    (r"^model\.decoder\.layer_norm\.", "decoder.ln."),
    (r"^model\.decoder\.embed_tokens\.weight$", "decoder.token_embedding.weight"),
    (r"^model\.decoder\.embed_positions\.weight$", "decoder.positional_embedding"),
    (r"^model\.encoder\.embed_positions\.weight$", "encoder.positional_embedding"),
    (r"^model\.(encoder|decoder)\.conv(\d)\.", r"\1.conv\2."),
    (r"^model\.(encoder|decoder)\.layers\.(\d+)\.", r"\1.blocks.\2."),
    (r"\.self_attn\.q_proj\.", ".attn.query."),
    (r"\.self_attn\.k_proj\.", ".attn.key."),
    (r"\.self_attn\.v_proj\.", ".attn.value."),
    (r"\.self_attn\.out_proj\.", ".attn.out."),
    (r"\.self_attn_layer_norm\.", ".attn_ln."),
    (r"\.encoder_attn\.q_proj\.", ".cross_attn.query."),
    (r"\.encoder_attn\.k_proj\.", ".cross_attn.key."),
    (r"\.encoder_attn\.v_proj\.", ".cross_attn.value."),
    (r"\.encoder_attn\.out_proj\.", ".cross_attn.out."),
    (r"\.encoder_attn_layer_norm\.", ".cross_attn_ln."),
    (r"\.fc1\.", ".mlp.0."),
    (r"\.fc2\.", ".mlp.2."),
    (r"\.final_layer_norm\.", ".mlp_ln."),
]


def convert(hf_dir: Path) -> dict:
    from transformers import WhisperConfig, WhisperForConditionalGeneration

    cfg = WhisperConfig.from_pretrained(hf_dir)
    model = WhisperForConditionalGeneration.from_pretrained(hf_dir, dtype=torch.float32)
    sd = {}
    for k, v in model.state_dict().items():
        if k == "proj_out.weight":  # tied with token embedding in openai-whisper
            continue
        nk = k
        for pat, rep in RENAME:
            nk = re.sub(pat, rep, nk)
        if nk.startswith("model."):
            raise KeyError(f"unmapped key {k}")
        sd[nk] = v.clone()
    dims = dict(n_mels=cfg.num_mel_bins, n_vocab=cfg.vocab_size, n_audio_ctx=cfg.max_source_positions,
                n_audio_state=cfg.d_model, n_audio_head=cfg.encoder_attention_heads, n_audio_layer=cfg.encoder_layers,
                n_text_ctx=cfg.max_target_positions, n_text_state=cfg.d_model, n_text_head=cfg.decoder_attention_heads,
                n_text_layer=cfg.decoder_layers)
    return {"dims": dims, "model_state_dict": sd}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("hf_dir", type=Path)
    ap.add_argument("out", type=Path)
    a = ap.parse_args()
    ck = convert(a.hf_dir)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(ck, a.out)
    print(f"saved {a.out} dims={ck['dims']} tensors={len(ck['model_state_dict'])}")


if __name__ == "__main__":
    main()
