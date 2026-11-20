"""Round-trip TTS numbers and dates: verbalize, speak, transcribe, parse back, gate.

Steelyard Credit is a fictional lender; its numbers are illustrative.
Dataset: steelyard-calls (synthetic, seed 20261121). Standard library only.
Python 3.11. No network. --edition india switches to the India edition's
fictional lender and data set (its block sits between the INDIA EDITION markers).

The round trip here runs on a CONSTRUCTED fixture: a toy TTS normalizer and a
toy 8 kHz STT written to reproduce documented or plausible behaviors (a
numeric date written month-first and read day-first by a Spanish voice, a
Spanish voice requested with the bare locale "es" reading a comma as a
decimal sign, a small model reading $1,000,000 as "one thousand thousand",
"@" and "." read by their symbol names, bare digits read as a cardinal).
No audio is synthesized. Swap `fixture_tts` and `fixture_stt` for your own
engines in `round_trip()` (see the adapter at the bottom).

Run:
    python3.11 tts-round-trip-numerics.py                    # global edition
    python3.11 tts-round-trip-numerics.py --edition india    # India edition
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import random
import re
from dataclasses import dataclass
from typing import Callable

# ---- GLOBAL constants (copied from WORLD-GLOBAL WG1-WG7; do not edit here) ------
GLOBAL = {
    "lender_note": "Steelyard Credit is a fictional lender; its numbers are illustrative.",
    "lender": "Steelyard Credit, Inc. (fictional US consumer lender, head office Tucson AZ)",
    "dataset": "steelyard-calls (synthetic, seed 20261121)",
    "seed": 20261121,
    "products": {  # code: (ticket $ range, payment $ range)
        "AUTO": ((8_000, 35_000), (245, 680)),
        "PIL": ((1_000, 40_000), (95, 1_850)),
        "POS": ((300, 6_000), (45, 520)),
        "SBL": ((25_000, 250_000), (980, 7_200)),
        "SDL": ((300, 3_000), (35, 140)),
    },
    "campaigns": {"AUTO-early-nov": "AUTO", "PIL-digital-nov": "PIL", "POS-short-nov": "POS",
                  "SBL-guar-nov": "SBL", "SDL-biwk-nov": "SDL"},
    "windows": {"default": ("08:00", "21:00"), "SDL": ("09:00", "20:00")},
    "languages": {"English": 64, "Spanish-dominant": 18, "Spanglish": 14, "other": 4},
    "bot_languages": ("English", "Spanish-dominant", "Spanglish"),  # other -> human
    "customer_advocate": {"name": "Ms Dana Brooks", "email": "advocate@steelyard.example",
                          "phone": "(520) 555-0199",
                          "address": "1200 Example Avenue, Tucson, AZ 85701"},
    "callback_number": "(520) 555-0100",
    "money": "integer cents in tools and CRM; dollars in speech",
    "dates": "ISO in tools; words in speech; en-US reads M/d, es-US reads d/M",
    "versions": {"tts": "vendorB-v4@8k", "stt": "vendorA-2026-10", "gold": "gold-v7"},
    "gold_v7_tts_lines": 500, "gold_v7_amount_lines": 400,
}
# -----------------------------------------------------------------------------------

CALL_DATE = dt.date(2026, 11, 20)

EN_UNITS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
            "fourteen fifteen sixteen seventeen eighteen nineteen").split()
EN_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
EN_NUM = {w: i for i, w in enumerate(EN_UNITS)}
EN_NUM.update({w: 10 * i for i, w in enumerate(EN_TENS) if i >= 2})
ORD_UNITS = ("_ first second third fourth fifth sixth seventh eighth ninth tenth eleventh "
             "twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth "
             "nineteenth").split()
EN_ORD = {w: i for i, w in enumerate(ORD_UNITS) if i >= 1}
EN_ORD.update({"twentieth": 20, "thirtieth": 30})
MONTHS = ("january february march april may june july august september october november "
          "december").split()

# Spanish number words, written without accents (ASCII), as the STT writes them here.
ES_UNITS = ("cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece "
            "catorce quince dieciseis diecisiete dieciocho diecinueve veinte veintiuno "
            "veintidos veintitres veinticuatro veinticinco veintiseis veintisiete "
            "veintiocho veintinueve").split()
ES_TENS = "_ _ veinte treinta cuarenta cincuenta sesenta setenta ochenta noventa".split()
ES_HUNDREDS = ("_ ciento doscientos trescientos cuatrocientos quinientos seiscientos "
               "setecientos ochocientos novecientos").split()
ES_NUM = {w: i for i, w in enumerate(ES_UNITS)}
ES_NUM.update({w: 10 * i for i, w in enumerate(ES_TENS) if i >= 3})
ES_NUM.update({w: 100 * i for i, w in enumerate(ES_HUNDREDS) if i >= 1})
ES_NUM.update({"cien": 100, "un": 1, "veintiun": 21})
ES_MONTHS = ("enero febrero marzo abril mayo junio julio agosto septiembre octubre "
             "noviembre diciembre").split()
WORD_NUM = {**EN_NUM, **ES_NUM}
MULT = {"hundred": 100, "thousand": 1_000, "mil": 1_000}
FILLER = {"dollars", "dollar", "dolares", "dolar", "and", "y"}
STATES = {"AZ": "Arizona", "CA": "California", "TX": "Texas", "FL": "Florida",
          "IL": "Illinois", "MA": "Massachusetts"}


# ---- the US verbalizer: English and Spanish -----------------------------------------
def en_below_100(n: int) -> str:
    if n < 20:
        return EN_UNITS[n]
    t, u = divmod(n, 10)
    return EN_TENS[t] + ("" if u == 0 else " " + EN_UNITS[u])


def en_say_int(n: int) -> str:
    """Integer in Western grouping: thousand, hundred."""
    def below_1000(k: int) -> str:
        h, r = divmod(k, 100)
        return " ".join(([f"{EN_UNITS[h]} hundred"] if h else []) + ([en_below_100(r)] if r else []))
    th, r = divmod(n, 1_000)
    parts = ([f"{below_1000(th)} thousand"] if th else []) + ([below_1000(r)] if r else [])
    return " ".join(parts) or "zero"


def es_below_100(n: int) -> str:
    if n < 30:
        return ES_UNITS[n]
    t, u = divmod(n, 10)
    return ES_TENS[t] + ("" if u == 0 else " y " + ES_UNITS[u])


def es_say_int(n: int) -> str:
    """Spanish cardinal: 'mil quinientos', 'ciento veinte mil', 'veintiun mil'."""
    def below_1000(k: int) -> str:
        h, r = divmod(k, 100)
        if h == 1 and r == 0:
            return "cien"
        return " ".join(([ES_HUNDREDS[h]] if h else []) + ([es_below_100(r)] if r else []))
    th, r = divmod(n, 1_000)
    parts = []
    if th:
        head = below_1000(th)
        head = head[:-1] if head.endswith("uno") else head   # uno -> un before mil
        parts.append("mil" if th == 1 else f"{head} mil")
    if r:
        parts.append(below_1000(r))
    return " ".join(parts) or "cero"


def say_amount(cents: int, lang: str) -> str:
    dollars = cents // 100
    return f"{es_say_int(dollars)} dolares" if lang == "es" else f"{en_say_int(dollars)} dollars"


def en_ordinal(n: int) -> str:
    if n in EN_ORD.values() and n < 20 or n in (20, 30):
        return {v: k for k, v in EN_ORD.items()}[n]
    t, u = divmod(n, 10)
    return f"{EN_TENS[t]} {ORD_UNITS[u]}"


def say_date(d: dt.date, lang: str) -> str:
    if lang == "es":   # day first: "tres de diciembre" [December third]
        return f"{'primero' if d.day == 1 else es_say_int(d.day)} de {ES_MONTHS[d.month - 1]}"
    return f"{MONTHS[d.month - 1].capitalize()} {en_ordinal(d.day)}"


def say_digits(digits: str, lang: str) -> str:
    """ZIP codes and other IDs digit by digit."""
    words = ES_UNITS if lang == "es" else EN_UNITS
    return " ".join(words[int(c)] for c in digits)


def say_phone(digits: str, lang: str) -> str:
    """10-digit NANP number in 3-3-4 groups, each digit spoken (the course's choice
    for Spanish too: how a Spanish voice groups digits is undocumented, so measure it)."""
    return ", ".join(say_digits(g, lang) for g in (digits[:3], digits[3:6], digits[6:]))


def say_house(n: int, lang: str) -> str:
    if lang == "en" and n % 100 == 0 and 1_000 <= n < 10_000:
        return f"{en_below_100(n // 100)} hundred"          # "twelve hundred"
    return es_say_int(n) if lang == "es" else en_say_int(n)


def say_email(addr: str, lang: str) -> str:
    local, domain = addr.split("@")
    at, dot = ("arroba", "punto") if lang == "es" else ("at", "dot")
    return f"{local} {at} {f' {dot} '.join(domain.split('.'))}"


def usd(cents: int) -> str:
    """$1,500.00 style (what the LLM wrote before the words-for-numbers rule)."""
    return f"${cents // 100:,}.{cents % 100:02d}"


# ---- the constructed fixture: a toy TTS normalizer and a toy 8 kHz STT ------------
def es_pairs(digits: str) -> str:
    """Toy Spanish reader for bare digits: pairs, and a pair that starts with zero
    is read as its second digit alone (constructed)."""
    out = []
    for i in range(0, len(digits), 2):
        p = digits[i:i + 2]
        out.append(ES_UNITS[int(p[1])] if len(p) == 2 and p[0] == "0" else es_below_100(int(p)))
    return ", ".join(out)


def fixture_tts(text: str, lang: str) -> str:
    """What a default normalizer says for numeric input (constructed). The English
    voice uses en-US; the Spanish voice was requested with the bare locale "es",
    so it reads numbers with Spain's conventions (comma decimal, day-first dates)."""
    def email(m: re.Match) -> str:
        return m.group(1) + " commercial at " + m.group(2).replace(".", " full stop ")

    def address(m: re.Match) -> str:
        house, street, state, zip_ = m.groups()
        zip_words = es_pairs(zip_) if lang == "es" else say_digits(zip_, "en")
        return f"{say_house(int(house), lang)} {street}, {STATES[state]}, {zip_words}"

    def amount(m: re.Match) -> str:
        raw = m.group(1)
        if lang == "es" and "," in raw:            # comma read as a decimal sign
            whole, dec = raw.split(",", 1)
            dec = dec.replace(",", "")
            zeros = len(dec) - len(dec.lstrip("0"))
            rest = [es_say_int(int(dec))] if dec.strip("0") else []
            return f"{es_say_int(int(whole))} coma {' '.join(['cero'] * zeros + rest)} dolares"
        return say_amount(int(raw.replace(",", "")) * 100, lang)

    def date(m: re.Match) -> str:
        a, b = int(m.group(1)), int(m.group(2))   # written M/d by the English stack
        if lang == "en":
            return f"{MONTHS[a - 1].capitalize()} {en_ordinal(b)}"
        if 1 <= b <= 12:                           # es reads d/M: day a, month b
            return f"{'primero' if a == 1 else es_say_int(a)} de {ES_MONTHS[b - 1]}"
        return f"{es_say_int(a)} barra {es_say_int(b)}"

    def phone(m: re.Match) -> str:
        digits = "".join(m.groups())
        return es_pairs(digits) if lang == "es" else say_phone(digits, "en")

    def bare_zip(m: re.Match) -> str:              # no say-as tag: en reads a cardinal
        return es_pairs(m.group(0)) if lang == "es" else en_say_int(int(m.group(0)))

    text = re.sub(r"([\w.]+)@([\w.]+\w)", email, text)
    text = re.sub(r"\b(\d{3,5}) ([A-Z][\w ]+, [A-Z][\w ]+), ([A-Z]{2}) (\d{5})\b", address, text)
    text = re.sub(r"\$([\d,]+\d)(?:\.\d\d)?", amount, text)   # the toy drops ".00"
    text = re.sub(r"\b(\d\d)/(\d\d)\b", date, text)
    text = re.sub(r"\((\d{3})\) (\d{3})-(\d{4})", phone, text)
    return re.sub(r"\b\d{5}\b", bare_zip, text)


def fixture_small_model(text: str) -> str:
    """A smaller TTS model's reading of a million (constructed after the documented
    'one thousand thousand dollars' example): every comma group becomes 'thousand'."""
    def amount(m: re.Match) -> str:
        groups = m.group(1).split(",")
        return " ".join([en_say_int(int(groups[0]))] + ["thousand"] * (len(groups) - 1)) + " dollars"
    return re.sub(r"\$([\d,]+\d)(?:\.\d\d)?", amount, text)


def fixture_stt(spoken: str) -> str:
    """Toy STT on 8 kHz mu-law audio (constructed): lowercase, no punctuation."""
    return " ".join(re.sub(r"[^\w\s@]", " ", spoken.lower().replace("-", " ")).split())


def phone_path(audio):
    """Plug point: resample to 8 kHz and G.711 mu-law encode before STT.
    The fixture passes text, so this is the identity here."""
    return audio


def round_trip(tts_input: str, lang: str, tts=fixture_tts, stt=fixture_stt) -> str:
    return stt(phone_path(tts(tts_input, lang)))


HUMAN_CONFUSIONS = {"fifteen": "fifty", "fifty": "fifteen", "fourteen": "forty",
                    "thirteen": "thirty", "doce": "dos", "trece": "tres"}


def human_reference_stt(line: str, rng: random.Random) -> str:
    """Toy STT on a consented volunteer reading the written-out line (constructed):
    the same STT, plus T01-style confusions on 6% of eligible lines."""
    toks = fixture_stt(line).split()
    hits = [i for i, t in enumerate(toks) if t in HUMAN_CONFUSIONS]
    if hits and rng.random() < 0.06:
        i = rng.choice(hits)
        toks[i] = HUMAN_CONFUSIONS[toks[i]]
    return " ".join(toks)


# ---- the parse-back scorer --------------------------------------------------------
def parse_number(toks: list[str]) -> float | None:
    """English or Spanish number words, or en-US digits, -> a value. None if unsure."""
    toks = [t for t in toks if t not in FILLER]
    if not toks:
        return None
    if len(toks) == 1 and re.fullmatch(r"\$?\d[\d,]*(\.\d+)?", toks[0]):
        return float(toks[0].lstrip("$").replace(",", ""))     # en-US separators
    if len(toks) >= 2 and all(WORD_NUM.get(t, 99) <= 9 for t in toks):
        return float("".join(str(WORD_NUM[t]) for t in toks))  # digit run
    if "coma" in toks:                                          # decimal comma
        k = toks.index("coma")
        whole, tail, zeros = parse_number(toks[:k]), toks[k + 1:], 0
        while zeros < len(tail) and tail[zeros] == "cero":
            zeros += 1
        rest = parse_number(tail[zeros:]) if tail[zeros:] else None
        dec = "0" * zeros + (str(int(rest)) if rest else "")
        return float(f"{int(whole)}.{dec}") if whole is not None and dec else None
    total, cur, last_mult = 0.0, 0.0, False
    for t in toks:
        if t in WORD_NUM:
            cur += WORD_NUM[t]
            last_mult = False
        elif t in MULT:
            if last_mult and cur == 0:
                return None                                     # "thousand thousand"
            if MULT[t] == 100:
                cur = (cur or 1) * 100
            else:
                total += (cur or 1) * MULT[t]
                cur = 0.0
            last_mult = True
        else:
            return None
    return (total + cur) or None


def canon_amount(text: str) -> int | None:
    """Spoken or written amount -> integer cents. None if no amount is found."""
    v = parse_number(text.lower().split())
    return round(v * 100) if v else None


def digits_from_words(toks: list[str]) -> str:
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        if t in EN_TENS[2:] and EN_NUM.get(nxt, 99) < 10:                 # "twenty five"
            out.append(str(EN_NUM[t] + EN_NUM[nxt]))
            i += 2
            continue
        if t in ES_TENS[3:] and nxt == "y" and i + 2 < len(toks) and \
                ES_NUM.get(toks[i + 2], 99) < 10:                         # "cincuenta y dos"
            out.append(str(ES_NUM[t] + ES_NUM[toks[i + 2]]))
            i += 3
            continue
        if WORD_NUM.get(t, 100) < 100:
            out.append(str(WORD_NUM[t]))
        elif t.isdigit():
            out.append(t)
        else:
            return ""
        i += 1
    return "".join(out)


def canon_digits(text: str, n: int) -> str | None:
    d = digits_from_words(text.lower().split())
    return d if re.fullmatch(rf"\d{{{n}}}", d) else None


def word_day(toks: list[str]) -> int | None:
    if toks and all(t in EN_ORD or t in WORD_NUM or t == "primero" for t in toks):
        return sum(EN_ORD.get(t, WORD_NUM.get(t, 1)) for t in toks)
    if len(toks) == 1 and re.fullmatch(r"\d{1,2}(st|nd|rd|th)?", toks[0]):
        return int(re.match(r"\d+", toks[0]).group())
    return None


def resolve(day: int, month: int) -> dt.date | None:
    try:
        d = dt.date(CALL_DATE.year, month, day)
    except ValueError:
        return None
    return d if d >= CALL_DATE else d.replace(year=d.year + 1)


def canon_date(text: str) -> dt.date | None:
    toks = [t for t in text.lower().split() if t not in ("the", "of", "on", "el", "de", "y")]
    for sep in ("slash", "barra"):                # explicit mdy policy: the stack writes M/d
        if sep in toks:
            k = toks.index(sep)
            month, day = word_day(toks[:k]), word_day(toks[k + 1:])
            return resolve(day, month) if day and month else None
    months = [i for i, t in enumerate(toks) if t in MONTHS or t in ES_MONTHS]
    if len(months) != 1:
        return None
    k = months[0]
    month = (MONTHS.index(toks[k]) if toks[k] in MONTHS else ES_MONTHS.index(toks[k])) + 1
    day = word_day(toks[:k] + toks[k + 1:])
    return resolve(day, month) if day else None


def canon_email(text: str) -> str | None:
    toks = text.lower().split()
    toks = ["@" if t in ("at", "arroba") else "." if t in ("dot", "punto") else t for t in toks]
    s = "".join(toks)
    return s if re.fullmatch(r"[a-z0-9._]+@[a-z0-9]+(\.[a-z0-9]+)+", s) else None


def canon_address(text: str) -> tuple | None:
    """(house number, street and city tokens..., ZIP); the ZIP must match exactly."""
    toks = text.lower().split()
    k = 0
    while k < len(toks) and (toks[k] in WORD_NUM or toks[k] in MULT):
        k += 1
    j = len(toks)
    while j > k and (toks[j - 1] in WORD_NUM or toks[j - 1] == "y"):
        j -= 1
    house = parse_number(toks[:k]) if k else None
    zip_ = canon_digits(" ".join(toks[j:]), 5)
    return (int(house), *toks[k:j], zip_) if house and zip_ else None


CANON = {"amount": canon_amount, "date": canon_date, "phone": lambda s: canon_digits(s, 10),
         "zip": lambda s: canon_digits(s, 5), "email": canon_email, "address": canon_address}

# ---- prompts from CRM templates (each Spanish template has its English gloss) -------
TEMPLATES = {
    ("amount", "en"): ["Your past-due amount is {}.", "Your payment is {}.",
                       "To pay off the loan in full you need to pay {}."],
    ("amount", "es"): ["Su saldo vencido es de {}.",          # Your past-due balance is {}.
                       "Su pago es de {}.",                   # Your payment is {}.
                       "Para liquidar el prestamo necesita pagar {}."],  # To pay off the loan...
    ("date", "en"): ["Your next payment is due on {}."],
    ("date", "es"): ["Su proximo pago vence el {}."],         # Your next payment is due on {}.
    ("phone", "en"): ["Is {} still the best number to reach you?"],
    ("phone", "es"): ["Sigue siendo {} el mejor numero para llamarle?"],  # Is {} still the best...
    ("zip", "en"): ["Thank you, ZIP code {} matches our records."],
    ("zip", "es"): ["Gracias, el codigo postal {} coincide con nuestros registros."],  # same
    ("email", "en"): ["Our complaints email is {}."],
    ("email", "es"): ["Nuestro correo de quejas es {}."],     # Our complaints email is {}.
    ("address", "en"): ["Our address is {}."],
    ("address", "es"): ["Nuestra direccion es {}."],          # Our address is {}.
}
AREA_CODES = ("520", "602", "213", "415", "713", "512", "305", "312", "617")
ZIP_PREFIXES = ("857", "850", "900", "941", "770", "787", "331", "606", "021")


def make_amount(rng: random.Random, kind: int) -> int:
    code = rng.choice(list(GLOBAL["products"]))
    (t_lo, t_hi), (p_lo, p_hi) = GLOBAL["products"][code]
    if kind == 0:                                  # past due: 1 or 2 payments
        d = rng.randint(p_lo, p_hi) * rng.choice((1, 2))
    elif kind == 1:                                # payment
        d = rng.randint(p_lo, p_hi)
    else:                                          # payoff, rounded to $500
        d = max(t_lo, rng.randint(t_lo, t_hi) // 500 * 500)
    return d * 100


def make_prompt(etype: str, rng: random.Random) -> dict:
    group = rng.choices(GLOBAL["bot_languages"], weights=(64, 18, 14))[0]
    lang = "en" if group == "English" else "es"   # Spanish-dominant and Spanglish: es voice
    k = rng.randrange(len(TEMPLATES[(etype, lang)]))
    tpl = TEMPLATES[(etype, lang)][k]
    adv = GLOBAL["customer_advocate"]
    if etype == "amount":
        gold = make_amount(rng, k)
        numeric, words = usd(gold), say_amount(gold, lang)
    elif etype == "date":
        gold = CALL_DATE + dt.timedelta(days=rng.randint(1, 72))
        numeric, words = gold.strftime("%m/%d"), say_date(gold, lang)
    elif etype == "phone":
        area, line = rng.choice(AREA_CODES), f"01{rng.randint(0, 99):02d}"   # 555-01XX
        gold = f"{area}555{line}"
        numeric, words = f"({area}) 555-{line}", say_phone(gold, lang)
    elif etype == "zip":
        gold = rng.choice(ZIP_PREFIXES) + f"{rng.randint(0, 99):02d}"
        numeric, words = gold, say_digits(gold, lang)
    elif etype == "email":
        gold = adv["email"]
        numeric, words = gold, say_email(gold, lang)
    else:
        street, zip_ = adv["address"].rsplit(" ", 1)          # "1200 Example ... AZ", "85701"
        house, rest = street.split(" ", 1)
        rest = re.sub(r", ([A-Z]{2})$", lambda m: ", " + STATES[m.group(1)], rest)
        gold = (int(house), *fixture_stt(rest).split(), zip_)
        numeric = adv["address"]
        words = f"{say_house(int(house), lang)} {rest}, {say_digits(zip_, lang)}"
    return {"type": etype, "lang": lang, "tpl": tpl, "gold": gold,
            "numeric": tpl.format(numeric), "words": tpl.format(words)}


def extract(transcript: str, tpl: str) -> str | None:
    """Strip the template's carrier words; what is left is the spoken entity."""
    pre, suf = (fixture_stt(s).split() for s in tpl.split("{}"))
    toks = transcript.split()
    if toks[:len(pre)] != pre or (suf and toks[len(toks) - len(suf):] != suf):
        return None
    return " ".join(toks[len(pre):len(toks) - len(suf)])


def score(p: dict, transcript: str) -> tuple[bool, object]:
    span = extract(transcript, p["tpl"])
    got = CANON[p["type"]](span) if span is not None else None
    return got == p["gold"], got


def global_intro() -> None:
    print(GLOBAL["lender_note"])
    print(f"dataset: {GLOBAL['dataset']}; call date {CALL_DATE}; fixture: constructed\n")
    # sanity checks on the canonicalizer (WORLD-GLOBAL WG7 forms 1-7; form 8 is R1's)
    for form in ["fifteen hundred", "one thousand five hundred", "1,500", "1500",
                 "$1,500.00", "mil quinientos", "mil quinientos dolares"]:
        assert canon_amount(form) == 150000, form
    assert canon_amount("two hundred fifty dollars") == canon_amount("doscientos cincuenta") == 25000
    assert canon_amount("ciento veinte mil") == canon_amount("one hundred twenty thousand") == 12000000
    t06 = round_trip("Su proximo pago de $680.00 vence el 12/03.", "es")   # trace T06
    assert t06 == "su proximo pago de seiscientos ochenta dolares vence el doce de marzo", t06
    heard = t06.split(" vence el ")[1]
    assert canon_date(heard) == dt.date(2027, 3, 12)
    bare_es = round_trip("$1,500.00", "es")
    assert bare_es == "uno coma quinientos dolares" and canon_amount(bare_es) == 150, bare_es
    small = fixture_stt(fixture_small_model("$1,000,000.00"))
    assert small == "one thousand thousand dollars" and canon_amount(small) is None, small
    print("WG7 surface forms 1-7 -> 150000 cents: ok")
    print(f"T06 line '12/03' (gold 2026-12-03) heard as: '{heard}' -> 2027-03-12")
    print(f"bare 'es' voice, '$1,500.00' heard as: '{bare_es}' -> 150 cents (gold 150000)")
    print(f"small model, '$1,000,000.00' heard as: '{small}' -> None (rejected)\n")


def global_date_rows(prompts: list[dict], speak: Callable, score_fn: Callable) -> list[str]:
    dates = [p for p in prompts if p["type"] == "date"]
    rows = []
    for label, sel in (("English", lambda p: p["lang"] == "en"),
                       ("Spanish, day 1-12", lambda p: p["lang"] == "es" and p["gold"].day <= 12),
                       ("Spanish, day 13-31", lambda p: p["lang"] == "es" and p["gold"].day > 12)):
        grp = [p for p in dates if sel(p)]
        ok = sum(score_fn(p, speak(p, p["numeric"]))[0] for p in grp)
        same = sum(p["gold"].day == p["gold"].month for p in grp)
        rows.append(f"date rows, numeric input, {label:<18}: {pct(ok, len(grp))}"
                    + (f"  (day == month in {same})" if "1-12" in label else ""))
    return rows


def global_check(tot: list[int], results: dict) -> None:
    """Pin this edition's own printed numbers, so a changed fixture fails loudly."""
    assert tot == [200, 140, 200, 199], tot
    assert results["numeric"][0] == 69, results["numeric"]


# ---- the acceptance gate (the same in every edition) --------------------------------
def binom_cdf(k: int, n: int, p: float) -> float:
    if p <= 0:
        return 1.0
    if p >= 1:
        return 0.0 if k < n else 1.0
    return sum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                        + i * math.log(p) + (n - i) * math.log1p(-p)) for i in range(k + 1))


def upper_bound(k: int, n: int, conf: float = 0.95) -> float:
    """Exact one-sided (Clopper-Pearson) upper bound on the error rate."""
    if k == 0:
        return 1 - (1 - conf) ** (1 / n)
    lo, hi = k / n, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if binom_cdf(k, n, mid) > 1 - conf else (lo, mid)
    return hi


def gate(k: int, n: int, min_match: float = 0.995) -> str:
    return "PASS" if k == 0 and (n - k) / n >= min_match else "FAIL"


def show(x: object) -> str:
    return x.isoformat() if isinstance(x, dt.date) else repr(x)


def pct(k: int, n: int) -> str:
    return f"{k:>3}/{n:<3} {100 * k / n:6.1f}%"


@dataclass
class Edition:
    world: dict
    intro: Callable[[], None]
    counts: dict
    make_prompt: Callable[[str, random.Random], dict]
    speak: Callable[[dict, str], str]            # (prompt, TTS input) -> heard transcript
    floor: Callable[[dict, random.Random], str]  # (prompt, rng) -> STT of a human reading
    score: Callable[[dict, str], tuple]
    date_rows: Callable[[list, Callable, Callable], list]
    check: Callable[[list, dict], None] = lambda tot, results: None


EDITIONS = {"global": Edition(
    world=GLOBAL, intro=global_intro,
    counts={"amount": 80, "date": 50, "phone": 25, "zip": 15, "email": 15, "address": 15},
    make_prompt=make_prompt, speak=lambda p, text: round_trip(text, p["lang"]),
    floor=lambda p, rng: human_reference_stt(p["words"], rng), score=score,
    date_rows=global_date_rows, check=global_check)}

# ---- INDIA EDITION START ---------------------------------------------------------
# ---- TARAZU constants (copied from WORLD.md W1-W7; do not edit here) --------
TARAZU = {
    "lender": "Tarazu Finance Ltd (fictional NBFC, head office Pune)",
    "dataset": "tarazu-calls (synthetic, seed 20261120)",
    "seed": 20261120,
    "products": {  # code: (ticket Rs range, EMI Rs range)
        "TW": ((60_000, 1_50_000), (2_450, 6_800)),
        "PL": ((25_000, 5_00_000), (1_900, 18_500)),
        "CD": ((8_000, 80_000), (1_100, 7_300)),
        "SBL": ((2_00_000, 25_00_000), (9_800, 72_000)),
        "MFI": ((30_000, 75_000), (1_350, 3_400)),
    },
    "campaigns": {"TW-early-nov": "TW", "PL-digital-nov": "PL", "CD-short-nov": "CD",
                  "SBL-guar-nov": "SBL", "MFI-fort-nov": "MFI"},
    "windows": {"default": ("08:00", "19:00"), "MFI": ("09:00", "18:00")},
    "languages": {"Hinglish": 58, "Hindi": 21, "Indian English": 9, "Marathi": 7, "Kannada": 5},
    "bot_languages": ("Hinglish", "Hindi", "Indian English"),  # Marathi, Kannada -> human
    "grievance_officer": {"name": "Ms Neha Kulkarni", "email": "grievance@tarazu.example",
                          "phone": "020-4000-0000",
                          "address": "Tarazu House, Baner Road, Pune 411045"},
    "fractions": {"sava": 1.25, "dedh": 1.5, "dhai": 2.5, "paune": -0.25, "saade": 0.5},
    "money": "integer paise in tools and CRM; rupees in speech",
    "dates": "ISO in tools; words in speech; explicit dmy policy for numeric dates",
    "versions": {"tts": "vendorB-v4@8k", "stt": "vendorA-2026-10", "gold": "gold-v7"},
    "gold_v7_tts_lines": 500, "gold_v7_amount_lines": 400,
}
# -----------------------------------------------------------------------------

HI_WORDS = (
    "ek do teen chaar paanch chhah saat aath nau das gyaarah baarah terah chaudah pandrah "
    "solah satrah athaarah unnees bees ikkees baaees teyees chaubees pachchees chhabbees "
    "sattaaees atthaaees untees tees ikattees battees taintees chauntees paintees chhattees "
    "saintees adtees untaalees chaalees iktaalees bayaalees taintaalees chavaalees paintaalees "
    "chhiyaalees saintaalees adtaalees unchaas pachaas ikyaavan baavan tirpan chauvan pachpan "
    "chhappan sattaavan atthaavan unsath saath iksath baasath tirsath chausath painsath "
    "chhiyaasath sadsath adsath unhattar sattar ikhattar bahattar tihattar chauhattar pachhattar "
    "chhihattar sathattar athhattar unaasi assi ikyaasi bayaasi tiraasi chauraasi pachaasi "
    "chhiyaasi sattaasi atthaasi navaasi nabbe ikyaanve baanve tiraanve chauraanve pachaanve "
    "chhiyaanve sattaanve atthaanve ninyaanve"
).split()
HI_NUM = {w: i + 1 for i, w in enumerate(HI_WORDS)}
HI_NUM.update({"zero": 0, "shunya": 0})
NUM_HI = {v: k for k, v in HI_NUM.items() if k != "shunya"}
TZ_MULT = {"sau": 100, "hundred": 100, "hazaar": 1_000, "thousand": 1_000,
           "lakh": 1_00_000, "crore": 1_00_00_000}
TZ_FILLER = {"rupees", "rupee", "rupaye", "rs", "and"}


# ---- the Indian verbalizer -------------------------------------------------
def tz_say_int(n: int, lang: str) -> str:
    """Integer in the Indian system: crore, lakh, thousand/hazaar, hundred/sau."""
    small = (lambda k: NUM_HI[k]) if lang == "hi" else en_below_100
    words = ("crore", "lakh", "hazaar", "sau") if lang == "hi" else \
            ("crore", "lakh", "thousand", "hundred")
    parts = []
    for size, word in zip((1_00_00_000, 1_00_000, 1_000, 100), words):
        q, n = divmod(n, size)
        if q:
            parts.append(f"{tz_say_int(q, lang) if q >= 100 else small(q)} {word}")
    if n:
        parts.append(small(n))
    return " ".join(parts) or ("zero" if lang == "en" else "shunya")


def colloquial_hi(rupees: int) -> str | None:
    """sava / dedh / dhai / paune X / saade X for exact lakh and hazaar values."""
    for size, word in ((1_00_000, "lakh"), (1_000, "hazaar")):
        x = rupees / size
        if x == 1.5:
            return f"dedh {word}"
        if x == 2.5:
            return f"dhai {word}"
        if x == 1.25:
            return f"sava {word}"
        if x >= 1.75 and (x + 0.25).is_integer() and x + 0.25 < 100:
            return f"paune {NUM_HI[int(x + 0.25)]} {word}"
        if x >= 3.5 and (x - 0.5).is_integer() and x < 100:
            return f"saade {NUM_HI[int(x - 0.5)]} {word}"
    return None


def tz_say_amount(paise: int, lang: str) -> str:
    rupees = paise // 100
    if lang == "hi":
        return f"{colloquial_hi(rupees) or tz_say_int(rupees, 'hi')} rupaye"
    return f"{tz_say_int(rupees, 'en')} rupees"


def tz_say_date(d: dt.date, lang: str) -> str:
    month = MONTHS[d.month - 1].capitalize()
    return f"{NUM_HI[d.day]} {month}" if lang == "hi" else f"{en_ordinal(d.day)} {month}"


def tz_say_digits(digits: str, lang: str) -> str:
    """IDs and pincodes digit by digit."""
    words = NUM_HI if lang == "hi" else dict(enumerate(EN_UNITS))
    return " ".join(words[int(c)] for c in digits)   # NUM_HI[0] is "zero"


def tz_say_email(addr: str) -> str:
    local, domain = addr.split("@")
    return f"{local} at {' dot '.join(domain.split('.'))}"


def inr(rupees: int) -> str:
    """Rs 1,50,000 style grouping (what the LLM wrote before the T06 rule)."""
    s = str(rupees)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return ",".join([head] + groups + [tail])


# ---- the constructed fixture: a toy TTS normalizer and a toy 8 kHz STT ------
def tz_fixture_tts(text: str) -> str:
    """What a default en-US text normalizer says for numeric input (constructed)."""
    def amount(m: re.Match) -> str:
        raw = m.group(1)
        if re.fullmatch(r"\d{1,2}(,\d\d)+,\d{3}", raw) and int(raw.replace(",", "")) >= 1_00_000:
            return "rupees " + " ".join(EN_UNITS[int(c)] for c in raw if c.isdigit())
        return "rupees " + tz_say_int(int(raw.replace(",", "")), "en")  # < 1 lakh: same grouping

    def date(m: re.Match) -> str:
        a, b = int(m.group(1)), int(m.group(2))   # written dd/mm, read as mm/dd
        if 1 <= a <= 12:
            return f"{MONTHS[a - 1].capitalize()} {en_ordinal(b)}"
        return f"{en_below_100(a)} slash {en_below_100(b)}"

    def pairs(m: re.Match) -> str:
        out = []
        for i in range(0, 6, 2):
            p = m.group(0)[i:i + 2]
            out.append(f"oh {EN_UNITS[int(p[1])]}" if p[0] == "0" else en_below_100(int(p)))
        return " ".join(out)

    def email(m: re.Match) -> str:
        return m.group(1) + " commercial at " + m.group(2).replace(".", " full stop ")

    text = re.sub(r"([\w.]+)@([\w.]+\w)", email, text)
    text = re.sub(r"Rs\.? ?([\d,]+\d)", amount, text)
    text = re.sub(r"\b(\d\d)/(\d\d)\b", date, text)
    return re.sub(r"\b\d{6}\b", pairs, text)


def tz_fixture_stt(spoken: str) -> str:
    """Toy STT on 8 kHz mu-law audio (constructed): drops 'oh', merges zero runs."""
    toks = re.sub(r"[^\w\s@]", " ", spoken.lower()).split()
    toks = [t for t in toks if t != "oh"]
    out, run = [], 0
    for t in toks:
        run = run + 1 if t == "zero" else 0
        if run == 3:          # a run of three or more zeros loses one
            continue
        out.append(t)
    return " ".join(out)


def tz_round_trip(tts_input: str, tts=tz_fixture_tts, stt=tz_fixture_stt) -> str:
    return stt(phone_path(tts(tts_input)))


TZ_HUMAN_CONFUSIONS = {"dhai": "do", "saat": "saath", "teen": "tees",
                       "fifteen": "fifty", "fourteen": "forty", "thirteen": "thirty"}


def tz_human_reference_stt(line: str, rng: random.Random) -> str:
    """Toy STT on a consented volunteer reading the written-out line (constructed):
    the same STT, plus T01-style confusions on 6% of eligible lines."""
    toks = tz_fixture_stt(line).split()
    hits = [i for i, t in enumerate(toks) if t in TZ_HUMAN_CONFUSIONS]
    if hits and rng.random() < 0.06:
        i = rng.choice(hits)
        toks[i] = TZ_HUMAN_CONFUSIONS[toks[i]]
    return " ".join(toks)


# ---- the parse-back scorer ----------------------------------------------------
def tz_is_num(t: str) -> bool:
    return t in HI_NUM or t in EN_NUM or bool(re.fullmatch(r"[\d,.]+", t))


def tz_num_val(t: str) -> float:
    if t in HI_NUM:
        return HI_NUM[t]
    if t in EN_NUM:
        return EN_NUM[t]
    return float(t.replace(",", ""))


def tz_canon_amount(text: str) -> int | None:
    """Spoken or written amount -> integer paise. None if no amount is found."""
    toks = [t for t in text.lower().replace("rs.", "rs ").split() if t not in TZ_FILLER]
    if not toks:
        return None
    if len(toks) >= 2 and all(t in HI_NUM or t in EN_NUM for t in toks) and \
            all(tz_num_val(t) <= 9 for t in toks):
        return int("".join(str(int(tz_num_val(t))) for t in toks)) * 100   # digit run
    total, cur, mod = 0.0, 0.0, None
    for t in toks:
        if t in ("sava", "paune", "saade"):
            mod = t
        elif t in ("dedh", "dhai"):
            cur += TARAZU["fractions"][t]
        elif tz_is_num(t):
            v = tz_num_val(t)
            if mod:
                v += {"sava": 0.25, "paune": -0.25, "saade": 0.5}[mod]
                mod = None
            cur += v
        elif t in TZ_MULT:
            if mod == "sava":
                cur, mod = 1.25, None
            if TZ_MULT[t] == 100:
                cur = (cur or 1) * 100
            else:
                total += (cur or 1) * TZ_MULT[t]
                cur = 0.0
        else:
            return None
    rupees = total + cur
    return round(rupees * 100) if rupees else None


def tz_digits_from_words(toks: list[str]) -> str:
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t in HI_NUM:
            out.append(str(HI_NUM[t]))
        elif t in EN_NUM:
            v = EN_NUM[t]
            if v >= 20 and i + 1 < len(toks) and toks[i + 1] in EN_NUM and EN_NUM[toks[i + 1]] < 10:
                v += EN_NUM[toks[i + 1]]
                i += 1
            out.append(str(v))
        elif t.isdigit():
            out.append(t)
        else:
            return ""
        i += 1
    return "".join(out)


def tz_canon_pincode(text: str) -> str | None:
    d = tz_digits_from_words(text.lower().split())
    return d if re.fullmatch(r"\d{6}", d) else None


def tz_word_day(toks: list[str]) -> int | None:
    if not toks:
        return None
    if all(t in EN_ORD or t in EN_NUM for t in toks):
        return sum(EN_ORD.get(t, EN_NUM.get(t, 0)) for t in toks)
    if len(toks) == 1 and toks[0] in HI_NUM:
        return HI_NUM[toks[0]]
    if len(toks) == 1 and re.fullmatch(r"\d{1,2}(st|nd|rd|th)?", toks[0]):
        return int(re.match(r"\d+", toks[0]).group())
    return None


def tz_canon_date(text: str) -> dt.date | None:
    toks = [t for t in text.lower().split() if t not in ("tarikh", "ko", "the", "of", "on")]
    if "slash" in toks:                          # explicit dmy policy for numeric dates
        k = toks.index("slash")
        day = tz_word_day(toks[:k])
        month = int(tz_digits_from_words(toks[k + 1:]) or 0)
        return resolve(day, month) if day else None
    months = [i for i, t in enumerate(toks) if t in MONTHS]
    if len(months) != 1:
        return None
    k = months[0]
    day = tz_word_day(toks[:k] + toks[k + 1:])
    return resolve(day, MONTHS.index(toks[k]) + 1) if day else None


def tz_canon_email(text: str) -> str | None:
    toks = text.lower().split()
    toks = ["@" if t == "at" else "." if t == "dot" else t for t in toks]
    s = "".join(toks)
    return s if re.fullmatch(r"[a-z0-9._]+@[a-z0-9]+(\.[a-z0-9]+)+", s) else None


def tz_canon_address(text: str) -> tuple[str, ...] | None:
    toks = re.sub(r"[^\w\s]", " ", text.lower()).split()
    k = next((i for i, t in enumerate(toks) if tz_is_num(t)), len(toks))
    pin = tz_canon_pincode(" ".join(toks[k:]))
    return tuple(toks[:k]) + (pin,) if pin else None


TZ_CANON = {"amount": tz_canon_amount, "date": tz_canon_date, "pincode": tz_canon_pincode,
            "email": tz_canon_email, "address": tz_canon_address}

# ---- prompts from CRM templates -----------------------------------------------
TZ_TEMPLATES = {
    ("amount", "hi"): ["Aapka overdue {} hai.", "Aapki EMI {} hai.",
                       "Poora loan band karne ke liye {} lagenge."],
    ("amount", "en"): ["Your overdue amount is {}.", "Your EMI is {}.",
                       "To close the loan in full you need to pay {}."],
    ("date", "hi"): ["Aapki agli EMI {} ko due hai."],
    ("date", "en"): ["Your next EMI is due on {}."],
    ("pincode", "hi"): ["Dhanyavaad, pincode {} match ho gaya."],
    ("pincode", "en"): ["Thank you, pincode {} matches our records."],
    ("email", "hi"): ["Hamara grievance email hai {}."],
    ("email", "en"): ["Our grievance email is {}."],
    ("address", "hi"): ["Hamara pata hai {}."],
    ("address", "en"): ["Our address is {}."],
}
PIN_PREFIXES = ("411", "440", "226", "208", "462", "452", "560", "110", "201", "122")


def tz_make_amount(rng: random.Random, kind: int) -> int:
    code = rng.choice(list(TARAZU["products"]))
    (t_lo, t_hi), (e_lo, e_hi) = TARAZU["products"][code]
    if kind == 0:                                  # overdue: 1 or 2 EMIs
        r = rng.randint(e_lo, e_hi) // 10 * 10 * rng.choice((1, 2))
    elif kind == 1:                                # EMI
        r = rng.randint(e_lo, e_hi) // 10 * 10
    else:                                          # foreclosure, rounded to Rs 5,000
        r = max(t_lo, rng.randint(t_lo, t_hi) // 5_000 * 5_000)
    return r * 100


def tz_make_prompt(etype: str, rng: random.Random) -> dict:
    lang = "en" if rng.choices(TARAZU["bot_languages"], weights=(58, 21, 9))[0] == \
        "Indian English" else "hi"
    k = rng.randrange(len(TZ_TEMPLATES[(etype, lang)]))
    tpl = TZ_TEMPLATES[(etype, lang)][k]
    g = TARAZU["grievance_officer"]
    if etype == "amount":
        gold = tz_make_amount(rng, k)
        numeric, words = f"Rs {inr(gold // 100)}", tz_say_amount(gold, lang)
    elif etype == "date":
        gold = CALL_DATE + dt.timedelta(days=rng.randint(1, 72))
        numeric, words = gold.strftime("%d/%m"), tz_say_date(gold, lang)
    elif etype == "pincode":
        gold = rng.choice(PIN_PREFIXES) + f"{rng.randint(0, 999):03d}"
        numeric, words = gold, tz_say_digits(gold, lang)
    elif etype == "email":
        gold = g["email"]
        numeric, words = gold, tz_say_email(gold)
    else:
        name, pin = g["address"].rsplit(" ", 1)
        gold = tuple(re.sub(r"[^\w\s]", " ", name.lower()).split()) + (pin,)
        numeric, words = g["address"], f"{name}, {tz_say_digits(pin, lang)}"
    return {"type": etype, "lang": lang, "tpl": tpl, "gold": gold,
            "numeric": tpl.format(numeric), "words": tpl.format(words)}


def tz_extract(transcript: str, tpl: str) -> str | None:
    """Strip the template's carrier words; what is left is the spoken entity."""
    pre, suf = (tz_fixture_stt(s).split() for s in tpl.split("{}"))
    toks = transcript.split()
    if toks[:len(pre)] != pre or (suf and toks[len(toks) - len(suf):] != suf):
        return None
    return " ".join(toks[len(pre):len(toks) - len(suf)])


def tz_score(p: dict, transcript: str) -> tuple[bool, object]:
    span = tz_extract(transcript, p["tpl"])
    got = TZ_CANON[p["type"]](span) if span is not None else None
    return got == p["gold"], got


def india_intro() -> None:
    print("Tarazu Finance is a fictional lender; its numbers are illustrative.")
    print(f"dataset: {TARAZU['dataset']}; call date {CALL_DATE}; fixture: constructed\n")
    # sanity checks on the canonicalizer (WORLD W7 forms 1-7; form 8 is R1's)
    for form in ["dedh lakh", "1.5 lakh", "1,50,000", "150000", "150,000",
                 "ek lakh pachaas hazaar", "one lakh fifty thousand"]:
        assert tz_canon_amount(form) == 15000000, form
    assert tz_canon_amount("dhai hazaar") == tz_canon_amount("do hazaar paanch sau") == 250000
    assert tz_canon_amount("paune do lakh") == 17500000 and tz_canon_amount("sava lakh") == 12500000
    t06 = tz_round_trip("Your next EMI is due on 05/12.")
    assert t06 == "your next emi is due on may twelfth", t06
    assert tz_canon_date(tz_extract(t06, "Your next EMI is due on {}.")) == dt.date(2027, 5, 12)
    print("W7 surface forms 1-7 -> 15000000 paise: ok")
    print(f"T06 line '05/12' (gold 2026-12-05) heard as: '{t06[24:]}' -> 2027-05-12\n")


def india_date_rows(prompts: list[dict], speak: Callable, score_fn: Callable) -> list[str]:
    dates = [p for p in prompts if p["type"] == "date"]
    rows = []
    for label, sel in (("day 1-12", lambda d: d.day <= 12), ("day 13-31", lambda d: d.day > 12)):
        grp = [p for p in dates if sel(p["gold"])]
        ok = sum(score_fn(p, speak(p, p["numeric"]))[0] for p in grp)
        same = sum(p["gold"].day == p["gold"].month for p in grp)
        rows.append(f"date rows, numeric input, {label:<9}: {pct(ok, len(grp))}"
                    + (f"  (day == month in {same})" if label == "day 1-12" else ""))
    return rows


EDITIONS["india"] = Edition(
    world=TARAZU, intro=india_intro,
    counts={"amount": 80, "date": 50, "pincode": 30, "email": 20, "address": 20},
    make_prompt=tz_make_prompt, speak=lambda p, text: tz_round_trip(text),
    floor=lambda p, rng: tz_human_reference_stt(p["words"], rng), score=tz_score,
    date_rows=india_date_rows)
# ---- INDIA EDITION END -----------------------------------------------------------


# ---- run ------------------------------------------------------------------------
def run(ed: Edition) -> None:
    ed.intro()
    world = ed.world
    rng = random.Random(world["seed"])
    prompts = [ed.make_prompt(t, rng) for t, n in ed.counts.items() for _ in range(n)]
    hrng = random.Random(world["seed"] + 1)
    rows, fails = {}, {}
    for p in prompts:
        ok_num, got = ed.score(p, ed.speak(p, p["numeric"]))
        ok_words, _ = ed.score(p, ed.speak(p, p["words"]))
        ok_floor, _ = ed.score(p, ed.floor(p, hrng))
        r = rows.setdefault(p["type"], [0, 0, 0, 0])
        r[0] += 1
        r[1] += ok_num
        r[2] += ok_words
        r[3] += ok_floor
        if not ok_num and p["type"] not in fails:
            fails[p["type"]] = (p["numeric"], ed.speak(p, p["numeric"]), got, p["gold"])
    print(f"{len(prompts)} prompts from CRM templates; exact match after the round trip")
    print(f"{'entity':<8} {'n':>4}  {'numeric input':>15}  {'written-out input':>17}  "
          f"{'STT floor (human)':>17}")
    for t, (n, a, b, c) in rows.items():
        print(f"{t:<8} {n:>4}  {pct(a, n):>15}  {pct(b, n):>17}  {pct(c, n):>17}")
    tot = [sum(r[i] for r in rows.values()) for i in range(4)]
    print(f"{'all':<8} {tot[0]:>4}  {pct(tot[1], tot[0]):>15}  {pct(tot[2], tot[0]):>17}  "
          f"{pct(tot[3], tot[0]):>17}")
    for line in ed.date_rows(prompts, ed.speak, ed.score):
        print(line)

    print("\nfirst failure per entity type, numeric input:")
    for t, (src, heard, got, gold) in fails.items():
        print(f"  {t:<7} TTS input: {src}")
        print(f"          heard:     {heard}")
        print(f"          parsed {show(got)}, expected {show(gold)}")

    # gate on a 400-line amount suite (gold-v7 has 400 amount lines)
    arng = random.Random(world["seed"] + 2)
    suite = [ed.make_prompt("amount", arng) for _ in range(world["gold_v7_amount_lines"])]
    print(f"\nacceptance gate: {len(suite)} amount lines, rule = exact match >= 99.5% and "
          "zero wrong amounts")
    print(f"{'input':<12} {'wrong':>7}  {'exact match':>11}  {'95% upper bound (one-sided)':>27}  gate")
    results = {}
    for style in ("words", "numeric"):
        k = sum(not ed.score(p, ed.speak(p, p[style]))[0] for p in suite)
        n = len(suite)
        ub = upper_bound(k, n)
        results[style] = (k, n, ub)
        name = "written-out" if style == "words" else "numeric"
        print(f"{name:<12} {k:>3}/{n:<3}  {100 * (n - k) / n:10.2f}%  {ub:>27.4f}  {gate(k, n)}")
    k, n, ub = results["words"]
    print(f"0 of {n}: exact bound {ub:.5f} ({100 * ub:.3f}%); rule of three 3/{n} = {3 / n:.4f}")

    # [C] numbers shared by every edition (W17 / WG17): 0 of 400 -> 0.746%, about 0.75%
    assert k == 0 and n == 400
    assert round(ub, 4) == 0.0075 and round(100 * ub, 3) == 0.746
    assert abs(ub - 0.0075) < 0.0002 and 3 / n == 0.0075
    assert gate(*results["words"][:2]) == "PASS" and gate(*results["numeric"][:2]) == "FAIL"
    ed.check(tot, results)
    print("all assertions passed")


def main() -> None:
    ap = argparse.ArgumentParser(description="Round-trip TTS numbers and dates.")
    ap.add_argument("--edition", choices=sorted(EDITIONS), default="global",
                    help="which fictional world to run (default: global)")
    run(EDITIONS[ap.parse_args().edition])


# ---- adapter: plug in your own engines -----------------------------------------
class YourEngines:
    """Replace the fixture with real engines. Keep the TTS version pinned and
    rerun the suite on every TTS or STT update.

        def tts(text: str, lang: str) -> bytes:   # request 8 kHz mu-law, as production
            ...                                    # does; set the full locale (es-US)
        def stt(audio: bytes) -> str:              # the production STT, same settings
            ...
        heard = round_trip(line, lang, tts=tts, stt=stt)
    """


if __name__ == "__main__":
    main()
