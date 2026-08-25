#!/usr/bin/env python3
"""Decode one fixture with Proton Media Foundation and compare it to a baseline."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


SUITE_DIR = Path(__file__).resolve().parent
TERMINATE_GRACE_SECONDS = 1.0


def print_error(error_type: str, detail: str) -> None:
    print(json.dumps({"status": "error", "error_type": error_type, "detail": detail}, sort_keys=True))


def stop_process_group(process: subprocess.Popen[str]) -> tuple[str, str]:
    process_group = process.pid
    try:
        os.killpg(process_group, signal.SIGTERM)
    except ProcessLookupError:
        pass

    deadline = time.monotonic() + TERMINATE_GRACE_SECONDS
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process_group, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        try:
            os.killpg(process_group, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return process.communicate()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("artifact")
    parser.add_argument("--proton", type=Path, required=True)
    parser.add_argument("--decoder", type=Path, default=SUITE_DIR / "bin" / "mf-decode.exe")
    parser.add_argument("--steam-client-install", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    fixture = args.corpus / args.artifact
    required = {
        "proton_not_found": args.proton,
        "decoder_not_found": args.decoder,
        "baseline_not_found": args.baseline,
        "fixture_not_found": fixture,
        "steam_client_install_not_found": args.steam_client_install,
    }
    for error_type, path in required.items():
        if not path.exists():
            print_error(error_type, os.fspath(path))
            return 2

    with tempfile.TemporaryDirectory(prefix="wma-mf-regression-") as temporary_directory:
        root = Path(temporary_directory)
        compat = root / "compat"
        cache = root / "cache"
        candidate = root / "candidate.s16le"
        compat.mkdir()
        cache.mkdir()

        environment = os.environ.copy()
        environment.pop("STEAM_COMPAT_MEDIA_PATH", None)
        environment.pop("STEAM_COMPAT_TRANSCODED_MEDIA_PATH", None)
        environment.update(
            {
                "XDG_CACHE_HOME": os.fspath(cache),
                "STEAM_COMPAT_DATA_PATH": os.fspath(compat),
                "STEAM_COMPAT_CLIENT_INSTALL_PATH": os.fspath(args.steam_client_install.resolve()),
                "PROTON_LOG": "0",
                "WINEDEBUG": "-all",
            }
        )
        command = [
            os.fspath(args.proton.resolve()),
            "runinprefix",
            os.fspath(args.decoder.resolve()),
            os.fspath(fixture.resolve()),
            os.fspath(candidate),
        ]
        try:
            process = subprocess.Popen(
                command,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                _decoder_stdout, decoder_stderr = process.communicate(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                stop_process_group(process)
                print_error("candidate_decode_timeout", f"timeout_seconds={args.timeout:g}")
                return 2
        except OSError as error:
            print_error("candidate_decode_start_failed", str(error))
            return 2

        if process.returncode:
            print_error("candidate_decode_failed", f"exit_status={process.returncode}")
            if decoder_stderr:
                print(decoder_stderr, file=sys.stderr, end="")
            return 2
        if not candidate.is_file():
            print_error("candidate_not_created", "decoder exited successfully without creating PCM output")
            return 2

        compared = subprocess.run(
            [
                sys.executable,
                os.fspath(SUITE_DIR / "compare_pcm.py"),
                os.fspath(args.baseline),
                os.fspath(args.corpus),
                args.artifact,
                os.fspath(candidate),
                "--ffmpeg",
                args.ffmpeg,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        try:
            comparison = json.loads(compared.stdout)
        except (json.JSONDecodeError, TypeError):
            comparison = None
        valid_exact = compared.returncode == 0 and isinstance(comparison, dict) and comparison.get("status") == "exact"
        valid_mismatch = compared.returncode == 1 and isinstance(comparison, dict) and comparison.get("status") == "mismatch"
        if not (valid_exact or valid_mismatch):
            print_error("comparison_failed", f"exit_status={compared.returncode}")
            if compared.stderr:
                print(compared.stderr, file=sys.stderr, end="")
            return 2
        print(json.dumps(comparison, sort_keys=True))
        return compared.returncode


if __name__ == "__main__":
    sys.exit(main())
