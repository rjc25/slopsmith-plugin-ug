"""Ultimate Guitar plugin — API routes for searching tabs and building CDLC."""

import asyncio
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

    @app.websocket("/ws/plugins/ultimate_guitar/build")
    async def ws_build(websocket: WebSocket, tab_url: str):
        """Build CDLC from a UG tab URL with real-time progress."""
        await websocket.accept()

        dlc = _get_dlc_dir()
        if not dlc:
            await websocket.send_json({"error": "DLC folder not configured"})
            await websocket.close()
            return

        progress_queue = asyncio.Queue()

        def _do_build():
            def report(stage, pct):
                progress_queue.put_nowait({"stage": stage, "progress": pct})

            try:
                import base64, re

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
                report(f"Selected {len(track_indices)} tracks: {', '.join(arr_names)}", 25)

                report("Generating MIDI audio...", 35)
                midi_audio = os.path.join(tempfile.mkdtemp(), "midi")
                midi_audio_path = gp_to_audio(str(gp_tmp), midi_audio)

                report("Converting tab to Rocksmith XML...", 55)
                xml_dir = tempfile.mkdtemp()
                xml_files = convert_file(str(gp_tmp), xml_dir,
                                         track_indices=track_indices,
                                         audio_offset=0.0,
                                         arrangement_names=name_map)

                title = song.title or gp_tmp.stem
                artist = song.artist or "Unknown"
                safe_t = re.sub(r'[<>:"/\\|?*]', '_', title)
                safe_a = re.sub(r'[<>:"/\\|?*]', '_', artist)
                output = str(dlc / f"{safe_t}_{safe_a}_midi_p.psarc")

                def on_progress(msg, pct):
                    mapped = 65 + pct * 0.3
                    report(msg, mapped)

                report("Compiling SNG and packing PSARC...", 65)
                build_cdlc(
                    xml_paths=xml_files,
                    arrangement_names=arr_names,
                    audio_path=midi_audio_path,
                    title=f"{title} (MIDI)",
                    artist=artist,
                    album=song.album or "",
                    output_path=output,
                    on_progress=on_progress,
                )

                progress_queue.put_nowait({
                    "done": True,
                    "progress": 100,
                    "stage": "Complete!",
                    "filename": Path(output).name,
                    "tracks": ", ".join(arr_names),
                })

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
