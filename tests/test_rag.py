import sqlite3

from vieedge.llm.prompts import build_messages
from vieedge.rag import KnowledgeBase, build_prompt_context
from vieedge.rag.index import add_title_index, fts_query, strip_marks


def make_db(path):
    db = sqlite3.connect(path)
    db.execute("CREATE VIRTUAL TABLE chunks USING fts5(title, body, tokenize='unicode61 remove_diacritics 2')")
    rows = [("Hồ Gươm", "Hồ Gươm là một hồ nước ngọt nằm ở trung tâm thành phố Hà Nội, gắn với truyền thuyết vua Lê Lợi trả gươm thần."),
            ("Phở", "Phở là món ăn truyền thống của người Việt, gồm bánh phở, nước dùng và thịt bò hoặc gà."),
            ("Đường Láng", "Đường Láng là một con đường ở Hà Nội, nối Ô Chợ Dừa với cầu Mới."),
            ("Sông Hồng", "Sông Hồng chảy qua Hà Nội và đổ ra biển ở vịnh Bắc Bộ.")]
    db.executemany("INSERT INTO chunks(title, body) VALUES (?, ?)", rows)
    db.commit()
    add_title_index(db)
    db.close()


def test_query_drops_stopwords_and_marks():
    q = fts_query("Cho mình hỏi Hồ Gươm ở đâu vậy?")
    assert '"ho"' in q and '"guom"' in q and '"ho guom"' in q
    assert '"hoi"' not in q and '"dau"' not in q
    assert strip_marks("Đường Gươm") == "đuong guom"   # FTS5 keeps đ


def test_search_tolerates_missing_diacritics(tmp_path):
    p = tmp_path / "kb.sqlite"
    make_db(p)
    kb = KnowledgeBase(p)
    assert kb.search("ho guom o dau")[0]["title"] == "Hồ Gươm"      # no diacritics (typical STT slip)
    assert kb.search("phở là món gì")[0]["title"] == "Phở"
    assert kb.search("là gì vậy") == []                             # only stop syllables -> nothing


def test_context_budget_and_prompt(tmp_path):
    p = tmp_path / "kb.sqlite"
    make_db(p)
    hits = KnowledgeBase(p).search("sông hồng chảy qua đâu")
    ctx = build_prompt_context(hits, max_chars=200, max_docs=1)
    assert ctx.startswith("[Sông Hồng]") and len(ctx) <= 260
    msgs = build_messages("Sông Hồng chảy qua đâu?", context=ctx)
    assert "Thông tin tham khảo" in msgs[-1]["content"] and msgs[0]["role"] == "system"
    assert build_messages("x")[-1]["content"] == "x"


def test_d_stroke_words_match(tmp_path):
    p = tmp_path / "kb.sqlite"
    make_db(p)
    assert KnowledgeBase(p).search("đường láng ở đâu")[0]["title"] == "Đường Láng"


def test_title_phrase_beats_generic_words(tmp_path):
    p = tmp_path / "kb.sqlite"
    make_db(p)
    db = sqlite3.connect(p)
    db.execute("INSERT INTO chunks(title, body) VALUES ('Diện tích', 'Diện tích là đại lượng đo kích thước mặt phẳng.')")
    db.execute("INSERT INTO chunks(title, body) VALUES ('Hà Nội', 'Hà Nội là thủ đô của Việt Nam, diện tích 3.359 km2.')")
    db.commit()
    db.execute("DROP TABLE art")
    db.execute("DROP TABLE tfts")
    add_title_index(db)
    db.close()
    hits = KnowledgeBase(p).search("Hà Nội có diện tích bao nhiêu")
    assert hits[0]["title"] == "Hà Nội"
