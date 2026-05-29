"""
Klasifikace vlaků z binárních souborů MQTT receiveru.
Adaptováno z klasifikace.ipynb pro přímou práci s .bin soubory.
"""
import struct
import math
import numpy as np
from pathlib import Path
from scipy.signal import butter, filtfilt, find_peaks, peak_widths, welch, peak_prominences


def _isna(x):
    """Náhrada za pd.isna – True pro None a NaN."""
    if x is None:
        return True
    try:
        return math.isnan(x)
    except TypeError:
        return False


def _notna(x):
    return not _isna(x)

from nastaveni import WAVE_SAMPLE_LEN, format_str

FS = 2000.0

# Záložní hardcoded databáze – použije se pouze pokud DB není dostupná
_TRAIN_DB_FALLBACK = [
    {"typ": "CZLoko1",            "pomer": 1.791667, "dvojkoli_mm": 2400},
    {"typ": "CZLoko2",            "pomer": 2.75,     "dvojkoli_mm": 2400},
    {"typ": "Škoda 380",          "pomer": 2.48,     "dvojkoli_mm": 2500},
    {"typ": "ALSTOM TRAXX 160",   "pomer": 2.988462, "dvojkoli_mm": 2600},
    {"typ": "ALSTOM TRAXX 160B",  "pomer": 2.996154, "dvojkoli_mm": 2600},
    {"typ": "ALSTOM TRAXX 140",   "pomer": 3.015385, "dvojkoli_mm": 2600},
    {"typ": "SIEMENS Vectron Dual","pomer": 3.0,     "dvojkoli_mm": 2700},
    {"typ": "SIEMENS Vectron CD", "pomer": 2.166667, "dvojkoli_mm": 3000},
    {"typ": "SIEMENS Vectron",    "pomer": 2.3,      "dvojkoli_mm": 3000},
    {"typ": "Škoda 363",          "pomer": 1.59375,  "dvojkoli_mm": 3200},
    {"typ": "Pendolino",          "pomer": 6.037037, "dvojkoli_mm": 2700},
    {"typ": "LEO Express",        "pomer": 4.925926, "dvojkoli_mm": 2700},
    {"typ": "Panter",             "pomer": 6.916667, "dvojkoli_mm": 2400},
    {"typ": "Elefant",            "pomer": 6.3,      "dvojkoli_mm": 2600},
    {"typ": "Newag Dragon 2",     "pomer": 1.00,     "dvojkoli_mm": 1950},
]


def _get_train_db():
    """Načte databázi typů vlaků z SQLite; při chybě vrátí záložní seznam."""
    try:
        from instance.data_funkce import dej_train_db_pro_klasifikaci
        db = dej_train_db_pro_klasifikaci()
        return db if db else _TRAIN_DB_FALLBACK
    except Exception:
        return _TRAIN_DB_FALLBACK

_PACKET_SIZE = struct.calcsize(format_str)
_CHAN0_VLT_START = 7
_CHAN0_INT_START = 7 + WAVE_SAMPLE_LEN
_CHAN1_VLT_START = 7 + 2 * WAVE_SAMPLE_LEN
_CHAN1_INT_START = 7 + 3 * WAVE_SAMPLE_LEN


def load_bin_channels(filepath):
    """
    Načte .bin soubor (konkatenované MQTT packety) a vrátí
    (chan_0_int, chan_0_vlt, chan_1_int, chan_1_vlt) jako numpy float pole.

    Pořadí kanálů v paketu dle format_str:
      indices 7..7+1024         → chan_0_vlt
      indices 7+1024..7+2048    → chan_0_int
      indices 7+2048..7+3072    → chan_1_vlt
      indices 7+3072..7+4096    → chan_1_int
    """
    raw = Path(filepath).read_bytes()
    n_packets = len(raw) // _PACKET_SIZE
    if n_packets == 0:
        empty = np.array([], dtype=float)
        return empty, empty, empty, empty

    chan_0_vlt = []
    chan_0_int = []
    chan_1_vlt = []
    chan_1_int = []

    for i in range(n_packets):
        chunk = raw[i * _PACKET_SIZE : (i + 1) * _PACKET_SIZE]
        data = struct.unpack(format_str, chunk)
        chan_0_vlt.extend(data[_CHAN0_VLT_START : _CHAN0_VLT_START + WAVE_SAMPLE_LEN])
        chan_0_int.extend(data[_CHAN0_INT_START : _CHAN0_INT_START + WAVE_SAMPLE_LEN])
        chan_1_vlt.extend(data[_CHAN1_VLT_START : _CHAN1_VLT_START + WAVE_SAMPLE_LEN])
        chan_1_int.extend(data[_CHAN1_INT_START : _CHAN1_INT_START + WAVE_SAMPLE_LEN])

    return (
        np.array(chan_0_int, dtype=float),
        np.array(chan_0_vlt, dtype=float),
        np.array(chan_1_int, dtype=float),
        np.array(chan_1_vlt, dtype=float),
    )


def _classify_locomotive(dt12, dt23, dt34, measured_ratio,
                          base_tolerance=0.15, max_speed_kmh=170.0):
    if _isna(dt12) or _isna(measured_ratio) or dt12 <= 0:
        return "neurčen"

    is_coco = 0.85 <= measured_ratio <= 1.15

    if _notna(dt34):
        if is_coco:
            if _notna(dt23) and abs(dt12 - dt23) / dt12 > 0.15:
                return "neurčen"
        else:
            if abs(dt12 - dt34) / dt12 > 0.15:
                return "neurčen"

    if is_coco and _notna(dt23):
        prumerny_cas = (dt12 + dt23) / 2.0
    elif _notna(dt34) and dt34 > 0:
        prumerny_cas = (dt12 + dt34) / 2.0
    else:
        prumerny_cas = dt12

    best_match = "neurčen"
    smallest_diff = float("inf")
    best_tolerance = base_tolerance

    for train in _get_train_db():
        diff = abs(measured_ratio - train["pomer"])
        rozvor_m = train["dvojkoli_mm"] / 1000.0
        rychlost_kmh = (rozvor_m / prumerny_cas) * 3.6
        current_tolerance = max(base_tolerance, train["pomer"] * 0.06)

        if rychlost_kmh <= max_speed_kmh and diff < smallest_diff:
            smallest_diff = diff
            best_match = train["typ"]
            best_tolerance = current_tolerance

    return best_match if smallest_diff <= best_tolerance else "neurčen"


def _calculate_speed(typ, dt12, dt23, dt34, measured_ratio):
    if typ in ("neurčen", "chyba_měření") or _isna(dt12) or dt12 <= 0:
        return None

    is_coco = _notna(measured_ratio) and 0.85 <= measured_ratio <= 1.15

    if is_coco and _notna(dt23):
        prumerny_cas = (dt12 + dt23) / 2.0
    elif _notna(dt34) and dt34 > 0:
        prumerny_cas = (dt12 + dt34) / 2.0
    else:
        prumerny_cas = dt12

    for train in _get_train_db():
        if train["typ"] == typ:
            return round((train["dvojkoli_mm"] / 1000.0 / prumerny_cas) * 3.6, 1)

    return None


def classify_bin_file(filepath, threshold=170, min_distance_s=0.05,
                      lowcut=1.0, highcut=50.0, filter_order=4, cut_samples=300):
    """
    Klasifikuje vlak ze .bin souboru.
    Vrátí dict s klíči:
      typ_vlaku, rychlost_kmh, poskozeni_podvozku, psd_mean,
      n_peaku, loco_ratio, chyba_mereni
    """
    seg, seg_vlt_raw, _, _ = load_bin_channels(filepath)

    if len(seg) <= cut_samples:
        return {
            "typ_vlaku": "neurčen",
            "rychlost_kmh": None,
            "poskozeni_podvozku": False,
            "psd_mean": None,
            "n_peaku": 0,
            "loco_ratio": None,
            "chyba_mereni": False,
            "chyba": "příliš krátký záznam",
        }

    b, a = butter(N=filter_order,
                  Wn=[lowcut / (FS / 2), highcut / (FS / 2)],
                  btype="bandpass")
    x_hp_full = filtfilt(b, a, seg)
    x_hp = x_hp_full[cut_samples:]
    seg_vlt_rez = seg_vlt_raw[cut_samples:]

    distance = int(min_distance_s * FS)
    peaks, _ = find_peaks(-x_hp, height=threshold, distance=distance)

    # Časování vrcholů
    dt12 = dt23 = dt34 = loco_ratio = float("nan")
    if len(peaks) >= 4:
        t = peaks / FS
        dt12 = t[1] - t[0]
        dt23 = t[2] - t[1]
        dt34 = t[3] - t[2]
        loco_ratio = dt23 / dt12 if dt12 > 0 else float("nan")

    # PSD analýza poškození podvozku (75–100 Hz)
    seg_vlt_no_dc = seg_vlt_rez - np.mean(seg_vlt_rez)
    freqs, psd = welch(seg_vlt_no_dc, fs=FS, nperseg=1024)
    maska = (freqs >= 75) & (freqs <= 100)
    psd_mean = float(np.mean(psd[maska]))
    poskozeni = psd_mean > 1000

    # Detekce chyby měření: první vrchol příliš brzo
    first_t = float((peaks[0] + cut_samples) / FS) if len(peaks) > 0 else float("nan")
    chyba_mereni = (not np.isnan(first_t)) and (first_t < 0.524)

    if chyba_mereni:
        typ = "chyba_měření"
        rychlost = None
    else:
        typ = _classify_locomotive(dt12, dt23, dt34, loco_ratio)
        rychlost = _calculate_speed(typ, dt12, dt23, dt34, loco_ratio)

    return {
        "typ_vlaku": typ,
        "rychlost_kmh": rychlost,
        "poskozeni_podvozku": poskozeni,
        "psd_mean": round(psd_mean, 1),
        "n_peaku": int(len(peaks)),
        "loco_ratio": None if np.isnan(loco_ratio) else round(float(loco_ratio), 3),
        "chyba_mereni": chyba_mereni,
    }


def get_waveform_data(filepath, max_points=5000,
                      threshold=170, min_distance_s=0.05,
                      lowcut=1.0, highcut=50.0, filter_order=4, cut_samples=300):
    """
    Vrátí data pro vykreslení grafu – všechny 4 kanály.
    Returns: (time_list, ch0_int, ch0_vlt, ch1_int, ch1_vlt, peaks_time_list)
    """
    seg, seg_vlt, seg1_int, seg1_vlt = load_bin_channels(filepath)
    if len(seg) == 0:
        return [], [], [], [], [], []

    b, a = butter(N=filter_order,
                  Wn=[lowcut / (FS / 2), highcut / (FS / 2)],
                  btype="bandpass")

    def _filter_ds(arr):
        if len(arr) == 0:
            return []
        f = filtfilt(b, a, arr)
        step = max(1, len(f) // max_points)
        return [round(float(f[i]), 2) for i in range(0, len(f), step)]

    x_hp_full = filtfilt(b, a, seg)
    total = len(x_hp_full)
    step = max(1, total // max_points)
    t_ds       = [round(i / FS, 4)          for i in range(0, total, step)]
    s_ch0_int  = [round(float(x_hp_full[i]), 2) for i in range(0, total, step)]
    s_ch0_vlt  = _filter_ds(seg_vlt)
    s_ch1_int  = _filter_ds(seg1_int)
    s_ch1_vlt  = _filter_ds(seg1_vlt)

    # Detekce vrcholů (na oříznutém ch0_int)
    peaks, _ = find_peaks(-x_hp_full[cut_samples:], height=threshold,
                          distance=int(min_distance_s * FS))
    peaks_t = [round((p + cut_samples) / FS, 4) for p in peaks]

    return t_ds, s_ch0_int, s_ch0_vlt, s_ch1_int, s_ch1_vlt, peaks_t
