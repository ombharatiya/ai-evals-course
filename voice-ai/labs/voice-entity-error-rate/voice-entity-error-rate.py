"""Entity error rate for spoken amounts and dates (aievals.co recipe R1).

Steelyard Credit is a fictional lender; its numbers are illustrative.
Standard library only. Python 3.11.
Run: python voice_entity_error_rate.py                  (global edition, the default)
     python voice_entity_error_rate.py --edition india  (India edition)
"""
from __future__ import annotations

import argparse
import datetime as dt
import random
import re
import unicodedata
from collections import Counter, defaultdict
from fractions import Fraction

EDITIONS: dict = {}     # edition name -> (constants block, report function)

# ---- GLOBAL constants (copied from the global world bible, world-global-v1.1) ----
GLOBAL = {
    "lender": "Steelyard Credit, Inc. (fictional; numbers are illustrative)",
    "dataset": "steelyard-calls (synthetic, seed 20261121)",
    "products": {"AUTO": "Auto loan", "PIL": "Personal installment loan, digital",
                 "POS": "Retail point-of-sale financing", "SBL": "Small business loan",
                 "SDL": "Credit-builder and small-dollar loan"},
    "campaigns": {"AUTO-early-nov": "AUTO", "PIL-digital-nov": "PIL", "POS-short-nov": "POS",
                  "SBL-guar-nov": "SBL", "SDL-biwk-nov": "SDL"},
    "calling_window_local": {"default": ("08:00", "21:00"), "SDL": ("09:00", "20:00")},
    "customer_advocate": {"name": "Ms Dana Brooks", "email": "advocate@steelyard.example",
                          "phone": "(520) 555-0199",
                          "address": "1200 Example Avenue, Tucson, AZ 85701"},
    "versions": {"stt": "vendorA-2026-10", "gold": "gold-v7", "taxonomy": "gl-fail-v4"},
    "money_unit": "integer cents in tools and the CRM; dollars in speech",
    "language_groups": ["English", "Spanish-dominant", "Spanglish"],
    "amount_shorthand": {"two fifty": "250.00", "two fifteen": "215.00"},
    "usd_1500_forms": [("fifteen hundred", "en-US"), ("one thousand five hundred", "en-US"),
                       ("1,500", "en-US"), ("1500", "en-US"), ("$1,500.00", "en-US"),
                       ("mil quinientos", "es-US"), ("mil quinientos dolares", "es-US"),
                       ("1.500", "es-ES")],
    "separators": {"en-US": (",", "."), "es-US": (",", "."),     # (group, decimal), CLDR 48
                   "es-MX": (",", "."), "es-ES": (".", ",")},
    "date_order": {"en-US": "mdy", "es-US": "dmy", "es-MX": "dmy", "es-ES": "dmy"},
}
SEED = 20261121
SCORER_VERSION = "steelyard-scorer-v1"

# ---- Lexicons (English and Spanish, accents folded) -------------------------
EN_NUM = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
EN_NUM.update({"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
               "seventy": 70, "eighty": 80, "ninety": 90})
ES_NUM = {w: i for i, w in enumerate(
    "cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce "
    "quince dieciseis diecisiete dieciocho diecinueve veinte veintiuno veintidos "
    "veintitres veinticuatro veinticinco veintiseis veintisiete veintiocho "
    "veintinueve".split())}
ES_NUM.update({"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
               "setenta": 70, "ochenta": 80, "noventa": 90, "cien": 100, "ciento": 100,
               "doscientos": 200, "trescientos": 300, "cuatrocientos": 400,
               "quinientos": 500, "seiscientos": 600, "setecientos": 700,
               "ochocientos": 800, "novecientos": 900})
NUM = {**EN_NUM, **ES_NUM}
MULT = {"hundred": 100, "thousand": 1000, "mil": 1000, "million": 1_000_000,
        "millon": 1_000_000, "millones": 1_000_000}
ORDINAL = {w: i + 1 for i, w in enumerate(
    "first second third fourth fifth sixth seventh eighth ninth tenth eleventh "
    "twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth "
    "nineteenth twentieth".split())}
ORDINAL.update({"thirtieth": 30, "primero": 1})
WEEKDAY = {d: i for i, d in enumerate("monday tuesday wednesday thursday friday saturday "
                                      "sunday".split())}
WEEKDAY.update({d: i for i, d in enumerate("lunes martes miercoles jueves viernes sabado "
                                           "domingo".split())})
MONTH = {m: i % 12 + 1 for i, m in enumerate(
    "january february march april may june july august september october november "
    "december enero febrero marzo abril mayo junio julio agosto septiembre octubre "
    "noviembre diciembre".split())}
RELATIVE = {"today": 0, "tomorrow": 1, "hoy": 0, "mañana": 1, "manana": 1}
CURRENCY = {"dollars", "dollar", "bucks", "dolares", "dolar"}
YES, NO = {"yes", "yeah", "yep", "si", "okay", "ok", "correct"}, {"no", "nope"}
YES_PAIRS = (["that's", "right"], ["eso", "es"])
BACKCHANNEL = {"uh-huh", "mm-hm", "mhm", "aja", "hmm"}


# ---- Canonicalization ------------------------------------------------------
def fold(s: str) -> str:
    """Drop accents (acute, diaeresis); keep the n with a tilde, which is a different letter."""
    return "".join(c if c in "ñÑ" else "".join(
        x for x in unicodedata.normalize("NFD", c) if not unicodedata.combining(x))
        for c in unicodedata.normalize("NFC", s))


def entity_tokens(text: str) -> list[str]:
    toks = []
    for t in fold(text.lower()).split():
        t = t.strip(",.?!;:\"()")
        parts = t.split("-")
        if len(parts) > 1 and all(p in NUM or p in ORDINAL for p in parts):
            toks += parts                           # "twenty-five", "twenty-third"
        elif t:
            toks.append(t)
    return toks


def _numeric(t: str, locale: str = "en-US") -> Fraction | None:
    """Digits read with the locale's separators: '1.500' is 1500 in es-ES and 1.5 in es-MX."""
    group, dec = GLOBAL["separators"][locale]
    t, g, d = t.lstrip("$"), re.escape(group), re.escape(dec)
    if re.fullmatch(rf"\d{{1,3}}(?:{g}\d{{3}})+(?:{d}\d+)?|\d+(?:{d}\d+)?", t):
        return Fraction(t.replace(group, "").replace(dec, "."))
    return None


def _is_num_at(toks: list[str], i: int, locale: str = "en-US") -> bool:
    t = toks[i]
    nxt, prv = (toks[i + 1] if i + 1 < len(toks) else ""), (toks[i - 1] if i else "")
    if t == "a":                                    # "a hundred twenty thousand"
        return nxt in ("hundred", "thousand")
    if t == "y":                                    # "treinta y cinco"
        return NUM.get(prv, 0) in range(20, 100, 10) and NUM.get(nxt, 10) < 10
    return _numeric(t, locale) is not None or t in NUM or t in MULT


def _run_end(toks: list[str], i: int, locale: str = "en-US") -> int:
    j = i
    while j < len(toks) and _is_num_at(toks, j, locale):
        j += 1
    return j


def _day_ordinal(toks: list[str], i: int) -> tuple[int, int] | None:
    """'20th', 'twentieth', 'twenty third' or 'el primero' -> (day, index after it)."""
    t, nxt = toks[i], (toks[i + 1] if i + 1 < len(toks) else "")
    m = re.fullmatch(r"(\d{1,2})(st|nd|rd|th)", t)
    if m:
        return int(m.group(1)), i + 1
    if t in ("twenty", "thirty") and ORDINAL.get(nxt, 99) <= 9:
        return NUM[t] + ORDINAL[nxt], i + 2
    return (ORDINAL[t], i + 1) if t in ORDINAL else None


def _fmt(v: Fraction) -> str:
    return str(v.numerator) if v.denominator == 1 else str(float(v))


def number_value(tokens: list[str], locale: str = "en-US") -> Fraction | None:
    """Western place values. In an amount, 'X fifty' with X from one to nine is X hundred fifty."""
    words = ["one" if t == "a" else t for t in tokens if t != "y"]
    if (len(words) > 1 and 1 <= EN_NUM.get(words[0], 0) <= 9
            and all(w in EN_NUM for w in words[1:])):
        rest = number_value(words[1:])
        if rest is not None and 10 <= rest <= 99:
            return EN_NUM[words[0]] * 100 + rest    # "two fifty" = 250, "four twenty-five" = 425
    total, cur, seen = Fraction(0), Fraction(0), False
    for t in words:
        if t in MULT:
            if MULT[t] == 100:
                cur = (cur or 1) * 100
            else:
                total, cur = total + (cur or 1) * MULT[t], Fraction(0)
            seen = True
            continue
        v = _numeric(t, locale)
        if v is None:
            v = NUM.get(t)
        if v is None:
            return None
        cur, seen = cur + v, True
    return total + cur if seen else None


def _cents(dollars: Fraction | None) -> int | None:
    return None if dollars is None or (dollars * 100).denominator != 1 else int(dollars * 100)


def canon_amount(text: str, locale: str = "en-US") -> int | None:
    """Spoken or written amount -> integer cents, or None."""
    toks = [t for t in entity_tokens(text) if t not in CURRENCY]
    ok = toks and _run_end(toks, 0, locale) == len(toks)
    return _cents(number_value(toks, locale)) if ok else None


def resolve_day(day, call_date: dt.date) -> dt.date | None:
    if day is None or Fraction(day).denominator != 1 or not 1 <= day <= 31:
        return None
    y, m = call_date.year, call_date.month
    for _ in range(3):
        try:
            d = dt.date(y, m, int(day))
            if d >= call_date:
                return d
        except ValueError:
            pass
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return None


def resolve_day_month(day, month: int, call_date: dt.date) -> dt.date | None:
    try:
        d = dt.date(call_date.year, month, int(day))
    except (ValueError, TypeError):
        return None
    return d if d >= call_date else d.replace(year=d.year + 1)


def resolve_weekday(wd: int, call_date: dt.date) -> dt.date:
    """Policy: 'next Friday' and 'el viernes' are the first Friday strictly after the call date."""
    return call_date + dt.timedelta(days=(wd - call_date.weekday()) % 7 or 7)


def extract(text: str, call_date: dt.date, locale: str = "en-US") -> list[tuple[str, object]]:
    """All amount, date and confirmation entities in one utterance, canonicalized."""
    toks, out, i = entity_tokens(text), [], 0
    if toks:
        if toks[:2] == ["si", "si"] or toks[0] in BACKCHANNEL:
            pass                                    # a backchannel is never a yes
        elif toks[0] in YES or toks[:2] in YES_PAIRS:
            out.append(("confirm", "yes"))
        elif toks[0] in NO:
            out.append(("confirm", "no"))
    while i < len(toks):
        t, prv = toks[i], (toks[i - 1] if i else "")
        if t in WEEKDAY:
            out.append(("date", resolve_weekday(WEEKDAY[t], call_date)))
            i += 1
        elif t in RELATIVE:
            out.append(("date", call_date + dt.timedelta(days=RELATIVE[t])))
            i += 1
        elif re.fullmatch(r"\d{1,2}/\d{1,2}", t):          # date order follows the locale
            a, b = map(int, t.split("/"))
            m, d = (a, b) if GLOBAL["date_order"][locale] == "mdy" else (b, a)
            out.append(("date", resolve_day_month(d, m, call_date) if 1 <= m <= 12 else None))
            i += 1
        elif t in MONTH and i + 1 < len(toks) and (
                _day_ordinal(toks, i + 1) or _numeric(toks[i + 1]) is not None):
            day, j = _day_ordinal(toks, i + 1) or (_numeric(toks[i + 1]), i + 2)
            out.append(("date", resolve_day_month(day, MONTH[t], call_date)))
            i = j
        elif _day_ordinal(toks, i):
            day, i = _day_ordinal(toks, i)
            out.append(("date", resolve_day(day, call_date)))
        elif _is_num_at(toks, i, locale):
            j = _run_end(toks, i, locale)
            run, after = toks[i:j], (toks[j] if j < len(toks) else "")
            val = number_value(run, locale)
            if after == "de" and j + 1 < len(toks) and toks[j + 1] in MONTH:
                out.append(("date", resolve_day_month(val, MONTH[toks[j + 1]], call_date)))
                j += 2                              # "el veinte de noviembre"
            elif prv == "el" and val is not None and val <= 31 and after not in CURRENCY:
                out.append(("date", resolve_day(val, call_date)))     # "el veinte"
            elif val is not None and (val >= 100 or after in CURRENCY or run[0][0] == "$"):
                out.append(("amount", _cents(val)))
            i = j
        else:
            i += 1
    return out


def entity_counts(gold: list, hyp: list, kind: str) -> tuple[int, int, int]:
    """Exact match after canonicalization. Returns (gold, missed, hallucinated)."""
    g = Counter(v for k, v in gold if k == kind)
    h = Counter(v for k, v in hyp if k == kind)
    hit = sum((g & h).values())
    return sum(g.values()), sum(g.values()) - hit, sum(h.values()) - hit


# ---- Scoring policies (the normalizer is part of the metric) ---------------
def _join_digit_groups(s: str) -> str:
    return re.sub(r"(?<=\d),(?=\d)", "", s)


def norm_raw(s: str) -> list[str]:
    return s.split()


def norm_whisper_basic(s: str) -> list[str]:
    """Mirror of Whisper's BasicTextNormalizer: NFKC keeps precomposed accents, no number rules."""
    s = s.lower()
    s = re.sub(r"[<\[][^>\]]*[>\]]", "", s)
    s = re.sub(r"\(([^)]+?)\)", "", s)
    s = "".join(" " if unicodedata.category(c)[0] in "MSP" else c
                for c in unicodedata.normalize("NFKC", s))
    return s.split()


def norm_nfc(s: str) -> list[str]:
    """NFC, lowercase, punctuation and symbols to spaces, digit groups joined, accents kept."""
    s = _join_digit_groups(unicodedata.normalize("NFC", s).lower())
    s = re.sub(r"(?<=\d)\.(?=\d)", "\x00", s)            # keep decimal points
    s = "".join(" " if unicodedata.category(c)[0] in "PS" else c for c in s)
    return s.replace("\x00", ".").split()


def norm_nfc_fold(s: str) -> list[str]:
    return [fold(t) for t in norm_nfc(s)]


def with_numerals(tokens: list[str]) -> list[str]:
    """Numeral canonicalization on top of any policy: a number run or an ordinal becomes its
    value, and a currency word right after a number is dropped."""
    out, i = [], 0
    while i < len(tokens):
        j = _run_end(tokens, i)
        if _day_ordinal(tokens, i):
            day, i = _day_ordinal(tokens, i)
            out.append(str(day))
        elif j > i:
            v = number_value(tokens[i:j])
            out.append(_fmt(v) if v is not None else " ".join(tokens[i:j]))
            i = j + (j < len(tokens) and fold(tokens[j]) in CURRENCY)
        else:
            out.append(tokens[i])
            i += 1
    return out


POLICIES = {"raw": norm_raw, "whisper-basic": norm_whisper_basic,
            "nfc": norm_nfc, "nfc+fold": norm_nfc_fold}


# ---- WER, CER and switch-word error -----------------------------------------
def align(ref: list, hyp: list) -> tuple[int, int, int]:
    """Levenshtein alignment; returns (substitutions, deletions, insertions)."""
    n, m = len(ref), len(hyp)
    d = [[(0, 0, 0, 0)] * (m + 1) for _ in range(n + 1)]   # (cost, S, D, I)
    for i in range(1, n + 1):
        d[i][0] = (i, 0, i, 0)
    for j in range(1, m + 1):
        d[0][j] = (j, 0, 0, j)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            c, s, de, ins = d[i - 1][j - 1]
            best = (c, s, de, ins) if ref[i - 1] == hyp[j - 1] else (c + 1, s + 1, de, ins)
            c, s, de, ins = d[i - 1][j]
            best = min(best, (c + 1, s, de + 1, ins))
            c, s, de, ins = d[i][j - 1]
            best = min(best, (c + 1, s, de, ins + 1))
            d[i][j] = best
    return d[n][m][1:]


def ref_errors(ref: list, hyp: list) -> list[bool]:
    """One flag per reference token: True if a minimum-edit alignment substitutes or deletes it."""
    n, m = len(ref), len(hyp)
    d = [[i + j if i * j == 0 else 0 for j in range(m + 1)] for i in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]),
                          d[i - 1][j] + 1, d[i][j - 1] + 1)
    flags, i, j = [False] * n, n, m
    while i > 0:
        if j > 0 and d[i][j] == d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]):
            flags[i - 1], i, j = ref[i - 1] != hyp[j - 1], i - 1, j - 1
        elif d[i][j] == d[i - 1][j] + 1:
            flags[i - 1], i = True, i - 1
        else:
            j -= 1
    return flags


def wer(ref: str, hyp: str, policy: str = "nfc+fold", numerals: bool = False):
    r, h = POLICIES[policy](ref), POLICIES[policy](hyp)
    if numerals:
        r, h = with_numerals(r), with_numerals(h)
    s, de, ins = align(r, h)
    return {"S": s, "D": de, "I": ins, "N": len(r), "wer": (s + de + ins) / max(len(r), 1)}


def cer_counts(ref: str, hyp: str) -> tuple[int, int]:
    r, h = " ".join(norm_nfc_fold(ref)), " ".join(norm_nfc_fold(hyp))
    return sum(align(list(r), list(h))), len(r)


def switch_word_counts(words: list[tuple[str, str]], hyp: str, lang: str = "es"):
    """PIER-style: errors on the reference words tagged `lang` only (insertions not counted).
    words = [(reference word, language tag)]. Returns (errors, tagged tokens)."""
    ref, tags = [], []
    for w, tag in words:
        for t in norm_nfc_fold(w):
            ref.append(t)
            tags.append(tag)
    flags = ref_errors(ref, norm_nfc_fold(hyp))
    return sum(f for f, t in zip(flags, tags) if t == lang), tags.count(lang)


# ---- Synthetic data: templates plus seeded error injection -----------------
AMOUNT_FORMS = {   # cents -> spoken surface forms by language (WG7 canonical values)
    25000: {"en": ["two fifty", "two hundred fifty"], "es": ["doscientos cincuenta dólares"],
            "num": ["250", "$250"]},
    21500: {"en": ["two fifteen", "two hundred fifteen"], "es": ["doscientos quince"],
            "num": ["215"]},
    42500: {"en": ["four twenty-five", "four hundred twenty-five"],
            "es": ["cuatrocientos veinticinco"], "num": ["$425"]},
    13000: {"en": ["one thirty", "a hundred thirty"], "es": ["ciento treinta dólares"],
            "num": ["130"]},
    35000: {"en": ["three fifty", "three hundred fifty"], "es": ["trescientos cincuenta"],
            "num": ["350"]},
    68000: {"en": ["six eighty", "six hundred eighty"], "es": ["seiscientos ochenta"],
            "num": ["$680"]},
    150000: {"en": ["fifteen hundred", "one thousand five hundred"],
             "es": ["mil quinientos", "mil quinientos dólares"], "num": ["1,500", "$1,500.00"]},
    12000000: {"en": ["a hundred twenty thousand"], "es": ["ciento veinte mil"],
               "num": ["120,000"]},
}
EN_ORD = {v: k for k, v in ORDINAL.items() if k != "primero"}
for _d in range(21, 32):
    EN_ORD.setdefault(_d, ("twenty-" if _d < 30 else "thirty-") + EN_ORD[_d % 10 or 10])
ES_DAY = {v: k for k, v in ES_NUM.items() if v <= 31}
ES_DAY.update({1: "primero", 16: "dieciséis", 22: "veintidós", 23: "veintitrés",
               26: "veintiséis"})
WEEKDAYS = {"en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
            "es": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]}
ES_MONTH = ("enero febrero marzo abril mayo junio julio agosto septiembre octubre "
            "noviembre diciembre").split()
TEMPLATES = {   # language group -> [(pieces [(text, language)], polarity of the opening word)]
    "English": [
        ([("yes I can pay {A} on {D}", "en")], "yes"),
        ([("yeah I can do {A} on {D}, rest next month", "en")], "yes"),
        ([("right now I only have {A}, the rest {D}", "en")], None),
        ([("I'll send {A} by {D}", "en")], None),
        ([("I already paid {A} last week", "en")], None),
        ([("can you text me the link for {A}", "en")], None),
        ([("no no, I said {A}", "en")], "no"),
        ([("after payday, {D}", "en")], None),
        ([("yes", "en")], "yes"), ([("no", "en")], "no"),
        ([("yes that's right", "en")], "yes"), ([("no, that's wrong", "en")], "no")],
    "Spanish-dominant": [
        ([("sí, puedo pagar {A} {D}", "es")], "yes"),
        ([("ahorita solo tengo {A}, el resto {D}", "es")], None),
        ([("le pago {A} {D}", "es")], None),
        ([("ya pagué {A} la semana pasada", "es")], None),
        ([("mándeme el enlace de {A}", "es")], None),
        ([("no, no, dije {A}", "es")], "no"),
        ([("sí", "es")], "yes"), ([("no", "es")], "no"),
        ([("sí, eso es", "es")], "yes"), ([("no, está mal", "es")], "no")],
    "Spanglish": [
        ([("sí, pero", "es"), ("my paycheck comes", "en"), ("{D}", "es"),
          ("so after that I can pay", "en")], "yes"),
        ([("I can do", "en"), ("{A}", "en"), ("{D}", "es")], None),
        ([("puedo pagar", "es"), ("{A}", "es"), ("next week, on", "en"), ("{D}", "en")], None),
        ([("ya pagué", "es"), ("{A}", "en"), ("last week", "en")], None),
        ([("okay,", "en"), ("entonces", "es"), ("{A}", "es"), ("on", "en"), ("{D}", "en")],
         "yes"),
        ([("no, no,", "es"), ("I said", "en"), ("{A}", "es")], "no")],
}
LOCALE = {"English": "en-US", "Spanish-dominant": "es-US", "Spanglish": "es-US"}
NUM_CONFUSION = {"fifty": "fifteen", "fifteen": "fifty", "thirty": "thirteen",
                 "eighty": "eighteen", "twenty-five": "twenty-nine", "cincuenta": "sesenta",
                 "doscientos": "trescientos", "trescientos": "doscientos", "quince": "trece",
                 "treinta": "trece", "quinientos": "cuatrocientos", "seiscientos": "setecientos",
                 "twentieth": "twelfth", "november": "december", "friday": "monday",
                 "veinte": "treinta", "noviembre": "diciembre", "viernes": "jueves"}
GEN_VARIANT = {"i'll": "all", "already": "all ready", "right": "write", "rest": "rust",
               "send": "sent", "said": "set", "link": "lint", "text": "next", "comes": "come",
               "paycheck": "pay check", "only": "lonely", "have": "half", "pagar": "pagan",
               "tengo": "tango", "resto": "restó", "entonces": "tonces", "dije": "dice",
               "ahorita": "ahora", "enlace": "enlaces", "semana": "semanas", "puedo": "pueda"}
ANGLO = {"sí": "see", "pero": "pedro", "viernes": "bee air ness", "ya": "yeah",
         "pagué": "page", "puedo": "pueblo", "pagar": "pa car", "entonces": "and on says",
         "dije": "the hay", "veinte": "bane tay", "doscientos": "those see and toes",
         "cincuenta": "seen when ta", "quince": "keen say", "ciento": "see and toe",
         "treinta": "train ta", "mil": "meal", "quinientos": "key and toes", "de": "day",
         "dólares": "dollar is", "veintitrés": "bent he tres", "noviembre": "no be em bray"}
CALL_DATES = [dt.date(2026, 11, d) for d in range(9, 20) if dt.date(2026, 11, d).weekday() != 6]
SYSTEMS = {   # per-token error probabilities, scaled by a per-speaker difficulty
    "A": {"gen": 0.15, "amt": 0.012, "digit": 0.004, "date": 0.015, "neg": 0.03,
          "yes": 0.04, "accent": 0.50, "numfmt": 0.30, "switch": 0.04},
    "B": {"gen": 0.10, "amt": 0.050, "digit": 0.012, "date": 0.025, "neg": 0.07,
          "yes": 0.07, "accent": 0.15, "numfmt": 0.05, "switch": 0.20},
}


def strip_accents(w: str) -> str:
    return "".join(x for x in unicodedata.normalize("NFD", w) if not unicodedata.combining(x))


def render_date(rng: random.Random, call: dt.date, lang: str) -> tuple[str, dt.date]:
    kind = rng.choices(["day", "month", "weekday", "other"], [5, 2, 2, 1])[0]
    if kind == "weekday":
        wd = rng.randrange(6)
        day_name = WEEKDAYS[lang][wd]
        return (f"next {day_name}" if lang == "en" else f"el {day_name}"), resolve_weekday(wd, call)
    if kind == "other" and lang == "es":
        return "mañana", call + dt.timedelta(days=1)
    target = call + dt.timedelta(days=rng.randint(1, 25))
    if lang == "en":
        if kind == "other":
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(target.day % 10 * (target.day // 10 != 1), "th")
            return f"the {target.day}{suffix}", target
        if kind == "month":
            return f"{target.strftime('%B')} {EN_ORD[target.day]}", target
        return f"the {EN_ORD[target.day]}", target
    if kind == "month":
        return f"el {ES_DAY[target.day]} de {ES_MONTH[target.month - 1]}", target
    return f"el {ES_DAY[target.day]}", target


def make_utterance(rng: random.Random, uid: str, speaker: str, group: str) -> dict:
    pieces, pol = rng.choice(TEMPLATES[group])
    call = rng.choice(CALL_DATES)
    segs, gold, style = [], [("confirm", pol)] if pol else [], "none"
    for chunk, lang in pieces:
        for piece in re.split(r"(\{[AD]\})", chunk):
            if piece == "{A}":
                cents = rng.choice(list(AMOUNT_FORMS))
                forms = AMOUNT_FORMS[cents][lang] + AMOUNT_FORMS[cents]["num"]
                form = rng.choice(forms)
                digits = f"${cents // 100:,}"           # how a formatting STT writes it
                segs += [(w, "amt", lang, digits) for w in form.split()]
                gold.append(("amount", cents))
                first = form.split()[0]
                style = ("digits" if first[0] in "$0123456789" else "es-words" if lang == "es"
                         else "shorthand" if number_value(entity_tokens(form)) is not None
                         and "hundred" not in form and "thousand" not in form else "en-words")
            elif piece == "{D}":
                phrase, target = render_date(rng, call, lang)
                segs += [(w, "date", lang, None) for w in phrase.split()]
                gold.append(("date", target))
            else:
                for w in piece.split():
                    role = ("pol" if not segs and w.strip(",") in ("yes", "yeah", "no", "sí", "okay")
                            else "gen")
                    segs.append((w, role, lang, None))
    ref = " ".join(w for w, *_ in segs)
    return {"uid": uid, "speaker": speaker, "group": group, "locale": LOCALE[group],
            "call": call, "ref": ref, "segs": segs, "gold": gold, "style": style,
            "words": [(w, lang) for w, _, lang, _ in segs]}


def inject(rng: random.Random, utt: dict, p: dict, m: float) -> str:
    out, amount_style = [], None
    for w, role, lang, digits in utt["segs"]:
        w = w.strip(",").lower()
        if role == "amt" and amount_style is None:  # decided once per amount
            spoken = w[0] not in "$0123456789"
            amount_style = "digits" if spoken and rng.random() < p["numfmt"] else "as-said"
            if amount_style == "digits":
                out.append(digits)                  # same amount, written as digits
        if role == "amt" and amount_style == "digits":
            continue
        if utt["group"] == "Spanglish" and lang == "es" and rng.random() < p["switch"] * m:
            out.append(ANGLO.get(w, w[:-1] if len(w) > 3 else w))   # language ID stuck on English
            continue
        if role in ("amt", "date"):
            if w[0].isdigit() and rng.random() < p["digit"] * m and len(w) > 1:
                k = rng.randrange(1, len(w))
                if w[k].isdigit():
                    w = w[:k] + str((int(w[k]) + rng.randint(1, 9)) % 10) + w[k + 1:]
            elif w in NUM_CONFUSION and rng.random() < p["date" if role == "date" else "amt"] * m:
                w = NUM_CONFUSION[w]
        elif role == "pol":
            if w in ("yes", "yeah", "sí", "okay") and rng.random() < p["yes"] * m:
                continue
            if w == "no" and rng.random() < p["neg"] * m:
                if rng.random() < 0.7:
                    continue
                w = "yeah" if lang == "en" else "sí"
        elif rng.random() < p["gen"] * m:                 # generic word error
            w = GEN_VARIANT.get(w, w[:-1] if len(w) > 3 else w + "h")
        if w != strip_accents(w) and rng.random() < p["accent"]:
            w = strip_accents(w)                    # many STT outputs drop accents
        out.append(w)
    if rng.random() < p["gen"] * m * 0.2:
        out.append("uh")
    return " ".join(out)


def make_set(rng: random.Random, n_utts: int, n_speakers: int, tag: str) -> list[dict]:
    groups, weights = GLOBAL["language_groups"], [64, 18, 14]   # account preference mix
    speakers = [(f"{tag}-spk{k:03d}", min(4.0, max(0.25, rng.lognormvariate(0, 0.6))),
                 rng.choices(groups, weights)[0]) for k in range(n_speakers)]
    utts = []
    for u in range(n_utts):
        spk, diff, group = speakers[u % n_speakers]
        utt = make_utterance(rng, f"{tag}-u{u:04d}", spk, group)
        utt["hyp"] = {s: inject(rng, utt, p, diff) for s, p in SYSTEMS.items()}
        utts.append(utt)
    return utts


# ---- Speaker-clustered bootstrap -------------------------------------------
def ratio_ci(units: list[tuple[str, int, int]], rng: random.Random, n_boot: int = 1000,
             cluster: bool = True) -> tuple[float, float, float]:
    """units = (cluster id, errors, opportunities). Percentile 95% interval of sum/sum."""
    groups = defaultdict(lambda: [0, 0])
    for i, (cid, e, n) in enumerate(units):
        g = groups[cid if cluster else i]
        g[0] += e
        g[1] += n
    keys = list(groups)
    point = sum(e for e, _ in groups.values()) / sum(n for _, n in groups.values())
    stats = []
    for _ in range(n_boot):
        e = n = 0
        for _k in range(len(keys)):
            ge, gn = groups[keys[rng.randrange(len(keys))]]
            e, n = e + ge, n + gn
        stats.append(e / n if n else 0.0)
    stats.sort()
    return point, stats[int(0.025 * n_boot)], stats[int(0.975 * n_boot) - 1]


def score(utts: list[dict], system: str) -> dict:
    tot = Counter()
    units = defaultdict(list)
    wrong_amount_wer = []                      # utterance WER of every wrong-amount utterance
    for u in utts:
        hyp, grp = u["hyp"][system], u["group"]
        w = wer(u["ref"], hyp)
        tot["edits"] += w["S"] + w["D"] + w["I"]
        tot["words"] += w["N"]
        tot[grp + "_edits"] += w["S"] + w["D"] + w["I"]
        tot[grp + "_words"] += w["N"]
        ce, cn = cer_counts(u["ref"], hyp)
        tot["cedits"], tot["chars"] = tot["cedits"] + ce, tot["chars"] + cn
        got = extract(hyp, u["call"], u["locale"])
        for kind in ("amount", "date", "confirm"):
            g, miss, hall = entity_counts(u["gold"], got, kind)
            tot[kind + "_gold"] += g
            tot[kind + "_miss"] += miss
            tot[kind + "_hall"] += hall
            if g:
                units[kind].append((u["speaker"], miss, g))
            if kind == "amount":
                tot[grp + "_amount_gold"] += g
                tot[grp + "_amount_miss"] += miss
                if miss:
                    wrong_amount_wer.append(w["wer"])
        gp = dict(u["gold"]).get("confirm")
        hp = dict(got).get("confirm")
        if gp and hp and gp != hp:
            tot["flips"] += 1
        if grp == "Spanglish":
            e, n = switch_word_counts(u["words"], hyp, "es")
            tot["switch_err"], tot["switch_n"] = tot["switch_err"] + e, tot["switch_n"] + n
            e, n = switch_word_counts(u["words"], hyp, "en")
            tot["other_err"], tot["other_n"] = tot["other_err"] + e, tot["other_n"] + n
    return {"tot": tot, "units": units, "wrong_amount_wer": wrong_amount_wer}


# ---- The report ------------------------------------------------------------
def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def run_global(world: dict) -> None:
    print(world["lender"])
    print(f"dataset {world['dataset']}; scorer policy nfc+fold ({SCORER_VERSION})")

    # Step 1: canonicalization checks
    print("\n== 1. Canonicalization ==")
    for form, loc in world["usd_1500_forms"]:
        cents = canon_amount(form, loc)
        print(f"  {form:<26} {loc:<6} -> {cents} cents")
        assert cents == 150_000, form
    mx = canon_amount("1.500", "es-MX")
    print(f"  {'1.500':<26} {'es-MX':<6} -> {mx} cents  (period decimal: one dollar fifty)")
    assert mx == 150
    wg7 = {"two fifty": 25000, "two hundred fifty": 25000, "$250": 25000,
           "doscientos cincuenta": 25000, "two fifteen": 21500, "four twenty-five": 42500,
           "cuatrocientos veinticinco dólares": 42500, "a hundred twenty thousand": 12_000_000,
           "ciento veinte mil": 12_000_000}
    for form, want in wg7.items():
        assert canon_amount(form) == want, (form, canon_amount(form))
    print(f"  {len(wg7)} more amount forms match; two fifteen -> {canon_amount('two fifteen')}")
    call = dt.date(2026, 11, 14)                       # T01's call date, a Saturday
    dates = [("the twentieth", "en-US", "2026-11-20"), ("November twentieth", "en-US", "2026-11-20"),
             ("el veinte de noviembre", "es-US", "2026-11-20"), ("next Friday", "en-US", "2026-11-20"),
             ("el viernes", "es-US", "2026-11-20"), ("the fifth", "en-US", "2026-12-05"),
             ("12/03", "en-US", "2026-12-03"), ("12/03", "es-US", "2027-03-12")]
    for phrase, loc, want in dates:
        got = [v for k, v in extract(phrase, call, loc) if k == "date"]
        print(f"  {phrase:<26} {loc:<6} -> {got[0].isoformat()}  (call date {call})")
        assert got[0].isoformat() == want, phrase

    # Step 2: the T01 pair
    print("\n== 2. T01: one substituted word ==")
    ref = "yeah I can do two fifty on the twentieth, rest next month"
    hyp = "yeah I can do two fifteen on the twentieth rest next month"
    w = wer(ref, hyp)
    g, miss, _ = entity_counts(extract(ref, call), extract(hyp, call), "amount")
    print(f"  WER {w['S'] + w['D'] + w['I']}/{w['N']} = {w['wer']:.3f}  (S={w['S']} D={w['D']} I={w['I']})")
    print(f"  amount entity errors {miss}/{g}: gold {extract(ref, call)[1][1]} cents, "
          f"STT {extract(hyp, call)[1][1]} cents")
    print(f"  raw policy (no punctuation strip): WER {wer(ref, hyp, 'raw')['wer']:.3f}")
    assert (w["S"] + w["D"] + w["I"], w["N"]) == (1, 12) and round(w["wer"], 3) == 0.083
    assert (miss, g) == (1, 1)

    # Step 3: synthetic sets
    rng = random.Random(SEED)
    small = make_set(rng, 400, 60, "s")
    gold7 = make_set(rng, 1200, 180, "g")
    for s in (small, gold7):                       # the canonicalizer agrees with the generator
        for u in s:
            got = extract(u["ref"], u["call"], u["locale"])
            assert sorted(got, key=repr) == sorted(u["gold"], key=repr), u["ref"]
    print("\n== 3. Bake-off on the 1,200-utterance set (180 speakers) ==")
    print("  extract(reference) == generator gold on all 1,600 utterances")
    boot = random.Random(SEED + 1)
    res = {s: score(gold7, s) for s in SYSTEMS}
    print("  entity error rate = gold entities not recovered exactly / gold entities")
    print(f"  {'sys':<4}{'WER':>7}{'CER':>7}  {'amount, 95% CI':<24}{'date, 95% CI':<24}{'flips':>5}")
    for s, r in res.items():
        t = r["tot"]
        a = ratio_ci(r["units"]["amount"], boot)
        d = ratio_ci(r["units"]["date"], boot)
        print(f"  {s:<4}{pct(t['edits'] / t['words']):>7}{pct(t['cedits'] / t['chars']):>7}  "
              f"{pct(a[0]) + ' [' + pct(a[1]) + ', ' + pct(a[2]) + ']':<24}"
              f"{pct(d[0]) + ' [' + pct(d[1]) + ', ' + pct(d[2]) + ']':<24}{t['flips']:>5}")
        r["amount"] = a[0]
        r["wer"] = t["edits"] / t["words"]
    assert res["B"]["wer"] < res["A"]["wer"] and res["B"]["amount"] > res["A"]["amount"]
    for s, r in res.items():
        t = r["tot"]
        ws = r["wrong_amount_wer"]
        print(f"  {s}: amounts {t['amount_gold']} gold, {t['amount_miss']} missed, "
              f"{t['amount_hall']} hallucinated; {len(ws)} utterances with a wrong amount, "
              f"{sum(x < 0.10 for x in ws)} of them at WER under 10%, "
              f"{sum(x < 0.20 for x in ws)} under 20%")
    print("  by language group:")
    print(f"    {'group':<18}{'utts':>5}{'WER A':>8}{'WER B':>8}{'amount A':>10}{'amount B':>10}")
    for grp in world["language_groups"]:
        ta, tb = res["A"]["tot"], res["B"]["tot"]
        n_utts = sum(u["group"] == grp for u in gold7)
        print(f"    {grp:<18}{n_utts:>5}{pct(ta[grp + '_edits'] / ta[grp + '_words']):>8}"
              f"{pct(tb[grp + '_edits'] / tb[grp + '_words']):>8}"
              f"{pct(ta[grp + '_amount_miss'] / ta[grp + '_amount_gold']):>10}"
              f"{pct(tb[grp + '_amount_miss'] / tb[grp + '_amount_gold']):>10}")
    print("  Spanglish, errors on the Spanish words only (PIER-style) and on the English words:")
    for s, r in res.items():
        t = r["tot"]
        print(f"    {s}: Spanish words {t['switch_err']}/{t['switch_n']} = "
              f"{pct(t['switch_err'] / t['switch_n'])}; English words {t['other_err']}/"
              f"{t['other_n']} = {pct(t['other_err'] / t['other_n'])}")
    ta, tb = res["A"]["tot"], res["B"]["tot"]
    assert tb["switch_err"] / tb["switch_n"] > ta["switch_err"] / ta["switch_n"]
    print("  system B, amount entity error rate by surface form:")
    by_style = defaultdict(lambda: [0, 0])
    for u in gold7:
        g, miss, _ = entity_counts(u["gold"], extract(u["hyp"]["B"], u["call"], u["locale"]),
                                   "amount")
        by_style[u["style"]][0] += miss
        by_style[u["style"]][1] += g
    for style in ("shorthand", "en-words", "es-words", "digits"):
        e, n = by_style[style]
        print(f"    {style:<9} {e:>3}/{n:<4} = {pct(e / n)}")

    # Step 4: interval width by set size
    print("\n== 4. 95% interval width, system B amount entity error rate ==")
    widths = {}
    for name, s in (("400 utterances / 60 speakers", small), ("1,200 / 180", gold7)):
        units = score(s, "B")["units"]["amount"]
        p, lo, hi = ratio_ci(units, boot)
        _, ulo, uhi = ratio_ci(units, boot, cluster=False)
        widths[name] = (hi - lo, uhi - ulo)
        print(f"  {name:<29} {pct(p)}  speaker-clustered [{pct(lo)}, {pct(hi)}] "
              f"width {100 * (hi - lo):.1f} pts; utterance-level width {100 * (uhi - ulo):.1f} pts")
    (w400, u400), (w1200, u1200) = widths.values()
    assert w1200 < w400

    # Step 5: the scorer policy moves WER, not entities
    print("\n== 5. Same hypotheses, five scoring policies (1,200 set) ==")
    print(f"  {'policy':<22}{'WER A':>8}{'WER B':>8}{'amount B':>10}")
    for pol in list(POLICIES) + ["nfc+fold+num"]:
        row = []
        for s in SYSTEMS:
            e = n = 0
            for u in gold7:
                x = wer(u["ref"], u["hyp"][s], pol.replace("+num", ""), pol.endswith("+num"))
                e, n = e + x["S"] + x["D"] + x["I"], n + x["N"]
            row.append(e / n)
        print(f"  {pol:<22}{pct(row[0]):>8}{pct(row[1]):>8}{pct(res['B']['amount']):>10}")

    print("\n  T08 first turn (call date 2026-11-16)")
    t08_call = dt.date(2026, 11, 16)
    t08_ref = "sí, pero my paycheck comes el viernes, so after that I can pay, like the twenty-third"
    t08 = {"STT as logged": "see pedro my paycheck comes el bee air ness so after that I can pay "
                            "like the twenty third",
           "formatted style": "si pero my paycheck comes el viernes so after that I can pay "
                              "like the 23rd"}
    for label, h in t08.items():
        cells = "  ".join(f"{p} {pct(wer(t08_ref, h, p)['wer'])}" for p in POLICIES)
        print(f"  {label:<16} {cells}  nfc+fold+num {pct(wer(t08_ref, h, numerals=True)['wer'])}")
    gold_t08, hyp_t08 = extract(t08_ref, t08_call, "es-US"), extract(t08["STT as logged"], t08_call)
    for kind in ("date", "confirm"):
        g, miss, _ = entity_counts(gold_t08, hyp_t08, kind)
        print(f"  STT as logged, {kind}: {g - miss}/{g} recovered")
    t08_words = [(w, "es") for w in "sí, pero".split()] + [(w, "en") for w in "my paycheck comes".split()] \
        + [(w, "es") for w in "el viernes,".split()] \
        + [(w, "en") for w in "so after that I can pay, like the twenty-third".split()]
    e_es, n_es = switch_word_counts(t08_words, t08["STT as logged"], "es")
    e_en, n_en = switch_word_counts(t08_words, t08["STT as logged"], "en")
    print(f"  STT as logged, Spanish words {e_es}/{n_es} wrong, English words {e_en}/{n_en} wrong")
    assert (e_es, n_es, e_en) == (3, 4, 0)

    print("\n  Locale fixture: Spanish references with accents, hypotheses in other styles")
    fixture = [("sí, pagué mil quinientos dólares", "si pague 1,500 dolares"),
               ("quince dólares", "15 dolares"),
               ("el doce de marzo", "el 12 de marzo"),
               ("son doscientos cincuenta", "son doscientos quince")]
    fx_wer = {}
    for pol in list(POLICIES) + ["nfc+fold+num"]:
        e = n = 0
        for r, h in fixture:
            x = wer(r, h, pol.replace("+num", ""), pol.endswith("+num"))
            e, n = e + x["S"] + x["D"] + x["I"], n + x["N"]
        fx_wer[pol] = e / n
    g = miss = 0
    for r, h in fixture:
        a, b, _ = entity_counts(extract(r, call, "es-US"), extract(h, call, "es-US"), "amount")
        g, miss = g + a, miss + b
    print("  " + "  ".join(f"{p} {pct(v)}" for p, v in fx_wer.items()))
    quince = {p: wer("quince dólares", "15 dolares", p.replace("+num", ""), p.endswith("+num"))["wer"]
              for p in ("whisper-basic", "nfc+fold+num")}
    print(f"  'quince dólares' vs '15 dolares': whisper-basic {pct(quince['whisper-basic'])}, "
          f"nfc+fold+num {pct(quince['nfc+fold+num'])}")
    print(f"  amount entity errors {miss}/{g} under every policy (entities are canonicalized first)")
    assert quince["whisper-basic"] > 0 and quince["nfc+fold+num"] == 0
    assert fx_wer["nfc+fold+num"] < fx_wer["whisper-basic"] and (miss, g) == (1, 3)
    print("\nAll assertions passed.")


EDITIONS["global"] = (GLOBAL, run_global)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Entity error rate for spoken amounts and dates.")
    ap.add_argument("--edition", choices=["global", "india"], default="global",
                    help="which fictional lender's data to run (default: global)")
    args = ap.parse_args(argv)
    if args.edition not in EDITIONS:
        ap.error("this copy has no India edition block; use the full file from the course repository")
    world, run = EDITIONS[args.edition]
    run(world)


# ==== India edition (Tarazu Finance, Hinglish). Not shown on the global recipe page. ====
# ---- TARAZU constants (copied from the course world bible, world-v1.1) ----
TARAZU = {
    "lender": "Tarazu Finance Ltd (fictional; numbers are illustrative)",
    "dataset": "tarazu-calls (synthetic, seed 20261120)",
    "products": {"TW": "Two-wheeler loan", "PL": "Personal loan, digital",
                 "CD": "Consumer durable EMI", "SBL": "Small business loan",
                 "MFI": "Microfinance (joint liability group)"},
    "campaigns": {"TW-early-nov": "TW", "PL-digital-nov": "PL", "CD-short-nov": "CD",
                  "SBL-guar-nov": "SBL", "MFI-fort-nov": "MFI"},
    "calling_window_local": {"default": ("08:00", "19:00"), "MFI": ("09:00", "18:00")},
    "grievance_officer": {"name": "Ms Neha Kulkarni", "email": "grievance@tarazu.example",
                          "phone": "020-4000-0000",
                          "address": "Tarazu House, Baner Road, Pune 411045"},
    "versions": {"stt": "vendorA-2026-10", "gold": "gold-v7", "taxonomy": "tz-fail-v4"},
    "money_unit": "integer paise in tools and the CRM; rupees in speech",
    "fractions": {"sava": "1.25", "dedh": "1.5", "dhai": "2.5",
                  "paune X": "X - 0.25", "saade X": "X + 0.5"},
    "rs_1_50_000_forms": ["dedh lakh", "1.5 lakh", "1,50,000", "150000", "150,000",
                          "ek lakh pachaas hazaar", "one lakh fifty thousand",
                          "१,५०,०००"],  # Devanagari digits
    "date_policy": "ISO date resolved against the call date; numeric d/m is read dmy",
}


def run_india(world: dict) -> None:
    """The India edition of this recipe, unchanged: Hinglish amounts in paise, T-WER."""
    SEED = 20261120

    # ---- Lexicons --------------------------------------------------------------
    HI_NUM = {"ek": 1, "do": 2, "teen": 3, "chaar": 4, "char": 4, "paanch": 5, "panch": 5,
              "chheh": 6, "chhe": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
              "gyaarah": 11, "baarah": 12, "terah": 13, "chaudah": 14, "pandrah": 15,
              "solah": 16, "satrah": 17, "athaarah": 18, "unnees": 19, "bees": 20,
              "ikkees": 21, "baais": 22, "teis": 23, "chaubees": 24, "pachchees": 25,
              "chhabbees": 26, "sattaees": 27, "athaais": 28, "untees": 29, "tees": 30,
              "iktees": 31, "chaalis": 40, "pachaas": 50, "saath": 60, "sattar": 70,
              "assi": 80, "nabbe": 90}
    EN_NUM = {w: i for i, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen "
        "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
    EN_NUM.update({"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
                   "seventy": 70, "eighty": 80, "ninety": 90})
    MULT = {"sau": 100, "hundred": 100, "hazaar": 1000, "hazar": 1000, "thousand": 1000,
            "lakh": 100_000, "lac": 100_000, "crore": 10_000_000, "karod": 10_000_000}
    FRAC = {"sava": Fraction(5, 4), "dedh": Fraction(3, 2), "dhai": Fraction(5, 2)}
    MOD = {"paune": Fraction(-1, 4), "saade": Fraction(1, 2)}
    ORDINAL = {w: i + 1 for i, w in enumerate(
        "first second third fourth fifth sixth seventh eighth ninth tenth eleventh "
        "twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth "
        "nineteenth twentieth".split())}
    ORDINAL["thirtieth"] = 30
    WEEKDAY = {"somvaar": 0, "mangalvaar": 1, "budhvaar": 2, "guruvaar": 3, "veervaar": 3,
               "shukravaar": 4, "shanivaar": 5, "ravivaar": 6, "monday": 0, "tuesday": 1,
               "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
    MONTH = {m: i + 1 for i, m in enumerate(
        "january february march april may june july august september october "
        "november december".split())}
    RELATIVE = {"aaj": 0, "kal": 1, "parson": 2, "tomorrow": 1}
    RUPEE = {"rs", "rupaye", "rupay", "rupees", "rupee"}
    DAY_MARK = {"tarikh", "tareekh", "taarikh"}
    YES, NO, BACKCHANNEL = {"haan", "haanji", "ji", "ha"}, {"nahi", "nahin", "na"}, {"hmm", "accha"}
    DEVA_DIGITS = str.maketrans("०१२३४५६७८९",
                                "0123456789")

    # T-WER style transliteration mapping, versioned: Devanagari token -> Tarazu's
    # code-mix reference convention (Hindi in Roman, English in Latin).
    TRANSLIT_VERSION = "tarazu-translit-v1"
    TRANSLIT = {unicodedata.normalize("NFC", k): v for k, v in {
        "हाँ": "haan", "हां": "haan", "नहीं": "nahi", "नही": "nahi", "मैं": "main",
        "मेरी": "meri", "है": "hai", "को": "ko", "तो": "toh", "आती": "aati",
        "तारीख": "tarikh", "बाकी": "baaki", "दूँगा": "dunga", "दूंगा": "dunga",
        "अभी": "abhi", "रुपये": "rupaye", "रूपये": "rupaye", "दो": "do", "पाँच": "paanch",
        "पांच": "paanch", "बीस": "bees", "ढाई": "dhai", "डेढ़": "dedh", "डेढ": "dedh",
        "हज़ार": "hazaar", "हजार": "hazaar", "लाख": "lakh", "सैलरी": "salary",
        "पेमेंट": "payment", "लिंक": "link", "नेक्स्ट": "next", "मंथ": "month",
        "ऑलरेडी": "already", "पे": "pay",
    }.items()}
    DEVA_OF = {}
    for _k, _v in TRANSLIT.items():
        DEVA_OF.setdefault(_v, _k)          # reverse map, used by the script-swap injector


    # ---- Canonicalization ------------------------------------------------------
    def entity_tokens(text: str) -> list[str]:
        s = unicodedata.normalize("NFC", text).lower().translate(DEVA_DIGITS)
        toks = [t.strip(",.?!;:\"'()") for t in s.split()]
        return [TRANSLIT.get(t, t) for t in toks if t]


    def _numeric(t: str) -> Fraction | None:
        t = t.replace(",", "")
        return Fraction(t) if re.fullmatch(r"\d+(\.\d+)?", t) else None


    def _is_num_token(t: str) -> bool:
        return (_numeric(t) is not None or t in HI_NUM or t in EN_NUM or t in MULT
                or t in FRAC or t in MOD)


    def _run_end(tokens: list[str], i: int) -> int:
        j = i
        while j < len(tokens) and _is_num_token(tokens[j]):
            j += 1
        return j


    def _ordinal(t: str) -> int | None:
        m = re.fullmatch(r"(\d{1,2})(st|nd|rd|th)", t)
        return int(m.group(1)) if m else ORDINAL.get(t)


    def _fmt(v: Fraction) -> str:
        return str(v.numerator) if v.denominator == 1 else str(float(v))


    def number_value(tokens: list[str]) -> Fraction | None:
        """Indian-system parse: sau multiplies the current group; hazaar/lakh/crore close it."""
        total, cur, seen, mod = Fraction(0), Fraction(0), False, None
        for t in tokens:
            if t in MOD:
                mod = MOD[t]
                continue
            if t in MULT:
                m = MULT[t]
                if m == 100:
                    cur = (cur or 1) * 100
                else:
                    total += (cur or 1) * m
                    cur = Fraction(0)
                seen = True
                continue
            v = _numeric(t)
            if v is None:
                v = HI_NUM.get(t, EN_NUM.get(t, FRAC.get(t)))
            if v is None:
                return None
            if mod is not None:
                v, mod = v + mod, None
            cur += v
            seen = True
        if mod is not None or not seen:
            return None
        return total + cur


    def canon_amount(text: str) -> int | None:
        """Spoken or written amount -> integer paise, or None."""
        toks = [t for t in entity_tokens(text) if t not in RUPEE]
        return _paise(number_value(toks)) if toks and _run_end(toks, 0) == len(toks) else None


    def _paise(rupees: Fraction | None) -> int | None:
        return None if rupees is None or (rupees * 100).denominator != 1 else int(rupees * 100)


    def resolve_day(day, call_date: dt.date) -> dt.date | None:
        if day is None or Fraction(day).denominator != 1 or not 1 <= day <= 31:
            return None
        y, m = call_date.year, call_date.month
        for _ in range(3):
            try:
                d = dt.date(y, m, int(day))
                if d >= call_date:
                    return d
            except ValueError:
                pass
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        return None


    def resolve_day_month(day, month: int, call_date: dt.date) -> dt.date | None:
        try:
            d = dt.date(call_date.year, month, int(day))
        except (ValueError, TypeError):
            return None
        return d if d >= call_date else d.replace(year=d.year + 1)


    def resolve_weekday(wd: int, call_date: dt.date) -> dt.date:
        """Policy: 'agle mangalvaar' is the first Tuesday strictly after the call date."""
        return call_date + dt.timedelta(days=(wd - call_date.weekday()) % 7 or 7)


    def extract(text: str, call_date: dt.date) -> list[tuple[str, object]]:
        """All amount, date and confirmation entities in one utterance, canonicalized."""
        toks, out, i = entity_tokens(text), [], 0
        if toks:
            if toks[:2] == ["haan", "haan"] or toks[0] in BACKCHANNEL:
                pass                                    # a backchannel is never a yes
            elif toks[0] in YES:
                out.append(("confirm", "yes"))
            elif toks[0] in NO:
                out.append(("confirm", "no"))
        while i < len(toks):
            t = toks[i]
            nxt = toks[i + 1] if i + 1 < len(toks) else ""
            if t in ("agle", "next") and nxt in WEEKDAY:
                out.append(("date", resolve_weekday(WEEKDAY[nxt], call_date)))
                i += 2
            elif t in RELATIVE:
                out.append(("date", call_date + dt.timedelta(days=RELATIVE[t])))
                i += 1
            elif re.fullmatch(r"\d{1,2}/\d{1,2}", t):           # explicit dmy policy
                d, m = map(int, t.split("/"))
                out.append(("date", resolve_day_month(d, m, call_date) if 1 <= m <= 12 else None))
                i += 1
            elif _ordinal(t):
                out.append(("date", resolve_day(_ordinal(t), call_date)))
                i += 1
            elif _is_num_token(t):
                j = _run_end(toks, i)
                run, after = toks[i:j], toks[j] if j < len(toks) else ""
                mults = [k for k, x in enumerate(run) if x in MULT]
                if mults and (after in DAY_MARK or after in MONTH):
                    # Policy: in "dedh lakh bees tarikh" the words after the last
                    # multiplier are the day; the rest is the amount.
                    out.append(("amount", _paise(number_value(run[:mults[-1] + 1]))))
                    run, mults = run[mults[-1] + 1:], []
                val = number_value(run) if run else None
                if after in DAY_MARK:
                    out.append(("date", resolve_day(val, call_date)))
                elif after in MONTH:
                    out.append(("date", resolve_day_month(val, MONTH[after], call_date)))
                elif after == "ko" and not mults and val is not None and val <= 31:
                    out.append(("date", resolve_day(val, call_date)))
                elif val is not None and (mults or after in RUPEE or
                                          (_numeric(run[0]) is not None and val >= 100)):
                    out.append(("amount", _paise(val)))
                i = j
            else:
                i += 1
        return out


    def entity_counts(gold: list, hyp: list, kind: str) -> tuple[int, int, int]:
        """Exact match after canonicalization. Returns (gold, missed, hallucinated)."""
        g = Counter(v for k, v in gold if k == kind)
        h = Counter(v for k, v in hyp if k == kind)
        hit = sum((g & h).values())
        return sum(g.values()), sum(g.values()) - hit, sum(h.values()) - hit


    # ---- Scoring policies (the normalizer is part of the metric) ---------------
    def _join_digit_groups(s: str) -> str:
        return re.sub(r"(?<=\d),(?=\d)", "", s)


    def norm_raw(s: str) -> list[str]:
        return s.split()


    def norm_whisper_basic(s: str) -> list[str]:
        """Mirror of Whisper's BasicTextNormalizer: marks (M*) become spaces, so matras go."""
        s = s.lower()
        s = re.sub(r"[<\[][^>\]]*[>\]]", "", s)
        s = re.sub(r"\(([^)]+?)\)", "", s)
        s = "".join(" " if unicodedata.category(c)[0] in "MSP" else c
                    for c in unicodedata.normalize("NFKC", s))
        return s.split()


    def norm_nfc(s: str) -> list[str]:
        """NFC, lowercase, punctuation and symbols to spaces, combining marks kept."""
        s = _join_digit_groups(unicodedata.normalize("NFC", s).lower())
        s = re.sub(r"(?<=\d)\.(?=\d)", "\x00", s)            # keep decimal points
        s = "".join(" " if unicodedata.category(c)[0] in "PS" else c for c in s)
        return s.replace("\x00", ".").split()


    def norm_nfc_twer(s: str) -> list[str]:
        return [TRANSLIT.get(t, t) for t in norm_nfc(s)]


    def with_numerals(tokens: list[str]) -> list[str]:
        """Numeral canonicalization on top of any policy: a number run becomes its value."""
        out, i = [], 0
        while i < len(tokens):
            j = _run_end(tokens, i)
            if j > i:
                v = number_value(tokens[i:j])
                out.append(_fmt(v) if v is not None else " ".join(tokens[i:j]))
                i = j
            elif _ordinal(tokens[i]):
                out.append(str(_ordinal(tokens[i])))
                i += 1
            else:
                out.append(tokens[i])
                i += 1
        return out


    POLICIES = {"raw": norm_raw, "whisper-basic": norm_whisper_basic,
                "nfc-only": norm_nfc, "nfc+t-wer": norm_nfc_twer}


    # ---- WER and CER -----------------------------------------------------------
    def align(ref: list, hyp: list) -> tuple[int, int, int]:
        """Levenshtein alignment; returns (substitutions, deletions, insertions)."""
        n, m = len(ref), len(hyp)
        d = [[(0, 0, 0, 0)] * (m + 1) for _ in range(n + 1)]   # (cost, S, D, I)
        for i in range(1, n + 1):
            d[i][0] = (i, 0, i, 0)
        for j in range(1, m + 1):
            d[0][j] = (j, 0, 0, j)
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                c, s, de, ins = d[i - 1][j - 1]
                best = (c, s, de, ins) if ref[i - 1] == hyp[j - 1] else (c + 1, s + 1, de, ins)
                c, s, de, ins = d[i - 1][j]
                best = min(best, (c + 1, s, de + 1, ins))
                c, s, de, ins = d[i][j - 1]
                best = min(best, (c + 1, s, de, ins + 1))
                d[i][j] = best
        return d[n][m][1:]


    def wer(ref: str, hyp: str, policy: str = "nfc+t-wer", numerals: bool = False):
        r, h = POLICIES[policy](ref), POLICIES[policy](hyp)
        if numerals:
            r, h = with_numerals(r), with_numerals(h)
        s, de, ins = align(r, h)
        return {"S": s, "D": de, "I": ins, "N": len(r), "wer": (s + de + ins) / max(len(r), 1)}


    def cer_counts(ref: str, hyp: str) -> tuple[int, int]:
        r, h = " ".join(norm_nfc_twer(ref)), " ".join(norm_nfc_twer(hyp))
        return sum(align(list(r), list(h))), len(r)


    # ---- Synthetic data: templates plus seeded error injection -----------------
    AMOUNT_FORMS = {   # paise -> spoken surface forms (W7 canonical values)
        250000: ["dhai hazaar", "do hazaar paanch sau", "2,500", "2500"],
        425000: ["chaar hazaar do sau pachaas", "4,250"],
        130000: ["ek hazaar teen sau", "terah sau", "1,300"],
        350000: ["saade teen hazaar", "teen hazaar paanch sau", "3,500"],
        150000: ["dedh hazaar", "pandrah sau", "1,500"],
        680000: ["chheh hazaar aath sau", "6,800"],
        12500000: ["sava lakh", "1,25,000"],
        15000000: ["dedh lakh", "1.5 lakh", "1,50,000", "ek lakh pachaas hazaar",
                   "one lakh fifty thousand"],
        17500000: ["paune do lakh", "1,75,000"],
    }
    DAY_WORD = {v: k for k, v in HI_NUM.items() if v <= 31 and k not in ("char", "panch", "chhe")}
    WEEKDAY_HI = ["somvaar", "mangalvaar", "budhvaar", "guruvaar", "shukravaar", "shanivaar"]
    TEMPLATES = [   # (text, confirmation polarity of the opening word)
        ("haan main {A} de dunga {D} ko", "yes"),
        ("haan main {A} de dunga {D} ko, baaki next month", "yes"),
        ("dekhiye abhi mere paas sirf {A} hai, {D} ko baaki bhar dunga", None),
        ("{D} tak {A} bhar dungi", None),
        ("abhi {A} hi de sakta hoon, baaki {D} ko", None),
        ("theek hai, {D} ko payment kar dunga", None),
        ("maine {A} already pay kar diya tha", None),
        ("{A} ka link bhej do", None),
        ("nahi nahi, {A} bola tha maine", "no"),
        ("salary ke baad, {K}", None),
        ("haan, but meri salary {K} aati hai, toh after that I can pay", "yes"),
        ("haan ji", "yes"), ("nahi", "no"), ("haan sahi hai", "yes"), ("nahi, galat hai", "no"),
    ]
    NUM_CONFUSION = {"dhai": "do", "dedh": "der", "paune": "pune", "saade": "saare",
                     "sava": "sau", "pachaas": "pachchees", "teen": "tees", "bees": "tees",
                     "aath": "saath", "sau": "so", "do": "dus", "fifty": "fifteen",
                     "mangalvaar": "mangal", "december": "november"}
    GEN_VARIANT = {"main": "mein", "hai": "he", "dunga": "doonga", "dungi": "doongi",
                   "kar": "car", "toh": "to", "baaki": "baki", "theek": "thik", "diya": "dia",
                   "hoon": "hun", "maine": "mainey", "tak": "tuk", "abhi": "abi",
                   "sakta": "sakte", "bhej": "bhaj", "meri": "mary", "aati": "aate"}
    CALL_DATES = [dt.date(2026, 11, d) for d in range(9, 20) if dt.date(2026, 11, d).weekday() != 6]
    SYSTEMS = {   # per-token error probabilities, scaled by a per-speaker difficulty
        "A": {"gen": 0.15, "amt": 0.012, "digit": 0.004, "date": 0.015, "neg": 0.03,
              "haan": 0.04, "script": 0.03},
        "B": {"gen": 0.10, "amt": 0.050, "digit": 0.012, "date": 0.025, "neg": 0.07,
              "haan": 0.07, "script": 0.06},
    }


    def render_date(rng: random.Random, call: dt.date) -> tuple[str, dt.date]:
        kind = rng.choices(["tarikh", "month", "weekday", "kal"], [5, 2, 2, 1])[0]
        if kind == "weekday":
            wd = rng.randrange(6)
            return f"agle {WEEKDAY_HI[wd]}", resolve_weekday(wd, call)
        if kind == "kal":
            return "kal", call + dt.timedelta(days=1)
        target = call + dt.timedelta(days=rng.randint(1, 25))
        day = DAY_WORD[target.day] if rng.random() < 0.7 else str(target.day)
        if kind == "month":
            return f"{day} {target.strftime('%B').lower()}", target
        return f"{day} tarikh", target


    def make_utterance(rng: random.Random, uid: str, speaker: str) -> dict:
        text, pol = rng.choice(TEMPLATES)
        call = rng.choice(CALL_DATES)
        segs, gold, style = [], [("confirm", pol)] if pol else [], "none"
        for piece in re.split(r"(\{[ADK]\})", text):
            if piece == "{A}":
                paise = rng.choice(list(AMOUNT_FORMS))
                form = rng.choice(AMOUNT_FORMS[paise])
                segs += [(w, "amt") for w in form.split()]
                gold.append(("amount", paise))
                style = ("fraction" if any(w in FRAC or w in MOD for w in form.split())
                         else "digits" if form[0].isdigit() else "words")
            elif piece in ("{D}", "{K}"):
                if piece == "{D}":
                    phrase, target = render_date(rng, call)
                else:
                    target = call + dt.timedelta(days=rng.randint(1, 25))
                    phrase = f"{target.day} ko"
                segs += [(w, "date") for w in phrase.split()]
                gold.append(("date", target))
            else:
                for w in piece.split():
                    role = "pol" if not segs and w.strip(",") in ("haan", "nahi") else "gen"
                    segs.append((w, role))
        ref = " ".join(w for w, _ in segs)
        return {"uid": uid, "speaker": speaker, "call": call, "ref": ref, "segs": segs,
                "gold": gold, "style": style}


    def inject(rng: random.Random, segs: list, p: dict, m: float) -> str:
        out = []
        for w, role in segs:
            w = w.strip(",").lower()
            if role in ("amt", "date"):
                if w[0].isdigit() and rng.random() < p["digit"] * m and len(w) > 1:
                    k = rng.randrange(1, len(w))
                    if w[k].isdigit():
                        w = w[:k] + str((int(w[k]) + rng.randint(1, 9)) % 10) + w[k + 1:]
                elif w in NUM_CONFUSION and rng.random() < p["date" if role == "date" else "amt"] * m:
                    w = NUM_CONFUSION[w]
            elif role == "pol":
                if w == "haan" and rng.random() < p["haan"] * m:
                    continue
                if w == "nahi" and rng.random() < p["neg"] * m:
                    if rng.random() < 0.7:
                        continue
                    w = "haan"
            elif rng.random() < p["gen"] * m:                 # generic word error
                w = GEN_VARIANT.get(w, w[:-1] if len(w) > 3 else w + "h")
            elif rng.random() < p["script"] * m and w in DEVA_OF:
                w = DEVA_OF[w]
            out.append(w)
        if rng.random() < p["gen"] * m * 0.2:
            out.append("na")
        return " ".join(out)


    def make_set(rng: random.Random, n_utts: int, n_speakers: int, tag: str) -> list[dict]:
        speakers = [(f"{tag}-spk{k:03d}", min(4.0, max(0.25, rng.lognormvariate(0, 0.6))))
                    for k in range(n_speakers)]
        utts = []
        for u in range(n_utts):
            spk, diff = speakers[u % n_speakers]
            utt = make_utterance(rng, f"{tag}-u{u:04d}", spk)
            utt["hyp"] = {s: inject(rng, utt["segs"], p, diff) for s, p in SYSTEMS.items()}
            utts.append(utt)
        return utts


    # ---- Speaker-clustered bootstrap -------------------------------------------
    def ratio_ci(units: list[tuple[str, int, int]], rng: random.Random, n_boot: int = 1000,
                 cluster: bool = True) -> tuple[float, float, float]:
        """units = (cluster id, errors, opportunities). Percentile 95% interval of sum/sum."""
        groups = defaultdict(lambda: [0, 0])
        for i, (cid, e, n) in enumerate(units):
            g = groups[cid if cluster else i]
            g[0] += e
            g[1] += n
        keys = list(groups)
        point = sum(e for e, _ in groups.values()) / sum(n for _, n in groups.values())
        stats = []
        for _ in range(n_boot):
            e = n = 0
            for _k in range(len(keys)):
                ge, gn = groups[keys[rng.randrange(len(keys))]]
                e, n = e + ge, n + gn
            stats.append(e / n if n else 0.0)
        stats.sort()
        return point, stats[int(0.025 * n_boot)], stats[int(0.975 * n_boot) - 1]


    def score(utts: list[dict], system: str) -> dict:
        tot = Counter()
        units = defaultdict(list)
        wrong_amount_wer = []                      # utterance WER of every wrong-amount utterance
        for u in utts:
            hyp = u["hyp"][system]
            w = wer(u["ref"], hyp)
            tot["edits"] += w["S"] + w["D"] + w["I"]
            tot["words"] += w["N"]
            ce, cn = cer_counts(u["ref"], hyp)
            tot["cedits"], tot["chars"] = tot["cedits"] + ce, tot["chars"] + cn
            got = extract(hyp, u["call"])
            for kind in ("amount", "date", "confirm"):
                g, miss, hall = entity_counts(u["gold"], got, kind)
                tot[kind + "_gold"] += g
                tot[kind + "_miss"] += miss
                tot[kind + "_hall"] += hall
                if g:
                    units[kind].append((u["speaker"], miss, g))
                if kind == "amount" and miss:
                    wrong_amount_wer.append(w["wer"])
            gp = dict(u["gold"]).get("confirm")
            hp = dict(got).get("confirm")
            if gp and hp and gp != hp:
                tot["flips"] += 1
        return {"tot": tot, "units": units, "wrong_amount_wer": wrong_amount_wer}


    # ---- The report ------------------------------------------------------------
    def pct(x: float) -> str:
        return f"{100 * x:.1f}%"


    def main() -> None:
        print(TARAZU["lender"])
        print(f"dataset {TARAZU['dataset']}; scorer policy nfc+t-wer ({TRANSLIT_VERSION})")

        # Step 1: canonicalization checks
        print("\n== 1. Canonicalization ==")
        for form in TARAZU["rs_1_50_000_forms"]:
            paise = canon_amount(form)
            print(f"  {form:<26} -> {paise} paise")
            assert paise == 15_000_000, form
        w7 = {"dhai hazaar": 250000, "do hazaar paanch sau": 250000, "2,500": 250000,
              "paune do lakh": 17_500_000, "sava lakh": 12_500_000,
              "chaar hazaar do sau pachaas rupaye": 425000, "saade teen hazaar": 350000}
        for form, want in w7.items():
            assert canon_amount(form) == want, (form, canon_amount(form))
        print(f"  {len(w7)} more amount forms match; paune do lakh -> {canon_amount('paune do lakh')}")
        call = dt.date(2026, 11, 14)                       # T01's call date, a Saturday
        dates = {"5 tarikh": "2026-12-05", "paanch December": "2026-12-05",
                 "agle mangalvaar": "2026-11-17", "salary ke baad, 8 ko": "2026-12-08",
                 "05/12": "2026-12-05", "bees tarikh ko": "2026-11-20"}
        for phrase, want in dates.items():
            got = [v for k, v in extract(phrase, call) if k == "date"]
            print(f"  {phrase:<26} -> {got[0].isoformat()}  (call date {call})")
            assert got[0].isoformat() == want, phrase

        # Step 2: the T01 pair
        print("\n== 2. T01: one substituted word ==")
        ref = "haan main dhai hazaar de dunga bees tarikh ko, baaki next month"
        hyp = "haan main do hazaar de dunga bees tarikh ko baaki next month"
        w = wer(ref, hyp)
        g, miss, _ = entity_counts(extract(ref, call), extract(hyp, call), "amount")
        print(f"  WER {w['S'] + w['D'] + w['I']}/{w['N']} = {w['wer']:.3f}  (S={w['S']} D={w['D']} I={w['I']})")
        print(f"  amount entity errors {miss}/{g}: gold {extract(ref, call)[1][1]} paise, "
              f"STT {extract(hyp, call)[1][1]} paise")
        print(f"  raw policy (no punctuation strip): WER {wer(ref, hyp, 'raw')['wer']:.3f}")
        assert (w["S"] + w["D"] + w["I"], w["N"]) == (1, 12) and round(w["wer"], 3) == 0.083
        assert (miss, g) == (1, 1)

        # Step 3: synthetic sets
        rng = random.Random(SEED)
        small = make_set(rng, 400, 60, "s")
        gold7 = make_set(rng, 1200, 180, "g")
        for s in (small, gold7):                       # the canonicalizer agrees with the generator
            for u in s:
                assert sorted(extract(u["ref"], u["call"]), key=repr) == sorted(u["gold"], key=repr), u["ref"]
        print("\n== 3. Bake-off on the 1,200-utterance set (180 speakers) ==")
        print("  extract(reference) == generator gold on all 1,600 utterances")
        boot = random.Random(SEED + 1)
        res = {s: score(gold7, s) for s in SYSTEMS}
        print("  entity error rate = gold entities not recovered exactly / gold entities")
        print(f"  {'sys':<4}{'WER':>7}{'CER':>7}  {'amount, 95% CI':<24}{'date, 95% CI':<24}{'flips':>5}")
        for s, r in res.items():
            t = r["tot"]
            a = ratio_ci(r["units"]["amount"], boot)
            d = ratio_ci(r["units"]["date"], boot)
            print(f"  {s:<4}{pct(t['edits'] / t['words']):>7}{pct(t['cedits'] / t['chars']):>7}  "
                  f"{pct(a[0]) + ' [' + pct(a[1]) + ', ' + pct(a[2]) + ']':<24}"
                  f"{pct(d[0]) + ' [' + pct(d[1]) + ', ' + pct(d[2]) + ']':<24}{t['flips']:>5}")
            r["amount"] = a[0]
            r["wer"] = t["edits"] / t["words"]
        assert res["B"]["wer"] < res["A"]["wer"] and res["B"]["amount"] > res["A"]["amount"]
        for s, r in res.items():
            t = r["tot"]
            ws = r["wrong_amount_wer"]
            print(f"  {s}: amounts {t['amount_gold']} gold, {t['amount_miss']} missed, "
                  f"{t['amount_hall']} hallucinated; {len(ws)} utterances with a wrong amount, "
                  f"{sum(x < 0.10 for x in ws)} of them at WER under 10%, "
                  f"{sum(x < 0.20 for x in ws)} under 20%")
        print("  system B, amount entity error rate by surface form:")
        by_style = defaultdict(lambda: [0, 0])
        for u in gold7:
            g, miss, _ = entity_counts(u["gold"], extract(u["hyp"]["B"], u["call"]), "amount")
            by_style[u["style"]][0] += miss
            by_style[u["style"]][1] += g
        for style in ("fraction", "words", "digits"):
            e, n = by_style[style]
            print(f"    {style:<9} {e:>3}/{n:<4} = {pct(e / n)}")

        # Step 4: interval width by set size
        print("\n== 4. 95% interval width, system B amount entity error rate ==")
        widths = {}
        for name, s in (("400 utterances / 60 speakers", small), ("1,200 / 180", gold7)):
            units = score(s, "B")["units"]["amount"]
            p, lo, hi = ratio_ci(units, boot)
            _, ulo, uhi = ratio_ci(units, boot, cluster=False)
            widths[name] = (hi - lo, uhi - ulo)
            print(f"  {name:<29} {pct(p)}  speaker-clustered [{pct(lo)}, {pct(hi)}] "
                  f"width {100 * (hi - lo):.1f} pts; utterance-level width {100 * (uhi - ulo):.1f} pts")
        (w400, u400), (w1200, u1200) = widths.values()
        assert w1200 < w400

        # Step 5: the scorer policy moves WER, not entities
        print("\n== 5. Same hypotheses, four scoring policies (1,200 set) ==")
        print(f"  {'policy':<22}{'WER A':>8}{'WER B':>8}{'amount B':>10}")
        for pol in list(POLICIES) + ["nfc+t-wer+numerals"]:
            row = []
            for s in SYSTEMS:
                e = n = 0
                for u in gold7:
                    x = wer(u["ref"], u["hyp"][s], pol.replace("+numerals", ""), pol.endswith("numerals"))
                    e, n = e + x["S"] + x["D"] + x["I"], n + x["N"]
                row.append(e / n)
            print(f"  {pol:<22}{pct(row[0]):>8}{pct(row[1]):>8}{pct(res['B']['amount']):>10}")

        print("\n  T08 first turn (call date 2026-11-16)")
        t08_call = dt.date(2026, 11, 16)
        t08_ref = "haan, but meri salary 7 ko aati hai, toh after that I can pay, around 9th"
        t08 = {"STT as logged": "hum but mary salary seven ko RT hai to after that I can pay around ninth",
               "Devanagari mode": "हाँ but मेरी सैलरी 7 को आती है तो after that I can pay around 9th"}
        for label, h in t08.items():
            cells = "  ".join(f"{p} {pct(wer(t08_ref, h, p)['wer'])}" for p in POLICIES)
            print(f"  {label:<16} {cells}")
        gold_t08, hyp_t08 = extract(t08_ref, t08_call), extract(t08["STT as logged"], t08_call)
        for kind in ("date", "confirm"):
            g, miss, _ = entity_counts(gold_t08, hyp_t08, kind)
            print(f"  STT as logged, {kind}: {g - miss}/{g} recovered")
        print(f"  STT as logged, nfc+t-wer+numerals: {pct(wer(t08_ref, t08['STT as logged'], numerals=True)['wer'])}")

        print("\n  Devanagari fixture: reference and hypothesis both in Devanagari")
        fixture = [("हाँ मैं ढाई हज़ार दूँगा", "हां मैं दो हजार दूंगा"),
                   ("डेढ़ लाख बीस तारीख को", "डेढ लाख बीस तारीख को"),
                   ("नहीं, अभी नहीं", "नही अभी नही"),
                   ("पाँच हज़ार रुपये", "पाँच हज़ार रुपये")]   # same text, two encodings
        fx_wer = {}
        for pol in POLICIES:
            e = n = 0
            for r, h in fixture:
                x = wer(r, h, pol)
                e, n = e + x["S"] + x["D"] + x["I"], n + x["N"]
            fx_wer[pol] = e / n
        g = miss = 0
        for r, h in fixture:
            a, b, _ = entity_counts(extract(r, call), extract(h, call), "amount")
            g, miss = g + a, miss + b
        print("  " + "  ".join(f"{p} {pct(v)}" for p, v in fx_wer.items()))
        print(f"  amount entity errors {miss}/{g} under every policy (entities are canonicalized first)")
        assert fx_wer["whisper-basic"] < fx_wer["nfc-only"] and (miss, g) == (1, 3)
        print("\nAll assertions passed.")

    main()


EDITIONS["india"] = (TARAZU, run_india)


if __name__ == "__main__":
    main()
