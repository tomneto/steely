"""Shared audio helpers for :mod:`steely.stt` adapters.

Resampling and format conversion live here (and are called from inside each
adapter) so every backend gets identical DSP — the worker never resamples.
"""
from steely.stt.audio.resample import pcm16le_to_float32le, to_backend_pcm

__all__ = ["to_backend_pcm", "pcm16le_to_float32le"]
