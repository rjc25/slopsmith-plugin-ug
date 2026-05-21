"""Stem separation via Demucs on Replicate API.

Adapted from slopsmith-stems/stem_separate.py for use as a library
with progress callbacks instead of print/tqdm.
"""

import os
from pathlib import Path

import replicate
import requests


DEMUCS_MODEL = "cjwbw/demucs:25a173108cff36ef9f80f854c162d01df9e6528be175794b81571f6e0feea7e1"
STEMS = ["drums", "bass", "vocals", "guitar", "other"]


def separate_stems(audio_path: Path, output_dir: Path,
                   api_token: str = None,
                   on_progress=None) -> dict:
    """Send audio to Demucs via Replicate and download stems.

    Args:
        audio_path: Path to audio file (mp3/ogg/wav)
        output_dir: Directory to save stem files
        api_token: Replicate API token (uses env var if not provided)
        on_progress: Callback(message, stem_name) for progress reporting

    Returns:
        Dict mapping stem name to file path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    def report(msg, stem=None):
        if on_progress:
            on_progress(msg, stem)

    # Set API token if provided
    old_token = os.environ.get("REPLICATE_API_TOKEN")
    if api_token:
        os.environ["REPLICATE_API_TOKEN"] = api_token

    try:
        report("Uploading audio to Demucs (Replicate)...")

        with open(audio_path, "rb") as f:
            output = replicate.run(
                DEMUCS_MODEL,
                input={
                    "audio": f,
                    "stem": "none",  # Return all stems
                }
            )

        stem_paths = {}
        for stem_url in output:
            url_lower = str(stem_url).lower()
            stem_name = None
            for s in STEMS:
                if s in url_lower:
                    stem_name = s
                    break

            if stem_name is None:
                continue

            stem_path = output_dir / f"{stem_name}.mp3"
            report(f"Downloading {stem_name} stem...", stem_name)

            response = requests.get(stem_url, stream=True)
            response.raise_for_status()
            with open(stem_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            stem_paths[stem_name] = stem_path

        report(f"Stem separation complete ({len(stem_paths)} stems)")
        return stem_paths

    finally:
        # Restore original token
        if api_token:
            if old_token:
                os.environ["REPLICATE_API_TOKEN"] = old_token
            else:
                os.environ.pop("REPLICATE_API_TOKEN", None)
