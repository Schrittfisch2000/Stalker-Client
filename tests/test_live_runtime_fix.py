from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from app import main
from app.live_runtime_fix import (
    _expected_ffmpeg_stops,
    _log_ffmpeg,
    _stable_live_ffmpeg_command,
    stop_hls_session,
)


class FakeStderr:
    async def readline(self) -> bytes:
        return b""


class FakeProcess:
    def __init__(self) -> None:
        self.returncode: int | None = None
        self.stderr = FakeStderr()
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 255

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def wait(self) -> int:
        while self.returncode is None:
            await asyncio.sleep(0)
        return self.returncode


class LiveFfmpegCommandTests(unittest.TestCase):
    def test_normalized_transport_timestamps_are_not_replaced_by_wallclock(self) -> None:
        command = _stable_live_ffmpeg_command(
            "itv",
            Path("/tmp/live-runtime-test"),
            Path("/tmp/live-runtime-test/index.m3u8"),
            0,
        )

        self.assertNotIn("-use_wallclock_as_timestamps", command)
        flags = command[command.index("-fflags") + 1]
        self.assertIn("genpts", flags)
        self.assertIn("discardcorrupt", flags)
        self.assertNotIn("igndts", flags)


class HlsLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_cleanup_waits_for_ffmpeg_before_removing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "session"
            directory.mkdir()
            (directory / "index.m3u8.tmp").write_text("pending", encoding="utf-8")

            process = FakeProcess()
            blocker = asyncio.Event()
            proxy_task = asyncio.create_task(blocker.wait())
            session_id = "cleanup-test"
            session = {
                "process": process,
                "proxy_task": proxy_task,
                "directory": directory,
                "last_access": 0.0,
                "media_type": "itv",
            }
            main._hls_sessions[session_id] = session
            log_task = asyncio.create_task(_log_ffmpeg(session_id, process))

            await stop_hls_session(session_id, session)
            await log_task

            self.assertTrue(process.terminated)
            self.assertFalse(process.killed)
            self.assertTrue(proxy_task.cancelled())
            self.assertFalse(directory.exists())
            self.assertNotIn(session_id, main._hls_sessions)
            self.assertNotIn(session_id, _expected_ffmpeg_stops)


if __name__ == "__main__":
    unittest.main()
