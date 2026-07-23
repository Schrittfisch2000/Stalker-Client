from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from . import main, safari_hls_fix

PROCESS_STOP_TIMEOUT_SECONDS = 5.0
_expected_ffmpeg_stops: set[str] = set()
_original_ffmpeg_command = safari_hls_fix._ffmpeg_command


def _stable_live_ffmpeg_command(
    media_type: str,
    directory: Path,
    playlist: Path,
    start_number: int,
) -> list[str]:
    command = _original_ffmpeg_command(media_type, directory, playlist, start_number)
    if media_type != "itv":
        return command

    while "-use_wallclock_as_timestamps" in command:
        index = command.index("-use_wallclock_as_timestamps")
        del command[index:index + 2]

    if "-fflags" in command:
        index = command.index("-fflags") + 1
        flags = [flag for flag in command[index].split("+") if flag and flag != "igndts"]
        command[index] = "+" + "+".join(flags)

    audio_codec = command.index("-c:a")
    command[audio_codec:audio_codec] = ["-af", "aresample=async=1000:first_pts=0"]

    return command


async def _wait_for_process_exit(process: Any) -> None:
    try:
        await asyncio.wait_for(process.wait(), timeout=PROCESS_STOP_TIMEOUT_SECONDS)
    except TimeoutError:
        if process.returncode is None:
            process.kill()
        await process.wait()


async def stop_hls_session(session_id: str, session: dict[str, Any]) -> None:
    _expected_ffmpeg_stops.add(session_id)

    proxy_task = session.get("proxy_task")
    if proxy_task is not None and not proxy_task.done():
        proxy_task.cancel()

    process = session.get("process")
    if process is not None and process.returncode is None:
        process.terminate()

    if proxy_task is not None:
        try:
            await proxy_task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            main.logger.warning(
                "TS-Proxy-Task beim Beenden fehlgeschlagen: Session=%s, Fehler=%s",
                session_id,
                exc,
            )

    if process is not None:
        await _wait_for_process_exit(process)

    directory = session.get("directory")
    if directory:
        main.shutil.rmtree(Path(directory), ignore_errors=True)

    if main._hls_sessions.get(session_id) is session:
        main._hls_sessions.pop(session_id, None)
    main.logger.info("HLS-Session sauber beendet: %s", session_id)


async def _log_ffmpeg(session_id: str, process: asyncio.subprocess.Process) -> None:
    lines: list[str] = []
    try:
        if process.stderr is not None:
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if text:
                    lines.append(text)
                    if len(lines) > 20:
                        lines.pop(0)

        code = await process.wait()
        expected = session_id in _expected_ffmpeg_stops
        if code != 0 and not expected:
            main.logger.error(
                "FFmpeg-HLS %s beendet (%s): %s",
                session_id,
                code,
                " | ".join(lines[-8:]),
            )
        elif code != 0:
            main.logger.info("FFmpeg-HLS %s erwartungsgemäß beendet (%s)", session_id, code)
        else:
            main.logger.info("FFmpeg-HLS %s beendet", session_id)
    finally:
        _expected_ffmpeg_stops.discard(session_id)


async def _cleanup_hls_sessions() -> None:
    while True:
        await asyncio.sleep(30)
        now = time.time()
        for session_id, session in list(main._hls_sessions.items()):
            max_idle = 60 if session.get("media_type") == "itv" else 300
            if now - session["last_access"] <= max_idle:
                continue
            await stop_hls_session(session_id, session)


async def _shutdown_hls_sessions() -> None:
    cleanup_task = main._cleanup_task
    if cleanup_task is not None:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

    for session_id, session in list(main._hls_sessions.items()):
        await stop_hls_session(session_id, session)


def install() -> None:
    safari_hls_fix._ffmpeg_command = _stable_live_ffmpeg_command
    main.log_ffmpeg = _log_ffmpeg
    main.cleanup_hls_sessions = _cleanup_hls_sessions

    if _shutdown_hls_sessions not in main.app.router.on_shutdown:
        main.app.router.on_shutdown.insert(0, _shutdown_hls_sessions)
