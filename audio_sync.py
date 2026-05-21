"""Audio synchronization via cross-correlation of spectrograms.

Finds the time offset between MIDI reference audio and real audio so that
GP charts can be automatically aligned to a real recording.

Adapted from slopsmith-stems/audio_sync.py for use as a library.
"""

import subprocess

import numpy as np


def load_audio_mono(filepath: str, sr: int = 22050, duration: float = None) -> np.ndarray:
    """Load audio file as mono numpy array using ffmpeg."""
    cmd = [
        "ffmpeg", "-i", str(filepath),
        "-ac", "1",
        "-ar", str(sr),
        "-f", "f32le",
        "-acodec", "pcm_f32le",
    ]
    if duration:
        cmd.extend(["-t", str(duration)])
    cmd.append("pipe:1")

    result = subprocess.run(cmd, capture_output=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()[:200]}")

    audio = np.frombuffer(result.stdout, dtype=np.float32)
    return audio


def compute_spectrogram(audio: np.ndarray, sr: int = 22050,
                        n_fft: int = 2048, hop_length: int = 512) -> np.ndarray:
    """Compute log-magnitude spectrogram using numpy STFT."""
    n_frames = 1 + (len(audio) - n_fft) // hop_length
    if n_frames <= 0:
        raise ValueError("Audio too short for spectrogram")

    window = np.hanning(n_fft)
    frames = np.zeros((n_fft, n_frames))
    for i in range(n_frames):
        start = i * hop_length
        frames[:, i] = audio[start:start + n_fft] * window

    spec = np.abs(np.fft.rfft(frames, axis=0))
    spec = np.log1p(spec)
    return spec


def cross_correlate_spectrograms(spec_a: np.ndarray, spec_b: np.ndarray) -> np.ndarray:
    """Cross-correlate two spectrograms along the time axis."""
    energy_a = np.sum(spec_a, axis=0)
    energy_b = np.sum(spec_b, axis=0)

    energy_a = (energy_a - np.mean(energy_a)) / (np.std(energy_a) + 1e-8)
    energy_b = (energy_b - np.mean(energy_b)) / (np.std(energy_b) + 1e-8)

    correlation = np.correlate(energy_a, energy_b, mode="full")
    return correlation


def find_offset(midi_path: str, real_audio_path: str,
                sr: int = 22050, duration: float = 30.0,
                hop_length: int = 512) -> tuple[float, float]:
    """Find the time offset between MIDI reference audio and real audio.

    Args:
        midi_path: MIDI-generated audio (reference timing from GP file)
        real_audio_path: Real audio recording to align to
        sr: Sample rate for analysis
        duration: Seconds to analyze
        hop_length: STFT hop length

    Returns:
        (offset_seconds, confidence) tuple.
        offset_seconds: positive means real audio starts AFTER MIDI.
        confidence: peak-to-noise ratio (>3.0 is good).
    """
    audio_midi = load_audio_mono(midi_path, sr=sr, duration=duration)
    audio_real = load_audio_mono(real_audio_path, sr=sr, duration=duration)

    spec_midi = compute_spectrogram(audio_midi, sr=sr, hop_length=hop_length)
    spec_real = compute_spectrogram(audio_real, sr=sr, hop_length=hop_length)

    correlation = cross_correlate_spectrograms(spec_midi, spec_real)

    peak_index = np.argmax(correlation)
    center = len(spec_midi[0]) - 1

    frame_offset = peak_index - center
    offset_seconds = frame_offset * hop_length / sr

    peak_value = correlation[peak_index]
    noise_floor = np.median(np.abs(correlation))
    confidence = float(peak_value / (noise_floor + 1e-8))

    return float(offset_seconds), confidence


def find_offset_per_segment(midi_path: str, real_audio_path: str,
                            sr: int = 22050, segment_duration: float = 15.0,
                            hop_length: int = 512) -> dict:
    """Find per-segment offsets to detect and correct drift.

    Instead of one global offset, splits both audio files into segments
    and cross-correlates each pair. Returns a warp curve that handles
    tempo drift, different intros, and local timing variations.

    Returns: {
        "segments": [{"start": 0.0, "end": 15.0, "offset": 0.12, "confidence": 8.5}, ...],
        "global_offset": 0.11,       # median of all segments
        "max_drift": 0.08,           # max difference between any two segments
        "has_drift": False,          # True if max_drift > 0.05s
        "warp_points": [(0.0, 0.12), (15.0, 0.10), ...],  # (time, offset) pairs
    }
    """
    audio_midi = load_audio_mono(midi_path, sr=sr)
    audio_real = load_audio_mono(real_audio_path, sr=sr)

    total_duration = min(len(audio_midi), len(audio_real)) / sr
    if total_duration < segment_duration * 2:
        # Song too short for segmented analysis, fall back to global
        offset, confidence = find_offset(midi_path, real_audio_path, sr=sr,
                                         duration=total_duration, hop_length=hop_length)
        return {
            "segments": [{"start": 0.0, "end": total_duration, "offset": offset, "confidence": confidence}],
            "global_offset": offset,
            "max_drift": 0.0,
            "has_drift": False,
            "warp_points": [(0.0, offset), (total_duration, offset)],
        }

    segments = []
    seg_start = 0.0

    while seg_start + segment_duration <= total_duration:
        start_sample = int(seg_start * sr)
        end_sample = start_sample + int(segment_duration * sr)

        chunk_midi = audio_midi[start_sample:end_sample]
        chunk_real = audio_real[start_sample:end_sample]

        if len(chunk_midi) < sr or len(chunk_real) < sr:
            break

        try:
            spec_m = compute_spectrogram(chunk_midi, sr=sr, hop_length=hop_length)
            spec_r = compute_spectrogram(chunk_real, sr=sr, hop_length=hop_length)

            correlation = cross_correlate_spectrograms(spec_m, spec_r)
            peak_index = np.argmax(correlation)
            center = len(spec_m[0]) - 1

            frame_offset = peak_index - center
            offset_sec = frame_offset * hop_length / sr

            peak_value = correlation[peak_index]
            noise_floor = np.median(np.abs(correlation))
            confidence = float(peak_value / (noise_floor + 1e-8))

            segments.append({
                "start": round(seg_start, 2),
                "end": round(seg_start + segment_duration, 2),
                "offset": round(offset_sec, 4),
                "confidence": round(confidence, 1),
            })
        except Exception:
            pass  # Skip segments that fail (e.g., silence)

        seg_start += segment_duration

    if not segments:
        offset, confidence = find_offset(midi_path, real_audio_path, sr=sr, hop_length=hop_length)
        return {
            "segments": [{"start": 0.0, "end": total_duration, "offset": offset, "confidence": confidence}],
            "global_offset": offset,
            "max_drift": 0.0,
            "has_drift": False,
            "warp_points": [(0.0, offset), (total_duration, offset)],
        }

    offsets = [s["offset"] for s in segments]
    global_offset = float(np.median(offsets))
    max_drift = max(offsets) - min(offsets)

    warp_points = [(s["start"] + segment_duration / 2, s["offset"]) for s in segments]

    return {
        "segments": segments,
        "global_offset": round(global_offset, 4),
        "max_drift": round(max_drift, 4),
        "has_drift": max_drift > 0.05,
        "warp_points": warp_points,
    }


def apply_warp_to_time(original_time: float, warp_points: list) -> float:
    """Apply a warp curve to adjust a single timestamp.

    Uses linear interpolation between warp points. Each warp point
    is (center_time, offset_at_that_time).

    Returns the adjusted time (original_time - interpolated_offset).
    """
    if not warp_points:
        return original_time

    if len(warp_points) == 1:
        return original_time - warp_points[0][1]

    # Clamp to range
    if original_time <= warp_points[0][0]:
        return original_time - warp_points[0][1]
    if original_time >= warp_points[-1][0]:
        return original_time - warp_points[-1][1]

    # Linear interpolation between surrounding points
    for i in range(len(warp_points) - 1):
        t0, off0 = warp_points[i]
        t1, off1 = warp_points[i + 1]
        if t0 <= original_time <= t1:
            frac = (original_time - t0) / (t1 - t0)
            interpolated_offset = off0 + frac * (off1 - off0)
            return max(0, original_time - interpolated_offset)

    return original_time - warp_points[-1][1]
