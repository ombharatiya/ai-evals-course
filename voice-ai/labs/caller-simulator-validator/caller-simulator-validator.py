"""Validate a simulated caller (aievals.co cookbook recipe R7).

Steelyard Credit is a fictional lender; its numbers are illustrative.
Dataset: steelyard-calls (synthetic, seed 20261121). Python 3.11 standard library, no network.
--edition india switches to the India edition's fictional lender, persona cards and
language mixes (its block sits between the INDIA EDITION markers below).

What it does:
  1. Builds a pairwise scenario grid over persona-flow x audio condition x language mix.
  2. Generates 120 simulated call transcripts (60 scenarios x 2 seeds) with seeded
     simulator drift.
  3. Runs three validators on every run (valid call end, behavioral fidelity to the
     persona card, caller-turn fidelity) and regenerates a rejected run up to 2 times.
  4. Compares 30 real calls with their simulated twins, per check (paired).
  5. Scores a two-rater attribution audit of the failed simulated runs (agent or
     simulator caused the first critical error), with Cohen's kappa.

Run:
    python3.11 -m venv .venv
    .venv/bin/python caller-simulator-validator.py                    # global edition
    .venv/bin/python caller-simulator-validator.py --edition india    # India edition
"""
from __future__ import annotations

import argparse
import itertools
import math
import random
import re
from collections import Counter

# --- GLOBAL constants (WORLD-GLOBAL world-global-v1.1; fictional lender, illustrative) ---
GLOBAL = {
    "lender_line": "Steelyard Credit is a fictional lender; its numbers are illustrative.",
    "dataset": "steelyard-calls (synthetic, seed 20261121)",
    "seed": 20261121,
    "products": {"AUTO": "auto loan", "PIL": "personal installment, digital",
                 "POS": "retail point-of-sale", "SBL": "small business (guarantor)",
                 "SDL": "credit-builder and small-dollar"},
    "calling_window_local": {"default": ("08:00", "21:00"), "SDL": ("09:00", "20:00")},
    "campaigns": {  # (book, silence budget ms, amount-asked / date-asked budget ms)
        "AUTO-early-nov": ("AUTO", 400, 600),
        "PIL-digital-nov": ("PIL", 400, 600),
        "POS-short-nov": ("POS", 400, 600),
        "SBL-guar-nov": ("SBL", 450, 650),
        "SDL-biwk-nov": ("SDL", 600, 800),
    },
    "languages": {"English": 0.64, "Spanish-dominant": 0.18, "Spanglish": 0.14, "other": 0.04},
    "customer_advocate": {"name": "Ms Dana Brooks", "email": "advocate@steelyard.example",
                          "phone": "(520) 555-0199",
                          "address": "1200 Example Avenue, Tucson, AZ 85701"},
    "media": {"sample_rate_hz": 8000, "codec": "G.711 mu-law", "frame_ms": 20, "frame_bytes": 160},
    "money_unit": "integer cents",
    "usd_1500_forms": ["fifteen hundred", "one thousand five hundred", "1,500", "1500",
                       "$1,500.00", "mil quinientos", "mil quinientos dolares",
                       "1.500 [es-ES]"],
    "usd_1500_cents": 150000,
    "sim_cost": {"audio_call": 0.30, "text_run": 0.025},           # WG20, US dollars
    "sim_cadence": {"nightly_audio": (240, 4), "per_commit_text": (600, 2)},  # WG19
    "twins_per_quarter": 30,                                       # WG19
}
# --- end GLOBAL constants ---

# One simulation seed for both editions, so every computed line below is identical
# in the global and India runs (the voice-simulation chapters quote them).
SIM_SEED = 20261120
MAX_RETRIES = 2
AUDIO = ["clean-16k", "phone-8k-mulaw", "phone-8k-loss5-snr10"]

# ---------- persona cards (WORLD-GLOBAL WG8, shortened for the simulator) ----------
# key: the caller's defining line per language mix. required / forbidden: markers the
# behavioral validator looks for in caller turns. facts: values the caller-turn
# validator checks. machine: no language check, no human speech allowed.
G_LANGS = ["Spanglish", "Spanish-dominant", "English"]   # mixed, other-dominant, English
G_CARDS = {
    "P01": dict(name="Ryan Mitchell, AUTO borrower, will pay", machine=False,
                key={"Spanglish": "si, le pago, el veinte I can do it",
                     "Spanish-dominant": "si, le pago el veinte",
                     "English": "yes I will pay it on the twentieth"},
                required=[r"veinte|twentieth"], forbidden=[r"already|wrong|lost my job"],
                facts={"date": r"veinte|twentieth"},
                drift="no, no, ese monto esta mal"),
    "P02": dict(name="Sofia Ramirez, POS borrower, already paid", machine=False,
                key={"Spanglish": "pero I already paid, el tres, con la tarjeta in the app",
                     "Spanish-dominant": "ya lo pague, el tres, con la tarjeta de debito en la app",
                     "English": "I already paid on the 3rd, with my debit card in the app"},
                required=[r"already|ya lo pague"], forbidden=[r"le pago manana|will pay"],
                facts={"paid_on": r"el tres|3rd", "confirmation_no": r"\bconfirmacion\b \d{12}"},
                content_interrupt=True,
                drift="bueno, esta bien, le pago manana"),
    "P03": dict(name="Marcus Reed, PIL borrower, disputes the late fee", machine=False,
                key={"Spanglish": "ese late fee esta mal, yo pague on time",
                     "Spanish-dominant": "ese cargo por atraso esta mal, yo no lo voy a pagar",
                     "English": "this late fee is wrong, I paid on time"},
                required=[r"esta mal|wrong"], forbidden=[r"le pago|will pay"],
                facts={}, drift="bueno, le pago todo"),
    "P04": dict(name="Daniela Torres, AUTO borrower, lost her job", machine=False,
                key={"Spanglish": "perdi mi trabajo, ahorita I cannot pay anything",
                     "Spanish-dominant": "perdi mi trabajo, ahorita no puedo pagar nada",
                     "English": "I lost my job, I cannot pay anything right now"},
                required=[r"perdi mi trabajo|lost my job"], forbidden=[r"le pago|will pay"],
                facts={}, drift="si, le pago el cinco"),
    "P05": dict(name="Kyle Mitchell, Ryan's adult brother", machine=False,
                key={"Spanglish": "esta en el trabajo, soy su hermano, what is this about",
                     "Spanish-dominant": "esta en el trabajo, yo soy su hermano",
                     "English": "he is at work right now, I am his brother, what is this about"},
                required=[r"trabajo|at work"], forbidden=[r"soy ryan|this is ryan"],
                facts={}, drift="si, yo soy Ryan, soy Ryan"),
    "P06": dict(name="Wrong number (recycled)", machine=False,
                key={"Spanglish": "usted tiene el numero equivocado",
                     "Spanish-dominant": "usted tiene el numero equivocado, senor",
                     "English": "you have the wrong number"},
                required=[r"numero equivocado|wrong number"], forbidden=[r"soy ryan|this is ryan"],
                facts={}, drift="si, yo soy Ryan, soy Ryan"),
    "P07": dict(name="Luis Herrera, SBL guarantor", machine=False,
                key={"Spanglish": "si, digame, what is this about? mi zip ocho cinco siete uno nueve",
                     "Spanish-dominant": "si digame de que se trata, zip ocho cinco siete uno nueve",
                     "English": "yes, what is this about? my zip is eight five seven one nine"},
                required=[r"de que se trata|what is this"], forbidden=[r"yo soy el deudor"],
                facts={"zip": r"ocho cinco siete uno nueve|eight five seven one nine"},
                drift="si, yo soy el deudor"),
    "P08": dict(name="Carrier voicemail greeting", machine=True,
                key={l: "[voicemail greeting] [beep after 9 s]" for l in G_LANGS},
                required=[r"\[beep"], forbidden=[r"^(si|yes|hello)"], facts={},
                drift="hello, si digame"),
    "P09": dict(name="Call-screening assistant / intercept / IVR", machine=True,
                key={l: "[call screening] the person you are calling is using a screening service,"
                        " say your name and why you are calling" for l in G_LANGS},
                required=[r"\[call screening"], forbidden=[r"^(si|yes|hello)"], facts={},
                drift="hello, si digame"),
    "P10": dict(name="Javier Ortiz, PIL borrower, driving", machine=False,
                key={"Spanglish": "voy manejando ahorita, llameme after six",
                     "Spanish-dominant": "voy manejando, llameme despues de las seis",
                     "English": "call me after six, I'm driving"},
                required=[r"after six|despues de las seis"], forbidden=[],
                facts={"callback": r"after six|despues de las seis"},
                drift="okay fine, tell me the amount now"),
    "P11": dict(name="Derek Wallace, SBL borrower, angry", machine=False,
                key={"Spanglish": "voy a poner una queja con la CFPB, me llaman todos los dias",
                     "Spanish-dominant": "voy a poner una queja con la CFPB, me llaman todos los dias, todos",
                     "English": "I will complain to the CFPB, you call me every day"},
                required=[r"queja|complaint|complain"], forbidden=[],
                facts={}, drift="bueno, esta bien, no hay problema"),
    "P12": dict(name="Valeria Cruz, PIL borrower, code-switcher", machine=False,
                key={"Spanglish": "si, pero my paycheck comes el viernes, so after that I can pay, el veintitres",
                     "Spanish-dominant": "si pero mi cheque llega el viernes, despues de eso el veintitres",
                     "English": "yes but my paycheck comes on Friday, so after that, around the twenty third"},
                required=[r"paycheck|cheque"], forbidden=[],
                facts={"date_after_payday": r"twenty third|veintitres"},
                drift="I can pay today"),
    "P13": dict(name="Ramon Diaz, SDL borrower, 64", machine=False,
                key={"Spanglish": "repitalo por favor, cuanto es the amount? no le escuche, more slowly please",
                     "Spanish-dominant": "repitalo por favor, cuanto es? no le escuche bien",
                     "English": "please repeat, how much is it? I did not hear properly"},
                required=[r"repitalo|repeat"], forbidden=[],
                facts={}, drift="si si, esta bien"),
}
G_TEXT = {
    "opener": {"Spanglish": "Hi, this is Steelyard Credit. I'm Hazel, an AI assistant. This call is recorded.",
               "Spanish-dominant": "Hola, le llamamos de Steelyard Credit. Soy Hazel, una asistente de"
                                   " inteligencia artificial. Esta llamada se graba.",
               "English": "Hi, this is Steelyard Credit. I'm Hazel, an AI assistant. This call is recorded."},
    "answer": {"Spanglish": "si, speaking", "Spanish-dominant": "si, digame", "English": "yes, speaking"},
    "verify": "Thank you. To verify your identity, can you tell me your ZIP code?",
    "ask_ref": "Do you have the confirmation number of the payment?",
    "give_ref": "si, confirmacion {ref}",
    "fact_forgot": "no se, no me acuerdo",
    "lang_swap_to_english": "yes okay I will see, please tell me again",
    "lang_swap_to_other": "si, esta bien, repitamelo por favor, no le entiendo",
    "hangup": "bueno, ya me voy, bye",
}
# English gloss for every Spanish line above (WG0). The example run prints them, and
# main() checks that no Spanish line is missing one.
G_GLOSS = {
    "si, le pago, el veinte I can do it": "yes, I'll pay you, on the twentieth I can do it",
    "si, le pago el veinte": "yes, I'll pay you on the twentieth",
    "no, no, ese monto esta mal": "no, no, that amount is wrong",
    "pero I already paid, el tres, con la tarjeta in the app":
        "but I already paid, on the third, with the card in the app",
    "ya lo pague, el tres, con la tarjeta de debito en la app":
        "I already paid it, on the third, with the debit card in the app",
    "bueno, esta bien, le pago manana": "okay, fine, I'll pay you tomorrow",
    "ese late fee esta mal, yo pague on time": "that late fee is wrong, I paid on time",
    "ese cargo por atraso esta mal, yo no lo voy a pagar":
        "that late charge is wrong, I am not going to pay it",
    "bueno, le pago todo": "okay, I'll pay you all of it",
    "perdi mi trabajo, ahorita I cannot pay anything": "I lost my job, right now I cannot pay anything",
    "perdi mi trabajo, ahorita no puedo pagar nada": "I lost my job, right now I can't pay anything",
    "si, le pago el cinco": "yes, I'll pay you on the fifth",
    "esta en el trabajo, soy su hermano, what is this about":
        "he's at work, I'm his brother, what is this about",
    "esta en el trabajo, yo soy su hermano": "he's at work, I'm his brother",
    "si, yo soy Ryan, soy Ryan": "yes, I'm Ryan, I'm Ryan",
    "usted tiene el numero equivocado": "you have the wrong number",
    "usted tiene el numero equivocado, senor": "you have the wrong number, sir",
    "si, digame, what is this about? mi zip ocho cinco siete uno nueve":
        "yes, go ahead, what is this about? my ZIP eight five seven one nine",
    "si digame de que se trata, zip ocho cinco siete uno nueve":
        "yes, tell me what this is about, ZIP eight five seven one nine",
    "si, yo soy el deudor": "yes, I am the borrower",
    "hello, si digame": "hello, yes, go ahead",
    "voy manejando ahorita, llameme after six": "I'm driving right now, call me after six",
    "voy manejando, llameme despues de las seis": "I'm driving, call me after six",
    "voy a poner una queja con la CFPB, me llaman todos los dias":
        "I'm going to file a complaint with the CFPB, you call me every day",
    "voy a poner una queja con la CFPB, me llaman todos los dias, todos":
        "I'm going to file a complaint with the CFPB, you call me every day, every one",
    "bueno, esta bien, no hay problema": "okay, fine, no problem",
    "si, pero my paycheck comes el viernes, so after that I can pay, el veintitres":
        "yes, but my paycheck comes on Friday, so after that I can pay, on the twenty-third",
    "si pero mi cheque llega el viernes, despues de eso el veintitres":
        "yes but my paycheck arrives on Friday, after that the twenty-third",
    "repitalo por favor, cuanto es the amount? no le escuche, more slowly please":
        "repeat it please, how much is the amount? I didn't hear you, more slowly please",
    "repitalo por favor, cuanto es? no le escuche bien": "repeat it please, how much is it? I didn't hear you well",
    "si si, esta bien": "yes yes, that's fine",
    "Hola, le llamamos de Steelyard Credit. Soy Hazel, una asistente de inteligencia artificial."
    " Esta llamada se graba.": "Hello, we are calling from Steelyard Credit. I'm Hazel, an"
    " artificial intelligence assistant. This call is recorded.",
    "si, speaking": "yes, speaking",
    "si, digame": "yes, go ahead",
    "si, confirmacion {ref}": "yes, confirmation {ref}",
    "no se, no me acuerdo": "I don't know, I don't remember",
    "si, esta bien, repitamelo por favor, no le entiendo":
        "yes, that's fine, repeat it for me please, I don't understand you",
    "bueno, ya me voy, bye": "okay, I'm going now, bye",
}
# Tokens for the language-mix check: Spanish words and English words in the caller turns.
G_OTHER = set("si le pago el veinte no ese monto esta mal pero tres con la tarjeta de debito en "
              "lo pague bueno bien manana confirmacion se acuerdo cargo por atraso yo voy "
              "pagar todo perdi mi trabajo ahorita puedo nada cinco soy su hermano que trata usted "
              "tiene numero equivocado senor digame ocho siete uno nueve deudor manejando "
              "llameme despues las seis poner una queja llaman todos los dias hay problema viernes "
              "eso veintitres cheque llega repitalo favor cuanto es escuche repitamelo ya entiendo".split())
G_EN = set("yeah i can pay do it yes will the twentieth already paid on rd with my debit card in "
           "app this late fee is wrong time lost job zip but cannot anything right now he at work am his "
           "brother what about you have number eight five seven one nine call me after six m "
           "driving complain to every day paycheck comes friday so that around twenty third "
           "please repeat how much did not hear properly amount slowly okay see tell again "
           "speaking fine today bye".split())
G_CHECKS = {  # check: (simulated pass prob, real pass prob) for the synthetic generator
    "task success (CRM diff)": (0.87, 0.70),
    "advocate details stated (C06)": (0.97, 0.87),
    "no clarification loop": (0.93, 0.77),
    "no talk-over": (0.97, 0.77),
    "amount stated correctly": (0.95, 0.80),
}

EDITIONS = {"global": dict(
    world=GLOBAL, langs=G_LANGS, cards=G_CARDS, text=G_TEXT, gloss=G_GLOSS,
    other_tokens=G_OTHER, en_tokens=G_EN, other_name="Spanish", checks=G_CHECKS,
    header=f"Validate a simulated caller (R7). {GLOBAL['lender_line']}",
    dataset_line=(f"Dataset: {GLOBAL['dataset']}; simulation seed {SIM_SEED}, shared with the"
                  " India edition. All data below is synthetic."),
    money=lambda x: f"${x:,.2f}",
)}

# ---- INDIA EDITION START ------------------------------------------------------------
# --- TARAZU constants (WORLD world-v1.1; fictional lender, illustrative) ---
TARAZU = {
    "dataset": "tarazu-calls (synthetic, seed 20261120)",
    "seed": 20261120,
    "products": {"TW": "two-wheeler", "PL": "personal, digital", "CD": "consumer durable",
                 "SBL": "small business", "MFI": "microfinance"},
    "calling_window_local": {"default": ("08:00", "19:00"), "MFI": ("09:00", "18:00")},
    "campaigns": {  # (book, silence budget ms, amount-asked / date-asked budget ms)
        "TW-early-nov": ("TW", 400, 600),
        "PL-digital-nov": ("PL", 400, 600),
        "CD-short-nov": ("CD", 400, 600),
        "SBL-guar-nov": ("SBL", 450, 650),
        "MFI-fort-nov": ("MFI", 600, 800),
    },
    "languages": {"Hinglish": 0.58, "Hindi": 0.21, "Indian English": 0.09,
                  "Marathi": 0.07, "Kannada": 0.05},
    "grievance_officer": {"name": "Ms Neha Kulkarni", "email": "grievance@tarazu.example",
                          "phone": "020-4000-0000",
                          "address": "Tarazu House, Baner Road, Pune 411045"},
    "media": {"sample_rate_hz": 8000, "codec": "G.711 mu-law", "frame_ms": 20, "frame_bytes": 160},
    "money_unit": "integer paise",
    "rs_1_50_000_forms": ["dedh lakh", "1.5 lakh", "1,50,000", "150000", "150,000",
                          "ek lakh pachaas hazaar", "one lakh fifty thousand"],  # 8th: Devanagari, R1
    "rs_1_50_000_paise": 15000000,
    "sim_cost": {"audio_call": 6.0, "text_run": 0.50},             # W20, rupees
    "sim_cadence": {"nightly_audio": (240, 4), "per_commit_text": (600, 2)},  # W19
    "twins_per_quarter": 30,                                       # W19
}
# --- end TARAZU constants ---

I_LANGS = ["Hinglish", "Hindi-dominant", "Indian English"]
# persona cards (WORLD W8, shortened for the simulator)
I_CARDS = {
    "P01": dict(name="Rahul Verma, TW borrower, will pay", machine=False,
                key={"Hinglish": "haan, I can pay, bees tarikh ko kar dunga",
                     "Hindi-dominant": "haan ji main bees tarikh ko de dunga",
                     "Indian English": "yes I will pay it on the 20th"},
                required=[r"bees tarikh|20th"], forbidden=[r"already|galat|naukri"],
                facts={"date": r"bees tarikh|20th"},
                drift="nahi nahi, yeh amount galat hai"),
    "P02": dict(name="Sunita Yadav, CD borrower, already paid", machine=False,
                key={"Hinglish": "arre maine already pay kar diya, teen tarikh ko, PhonePe se",
                     "Hindi-dominant": "arre maine to teen tarikh ko hi bhar diya, PhonePe se",
                     "Indian English": "I already paid on the 3rd, through PhonePe"},
                required=[r"already|bhar diya"], forbidden=[r"de dungi|will pay"],
                facts={"paid_on": r"teen tarikh|3rd", "utr": r"\butr\b \d{12}"},
                content_interrupt=True,
                drift="accha theek hai, main kal de dungi"),
    "P03": dict(name="Imran Shaikh, PL borrower, disputes the late fee", machine=False,
                key={"Hinglish": "yeh late fee galat hai, maine time pe pay kiya tha",
                     "Hindi-dominant": "yeh late fee galat hai ji, main nahi bharunga",
                     "Indian English": "this late fee is wrong, I paid on time"},
                required=[r"galat|wrong"], forbidden=[r"de dunga|will pay"],
                facts={}, drift="theek hai, main poora de dunga"),
    "P04": dict(name="Kavita Joshi, TW borrower, lost her job", machine=False,
                key={"Hinglish": "meri naukri chali gayi hai, right now I cannot pay anything",
                     "Hindi-dominant": "meri naukri chali gayi hai ji, abhi kuch nahi de sakti",
                     "Indian English": "I lost my job, I cannot pay anything right now"},
                required=[r"naukri chali|lost my job"], forbidden=[r"de dungi|will pay"],
                facts={}, drift="haan main paanch tarikh ko de dungi"),
    "P05": dict(name="Pooja Verma, Rahul's wife", machine=False,
                key={"Hinglish": "woh office gaye hain, main unki wife bol rahi hoon, kya kaam hai",
                     "Hindi-dominant": "woh office gaye hain, main unki patni bol rahi hoon",
                     "Indian English": "he is at the office, I am his wife, what is this about"},
                required=[r"office"], forbidden=[r"main hi rahul|this is rahul"],
                facts={}, drift="haan main hi Rahul bol raha hoon"),
    "P06": dict(name="Wrong number (recycled)", machine=False,
                key={"Hinglish": "aap galat number pe call kar rahe ho",
                     "Hindi-dominant": "aap galat number pe call kar rahe ho ji",
                     "Indian English": "you have the wrong number"},
                required=[r"galat number|wrong number"], forbidden=[r"main hi rahul|this is rahul"],
                facts={}, drift="haan main hi Rahul bol raha hoon"),
    "P07": dict(name="Ramesh Patil, SBL guarantor", machine=False,
                key={"Hinglish": "haan, bolo, what is this about? mera pincode chaar ek ek zero zero saat",
                     "Hindi-dominant": "haan bolo kya baat hai, pincode chaar ek ek zero zero saat",
                     "Indian English": "yes, what is this about? my pincode is four one one zero zero seven"},
                required=[r"kya baat|what is this"], forbidden=[r"main borrower"],
                facts={"pincode": r"chaar ek ek zero zero saat|four one one zero zero seven"},
                drift="haan main hi borrower hoon"),
    "P08": dict(name="Carrier voicemail greeting", machine=True,
                key={l: "[voicemail greeting] [beep after 9 s]" for l in I_LANGS},
                required=[r"\[beep"], forbidden=[r"^(haan|yes|hello)"], facts={},
                drift="hello, haan bolo"),
    "P09": dict(name="Operator announcement / IVR", machine=True,
                key={l: "[announcement] woh abhi vyast hai, kripya thodi der baad call karein"
                     for l in I_LANGS},
                required=[r"\[announcement"], forbidden=[r"^(haan|yes|hello)"], facts={},
                drift="hello, haan bolo"),
    "P10": dict(name="Arjun Mehta, PL borrower, driving", machine=False,
                key={"Hinglish": "abhi driving kar raha hoon, call me after 6",
                     "Hindi-dominant": "abhi gaadi chala raha hoon, chhe baje ke baad call karo",
                     "Indian English": "call me after 6, I'm driving"},
                required=[r"after 6|chhe baje"], forbidden=[],
                facts={"callback": r"after 6|chhe baje"},
                drift="okay fine, tell me the amount now"),
    "P11": dict(name="Deepak Singh, SBL borrower, angry", machine=False,
                key={"Hinglish": "main RBI mein complaint karunga, roz call aata hai",
                     "Hindi-dominant": "main RBI mein shikayat karunga, roz roz call aata hai",
                     "Indian English": "I will complain to the RBI, you call me every day"},
                required=[r"complaint|shikayat|complain"], forbidden=[],
                facts={}, drift="accha theek hai, koi baat nahi"),
    "P12": dict(name="Neha Gupta, PL borrower, code-switcher", machine=False,
                key={"Hinglish": "haan, but meri salary 7 ko aati hai, toh after that I can pay, around 9th",
                     "Hindi-dominant": "haan par meri salary saat ko aati hai, uske baad nau tarikh ko",
                     "Indian English": "yes but my salary comes on the 7th, so after that, around the 9th"},
                required=[r"salary"], forbidden=[],
                facts={"date_after_7": r"9th|nau tarikh"},
                drift="I can pay today itself"),
    "P13": dict(name="Shankar Rao, MFI borrower, 64", machine=False,
                key={"Hinglish": "phir se boliye please, kitna amount hai? main slowly sun raha hoon",
                     "Hindi-dominant": "phir se boliye ji, kitna hai? theek se sunai nahi diya",
                     "Indian English": "please repeat, how much is it? I did not hear properly"},
                required=[r"phir se|repeat"], forbidden=[],
                facts={}, drift="haan haan theek hai"),
}
_I_OPENER = ("Namaste, main Asha bol rahi hoon, Tarazu Finance ki AI assistant. "
             "Yeh call record ho rahi hai.")
I_TEXT = {
    "opener": {l: _I_OPENER for l in I_LANGS},
    "answer": {"Hinglish": "haan ji, speaking", "Hindi-dominant": "haan ji, boliye",
               "Indian English": "yes, speaking"},
    "verify": "Dhanyavaad. Pehchaan ke liye, kya aap apna pincode bata sakte hain?",
    "ask_ref": "Kya aapke paas UTR number hai?",
    "give_ref": "haan, UTR {ref}",
    "fact_forgot": "pata nahi, yaad nahi",
    "lang_swap_to_english": "yes okay I will see, please tell me again",
    "lang_swap_to_other": "haan ji theek hai, phir se boliye na",
    "hangup": "achha main rakhti hoon, bye",
}
I_HI = set("haan ji main maine kar diya hai hain ko ki ka ke toh nahi aap mera meri tarikh se abhi "
           "kuch de sakti sakta dunga dungi gaye woh kya kaam galat yeh naukri chali gayi phir boliye "
           "bolo baat aati boliye theek sahi raha rahi hoon gaadi chala baje baad karo par uske nau "
           "saat teen bees chaar ek zero pe arre bhi poora sunai diya kitna shikayat roz aata unki "
           "patni bharunga bhar time kiya tha karunga mein na pata yaad hi".split())
I_EN = set("i can pay after that call me driving the is my yes but around already you have wrong "
           "number this late fee on paid through will complain to every day what about he at office "
           "am his wife lost job cannot anything right now so comes please repeat how much it did "
           "not hear properly okay see tell again speaking time salary four one seven slowly amount job".split())
I_CHECKS = {
    "task success (CRM diff)": (0.87, 0.70),
    "grievance details stated (C06)": (0.97, 0.87),
    "no clarification loop": (0.93, 0.77),
    "no talk-over": (0.97, 0.77),
    "amount stated correctly": (0.95, 0.80),
}
EDITIONS["india"] = dict(
    world=TARAZU, langs=I_LANGS, cards=I_CARDS, text=I_TEXT, gloss={},
    other_tokens=I_HI, en_tokens=I_EN, other_name="Hindi", checks=I_CHECKS,
    header="Validate a simulated caller (R7). Tarazu Finance is a fictional lender;"
           " its numbers are illustrative.",
    dataset_line=f"Dataset: {TARAZU['dataset']}. All data below is synthetic.",
    money=lambda x: f"Rs {x:,.0f}",
)
# ---- INDIA EDITION END --------------------------------------------------------------

# The active edition. use_edition() fills these names; the code below reads only them.
ED: dict = {}
WORLD: dict = {}
LANGS: list[str] = []
CARDS: dict = {}
TEXT: dict = {}
CHECKS: dict = {}


def use_edition(name: str) -> None:
    global ED, WORLD, LANGS, CARDS, TEXT, CHECKS
    ED = EDITIONS[name]
    WORLD, LANGS, CARDS, TEXT, CHECKS = (ED["world"], ED["langs"], ED["cards"], ED["text"],
                                         ED["checks"])

# Valid persona-flow pairs (WG9 / W9 primary pairs plus plausible variants). 20 pairs,
# the same ids in both editions.
PERSONA_FLOWS = [
    ("P01", "F01"), ("P01", "F09"), ("P02", "F02"), ("P02", "F03"), ("P03", "F03"),
    ("P03", "F02"), ("P04", "F04"), ("P04", "F09"), ("P05", "F05"), ("P06", "F05"),
    ("P07", "F06"), ("P08", "F07"), ("P09", "F08"), ("P10", "F09"), ("P10", "F01"),
    ("P11", "F10"), ("P11", "F03"), ("P12", "F01"), ("P13", "F01"), ("P13", "F04"),
]
TERMINAL = {"F01": "end_call(ptp)", "F02": "end_call(paid)", "F03": "end_call(dispute)",
            "F04": "transfer_to_human(hardship)", "F05": "mark_contact(third_party)",
            "F06": "transfer_to_human(collections_l2)", "F07": "mark_contact(voicemail)",
            "F08": "mark_contact(ivr)", "F09": "schedule_callback(borrower)",
            "F10": "transfer_to_human(grievance)"}

# ---------- part 1: a pairwise scenario grid ----------

def build_grid() -> list[dict]:
    """3 rows per persona-flow pair; audio = j, language = (j + i) mod 3 (a Latin square)."""
    rows = []
    for i, (p, f) in enumerate(PERSONA_FLOWS):
        for j in range(3):
            rows.append({"sid": f"S{len(rows) + 1:03d}", "persona": p, "flow": f,
                         "audio": AUDIO[j], "lang": LANGS[(j + i) % 3]})
    return rows


def pair_coverage(rows: list[dict]) -> dict[str, tuple[int, int]]:
    levels = {"persona_flow": [f"{p}-{f}" for p, f in PERSONA_FLOWS], "audio": AUDIO, "lang": LANGS}
    out = {}
    for a, b in itertools.combinations(levels, 2):
        need = set(itertools.product(levels[a], levels[b]))
        got = {(r_val(r, a), r_val(r, b)) for r in rows}
        out[f"{a} x {b}"] = (len(need & got), len(need))
    return out


def r_val(r: dict, factor: str) -> str:
    return f"{r['persona']}-{r['flow']}" if factor == "persona_flow" else r[factor]

# ---------- part 2a: a stand-in simulator with seeded drift ----------

DRIFT_MENU = [  # (kind, probability per attempt)
    ("truncated", 0.04),          # media dropped, no terminal event
    ("early_hangup", 0.03),       # simulated caller leaves before the flow ends
    ("behavior", 0.06),          # caller abandons the card (the key line is replaced)
    ("fact", 0.04),               # caller forgets or changes a fact the card says they know
    ("language", 0.03),           # caller drops the card's language mix
    ("timer_interrupt", 0.08),    # interruption on a timer, not on content: no validator checks it
]


def simulate(scn: dict, seed: int) -> dict:
    rng = random.Random(seed)
    card = CARDS[scn["persona"]]
    u, drift, acc = rng.random(), None, 0.0
    for kind, p in DRIFT_MENU:
        acc += p
        if u < acc:
            drift = kind
            break
    if drift == "fact" and not card["facts"]:
        drift = "language"
    if drift == "language" and card["machine"]:
        drift = "behavior"
    lang = scn["lang"]
    key = card["key"][lang]
    turns = [("agent", TEXT["opener"][lang])]
    if card["machine"]:
        turns.insert(0, ("caller", key))
    else:
        turns.append(("caller", TEXT["answer"][lang]))
        turns.append(("agent", TEXT["verify"]))
        turns.append(("caller-interrupt" if card.get("content_interrupt") else "caller", key))
    if scn["persona"] == "P02":
        turns.append(("agent", TEXT["ask_ref"]))
        ref = "".join(str(rng.randrange(10)) for _ in range(12))
        turns.append(("caller", TEXT["give_ref"].format(ref=ref)))
    if drift == "behavior":
        turns = [(s, card["drift"] if t == key else t) for s, t in turns]
    elif drift == "fact":
        fact_re = re.compile("|".join(card["facts"].values()), re.I)
        turns = [(s, fact_re.sub(TEXT["fact_forgot"], t) if s.startswith("caller") else t)
                 for s, t in turns]
    elif drift == "language":
        swap = TEXT["lang_swap_to_english"] if lang != LANGS[2] else TEXT["lang_swap_to_other"]
        turns = [(s, swap if (s.startswith("caller") and t != key) else t) for s, t in turns]
    elif drift == "timer_interrupt":
        turns.append(("caller-timer", "hello? hello?"))
    if drift == "truncated":
        end = None
    elif drift == "early_hangup":
        turns.append(("caller", TEXT["hangup"]))
        end = "caller_hangup"
    else:
        end = TERMINAL[scn["flow"]]
    return {"sid": scn["sid"], "seed": seed, "scn": scn, "turns": turns, "end": end,
            "drift": drift}

# ---------- part 2b: three validators and the regenerate loop ----------

def other_share(text: str) -> float | None:
    """Share of the non-English language's words among the words we can label."""
    toks = re.findall(r"[a-z]+", text.lower())
    other = sum(t in ED["other_tokens"] for t in toks)
    en = sum(t in ED["en_tokens"] for t in toks)
    return None if other + en == 0 else other / (other + en)


def v_call_end(run: dict) -> str | None:
    if run["end"] is None:
        return "no terminal event (call truncated)"
    if run["end"] == "caller_hangup":
        return "simulated caller hung up before the flow's terminal state"
    return None


def v_behaviour(run: dict) -> str | None:
    card = CARDS[run["scn"]["persona"]]
    caller = [t for s, t in run["turns"] if s.startswith("caller")]
    for pat in card["required"]:
        if not any(re.search(pat, t, re.I) for t in caller):
            return f"required behavior missing ({pat})"
    for pat in card["forbidden"]:
        if any(re.search(pat, t, re.I) for t in caller):
            return f"forbidden behavior present ({pat})"
    if card.get("content_interrupt") and not any(s == "caller-interrupt" for s, _ in run["turns"]):
        return "content-triggered interruption missing"
    return None


def v_caller_turns(run: dict) -> str | None:
    card, lang = CARDS[run["scn"]["persona"]], run["scn"]["lang"]
    caller = " ".join(t for s, t in run["turns"] if s.startswith("caller"))
    for name, pat in card["facts"].items():
        if not re.search(pat, caller, re.I):
            return f"caller fact missing or changed ({name})"
    if card["machine"]:
        return None
    share = other_share(caller)
    if share is not None:
        mixed, dominant, english = LANGS
        what = f"{ED['other_name']} share {share:.2f}, card {lang}"
        if lang == english and share > 0.4:
            return f"language mix off card ({what})"
        if lang == dominant and share < 0.6:
            return f"language mix off card ({what})"
        if lang == mixed and not 0.2 <= share <= 0.9:
            return f"language mix off card ({what})"
    return None


VALIDATORS = [("valid call end", v_call_end), ("behavioral fidelity", v_behaviour),
              ("caller-turn fidelity", v_caller_turns)]


def validate(run: dict) -> tuple[str, str] | None:
    for name, fn in VALIDATORS:
        reason = fn(run)
        if reason:
            return name, reason
    return None


def run_with_regeneration(scn: dict, base_seed: int) -> tuple[dict, list[tuple[str, str]], bool]:
    """Simulate, validate, regenerate a rejected run up to MAX_RETRIES times."""
    rejections = []
    for attempt in range(MAX_RETRIES + 1):
        run = simulate(scn, base_seed + 1000 * attempt)
        verdict = validate(run)
        if verdict is None:
            return run, rejections, True
        assert run["drift"] not in (None, "timer_interrupt"), f"false rejection: {verdict}"
        rejections.append(verdict)
    return run, rejections, False

# ---------- part 3: sim-vs-real on 30 twins ----------

def make_twins(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    twins = []
    for i in range(n):
        row = {"twin": f"R{i + 1:02d}", "lang": LANGS[i % 3], "sim": {}, "real": {}}
        for chk, (ps, pr) in CHECKS.items():
            u = rng.random()  # shared draw: the twin is the same scenario
            row["sim"][chk] = u < ps
            row["real"][chk] = u < pr
            if rng.random() < 0.05:  # sim and real do not always fail on the same call
                row["sim"][chk] = not row["sim"][chk]
        twins.append(row)
    return twins


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def paired_bootstrap_mean_gap(twins: list[dict], reps: int, seed: int) -> tuple[float, float]:
    rng = random.Random(seed)
    n, stats = len(twins), []
    for _ in range(reps):
        sample = [twins[rng.randrange(n)] for _ in range(n)]
        gaps = [sum(t["sim"][c] - t["real"][c] for t in sample) / n for c in CHECKS]
        stats.append(sum(gaps) / len(gaps))
    stats.sort()
    return stats[int(0.025 * reps)], stats[int(0.975 * reps) - 1]

# ---------- part 4: two-rater attribution audit ----------

def cohen_kappa(a: list[str], b: list[str]) -> tuple[float, float]:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / n ** 2
    return po, (po - pe) / (1 - pe)


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return centre - half, centre + half


AGENT_PASS = {"P02": 0.70, "P11": 0.70, "P12": 0.55, "P13": 0.65}  # others 0.80


def agent_outcome(run: dict) -> tuple[bool, str]:
    """Return (passed, true cause of failure). Synthetic: a stand-in for your checks."""
    rng = random.Random(run["seed"] * 7 + 3)
    if run["drift"] == "timer_interrupt" and rng.random() < 0.7:
        return False, "simulator"
    p = AGENT_PASS.get(run["scn"]["persona"], 0.80)
    return (True, "") if rng.random() < p else (False, "agent")


def rate(rng: random.Random, truth: str, acc: float) -> str:
    if rng.random() < acc:
        return truth
    return "simulator" if truth == "agent" else "agent"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--edition", choices=list(EDITIONS), default="global",
                    help="which fictional world's cards and labels to use (default: global)")
    use_edition(ap.parse_args().edition)
    if ED["gloss"]:  # every line with words of the other language carries an English gloss
        lines = [t for c in CARDS.values() for t in [*c["key"].values(), c["drift"]]]
        lines += [t for v in TEXT.values() for t in (v.values() if isinstance(v, dict) else [v])]
        missing = [t for t in set(lines) if other_share(t) and t not in ED["gloss"]]
        assert not missing, f"no gloss for: {missing}"
    print(ED["header"])
    print(ED["dataset_line"] + "\n")

    # part 1
    grid = build_grid()
    full = len(PERSONA_FLOWS) * len(AUDIO) * len(LANGS)
    cov = pair_coverage(grid)
    print("== 1. scenario grid ==")
    print(f"persona-flow pairs: {len(PERSONA_FLOWS)}; audio conditions: {len(AUDIO)};"
          f" language mixes: {len(LANGS)}")
    print(f"full factorial: {full} scenarios; pairwise grid: {len(grid)} scenarios")
    for name, (got, need) in cov.items():
        print(f"  {name:<24} {got}/{need} pairs covered")
    assert len(grid) == 60 and full == 180
    assert all(got == need for got, need in cov.values())
    assert {(r["persona"], r["flow"]) for r in grid} == set(PERSONA_FLOWS)

    # part 2
    runs, first_reasons, all_reasons, attempts, unrecovered = [], Counter(), Counter(), 0, 0
    reason_text, dropped = Counter(), []
    first_pass_rejects = 0
    for k in range(2):
        for scn in grid:
            base = SIM_SEED + 10 * int(scn["sid"][1:]) + k
            run, rejections, ok = run_with_regeneration(scn, base)
            attempts += len(rejections) + (1 if ok else 0)
            if rejections:
                first_pass_rejects += 1
                first_reasons[rejections[0][0]] += 1
                reason_text[rejections[0][1]] += 1
            for name, _ in rejections:
                all_reasons[name] += 1
            if ok:
                runs.append(run)
            else:
                unrecovered += 1
                dropped.append(f"{scn['sid']} {scn['persona']}-{scn['flow']} seed {k}")
    planned = 2 * len(grid)
    print(f"\n== 2. validators and regeneration (up to {MAX_RETRIES} retries) ==")
    print(f"planned runs: {planned}; simulator calls placed: {attempts}")
    print(f"rejected on first attempt: {first_pass_rejects}/{planned}"
          f" = {first_pass_rejects / planned:.1%}")
    for name, _ in VALIDATORS:
        print(f"  first-attempt rejections by {name:<22} {first_reasons[name]}")
    for text, count in reason_text.most_common():
        print(f"    {count:>2}  {text}")
    print(f"all rejections incl. retries: {sum(all_reasons.values())}")
    print(f"still invalid after {MAX_RETRIES} retries (dropped, reported): {unrecovered}"
          f" ({', '.join(dropped)})")
    print(f"valid runs kept: {len(runs)}")
    undetected = sum(r["drift"] == "timer_interrupt" for r in runs)
    print(f"kept runs with a timer-based interruption (no validator checks it): {undetected}")
    extra = attempts - planned
    nightly_calls = WORLD["sim_cadence"]["nightly_audio"][0] * WORLD["sim_cadence"]["nightly_audio"][1]
    per_call = WORLD["sim_cost"]["audio_call"]
    print(f"regeneration overhead: {extra / planned:.1%} extra calls; at the nightly"
          f" {nightly_calls} audio calls x {ED['money'](per_call)} that is about"
          f" {ED['money'](nightly_calls * per_call * extra / planned)} a night")
    example = next(r for r in runs if r["scn"]["persona"] == "P12" and r["scn"]["lang"] == LANGS[0])
    assert attempts == planned + extra and len(runs) + unrecovered == planned
    assert first_pass_rejects > 0 and all(first_reasons[n] > 0 for n, _ in VALIDATORS)
    # regression lock for simulation seed 20261120, the same in both editions (pages quote these)
    assert (attempts, first_pass_rejects, unrecovered, len(runs), undetected) == (152, 25, 2, 118, 10)
    assert [first_reasons[n] for n, _ in VALIDATORS] == [11, 7, 7]
    assert sum(all_reasons.values()) == 34
    assert dropped == ["S008 P02-F02 seed 0", "S031 P07-F06 seed 0"]

    # part 3
    twins = make_twins(WORLD["twins_per_quarter"], SIM_SEED + 5)
    n = len(twins)
    print(f"\n== 3. sim vs real on {n} consented, redacted real calls and their twins ==")
    print(f"{'check':<32}{'sim':>6}{'real':>6}{'gap':>7}{'b':>4}{'c':>4}{'McNemar p':>11}")
    gaps = []
    for chk in CHECKS:
        s = sum(t["sim"][chk] for t in twins)
        r = sum(t["real"][chk] for t in twins)
        b = sum(t["sim"][chk] and not t["real"][chk] for t in twins)
        c = sum(t["real"][chk] and not t["sim"][chk] for t in twins)
        gaps.append((s - r) / n)
        print(f"{chk:<32}{s / n:>6.2f}{r / n:>6.2f}{(s - r) / n:>+7.2f}{b:>4}{c:>4}"
              f"{mcnemar_exact(b, c):>11.3f}")
        assert s > r, f"simulator should flatter on {chk}"
    mean_gap = sum(gaps) / len(gaps)
    lo, hi = paired_bootstrap_mean_gap(twins, 2000, SIM_SEED + 6)
    print(f"mean overestimate: {mean_gap:+.3f} (paired bootstrap 95% CI {lo:+.3f} to {hi:+.3f})")
    print("b = sim pass, real fail; c = real pass, sim fail")
    width = max(map(len, LANGS)) + 1
    for lang in LANGS:
        sub = [t for t in twins if t["lang"] == lang]
        ts = sum(t["sim"]["task success (CRM diff)"] for t in sub)
        tr = sum(t["real"]["task success (CRM diff)"] for t in sub)
        print(f"  task success, {lang:<{width}} sim {ts}/{len(sub)}  real {tr}/{len(sub)}")
    assert mean_gap > 0 and lo > 0
    assert round(mean_gap, 3) == 0.087 and round(gaps[0], 2) == 0.20
    assert (round(lo, 3), round(hi, 3)) == (0.020, 0.160)

    # part 4
    failed = [r for r in runs if not agent_outcome(r)[0]]
    truth = [agent_outcome(r)[1] for r in failed]
    rng = random.Random(SIM_SEED + 7)
    r1 = [rate(rng, t, 0.90) for t in truth]
    r2 = [rate(rng, t, 0.88) for t in truth]
    po, kappa = cohen_kappa(r1, r2)
    agreed = [a for a, b in zip(r1, r2) if a == b]
    final = [a if a == b else t for a, b, t in zip(r1, r2, truth)]  # disagreements adjudicated
    sim_k = final.count("simulator")
    wl, wh = wilson(sim_k, len(final))
    print(f"\n== 4. two-rater attribution of {len(failed)} failed simulated runs ==")
    print(f"rater 1: {Counter(r1)['agent']} agent, {Counter(r1)['simulator']} simulator;"
          f" rater 2: {Counter(r2)['agent']} agent, {Counter(r2)['simulator']} simulator")
    print(f"agreement {po:.3f}; Cohen's kappa {kappa:.3f}; disagreements adjudicated:"
          f" {len(failed) - len(agreed)}")
    print(f"simulator caused the first critical error: {sim_k}/{len(final)} = {sim_k / len(final):.1%}"
          f" (Wilson 95% {wl:.3f} to {wh:.3f})")
    tim = sum(r["drift"] == "timer_interrupt" for r in failed)
    print(f"failed runs with a timer-based interruption: {tim}")
    assert 0 < kappa < 1 and sim_k > 0 and len(failed) >= 20
    assert (len(failed), sim_k, round(po, 3), round(kappa, 3)) == (42, 7, 0.810, 0.475)
    assert (round(wl, 3), round(wh, 3), tim) == (0.083, 0.306, 7)
    assert all(r["drift"] == "timer_interrupt" for r, f in zip(failed, final) if f == "simulator")

    print(f"\nP12 example run {example['sid']} ({example['scn']['lang']},"
          f" {example['scn']['audio']}), end = {example['end']}:")
    for spk, text in example["turns"]:
        print(f"  {spk:<16} {text}")
        if text in ED["gloss"]:
            print(f"  {'':<16} gloss: {ED['gloss'][text]}")
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
