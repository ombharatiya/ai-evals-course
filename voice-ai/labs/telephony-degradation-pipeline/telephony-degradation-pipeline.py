"""A phone-path degradation pipeline in numpy (aievals.co cookbook recipe).

Steelyard Credit is a fictional lender; its numbers are illustrative.

Takes 16 kHz audio (a synthetic chirp by default, or your own consented WAV),
runs it through a teaching model of the phone path, and writes the source plus
four condition WAVs for your STT:

    band-pass 300-3400 Hz -> resample to 8 kHz -> G.711-style mu-law round trip
    -> Gilbert-Elliott burst loss on 20 ms frames -> optional noise at a fixed SNR

Run:
    python3.11 -m venv .venv && .venv/bin/pip install numpy==2.1.3
    .venv/bin/python telephony-degradation-pipeline.py
    .venv/bin/python telephony-degradation-pipeline.py --wav my_consented_16k.wav
    .venv/bin/python telephony-degradation-pipeline.py --edition india

--edition picks the world (default global). The signal path is the same in both;
only the seed, the dataset name and the condition-matrix levels change.

The filters and the companding here are for teaching. Gate on the ITU-T
Software Tool Library (G.191) or on real 8 kHz calls, not on this file.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import os
import wave

import numpy as np

# --- GLOBAL constants (WORLD-GLOBAL world-global-v1.1; fictional lender, illustrative) ---
GLOBAL = {
    "lender_note": "Steelyard Credit is a fictional lender; its numbers are illustrative.",
    "dataset": "steelyard-calls (synthetic, seed 20261121)",
    "seed": 20261121,
    "clip_loss5_frozen": (6, [1, 1, 1, 3]),  # [C] frames lost and bursts on the chirp at a 5% target
    "products": {"AUTO": "auto loan", "PIL": "personal installment, digital",
                 "POS": "retail point-of-sale", "SBL": "small business, guarantor",
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
                       "$1,500.00", "mil quinientos", "mil quinientos dolares"],  # 8th: "1.500" es-ES, R1
    "usd_1500_cents": 150000,
    "factors": {  # condition matrix levels (WG19)
        "carrier": ["carrier-a-mobile", "carrier-b-mobile", "carrier-c-mobile", "voip-leg"],
        "codec_chain": ["amrnb->mulaw", "amrwb->mulaw", "opus->mulaw"],
        "language_mix": ["English", "Spanish-dominant", "Spanglish"],
    },
}
# --- end GLOBAL constants ---
EDITIONS = {"global": GLOBAL}

# --- India edition constants (WORLD world-v1.1; fictional lender, illustrative) ---
TARAZU = {
    "lender_note": "Tarazu Finance is a fictional lender; its numbers are illustrative.",
    "dataset": "tarazu-calls (synthetic, seed 20261120)",
    "seed": 20261120,
    "clip_loss5_frozen": (20, [9, 1, 1, 4, 1, 1, 2, 1]),  # [C] frames lost and bursts on the chirp at 5%
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
    "factors": {  # condition matrix levels (W19)
        "carrier": ["carrier-1", "carrier-2", "carrier-3", "carrier-4"],
        "codec_chain": ["mulaw", "alaw->mulaw", "amrnb->mulaw"],
        "language_mix": ["Hinglish", "Hindi", "Indian English"],
    },
}
EDITIONS["india"] = TARAZU
# --- end India edition constants ---

SR_WIDE = 16000
SR_PHONE = GLOBAL["media"]["sample_rate_hz"]  # the same 8 kHz, 160-byte media in every edition
FRAME = GLOBAL["media"]["frame_bytes"]  # 160 mu-law bytes = 160 samples = 20 ms at 8 kHz
assert all(w["media"] == GLOBAL["media"] for w in EDITIONS.values())


# ---------- [1] signals and the band-pass ----------

def synth_source(seconds: float = 4.0, sr: int = SR_WIDE) -> np.ndarray:
    """Linear chirp 100 Hz -> 7 kHz plus tones at 1 kHz and 5 kHz, peak about -3 dBFS."""
    t = np.arange(int(seconds * sr)) / sr
    f0, f1 = 100.0, 7000.0
    chirp = np.sin(2 * np.pi * (f0 * t + (f1 - f0) * t**2 / (2 * seconds)))
    x = 0.40 * chirp + 0.15 * np.sin(2 * np.pi * 1000 * t) + 0.15 * np.sin(2 * np.pi * 5000 * t)
    return x / np.max(np.abs(x)) * 10 ** (-3 / 20)


def bandpass(x: np.ndarray, sr: int, lo: float = 300.0, hi: float = 3400.0) -> np.ndarray:
    """Brick-wall FFT mask. A teaching filter: it rings, and it is not G.712."""
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / sr)
    spec[(freqs < lo) | (freqs > hi)] = 0
    return np.fft.irfft(spec, n=len(x))


def band_energy(x: np.ndarray, sr: int, lo: float, hi: float) -> float:
    """Share of the signal's energy above lo and up to hi Hz, in dB (0 dB = all of it)."""
    power = np.abs(np.fft.rfft(x)) ** 2
    freqs = np.fft.rfftfreq(len(x), 1 / sr)
    share = power[(freqs > lo) & (freqs <= hi)].sum() / power.sum()
    return 10 * np.log10(max(share, 1e-30))


def resample_poly_np(x: np.ndarray, up: int, down: int, taps: int = 161) -> np.ndarray:
    """Zero-stuff by `up`, Kaiser-windowed sinc low-pass, keep every `down`-th sample."""
    cutoff = 0.5 / max(up, down)  # cycles per sample at the upsampled rate
    n = np.arange(taps) - (taps - 1) / 2
    h = 2 * cutoff * np.sinc(2 * cutoff * n) * np.kaiser(taps, 8.6)
    h *= up / h.sum()
    stuffed = np.zeros(len(x) * up)
    stuffed[::up] = x
    y = np.convolve(stuffed, h)[(taps - 1) // 2:(taps - 1) // 2 + len(stuffed)]
    return y[::down]


# ---------- [2] mu-law ----------

MU = 255.0


def mulaw_encode(x: np.ndarray) -> np.ndarray:
    """Continuous mu-law (mu = 255) to 8-bit codes. Not the bit-exact G.711 segment table."""
    x = np.clip(x, -1.0, 1.0)
    y = np.sign(x) * np.log1p(MU * np.abs(x)) / np.log1p(MU)
    return np.round((y + 1) / 2 * 255).astype(np.uint8)


def mulaw_decode(codes: np.ndarray) -> np.ndarray:
    y = codes.astype(np.float64) / 255 * 2 - 1
    return np.sign(y) * np.expm1(np.abs(y) * np.log1p(MU)) / MU


def linear8_round_trip(x: np.ndarray) -> np.ndarray:
    """Plain 8-bit linear quantization, for contrast with companding."""
    return np.round(np.clip(x, -1, 1) * 127) / 127


def snr_db(ref: np.ndarray, test: np.ndarray) -> float:
    err = test - ref
    return 10 * np.log10(np.sum(ref**2) / max(np.sum(err**2), 1e-30))


# ---------- [3] burst loss ----------

def gilbert_elliott(n_frames: int, p: float, r: float, seed: int) -> np.ndarray:
    """Two-state burst loss. p = P(good -> bad), r = P(bad -> good); every bad frame is lost.
    Stationary loss rate p / (p + r); mean burst length 1 / r frames."""
    rng = np.random.default_rng(seed)
    u = rng.random(n_frames + 1)
    lost = np.zeros(n_frames, dtype=bool)
    bad = u[0] < p / (p + r)  # start in the stationary distribution
    for i in range(n_frames):
        lost[i] = bad
        bad = (u[i + 1] >= r) if bad else (u[i + 1] < p)
    return lost


def burst_lengths(mask: np.ndarray) -> list[int]:
    runs, run = [], 0
    for lost in mask:
        if lost:
            run += 1
        elif run:
            runs.append(run)
            run = 0
    if run:
        runs.append(run)
    return runs


def apply_loss(x: np.ndarray, mask: np.ndarray, fill: str = "zero", frame: int = FRAME) -> np.ndarray:
    """Drop 20 ms frames. fill='zero' plays silence; fill='repeat' replays the last good
    frame (a crude concealment, not G.711 Appendix I)."""
    y = x.copy()
    last_good = np.zeros(frame)
    for i, lost in enumerate(mask):
        seg = slice(i * frame, (i + 1) * frame)
        if seg.start >= len(y):
            break
        if lost:
            y[seg] = 0.0 if fill == "zero" else last_good[: len(y[seg])]
        else:
            last_good = x[seg].copy()
    return y


def ge_params(target_loss: float, r: float) -> float:
    """p that gives the target stationary loss for a chosen r."""
    return target_loss * r / (1 - target_loss)


# ---------- [4] noise ----------

def mix_snr(x: np.ndarray, noise: np.ndarray, snr: float) -> np.ndarray:
    gain = np.sqrt(np.mean(x**2) / (np.mean(noise**2) * 10 ** (snr / 10)))
    return x + gain * noise


# ---------- [5] WAV I/O ----------

def read_wav_16k(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, SR_WIDE):
            raise SystemExit(f"{path}: need mono 16-bit PCM at 16 kHz")
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    return pcm.astype(np.float64) / 32768


def write_wav(path: str, x: np.ndarray, sr: int) -> int:
    pcm = (np.clip(x, -1, 1 - 1 / 32768) * 32768).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return os.path.getsize(path)


# ---------- [6] the condition matrix ----------

def matrix_factors(world: dict) -> dict:
    """Five factors in a fixed order; carrier, codec chain and language mix come from the edition."""
    f = world["factors"]
    return {"carrier": f["carrier"], "codec_chain": f["codec_chain"], "loss": ["1%", "5%", "10%"],
            "snr": ["clean", "20 dB", "10 dB"], "language_mix": f["language_mix"]}


def condition_matrix(factors: dict) -> list[dict]:
    """Every carrier x codec chain x loss combination once; SNR and language mix assigned
    with modular arithmetic so every pair of levels of every two factors appears."""
    rows = []
    for c, k, l in itertools.product(range(4), range(3), range(3)):
        rows.append({
            "carrier": factors["carrier"][c],
            "codec_chain": factors["codec_chain"][k],
            "loss": factors["loss"][l],
            "snr": factors["snr"][(k + l) % 3],
            "language_mix": factors["language_mix"][(k + 2 * l + c) % 3],
        })
    return rows


def pair_coverage(rows: list[dict], factors: dict) -> tuple[int, int]:
    needed = covered = 0
    for a, b in itertools.combinations(factors, 2):
        seen = {(row[a], row[b]) for row in rows}
        for pair in itertools.product(factors[a], factors[b]):
            needed += 1
            covered += pair in seen
    return covered, needed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edition", choices=sorted(EDITIONS), default="global",
                    help="which world's seed and matrix levels to use (default global)")
    ap.add_argument("--wav", help="your own consented mono 16-bit 16 kHz WAV")
    ap.add_argument("--out", default="phone_path_out")
    args = ap.parse_args()
    world = EDITIONS[args.edition]
    seed = world["seed"]
    os.makedirs(args.out, exist_ok=True)

    print(world["lender_note"])
    print(f"Edition: {args.edition}. Dataset: {world['dataset']}")
    src = read_wav_16k(args.wav) if args.wav else synth_source()
    src = src[: len(src) - len(src) % (2 * FRAME)]  # whole 20 ms frames after resampling
    print(f"Source: {'your WAV' if args.wav else 'synthetic chirp 100 Hz -> 7 kHz + 1 kHz and 5 kHz tones'}, "
          f"{len(src) / SR_WIDE:.2f} s at {SR_WIDE} Hz")

    # [1] what the line removes
    band = bandpass(src, SR_WIDE)
    phone = resample_poly_np(band, up=1, down=2)
    codes = mulaw_encode(phone)
    phone_mu = mulaw_decode(codes)
    print("\n[1] Energy above 3.4 kHz, as a share of each signal's total")
    stages = [("source, 16 kHz", src, SR_WIDE), ("after 300-3400 Hz band-pass", band, SR_WIDE),
              ("after resample to 8 kHz", phone, SR_PHONE), ("after mu-law round trip", phone_mu, SR_PHONE)]
    above = {}
    for name, sig, sr in stages:
        above[name] = band_energy(sig, sr, 3400, sr / 2)
        shown = f"{above[name]:8.1f}" if above[name] > -200 else "  < -200"
        print(f"  {name:30s} {shown} dB")
    below = band_energy(src, SR_WIDE, 0, 300)
    print(f"  source energy below 300 Hz     {below:8.1f} dB  (also removed by the band-pass)")
    drop_filter = above["source, 16 kHz"] - above["after resample to 8 kHz"]
    drop_coded = above["source, 16 kHz"] - above["after mu-law round trip"]
    print(f"  drop through band-pass + 8 kHz: {drop_filter:.1f} dB; after mu-law: {drop_coded:.1f} dB "
          f"(mu-law noise is broadband)")
    assert above["after resample to 8 kHz"] < -40, "band-pass + 8 kHz must leave under -40 dB above 3.4 kHz"
    if not args.wav:  # chirp thresholds; speech has far less energy above 3.4 kHz to begin with
        assert above["source, 16 kHz"] > -10, "source must carry energy above 3.4 kHz"
        assert drop_filter > 40 and drop_coded > 40, "phone path must be more than 40 dB down above 3.4 kHz"
        frozen = [round(above[name], 1) for name, _, _ in stages if name != "after 300-3400 Hz band-pass"]
        assert frozen == [-2.9, -68.6, -46.0] and (round(drop_filter, 1), round(drop_coded, 1)) == (65.7, 43.1)

    # [2] is mu-law the problem?
    print("\n[2] Round-trip SNR on the 8 kHz phone-band signal")
    print(f"  {'level':>14s} {'mu-law 8-bit':>13s} {'linear 8-bit':>13s}")
    snrs = {}
    for level_db in (-3, -33):
        x = phone / np.max(np.abs(phone)) * 10 ** (level_db / 20)
        mu = snr_db(x, mulaw_decode(mulaw_encode(x)))
        lin = snr_db(x, linear8_round_trip(x))
        snrs[level_db] = (mu, lin)
        print(f"  {f'peak {level_db} dBFS':>14s} {mu:10.1f} dB {lin:10.1f} dB")
    print(f"  mu-law moves {snrs[-3][0] - snrs[-33][0]:.1f} dB over a 30 dB level drop; "
          f"linear moves {snrs[-3][1] - snrs[-33][1]:.1f} dB")
    assert snrs[-33][0] - snrs[-33][1] > 20, "at -33 dBFS mu-law should beat 8-bit linear by 20 dB"
    if not args.wav:  # chirp thresholds; speech's higher crest factor costs mu-law a few dB at -33
        assert min(snrs[-3][0], snrs[-33][0]) > 30, "mu-law should stay above 30 dB SNR"
        assert snrs[-3][0] - snrs[-33][0] < 5 < snrs[-3][1] - snrs[-33][1]
        assert [round(v, 1) for v in (*snrs[-3], *snrs[-33])] == [37.7, 40.9, 34.8, 9.5], "frozen SNRs moved"
    payload = codes.tobytes()
    n_frames = len(payload) // FRAME
    print(f"  mu-law payload: {len(payload):,} bytes = {n_frames} frames of {FRAME} bytes (20 ms each)")
    assert len(payload) % FRAME == 0 and n_frames * 20 == round(1000 * len(src) / SR_WIDE)

    # [3] burst loss
    r = 0.5
    print(f"\n[3] Gilbert-Elliott loss on 20 ms frames, r = {r} (mean burst {1 / r:.1f} frames = "
          f"{20 / r:.0f} ms), 50,000 frames x 10 seeds")
    print(f"  {'target':>6s} {'p':>8s} {'realised loss (min-max)':>27s} {'mean burst':>11s}   netem equivalent")
    for target in (0.01, 0.05, 0.10):
        p = ge_params(target, r)
        losses, bursts = [], []
        for s in range(10):
            mask = gilbert_elliott(50_000, p, r, seed=seed + s)
            losses.append(mask.mean())
            bursts.extend(burst_lengths(mask))
        mean_loss, mean_burst = float(np.mean(losses)), float(np.mean(bursts))
        print(f"  {target:6.0%} {p:8.5f} {mean_loss:9.4f} ({min(losses):.4f}-{max(losses):.4f}) "
              f"{mean_burst:9.2f}    netem loss gemodel {100 * p:.2f}% {100 * r:.0f}% 100% 0%")
        assert abs(mean_loss - target) / target < 0.05, "realised loss should match p/(p+r)"
        assert abs(mean_burst - 1 / r) < 0.05, "mean burst should match 1/r"

    mask5 = gilbert_elliott(n_frames, ge_params(0.05, r), r, seed=seed)
    zero5 = apply_loss(phone_mu, mask5, "zero")
    rep5 = apply_loss(phone_mu, mask5, "repeat")
    print(f"  this clip at 5%: {int(mask5.sum())} of {n_frames} frames lost, bursts {burst_lengths(mask5)}")
    if not args.wav:
        assert (int(mask5.sum()), burst_lengths(mask5)) == world["clip_loss5_frozen"], "seeded loss draw moved"
    print(f"  waveform SNR vs the unlost phone signal: zero fill {snr_db(phone_mu, zero5):.1f} dB, "
          f"repeat fill {snr_db(phone_mu, rep5):.1f} dB")

    # [4] noise at a fixed SNR
    rng = np.random.default_rng(seed)
    noise = resample_poly_np(bandpass(rng.standard_normal(len(src)), SR_WIDE), 1, 2)
    noisy = mix_snr(phone, noise, 10.0)
    realised = snr_db(phone, noisy)
    print(f"\n[4] Noise mixed at a 10 dB target: realised {realised:.2f} dB")
    assert abs(realised - 10.0) < 0.01

    # [5] write the source and four conditions
    noisy_mu = mulaw_decode(mulaw_encode(noisy))
    conditions = [
        ("00_source_16k.wav", src, SR_WIDE),
        ("01_phone_mulaw.wav", phone_mu, SR_PHONE),
        ("02_phone_mulaw_loss5.wav", zero5, SR_PHONE),
        ("03_phone_mulaw_snr10.wav", noisy_mu, SR_PHONE),
        ("04_phone_mulaw_snr10_loss5.wav", apply_loss(noisy_mu, mask5, "zero"), SR_PHONE),
    ]
    print(f"\n[5] Files in {args.out}/ (16-bit PCM WAV)")
    for name, sig, sr in conditions:
        size = write_wav(os.path.join(args.out, name), sig, sr)
        print(f"  {name:32s} {sr:5d} Hz {size:8,d} bytes")
        if not args.wav:
            assert size == 44 + 2 * len(sig) == 44 + 2 * 4 * sr

    # [6] which conditions to run
    factors = matrix_factors(world)
    rows = condition_matrix(factors)
    full = int(np.prod([len(v) for v in factors.values()]))
    covered, needed = pair_coverage(rows, factors)
    triples = {(row["carrier"], row["codec_chain"], row["loss"]) for row in rows}
    with open(os.path.join(args.out, "conditions.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(factors))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n[6] Condition matrix: full factorial {full} cells; design {len(rows)} rows "
          f"({len(triples)} distinct carrier x codec chain x loss cells)")
    print(f"  level pairs covered: {covered} of {needed} across all 10 factor pairs")
    for row in rows[:3]:
        print("  " + ", ".join(row.values()))
    assert full == 324 and len(rows) == 36 and len(triples) == 36 and covered == needed
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
