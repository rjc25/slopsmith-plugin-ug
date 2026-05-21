"""Ultimate Guitar plugin — API routes for searching tabs and building CDLC."""

import asyncio
import base64
import os
import tempfile
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect

_get_dlc_dir = None


def setup(app, context):
    global _get_dlc_dir
    _get_dlc_dir = context["get_dlc_dir"]

    @app.get("/api/plugins/ultimate_guitar/search")
    async def search_ug(q: str):
        loop = asyncio.get_event_loop()

        def _search():
            try:
                import ug_client
                return ug_client.search(q)
            except Exception:
                pass
            try:
                from ug_browser import search
                return search(q)
            except Exception as e:
                if "404" in str(e):
                    return []  # No results found on UG
                if "403" in str(e):
                    raise RuntimeError("Cloudflare blocked the request. Try again in a moment.")
                raise RuntimeError(f"Ultimate Guitar search failed: {e}")

        try:
            results = await asyncio.wait_for(
                loop.run_in_executor(None, _search),
                timeout=60,
            )
            return {"results": results}
        except asyncio.TimeoutError:
            return {"error": "Search timed out (60s). Try again."}
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/plugins/ultimate_guitar/upload_audio")
    async def upload_audio(data: dict):
        """Receive an audio file as base64, save to temp, return server path."""
        audio_filename = data.get("filename", "")
        audio_b64 = data.get("data", "")
        if not audio_filename or not audio_b64:
            return {"error": "No audio file data"}

        try:
            audio_data = base64.b64decode(audio_b64)
        except Exception:
            return {"error": "Invalid audio file data"}

        audio_ext = Path(audio_filename).suffix.lower()
        if audio_ext not in ('.mp3', '.ogg', '.wav', '.flac'):
            return {"error": f"Unsupported audio format ({audio_ext}). Use MP3, OGG, WAV, or FLAC."}

        tmp_dir = Path(tempfile.mkdtemp())
        tmp = tmp_dir / audio_filename
        tmp.write_bytes(audio_data)
        return {"audio_path": str(tmp)}

    @app.websocket("/ws/plugins/ultimate_guitar/build")
    async def ws_build(websocket: WebSocket, tab_url: str,
                       audio_path: str = "",
                       audio_local_path: str = "",
                       stem_split: str = "",
                       replicate_key: str = ""):
        """Build CDLC from a UG tab URL with real-time progress.

        Supports optional real audio (via uploaded path or local path),
        auto-sync of chart timing to real audio, and Demucs stem separation.
        """
        await websocket.accept()

        dlc = _get_dlc_dir()
        if not dlc:
            await websocket.send_json({"error": "DLC folder not configured"})
            await websocket.close()
            return

        # Resolve real audio file if provided
        audio_tmp_path = None
        use_real_audio = False

        if audio_path and Path(audio_path).exists():
            audio_tmp_path = audio_path
            use_real_audio = True
        elif audio_local_path:
            p = Path(audio_local_path)
            if not p.exists():
                await websocket.send_json({"error": f"Audio file not found: {audio_local_path}"})
                await websocket.close()
                return
            if p.suffix.lower() not in ('.mp3', '.ogg', '.wav', '.flac'):
                await websocket.send_json({"error": f"Unsupported audio format ({p.suffix}). Use MP3, OGG, WAV, or FLAC."})
                await websocket.close()
                return
            audio_tmp_path = str(p)
            use_real_audio = True

        do_stems = stem_split == "1" and use_real_audio

        if do_stems and not replicate_key:
            await websocket.send_json({"error": "Replicate API key required for stem separation"})
            await websocket.close()
            return

        progress_queue = asyncio.Queue()

        def _do_build():
            def report(stage, pct):
                progress_queue.put_nowait({"stage": stage, "progress": pct})

            try:
                import re

                report("Downloading tab from Ultimate Guitar...", 5)
                try:
                    from ug_browser import download as ug_download
                    dl = ug_download(tab_url)
                except ImportError:
                    import ug_client
                    dl = ug_client.download(tab_url)

                gp_data = base64.b64decode(dl["data_base64"])
                filename = dl["filename"]
                gp_tmp = Path(tempfile.mkdtemp()) / filename
                gp_tmp.write_bytes(gp_data)

                report("Parsing Guitar Pro file...", 15)
                from gp2rs import convert_file, auto_select_tracks
                from gp2midi import gp_to_audio
                from cdlc_builder import build_cdlc
                import guitarpro

                try:
                    song = guitarpro.parse(str(gp_tmp))
                except Exception as e:
                    err = str(e)
                    if "unsupported" in err.lower() or "version" in err.lower():
                        ext = Path(filename).suffix.lower()
                        progress_queue.put_nowait({"error": f"Unsupported Guitar Pro format ({ext}). Only GP3/GP4/GP5 are supported."})
                        return
                    raise

                track_indices, name_map = auto_select_tracks(str(gp_tmp))
                if not track_indices:
                    progress_queue.put_nowait({"error": "No guitar/bass tracks found in tab"})
                    return

                arr_names = [name_map.get(i, "Lead") for i in track_indices]
                report(f"Selected {len(track_indices)} tracks: {', '.join(arr_names)}", 20)

                # Always generate MIDI audio (needed for sync reference even with real audio)
                report("Generating MIDI audio...", 25)
                midi_audio = os.path.join(tempfile.mkdtemp(), "midi")
                midi_audio_path = gp_to_audio(str(gp_tmp), midi_audio)

                # Determine final audio and offset
                final_audio_path = midi_audio_path
                audio_offset = 0.0

                if use_real_audio and audio_tmp_path:
                    final_audio_path = audio_tmp_path

                    # Auto-sync: cross-correlate MIDI against real audio
                    report("Auto-syncing chart to audio...", 35)
                    try:
                        from audio_sync import find_offset
                        offset, confidence = find_offset(midi_audio_path, audio_tmp_path)
                        audio_offset = offset
                        conf_str = f"(confidence: {confidence:.1f}x)"
                        if confidence < 3.0:
                            conf_str += " [LOW - audio may differ significantly]"
                        report(f"Auto-sync offset: {offset:+.3f}s {conf_str}", 42)
                    except Exception as e:
                        report(f"Auto-sync failed ({e}), using offset 0.0", 42)
                        audio_offset = 0.0

                report("Converting tab to Rocksmith XML...", 48)
                xml_dir = tempfile.mkdtemp()
                xml_files = convert_file(str(gp_tmp), xml_dir,
                                         track_indices=track_indices,
                                         audio_offset=audio_offset,
                                         arrangement_names=name_map)

                title = song.title or gp_tmp.stem
                artist = song.artist or "Unknown"
                safe_t = re.sub(r'[<>:"/\\|?*]', '_', title)
                safe_a = re.sub(r'[<>:"/\\|?*]', '_', artist)

                # MIDI suffix only when using MIDI audio
                if use_real_audio:
                    output = str(dlc / f"{safe_t}_{safe_a}_p.psarc")
                    display_title = title
                else:
                    output = str(dlc / f"{safe_t}_{safe_a}_midi_p.psarc")
                    display_title = f"{title} (MIDI)"

                def on_progress(msg, pct):
                    mapped = 55 + pct * 0.25
                    report(msg, mapped)

                report("Compiling SNG and packing PSARC...", 55)
                build_cdlc(
                    xml_paths=xml_files,
                    arrangement_names=arr_names,
                    audio_path=final_audio_path,
                    title=display_title,
                    artist=artist,
                    album=song.album or "",
                    output_path=output,
                    on_progress=on_progress,
                )

                # Stem separation (only with real audio)
                stem_info = None
                if do_stems:
                    report("Separating stems with Demucs...", 82)
                    try:
                        from stem_separate import separate_stems
                        stem_dir = Path(output).parent / f"{safe_t}_{safe_a}_stems"

                        def on_stem_progress(msg, stem=None):
                            report(f"Stems: {msg}", 85 if not stem else 90)

                        stems = separate_stems(
                            audio_path=Path(final_audio_path),
                            output_dir=stem_dir,
                            api_token=replicate_key,
                            on_progress=on_stem_progress,
                        )
                        stem_names = list(stems.keys())
                        stem_info = f"Stems saved: {', '.join(stem_names)} in {stem_dir.name}/"
                        report(f"Stem separation complete ({len(stems)} stems)", 98)
                    except Exception as e:
                        report(f"Stem separation failed: {e}", 98)
                        stem_info = f"Stem separation failed: {e}"

                done_msg = {
                    "done": True,
                    "progress": 100,
                    "stage": "Complete!",
                    "filename": Path(output).name,
                    "tracks": ", ".join(arr_names),
                }
                if use_real_audio:
                    done_msg["audio_offset"] = f"{audio_offset:+.3f}s"
                if stem_info:
                    done_msg["stems"] = stem_info

                progress_queue.put_nowait(done_msg)

            except Exception as e:
                import traceback
                traceback.print_exc()
                progress_queue.put_nowait({"error": str(e)})

        loop = asyncio.get_event_loop()
        build_task = loop.run_in_executor(None, _do_build)

        try:
            while True:
                try:
                    msg = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                    await websocket.send_json(msg)
                    if msg.get("done") or msg.get("error"):
                        break
                except asyncio.TimeoutError:
                    if build_task.done():
                        break
        except WebSocketDisconnect:
            pass

        await websocket.close()
