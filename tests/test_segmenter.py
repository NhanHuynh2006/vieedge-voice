from vieedge.tts.segmenter import SentenceSegmenter


def feed(seg, text, step=3):
    out = []
    for i in range(0, len(text), step):
        out += seg.push(text[i:i + step])
    return out + seg.flush()


def test_first_chunk_cut_early_at_comma():
    seg = SentenceSegmenter(first_min=18, min_chars=12)
    chunks = feed(seg, "Hà Nội là thủ đô của Việt Nam, nằm ở đồng bằng sông Hồng. Thành phố có hơn một nghìn năm lịch sử.")
    assert chunks[0] == "Hà Nội là thủ đô của Việt Nam,"
    assert chunks[-1].endswith("lịch sử.")


def test_no_split_on_decimal_or_abbrev():
    seg = SentenceSegmenter(first_min=5, min_chars=5)
    chunks = feed(seg, "Số pi xấp xỉ 3.14 thôi. Mình sống ở TP. HCM nhiều năm rồi.")
    assert "3.14" in chunks[0]
    assert any("TP. HCM" in c for c in chunks)


def test_everything_emitted():
    text = "Một. Hai ba bốn năm sáu bảy tám chín mười. Mười một"
    seg = SentenceSegmenter(first_min=3, min_chars=3)
    assert "".join(feed(seg, text)).replace(" ", "") == text.replace(" ", "")


def test_first_chunk_word_cap():
    seg = SentenceSegmenter(first_min=18, min_chars=12, first_max_words=5)
    chunks = feed(seg, "Bạn nên uống đủ nước mỗi ngày và ngủ đủ giấc để khỏe mạnh.")
    assert len(chunks[0].split()) == 5
