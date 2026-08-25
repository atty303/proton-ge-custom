#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


SUITE_DIR = Path(__file__).resolve().parents[1]


def make_corpus(root: Path, name: str, artifacts: dict[str, bytes]) -> Path:
    corpus = root / name
    corpus.mkdir()
    records = []
    for artifact, pcm in artifacts.items():
        (corpus / artifact).write_bytes(pcm)
        records.append({
            "status": "complete",
            "artifact": artifact,
            "source_sha256": hashlib.sha256(pcm).hexdigest(),
            "stream": {"index": 0},
            "pcm": {
                "bytes": len(pcm),
                "sha256": hashlib.sha256(pcm).hexdigest(),
                "frame_size": 4,
            },
        })
    (corpus / "ffmpeg-pcm-baseline.json").write_text(
        json.dumps({"artifacts": records}), encoding="utf-8"
    )
    return corpus


class MediaFoundationCorpusRunnerTest(unittest.TestCase):
    def test_checks_every_artifact_across_all_corpora(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = make_corpus(root, "dump", {"first.wma": b"one", "shared.wma": b"same"})
            second = make_corpus(root, "dump2", {"second.asf": b"two", "shared.wma": b"same"})
            steam = root / "steam"
            steam.mkdir()
            decoder = root / "mf-decode.exe"
            decoder.touch()
            helper = root / "fake_decode.py"
            helper.write_text(
                "import json, pathlib, sys\n"
                "source, output = map(pathlib.Path, sys.argv[1:])\n"
                "for fixture in sorted((*source.glob('*.wma'), *source.glob('*.asf'))):\n"
                " candidate = output / (fixture.name + '.s16le')\n"
                " candidate.write_bytes(fixture.read_bytes())\n"
                " print(json.dumps({'status':'complete','artifact':fixture.name}), flush=True)\n",
                encoding="utf-8",
            )
            proton = root / "proton"
            proton.write_text(
                "#!/bin/sh\n"
                "test \"$1\" = runinprefix || exit 64\n"
                "test \"$3\" = --directory || exit 65\n"
                f"exec {sys.executable} {helper} \"$4\" \"$5\"\n",
                encoding="utf-8",
            )
            proton.chmod(0o755)
            report = root / "result.json"

            process = subprocess.run(
                [
                    sys.executable,
                    str(SUITE_DIR / "run_mf_corpus.py"),
                    str(first),
                    str(second),
                    "--proton", str(proton),
                    "--decoder", str(decoder),
                    "--steam-client-install", str(steam),
                    "--output", str(report),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertEqual(process.returncode, 0, process.stderr)
            summary = json.loads(process.stdout)
            self.assertEqual(summary["corpora"], 2)
            self.assertEqual(summary["artifacts"], 4)
            self.assertEqual(summary["unique_sources"], 3)
            self.assertEqual(summary["exact"], 4)
            document = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(len(document["results"]), 4)

    def test_rejects_a_stale_baseline_before_starting_proton(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            corpus = make_corpus(root, "dump", {"fixture.wma": b"fixture"})
            (corpus / "extra.wma").write_bytes(b"extra")
            steam = root / "steam"
            steam.mkdir()
            decoder = root / "mf-decode.exe"
            decoder.touch()
            proton = root / "proton"
            proton.touch()

            process = subprocess.run(
                [
                    sys.executable,
                    str(SUITE_DIR / "run_mf_corpus.py"),
                    str(corpus),
                    "--proton", str(proton),
                    "--decoder", str(decoder),
                    "--steam-client-install", str(steam),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertEqual(process.returncode, 2)
            self.assertEqual(json.loads(process.stdout)["error_type"], "baseline_invalid")

    def test_timeout_terminates_the_batch_process_group(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            corpus = make_corpus(root, "dump", {"fixture.wma": b"fixture"})
            steam = root / "steam"
            steam.mkdir()
            decoder = root / "mf-decode.exe"
            decoder.touch()
            proton = root / "proton"
            child_pid = root / "child.pid"
            proton.write_text(
                "#!/bin/sh\n"
                "sh -c 'trap \"\" TERM; exec sleep 60' </dev/null >/dev/null 2>&1 &\n"
                f"echo $! > {shlex.quote(str(child_pid))}\n"
                "wait\n",
                encoding="utf-8",
            )
            proton.chmod(0o755)

            process = subprocess.run(
                [
                    sys.executable,
                    str(SUITE_DIR / "run_mf_corpus.py"),
                    str(corpus),
                    "--proton", str(proton),
                    "--decoder", str(decoder),
                    "--steam-client-install", str(steam),
                    "--timeout", "0.1",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertEqual(process.returncode, 2, process.stderr)
            self.assertEqual(json.loads(process.stdout)["error_type"], "corpus_run_failed")
            with self.assertRaises(ProcessLookupError):
                os.kill(int(child_pid.read_text(encoding="utf-8")), 0)


if __name__ == "__main__":
    unittest.main()
