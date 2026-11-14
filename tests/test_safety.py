import json
from pathlib import Path

import pytest

from vieedge.fastpath import FastPath
from vieedge.safety import SafetyCards

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "data/an_toan/the_an_toan.json"


@pytest.fixture(scope="module")
def sc():
    return SafetyCards(CARDS)


def test_every_card_is_sourced_and_short():
    d = json.loads(CARDS.read_text(encoding="utf-8"))
    src = json.loads((ROOT / "data/an_toan/nguon.json").read_text(encoding="utf-8"))
    for c in d["the"]:
        assert c["nguon"] and all(s in src for s in c["nguon"]), c["id"]
        assert 20 <= len(c["noi"].split()) <= 110, c["id"]
        assert "--" not in c["noi"] and "—" not in c["noi"]


@pytest.mark.parametrize("q,card", [
    ("Bị rắn cắn ở chân phải làm gì?", "ran_can"),
    ("Đi rẫy bị rắn lục cắn", "ran_can"),
    ("Có người đuối nước vừa vớt lên", "duoi_nuoc"),
    ("Em bé ba tháng bị sặc sữa", "hoc_tre_so_sinh"),
    ("Con năm tuổi bị hóc kẹo", "hoc_di_vat"),
    ("Nước đang dâng vào nhà phải làm gì", "ngap_lut"),
    ("Nước đang dâng có nên cúp cầu dao điện không", "an_toan_dien_ngap"),
    ("Số cứu hỏa ở Việt Nam là bao nhiêu", "so_khan_cap"),
])
def test_cards(sc, q, card):
    m = sc.match(q)
    assert m is not None and m.card is not None and m.card.id == card


@pytest.mark.parametrize("q", [
    "Lũ quét hình thành như thế nào?", "Tại sao dưới nước âm thanh truyền nhanh hơn?", "bật tính năng offline ở đâu",
    "Kỹ năng nào quan trọng khi cần học ngôn ngữ mới", "Đồ hộp bị phồng có ăn được không", "Lũ trẻ trong xóm hay chơi gì",
    "Bão giá xăng dầu tháng này thế nào", "Mình sốt ruột chờ kết quả thi"])
def test_not_safety(sc, q):
    assert sc.match(q) is None


def test_fallback_without_card(sc):
    m = sc.match("Bị đỉa bám vào chân không gỡ ra được phải làm gì?")   # no leech card: the fixed "call 115" answer
    assert m is not None and m.card is None and "một một lăm" in m.say


def test_fastpath_puts_safety_first():
    fp = FastPath(str(ROOT / "data/fastpath/faq.jsonl"), safety_path=str(CARDS))
    h = fp.lookup("Bị chó cắn thì phải làm gì?")
    assert h is not None and h.source == "safety" and h.intent == "cho_meo_can"
    assert fp.lookup("Thủ đô của Pháp là gì?") is None


@pytest.mark.parametrize("q,card", [
    ("Bé hai tuổi ngừng thở", "hoi_suc_tre_em"),
    ("Em bé ba tháng tuổi không thở", "hoi_suc_so_sinh"),
    ("Người lớn ngã gục không thở", "hoi_suc_tim_phoi"),
    ("Bị bọ cạp đốt vào tay", "bo_cap"),
    ("Chảy máu cam không ngừng", "chay_mau_cam"),
    ("Có động đất phải làm gì", "dong_dat"),
    ("Hóa chất bắn vào mắt", "mat"),
    ("Bị axit bắn vào tay", "bong_hoa_chat"),
])
def test_new_cards_and_redirects(sc, q, card):
    m = sc.match(q)
    assert m is not None and m.card is not None and m.card.id == card


@pytest.mark.parametrize("q", ["Cung Bọ Cạp hợp với cung nào", "Nấu lẩu nấm thế nào cho ngon", "Sốt cà chua làm thế nào",
                               "Đường huyết bình thường là bao nhiêu", "Tại sao lại bị chảy máu cam"])
def test_new_cards_do_not_trigger(sc, q):
    assert sc.match(q) is None


def test_classifier_parity_features():
    from vieedge.safety import clf_features
    assert clf_features("Rắn cắn!") == sorted({"w:rắn", "w:cắn", "a:ran", "a:can", "b:rắn_cắn", "c:ran_can"})


@pytest.mark.parametrize("q,card", [
    ("Bị sứa đốt khi tắm biển phải làm gì?", "sua_dot"),
    ("Có kẻ xả súng trong siêu thị", "tan_cong_vu_khi"),
    ("Ở Nhật gọi cấp cứu số mấy", "so_khan_cap_quoc_te"),
    ("Gọi cấp cứu số mấy", "so_khan_cap"),
    ("Ngửi thấy mùi gas trong bếp", "ro_ri_gas"),
    ("Có người ngất dưới hầm biogas", "khi_doc_ham"),
])
def test_global_and_second_batch(sc, q, card):
    m = sc.match(q)
    assert m is not None and m.card is not None and m.card.id == card
