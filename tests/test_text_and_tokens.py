from vieedge.stt.tokens import prompt_tokens, tokens_to_text
from vieedge.textproc import collapse_repeats, normalize_question, wer_normalize


def test_bpe_decoding_vietnamese():
    # GPT-2 byte-level BPE: 'Ġ' = space, multi-byte UTF-8 split over tokens
    toks = ["<|startoftranscript|>", "<|vi|>", "xin", "Ġch", "Ã", "ł", "o", "<|endoftext|>"]
    assert tokens_to_text(toks) == "xin chào"


def test_prompt():
    assert prompt_tokens("vi") == ["<|startoftranscript|>", "<|vi|>", "<|transcribe|>", "<|notimestamps|>"]


def test_question_cleanup():
    assert normalize_question("thủ đô việt nam là gì") == "Thủ đô việt nam là gì?"
    assert normalize_question("Hãy subscribe cho kênh") == ""
    assert collapse_repeats("xin chào xin chào xin chào bạn") == "xin chào bạn"


def test_wer_normalize():
    assert wer_normalize("Xin CHÀO, bạn!") == "xin chào bạn"
