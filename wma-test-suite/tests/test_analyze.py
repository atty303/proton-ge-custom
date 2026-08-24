#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave


SUITE_DIR = Path(__file__).resolve().parents[1]


class AnalyzeIntegrationTest(unittest.TestCase):
    def test_builds_s16le_baseline_for_wmav2_asf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            wav = root / "source.wav"
            corpus = root / "corpus"
            corpus.mkdir()
            artifact = corpus / "fixture.wma"
            report = root / "report.json"

            with wave.open(str(wav), "wb") as output:
                output.setnchannels(2)
                output.setsampwidth(2)
                output.setframerate(44100)
                output.writeframes(bytes(44100 * 2 * 2 // 10))
            subprocess.run(
                ["ffmpeg", "-v", "error", "-nostdin", "-i", str(wav), "-c:a", "wmav2", str(artifact)],
                check=True,
            )
            subprocess.run(
                [sys.executable, str(SUITE_DIR / "analyze.py"), str(corpus), "--output", str(report), "--jobs", "1"],
                check=True,
            )

            document = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(document["status"], "complete")
            self.assertEqual(document["summary"]["codecs"], {"wmav2": 1})
            self.assertEqual(document["artifacts"][0]["pcm"]["format"], "s16le")
            self.assertEqual(document["artifacts"][0]["pcm"]["channels"], 2)
            self.assertEqual(document["artifacts"][0]["pcm"]["sample_rate"], 44100)
            self.assertGreater(document["artifacts"][0]["pcm"]["frames"], 0)


if __name__ == "__main__":
    unittest.main()
