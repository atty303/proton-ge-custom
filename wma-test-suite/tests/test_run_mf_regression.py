#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
import wave


SUITE_DIR = Path(__file__).resolve().parents[1]


class MediaFoundationRegressionRunnerTest(unittest.TestCase):
    def test_reports_a_truncated_candidate_as_a_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            steam = root / "steam"
            corpus = root / "corpus"
            steam.mkdir()
            corpus.mkdir()
            wav = root / "source.wav"
            fixture = corpus / "fixture.wma"
            baseline = root / "baseline.json"
            reference = root / "reference.s16le"
            fake_proton = root / "proton"
            decoder = root / "mf-decode.exe"

            with wave.open(str(wav), "wb") as output:
                output.setnchannels(2)
                output.setsampwidth(2)
                output.setframerate(44100)
                output.writeframes(bytes(44100 * 2 * 2 // 2))
            subprocess.run(
                ["ffmpeg", "-v", "error", "-nostdin", "-i", str(wav), "-c:a", "wmav2", str(fixture)],
                check=True,
            )
            subprocess.run(
                [sys.executable, str(SUITE_DIR / "analyze.py"), str(corpus), "--output", str(baseline), "--jobs", "1"],
                check=True,
            )
            subprocess.run(
                ["ffmpeg", "-v", "error", "-nostdin", "-i", str(fixture), "-f", "s16le", str(reference)],
                check=True,
            )
            fake_proton.write_text(
                "#!/bin/sh\n"
                "test \"$1\" = runinprefix || exit 64\n"
                "test -z \"${STEAM_COMPAT_MEDIA_PATH:-}\" || exit 65\n"
                "test -z \"${STEAM_COMPAT_TRANSCODED_MEDIA_PATH:-}\" || exit 66\n"
                "python3 -c 'import sys; from pathlib import Path; data=Path(sys.argv[1]).read_bytes(); "
                "Path(sys.argv[2]).write_bytes(data[:len(data)//3])' "
                f"{shlex.quote(str(reference))} \"$4\"\n",
                encoding="utf-8",
            )
            fake_proton.chmod(0o755)
            decoder.touch()

            environment = os.environ.copy()
            environment["STEAM_COMPAT_MEDIA_PATH"] = str(root / "existing-media")
            environment["STEAM_COMPAT_TRANSCODED_MEDIA_PATH"] = str(root / "existing-transcoded-media")
            process = subprocess.run(
                [
                    sys.executable,
                    str(SUITE_DIR / "run_mf_regression.py"),
                    str(baseline),
                    str(corpus),
                    fixture.name,
                    "--proton", str(fake_proton),
                    "--decoder", str(decoder),
                    "--steam-client-install", str(steam),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                text=True,
                check=False,
            )

            self.assertEqual(process.returncode, 1, process.stderr)
            result = json.loads(process.stdout)
            self.assertEqual(result["status"], "mismatch")
            self.assertEqual(result["kind"], "candidate_prefix")
            self.assertGreater(result["missing_bytes"], 0)

    def test_timeout_terminates_the_proton_process_group(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            steam = root / "steam"
            corpus = root / "corpus"
            steam.mkdir()
            corpus.mkdir()
            fixture = corpus / "fixture.wma"
            fixture.touch()
            baseline = root / "baseline.json"
            baseline.write_text('{"artifacts": []}', encoding="utf-8")
            decoder = root / "mf-decode.exe"
            decoder.touch()
            fake_proton = root / "proton"
            child_pid = root / "child.pid"
            fake_proton.write_text(
                "#!/bin/sh\n"
                "sh -c 'trap \"\" TERM; exec sleep 60' </dev/null >/dev/null 2>&1 &\n"
                f"echo $! > {shlex.quote(str(child_pid))}\n"
                "wait\n",
                encoding="utf-8",
            )
            fake_proton.chmod(0o755)

            process = subprocess.run(
                [
                    sys.executable,
                    str(SUITE_DIR / "run_mf_regression.py"),
                    str(baseline),
                    str(corpus),
                    fixture.name,
                    "--proton", str(fake_proton),
                    "--decoder", str(decoder),
                    "--steam-client-install", str(steam),
                    "--timeout", "0.2",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertEqual(process.returncode, 2, process.stderr)
            self.assertEqual(json.loads(process.stdout)["error_type"], "candidate_decode_timeout")
            pid = int(child_pid.read_text(encoding="utf-8"))
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_comparison_failure_is_not_reported_as_a_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            steam = root / "steam"
            corpus = root / "corpus"
            steam.mkdir()
            corpus.mkdir()
            fixture = corpus / "fixture.wma"
            fixture.write_bytes(b"fixture")
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "artifacts": [
                            {
                                "artifact": fixture.name,
                                "pcm": {"bytes": 8, "sha256": "0" * 64, "frame_size": 4},
                                "stream": {"index": 0},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            decoder = root / "mf-decode.exe"
            decoder.touch()
            fake_proton = root / "proton"
            fake_proton.write_text("#!/bin/sh\nprintf candidate > \"$4\"\n", encoding="utf-8")
            fake_proton.chmod(0o755)

            process = subprocess.run(
                [
                    sys.executable,
                    str(SUITE_DIR / "run_mf_regression.py"),
                    str(baseline),
                    str(corpus),
                    fixture.name,
                    "--proton", str(fake_proton),
                    "--decoder", str(decoder),
                    "--steam-client-install", str(steam),
                    "--ffmpeg", str(root / "missing-ffmpeg"),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertEqual(process.returncode, 2)
            self.assertEqual(json.loads(process.stdout)["error_type"], "comparison_failed")


if __name__ == "__main__":
    unittest.main()
