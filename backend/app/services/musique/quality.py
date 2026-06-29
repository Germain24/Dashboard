"""Qualité audio (déduite du fichier) et statut d'achat Qobuz (fonctions pures)."""
from __future__ import annotations


def quality_tier(suffix: str, bits_per_sample: int | None, sample_rate_hz: int | None) -> str:
    """lossy (MP3) | cd (FLAC 16/≤48kHz) | hires (FLAC ≥24 bit ou >48kHz) | dsd."""
    ext = suffix.lower()
    if ext == ".dsf":
        return "dsd"
    if ext == ".mp3":
        return "lossy"
    # FLAC et autres lossless
    if (bits_per_sample or 0) >= 24 or (sample_rate_hz or 0) > 48000:
        return "hires"
    return "cd"


def _khz(sample_rate_hz: int | None) -> str:
    if not sample_rate_hz:
        return ""
    val = sample_rate_hz / 1000
    txt = (f"{val:.1f}".rstrip("0").rstrip(".")).replace(".", ",")
    return f"{txt} kHz"


def quality_label(suffix: str, bitrate_kbps: int | None,
                  sample_rate_hz: int | None, bits_per_sample: int | None) -> str:
    tier = quality_tier(suffix, bits_per_sample, sample_rate_hz)
    if tier == "dsd":
        return "DSD"
    if tier == "lossy":
        return f"MP3 ({bitrate_kbps} kbps)" if bitrate_kbps else "MP3"
    details = " · ".join(p for p in (
        f"{bits_per_sample} bit" if bits_per_sample else "",
        _khz(sample_rate_hz),
    ) if p)
    base = "FLAC CD" if tier == "cd" else "Hi-Res"
    return f"{base} ({details})" if details else base


def purchase_status(tier: str, qobuz_available: bool | None) -> str:
    """owned (déjà en qualité) | to_buy | unavailable | unknown."""
    if tier != "lossy":
        return "owned"
    if qobuz_available is True:
        return "to_buy"
    if qobuz_available is False:
        return "unavailable"
    return "unknown"
