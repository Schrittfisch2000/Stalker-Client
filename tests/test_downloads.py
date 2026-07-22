from __future__ import annotations

import unittest

from app.downloads import _content_disposition, _download_filename, _ffmpeg_download_command, _safe_download_name


class FakePortal:
    cookies = {"mac": "00:1A:79:00:00:00", "stb_lang": "de"}

    def portal_headers_for_stream(self) -> dict[str, str]:
        return {"User-Agent": "Test-Agent", "Referer": "http://portal.invalid/"}


class DownloadHelperTests(unittest.TestCase):
    def test_filename_is_sanitized_and_uses_mkv(self) -> None:
        self.assertEqual(_safe_download_name('  Film: Test?  '), "Film_ Test_")
        self.assertEqual(_download_filename('Film: Test?'), "Film_ Test_.mkv")
        self.assertEqual(_download_filename('Episode.mkv'), "Episode.mkv")

    def test_content_disposition_contains_ascii_and_utf8_names(self) -> None:
        value = _content_disposition("Ärger Folge 1.mkv")
        self.assertIn('filename="Arger Folge 1.mkv"', value)
        self.assertIn("filename*=UTF-8''%C3%84rger%20Folge%201.mkv", value)

    def test_ffmpeg_remuxes_without_reencoding(self) -> None:
        command = _ffmpeg_download_command("http://portal.invalid/video", FakePortal())
        self.assertIn("-c", command)
        self.assertEqual(command[command.index("-c") + 1], "copy")
        self.assertEqual(command[command.index("-f") + 1], "matroska")
        headers = command[command.index("-headers") + 1]
        self.assertIn("User-Agent: Test-Agent\r\n", headers)
        self.assertIn("Cookie: mac=00:1A:79:00:00:00; stb_lang=de\r\n", headers)


if __name__ == "__main__":
    unittest.main()
