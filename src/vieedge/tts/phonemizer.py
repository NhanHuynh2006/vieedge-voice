"""espeak-ng phonemizer via ctypes (what Piper does internally, without the piper-phonemize wheel).

Piper vi_VN voices were trained on espeak-ng IPA for voice "vi". espeak returns one clause per
call and swallows the punctuation, so text is split into clauses here and the punctuation is
re-appended (Piper's phoneme_id_map has ids for , . ! ? etc.). Output is NFD-decomposed like Piper.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import re
import threading
import unicodedata

AUDIO_OUTPUT_SYNCHRONOUS = 0x02
espeakCHARS_UTF8 = 1
espeakPHONEMES_IPA = 0x02

_CLAUSE = re.compile(r"([^.,!?;:…]+)([.,!?;:…]*)")
_LANG_SWITCH = re.compile(r"\([a-z\-]{2,8}\)")  # espeak "(en)...(vi)" language-switch flags


class EspeakPhonemizer:
    _lock = threading.Lock()  # libespeak-ng is not thread safe
    _inited: dict = {}

    def __init__(self, voice: str = "vi", data_path: str | None = None):
        name = ctypes.util.find_library("espeak-ng") or "libespeak-ng.so.1"
        self.lib = ctypes.cdll.LoadLibrary(name)
        self.lib.espeak_TextToPhonemes.restype = ctypes.c_char_p
        self.lib.espeak_TextToPhonemes.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_int, ctypes.c_int]
        self.lib.espeak_Initialize.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        self.lib.espeak_SetVoiceByName.argtypes = [ctypes.c_char_p]
        with self._lock:
            key = (name, data_path)
            if key not in self._inited:
                sr = self.lib.espeak_Initialize(AUDIO_OUTPUT_SYNCHRONOUS, 0,
                                                data_path.encode() if data_path else None, 0)
                if sr <= 0:
                    raise RuntimeError(f"espeak_Initialize failed (data_path={data_path})")
                self._inited[key] = True
            if self.lib.espeak_SetVoiceByName(voice.encode()) != 0:
                raise RuntimeError(f"espeak voice {voice!r} not found")
        self.voice = voice

    def _clause(self, text: str) -> str:
        buf = ctypes.create_string_buffer(text.encode("utf-8"))
        ptr = ctypes.c_void_p(ctypes.addressof(buf))
        out = []
        while ptr.value:
            ph = self.lib.espeak_TextToPhonemes(ctypes.byref(ptr), espeakCHARS_UTF8, espeakPHONEMES_IPA)
            if ph:
                out.append(_LANG_SWITCH.sub("", ph.decode("utf-8", errors="ignore")).strip())
        return " ".join(p for p in out if p)

    def phonemize(self, text: str) -> list[str]:
        """Text -> list of sentences, each a string of IPA phoneme codepoints (NFD)."""
        sentences: list[str] = []
        cur: list[str] = []
        with self._lock:
            self.lib.espeak_SetVoiceByName(self.voice.encode())
            for m in _CLAUSE.finditer(text):
                words, punct = m.group(1).strip(), m.group(2)
                if not words:
                    continue
                ph = self._clause(words)
                p = punct[:1] if punct else ""
                cur.append(ph + p)
                if p in (".", "!", "?", "…"):
                    sentences.append(" ".join(cur))
                    cur = []
        if cur:
            sentences.append(" ".join(cur))
        return [unicodedata.normalize("NFD", s) for s in sentences]
