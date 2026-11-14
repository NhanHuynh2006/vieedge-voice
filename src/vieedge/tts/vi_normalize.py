"""Vietnamese text normalisation for TTS (PLAN §5.3, experiment T2).

Piper/espeak read digits and symbols poorly in Vietnamese ("2026", "14:30", "50%", "km/h",
"TP.HCM"...). Everything the LLM may produce is rewritten into spoken words *before* TTS:

  numbers (integers, thousand separators, decimals, negatives, ranges), ordinals,
  dates, times, percentages, currencies, units, Roman numerals (thế kỷ XXI),
  common abbreviations / acronyms, phone-like digit strings, and Markdown / emoji removal.

Reading rules follow standard (northern) Vietnamese: 21 = hai mươi mốt, 24 = hai mươi tư,
25 = hai mươi lăm, 105 = một trăm linh năm, 2026 = hai nghìn không trăm hai mươi sáu.
"""
from __future__ import annotations

import re
import unicodedata

DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
SCALES = ["", "nghìn", "triệu", "tỷ"]


# ----------------------------------------------------------------------------- numbers
def _read_two(n: int, full: bool) -> str:
    """0..99. `full`: inside a larger number (05 -> 'linh năm')."""
    tens, unit = divmod(n, 10)
    if tens == 0:
        if unit == 0:
            return ""
        return ("linh " if full else "") + DIGITS[unit]
    if tens == 1:
        head = "mười"
        if unit == 0:
            return head
        if unit == 5:
            return head + " lăm"
        return head + " " + DIGITS[unit]
    head = DIGITS[tens] + " mươi"
    if unit == 0:
        return head
    if unit == 1:
        return head + " mốt"
    if unit == 4:
        return head + " tư"
    if unit == 5:
        return head + " lăm"
    return head + " " + DIGITS[unit]


def _read_three(n: int, full: bool) -> str:
    """0..999; `full` forces 'không trăm' for groups after the leading one."""
    hundreds, rest = divmod(n, 100)
    if hundreds == 0 and not full:
        return _read_two(rest, False)
    out = DIGITS[hundreds] + " trăm"
    if rest:
        out += " " + _read_two(rest, True)
    return out


def number_to_words(n: int) -> str:
    if n < 0:
        return "âm " + number_to_words(-n)
    if n < 10:
        return DIGITS[n]
    if n < 100:
        return _read_two(n, False)
    groups = []
    while n > 0:
        groups.append(n % 1000)
        n //= 1000
    if len(groups) > len(SCALES):  # >= 10^12: "nghìn tỷ" style
        hi = int("".join(f"{g:03d}" for g in reversed(groups[3:])))
        lo = groups[:3]
        return (number_to_words(hi) + " tỷ " + _join_groups(lo, leading=False)).strip()
    return _join_groups(groups, leading=True)


def _join_groups(groups: list[int], leading: bool) -> str:
    parts = []
    top = len(groups) - 1
    for i in range(top, -1, -1):
        g = groups[i]
        if g == 0:
            continue
        is_leading = leading and i == top
        words = _read_three(g, full=not is_leading)
        scale = SCALES[i] if i < len(SCALES) else ""
        parts.append((words + " " + scale).strip())
    return " ".join(parts).strip() or "không"


def digits_to_words(s: str) -> str:
    return " ".join(DIGITS[int(c)] for c in s if c.isdigit())


def decimal_to_words(int_part: str, frac: str, sep_word: str = "phẩy") -> str:
    left = number_to_words(int(int_part)) if int_part else "không"
    frac = frac.rstrip("0") or "0"
    if len(frac) <= 2 and not frac.startswith("0"):
        right = number_to_words(int(frac))
    else:
        right = digits_to_words(frac)
    return f"{left} {sep_word} {right}"


ORDINAL = {1: "nhất", 4: "tư"}


def ordinal_words(n: int) -> str:
    return ORDINAL.get(n, number_to_words(n))


MONTH = {4: "tư"}


def month_words(m: int) -> str:
    return MONTH.get(m, number_to_words(m))


ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def roman_to_int(s: str) -> int | None:
    if not s or not re.fullmatch(r"M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})", s):
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN[ch]
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


# ----------------------------------------------------------------------------- lexicons
UNITS = {
    "km/h": "ki lô mét trên giờ", "m/s": "mét trên giây", "kWh": "ki lô oát giờ",
    "km²": "ki lô mét vuông", "km2": "ki lô mét vuông", "m²": "mét vuông", "m2": "mét vuông",
    "m³": "mét khối", "m3": "mét khối", "cm²": "xen ti mét vuông", "cm2": "xen ti mét vuông",
    "km": "ki lô mét", "cm": "xen ti mét", "mm": "mi li mét", "nm": "na nô mét", "m": "mét",
    "kg": "ki lô gam", "mg": "mi li gam", "g": "gam", "tấn": "tấn",
    "ml": "mi li lít", "l": "lít", "ha": "héc ta",
    "°C": "độ xê", "ºC": "độ xê", "°F": "độ ép", "độ C": "độ xê", "°": "độ",
    "GHz": "gi ga héc", "MHz": "mê ga héc", "kHz": "ki lô héc", "Hz": "héc",
    "TB": "tê ra bai", "GB": "gi ga bai", "MB": "mê ga bai", "KB": "ki lô bai",
    "kW": "ki lô oát", "MW": "mê ga oát", "W": "oát", "V": "vôn", "mAh": "mi li am pe giờ", "A": "am pe",
    "ms": "mi li giây", "h": "giờ", "s": "giây", "ph": "phút",
    "TOPS": "tốp", "tỷ": "tỷ", "triệu": "triệu",
}
CURRENCY_AFTER = {"đ": "đồng", "₫": "đồng", "VND": "đồng", "VNĐ": "đồng", "vnđ": "đồng", "vnd": "đồng",
                  "USD": "đô la Mỹ", "usd": "đô la Mỹ", "EUR": "ơ rô", "€": "ơ rô"}
CURRENCY_BEFORE = {"$": "đô la", "€": "ơ rô", "£": "bảng Anh", "¥": "yên"}

ABBREV = {
    "TP.HCM": "thành phố Hồ Chí Minh", "TP. HCM": "thành phố Hồ Chí Minh", "TPHCM": "thành phố Hồ Chí Minh",
    "TP HCM": "thành phố Hồ Chí Minh", "HCM": "Hồ Chí Minh", "TP.": "thành phố", "Tp.": "thành phố",
    "HN": "Hà Nội", "VN": "Việt Nam", "ĐH": "đại học", "ĐHQG": "đại học quốc gia", "UBND": "ủy ban nhân dân",
    "THPT": "trung học phổ thông", "THCS": "trung học cơ sở", "CLB": "câu lạc bộ", "HLV": "huấn luyện viên",
    "GS.TS": "giáo sư tiến sĩ", "PGS.TS": "phó giáo sư tiến sĩ", "PGS": "phó giáo sư", "GS": "giáo sư",
    "TS": "tiến sĩ", "ThS": "thạc sĩ", "Th.S": "thạc sĩ", "BS": "bác sĩ", "KS": "kỹ sư",
    "v.v.": "vân vân", "v.v": "vân vân", "vv.": "vân vân", "VD": "ví dụ", "vd": "ví dụ", "e.g.": "ví dụ",
    "Q.": "quận", "P.": "phường", "TW": "trung ương", "CHXHCN": "cộng hòa xã hội chủ nghĩa",
    "NXB": "nhà xuất bản", "SĐT": "số điện thoại", "sđt": "số điện thoại", "TNHH": "trách nhiệm hữu hạn",
    "COVID-19": "cô vít mười chín", "COVID": "cô vít", "WHO": "tổ chức y tế thế giới", "ASEAN": "a si an",
    "AI": "ây ai", "CPU": "xê pê u", "GPU": "gờ pê u", "NPU": "nờ pê u", "USB": "u ét bê", "IoT": "ai ô ti",
    "OK": "ô kê", "ok": "ô kê", "Wi-Fi": "oai phai", "WiFi": "oai phai", "wifi": "oai phai",
    "TV": "ti vi", "PC": "pi xi", "SMS": "ét em ét", "PIN": "pin",
}
LETTER = {"A": "a", "B": "bê", "C": "xê", "D": "đê", "Đ": "đê", "E": "e", "F": "ép", "G": "gờ", "H": "hát",
          "I": "i", "J": "giây", "K": "ca", "L": "e lờ", "M": "em mờ", "N": "en nờ", "O": "o", "P": "pê",
          "Q": "quy", "R": "e rờ", "S": "ét", "T": "tê", "U": "u", "V": "vê", "W": "vê kép", "X": "ích",
          "Y": "i dài", "Z": "dét"}
SYMBOLS = {"&": " và ", "+": " cộng ", "=": " bằng ", "~": " khoảng ", "≈": " xấp xỉ ", ">": " lớn hơn ",
           "<": " nhỏ hơn ", "≥": " lớn hơn hoặc bằng ", "≤": " nhỏ hơn hoặc bằng ", "×": " nhân ",
           "÷": " chia ", "@": " a còng ", "→": " sang ", "–": ", ", "—": ", ", "…": ". "}

_NUM = r"\d{1,3}(?:\.\d{3})+|\d+"  # 1.000.000 (vi thousands) or plain


def _to_int(s: str) -> int:
    return int(s.replace(".", "").replace(" ", ""))


# ----------------------------------------------------------------------------- passes
def strip_markdown(t: str) -> str:
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"https?://\S+|www\.\S+", " ", t)
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"^\s*>\s?", "", t, flags=re.M)
    t = re.sub(r"^\s*(?:[-*+•]|\d+[.)])\s+", "", t, flags=re.M)  # list markers
    t = re.sub(r"(\*\*|__|\*|_|~~)(.+?)\1", r"\2", t)
    t = re.sub(r"\|", ", ", t)
    t = t.replace("*", " ").replace("#", " ")
    # lines -> sentences
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    out = []
    for ln in lines:
        out.append(ln if re.search(r"[.!?:;,]$", ln) else ln + ".")
    return " ".join(out) if len(out) > 1 else (lines[0] if lines else "")


def strip_emoji(t: str) -> str:
    keep = "°º²³€£¥₫$%&+=~≈><≥≤×÷@→"
    return "".join(ch for ch in t if ch in keep or not (
        unicodedata.category(ch) in ("So", "Cs", "Co") or 0x1F000 <= ord(ch) <= 0x1FAFF
        or 0x2600 <= ord(ch) <= 0x27BF or ord(ch) in (0xFE0F, 0x200D)))


def expand_abbrev(t: str) -> str:
    for k in sorted(ABBREV, key=len, reverse=True):
        pat = r"(?<![\wÀ-ỹ])" + re.escape(k) + (r"(?![\wÀ-ỹ])" if k[-1].isalnum() else "")
        t = re.sub(pat, ABBREV[k], t)
    return t


def expand_dates_times(t: str) -> str:
    # dd/mm/yyyy, dd-mm-yyyy
    def dmy(m: re.Match) -> str:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (1 <= d <= 31 and 1 <= mo <= 12):
            return m.group(0)
        pre = "" if re.search(r"ngày\s*$", t[: m.start()]) else "ngày "
        return f"{pre}{number_to_words(d)} tháng {month_words(mo)} năm {number_to_words(y)}"

    t = re.sub(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", dmy, t)

    # mm/yyyy
    def my(m: re.Match) -> str:
        mo, y = int(m.group(1)), int(m.group(2))
        if not 1 <= mo <= 12:
            return m.group(0)
        pre = "" if re.search(r"tháng\s*$", t[: m.start()]) else "tháng "
        return f"{pre}{month_words(mo)} năm {number_to_words(y)}"

    t = re.sub(r"\b(\d{1,2})/(\d{4})\b", my, t)

    # dd/mm (only when it is a plausible date)
    def dm(m: re.Match) -> str:
        d, mo = int(m.group(1)), int(m.group(2))
        if not (1 <= d <= 31 and 1 <= mo <= 12):
            return m.group(0)
        pre = "" if re.search(r"ngày\s*$", t[: m.start()]) else "ngày "
        return f"{pre}{number_to_words(d)} tháng {month_words(mo)}"

    t = re.sub(r"(?<![\d.,])\b(\d{1,2})/(\d{1,2})\b(?![\d/])", dm, t)

    # "tháng 4" -> "tháng tư"
    t = re.sub(r"\btháng\s+(\d{1,2})\b", lambda m: "tháng " + month_words(int(m.group(1))) if 1 <= int(m.group(1)) <= 12 else m.group(0), t)
    # "năm 2026"
    t = re.sub(r"\bnăm\s+(\d{3,4})\b", lambda m: "năm " + number_to_words(int(m.group(1))), t)

    # hh:mm(:ss)
    def hm(m: re.Match) -> str:
        h, mi = int(m.group(1)), int(m.group(2))
        if h > 24 or mi > 59:
            return m.group(0)
        s = f"{number_to_words(h)} giờ"
        if mi:
            s += f" {number_to_words(mi)} phút"
        if m.group(3):
            s += f" {number_to_words(int(m.group(3)))} giây"
        return s

    t = re.sub(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b", hm, t)
    # 7h30, 7h, 7g30
    t = re.sub(r"\b(\d{1,2})[hg](\d{2})?\b(?!\w)",
               lambda m: f"{number_to_words(int(m.group(1)))} giờ" + (f" {number_to_words(int(m.group(2)))}" if m.group(2) and int(m.group(2)) else ""), t)
    return t


def expand_roman(t: str) -> str:
    def rep(m: re.Match) -> str:
        v = roman_to_int(m.group(2))
        return f"{m.group(1)} {number_to_words(v)}" if v else m.group(0)

    return re.sub(r"\b(thế kỷ|thế kỉ|Thế kỷ|Thế kỉ|khóa|đại hội|Đại hội|chương|Chương|phần|Phần)\s+([IVXLCDM]+)\b", rep, t)


def expand_ordinals(t: str) -> str:
    t = re.sub(r"\b(thứ|Thứ|hạng|lần thứ)\s+(\d+)\b", lambda m: f"{m.group(1)} {ordinal_words(int(m.group(2)))}", t)
    return t


def expand_money_percent_units(t: str) -> str:
    # $5, $1.5
    def before(m: re.Match) -> str:
        sym, num = m.group(1), m.group(2)
        return f"{_num_words(num)} {CURRENCY_BEFORE[sym]}"

    t = re.sub(r"([$€£¥])\s?(\d[\d.,]*)", before, t)

    # 5.000đ / 5 triệu đồng / 20 USD
    cur = "|".join(re.escape(k) for k in sorted(CURRENCY_AFTER, key=len, reverse=True))
    t = re.sub(rf"(\d[\d.,]*)\s?({cur})(?![\wÀ-ỹ])", lambda m: f"{_num_words(m.group(1))} {CURRENCY_AFTER[m.group(2)]}", t)

    # percent
    t = re.sub(r"(\d[\d.,]*)\s?%", lambda m: f"{_num_words(m.group(1))} phần trăm", t)

    # units after numbers (longest first)
    unit_re = "|".join(re.escape(k) for k in sorted(UNITS, key=len, reverse=True))
    t = re.sub(rf"(\d[\d.,]*)\s?({unit_re})(?![\wÀ-ỹ²³])", lambda m: f"{_num_words(m.group(1))} {UNITS[m.group(2)]}", t)
    return t


def _num_words(s: str) -> str:
    s = s.strip()
    neg = s.startswith("-")
    s = s.lstrip("-")
    s = s.rstrip(".,")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):  # 1.000.000 -> vi thousands
        w = number_to_words(_to_int(s))
    elif re.fullmatch(r"\d{1,3}(?:,\d{3}){2,}", s):  # 1,000,000 (en thousands, >= 2 groups)
        w = number_to_words(int(s.replace(",", "")))
    elif re.fullmatch(r"\d+,\d+", s):  # 3,5 vi decimal
        a, b = s.split(",")
        w = decimal_to_words(a, b, "phẩy")
    elif re.fullmatch(r"\d+\.\d+", s):  # 3.14 (not a thousands group) -> decimal
        a, b = s.split(".")
        w = decimal_to_words(a, b, "phẩy")
    elif s.isdigit():
        if len(s) >= 8 or (len(s) > 1 and s.startswith("0")):  # phone numbers, codes
            w = digits_to_words(s)
        else:
            w = number_to_words(int(s))
    else:
        return s
    return ("âm " + w) if neg else w


def expand_numbers(t: str) -> str:
    # ranges 5-10 / 2020–2025
    t = re.sub(r"\b(\d[\d.,]*)\s?[-–]\s?(\d[\d.,]*)\b", lambda m: f"{_num_words(m.group(1))} đến {_num_words(m.group(2))}", t)
    # negative numbers
    t = re.sub(r"(?<![\w\d])-(\d[\d.,]*\d|\d)", lambda m: "âm " + _num_words(m.group(1)), t)
    # all remaining numbers (keep a trailing sentence period out of the number)
    def rep(m: re.Match) -> str:
        w = _num_words(m.group(0))
        nxt = t[m.end():m.end() + 1]
        return w + (" " if nxt.isalpha() else "")

    t = re.sub(r"\d+(?:[.,]\d+)*", rep, t)
    return t


def expand_acronyms(t: str) -> str:
    def rep(m: re.Match) -> str:
        w = m.group(0)
        return " ".join(LETTER.get(c, c) for c in w)

    return re.sub(r"(?<![\wÀ-ỹ])[A-ZĐ]{2,5}(?![\wÀ-ỹ])", rep, t)


def expand_symbols(t: str) -> str:
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = re.sub(r"(?<=\w)/(?=\w)", " trên ", t)
    t = re.sub(r"[\"“”‘’«»()\[\]{}]", " ", t)
    return t


def cleanup(t: str) -> str:
    t = re.sub(r"\s+([.,!?;:])", r"\1", t)
    t = re.sub(r"([.,!?;:])(?=[^\s.,!?;:])", r"\1 ", t)
    t = re.sub(r"([.!?])[.!?]+", r"\1", t)
    t = re.sub(r",\s*,", ",", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip(" ,;")


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text)
    t = strip_markdown(t)
    t = strip_emoji(t)
    t = expand_abbrev(t)
    t = expand_dates_times(t)
    t = expand_roman(t)
    t = expand_ordinals(t)
    t = expand_money_percent_units(t)
    t = expand_numbers(t)
    t = expand_acronyms(t)
    t = expand_symbols(t)
    return cleanup(t)
