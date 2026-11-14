import pytest

from vieedge.tts.vi_normalize import normalize, number_to_words


@pytest.mark.parametrize("n,expected", [
    (0, "không"), (5, "năm"), (10, "mười"), (11, "mười một"), (15, "mười lăm"), (20, "hai mươi"),
    (21, "hai mươi mốt"), (24, "hai mươi tư"), (25, "hai mươi lăm"), (55, "năm mươi lăm"),
    (100, "một trăm"), (101, "một trăm linh một"), (105, "một trăm linh năm"), (110, "một trăm mười"),
    (115, "một trăm mười lăm"), (999, "chín trăm chín mươi chín"),
    (1000, "một nghìn"), (1005, "một nghìn không trăm linh năm"), (1010, "một nghìn không trăm mười"),
    (2026, "hai nghìn không trăm hai mươi sáu"), (10000, "mười nghìn"), (21000, "hai mươi mốt nghìn"),
    (1_000_000, "một triệu"), (1_250_000, "một triệu hai trăm năm mươi nghìn"),
    (3_000_005, "ba triệu không trăm linh năm"), (2_000_000_000, "hai tỷ"),
    (-7, "âm bảy"),
])
def test_number_to_words(n, expected):
    assert number_to_words(n) == expected


@pytest.mark.parametrize("text,expected", [
    ("Năm 2026", "Năm hai nghìn không trăm hai mươi sáu"),
    ("Giá là 50%", "Giá là năm mươi phần trăm"),
    ("Hôm nay 03/10/2026", "Hôm nay ngày ba tháng mười năm hai nghìn không trăm hai mươi sáu"),
    ("ngày 30/4", "ngày ba mươi tháng tư"),
    ("Họp lúc 14:30", "Họp lúc mười bốn giờ ba mươi phút"),
    ("Hẹn 7h30 sáng", "Hẹn bảy giờ ba mươi sáng"),
    ("Tốc độ 60 km/h", "Tốc độ sáu mươi ki lô mét trên giờ"),
    ("Nhiệt độ 37,5°C", "Nhiệt độ ba mươi bảy phẩy năm độ xê"),
    ("Dân số 1.000.000 người", "Dân số một triệu người"),
    ("Pi bằng 3.14", "Pi bằng ba phẩy mười bốn"),
    ("Giá 25.000đ", "Giá hai mươi lăm nghìn đồng"),
    ("Giá $5", "Giá năm đô la"),
    ("Tôi ở TP.HCM", "Tôi ở thành phố Hồ Chí Minh"),
    ("thế kỷ XXI", "thế kỷ hai mươi mốt"),
    ("Thứ 4 tuần sau", "Thứ tư tuần sau"),
    ("hạng 1", "hạng nhất"),
    ("từ 5-10 phút", "từ năm đến mười phút"),
    ("Nặng 2 kg", "Nặng hai ki lô gam"),
    ("Gọi 0901234567", "Gọi không chín không một hai ba bốn năm sáu bảy"),
    ("tháng 4 năm 1975", "tháng tư năm một nghìn chín trăm bảy mươi lăm"),
    ("Hailo-8L đạt 13 TOPS", "Hailo-tám L đạt mười ba tốp"),
])
def test_normalize(text, expected):
    assert normalize(text) == expected


def test_markdown_removed():
    md = "**Hà Nội** là thủ đô.\n- Diện tích: 3.359 km²\n- Dân số khoảng 8,5 triệu"
    out = normalize(md)
    assert "*" not in out and "-" not in out
    assert "ba nghìn ba trăm năm mươi chín ki lô mét vuông" in out
    assert "tám phẩy năm triệu" in out


def test_emoji_and_symbols():
    out = normalize("Chúc bạn vui 😊 & khỏe!")
    assert "😊" not in out and "và" in out


def test_no_digits_left():
    import re

    out = normalize("Ngày 2/9/1945, lúc 14:00, có 500 nghìn người, chiếm 12,5% và 3/4 số dân.")
    assert not re.search(r"\d", out), out
