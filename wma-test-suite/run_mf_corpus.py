#!/usr/bin/env python3
"""Check every artifact in one or more external WMA dump corpora."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, TextIO

SUITE_DIR = Path(__file__).resolve().parent
BASELINE_NAME = "ffmpeg-pcm-baseline.json"
READ_SIZE = 1024 * 1024
TERMINATE_GRACE_SECONDS = 1.0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(READ_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def load_baseline(corpus: Path) -> tuple[Path, dict[str, dict[str, Any]]]:
    baseline = corpus / BASELINE_NAME
    document = json.loads(baseline.read_text(encoding="utf-8"))
    records: dict[str, dict[str, Any]] = {}
    for record in document.get("artifacts", []):
        artifact = record.get("artifact")
        if not isinstance(artifact, str):
            raise ValueError(f"baseline record without an artifact in {baseline}")
        if artifact in records:
            raise ValueError(f"multiple audio streams for {artifact} in {baseline}")
        if record.get("status") != "complete" or not isinstance(record.get("pcm"), dict):
            raise ValueError(f"incomplete baseline record for {artifact} in {baseline}")
        records[artifact] = record
    if not records:
        raise ValueError(f"baseline has no complete artifacts: {baseline}")
    fixtures = {path.name for pattern in ("*.wma", "*.asf") for path in corpus.glob(pattern)}
    if fixtures != records.keys():
        missing = sorted(fixtures - records.keys())
        stale = sorted(records.keys() - fixtures)
        raise ValueError(
            f"baseline/corpus inventory mismatch in {corpus}: missing={len(missing)} stale={len(stale)}"
        )
    return baseline, records


def compare_candidate(
    baseline: Path,
    corpus: Path,
    artifact: str,
    record: dict[str, Any],
    candidate: Path,
    ffmpeg: str,
) -> tuple[int, dict[str, Any]]:
    pcm = record["pcm"]
    candidate_size = candidate.stat().st_size
    candidate_hash = sha256_file(candidate)
    if candidate_size == pcm["bytes"] and candidate_hash == pcm["sha256"]:
        return 0, {
            "status": "exact",
            "artifact": artifact,
            "candidate_bytes": candidate_size,
            "candidate_sha256": candidate_hash,
            "reference_bytes": pcm["bytes"],
            "reference_sha256": pcm["sha256"],
            "frame_size": pcm["frame_size"],
        }

    compared = subprocess.run(
        [
            sys.executable,
            os.fspath(SUITE_DIR / "compare_pcm.py"),
            os.fspath(baseline),
            os.fspath(corpus),
            artifact,
            os.fspath(candidate),
            "--ffmpeg",
            ffmpeg,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    try:
        comparison = json.loads(compared.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"comparison produced invalid JSON for {artifact}") from error
    if compared.returncode != 1 or comparison.get("status") != "mismatch":
        raise RuntimeError(f"comparison failed for {artifact}: exit_status={compared.returncode}")
    return 1, comparison


def read_lines(stream: TextIO, output: queue.Queue[str | None]) -> None:
    try:
        for line in stream:
            output.put(line)
    finally:
        output.put(None)


def stop_process(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + TERMINATE_GRACE_SECONDS
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run_corpus(
    corpus: Path,
    baseline: Path,
    records: dict[str, dict[str, Any]],
    proton: Path,
    decoder: Path,
    environment: dict[str, str],
    candidate_directory: Path,
    ffmpeg: str,
    timeout: float,
    verbose_mismatches: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    command = [
        os.fspath(proton.resolve()),
        "runinprefix",
        os.fspath(decoder.resolve()),
        "--directory",
        os.fspath(corpus.resolve()),
        os.fspath(candidate_directory.resolve()),
    ]
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as decoder_stderr:
        process = subprocess.Popen(
            command,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=decoder_stderr,
            text=True,
            start_new_session=True,
        )
        assert process.stdout is not None
        lines: queue.Queue[str | None] = queue.Queue()
        reader = threading.Thread(target=read_lines, args=(process.stdout, lines), daemon=True)
        reader.start()
        seen: set[str] = set()
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        try:
            while True:
                try:
                    line = lines.get(timeout=timeout)
                except queue.Empty as error:
                    raise RuntimeError(
                        f"candidate decode timed out after {timeout:g}s without an artifact result"
                    ) from error
                if line is None:
                    break
                try:
                    decoded = json.loads(line)
                except json.JSONDecodeError as error:
                    raise RuntimeError("candidate decoder produced invalid JSON") from error
                artifact = decoded.get("artifact")
                if not isinstance(artifact, str) or artifact not in records or artifact in seen:
                    raise RuntimeError(f"candidate decoder returned an unexpected artifact: {artifact!r}")
                seen.add(artifact)
                candidate = candidate_directory / f"{artifact}.s16le"
                try:
                    if decoded.get("status") != "complete":
                        error = {"status": "error", "artifact": artifact,
                                 "error_type": decoded.get("error_type", "candidate_decode_failed")}
                        errors.append(error)
                        continue
                    if not candidate.is_file():
                        raise RuntimeError(f"candidate output was not created for {artifact}")
                    return_code, comparison = compare_candidate(
                        baseline, corpus, artifact, records[artifact], candidate, ffmpeg
                    )
                    comparison["corpus"] = corpus.name
                    results.append(comparison)
                    if return_code and verbose_mismatches:
                        print(json.dumps(comparison, sort_keys=True), flush=True)
                finally:
                    candidate.unlink(missing_ok=True)
        except BaseException:
            stop_process(process)
            reader.join(timeout=TERMINATE_GRACE_SECONDS)
            raise

        return_code = process.wait()
        reader.join()
        if seen != records.keys():
            raise RuntimeError(f"candidate decoder omitted {len(records.keys() - seen)} artifact(s)")
        if return_code not in (0, 1):
            decoder_stderr.seek(0)
            raise RuntimeError(f"candidate decoder exited with {return_code}: {decoder_stderr.read().strip()}")
        return results, errors


def write_report(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", nargs="+", type=Path)
    parser.add_argument("--proton", type=Path, required=True)
    parser.add_argument("--decoder", type=Path, default=SUITE_DIR / "bin" / "mf-decode.exe")
    parser.add_argument("--steam-client-install", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--timeout", type=float, default=120.0,
                        help="Maximum silence between per-artifact decoder results")
    parser.add_argument("--output", type=Path, help="Write the complete structured result report")
    parser.add_argument("--verbose-mismatches", action="store_true",
                        help="Print each mismatch as JSON in addition to the final report")
    args = parser.parse_args()

    required = [args.proton, args.decoder, args.steam_client_install, *args.corpus]
    missing = next((path for path in required if not path.exists()), None)
    if missing is not None:
        print(json.dumps({"status": "error", "error_type": "path_not_found", "detail": os.fspath(missing)}))
        return 2
    try:
        baselines = [(corpus, *load_baseline(corpus)) for corpus in args.corpus]
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "error", "error_type": "baseline_invalid", "detail": str(error)}))
        return 2

    with tempfile.TemporaryDirectory(prefix="wma-mf-corpus-") as temporary_directory:
        root = Path(temporary_directory)
        compat = root / "compat"
        cache = root / "cache"
        candidates = root / "candidates"
        compat.mkdir()
        cache.mkdir()
        candidates.mkdir()
        environment = os.environ.copy()
        environment.pop("STEAM_COMPAT_MEDIA_PATH", None)
        environment.pop("STEAM_COMPAT_TRANSCODED_MEDIA_PATH", None)
        environment.update({
            "XDG_CACHE_HOME": os.fspath(cache),
            "STEAM_COMPAT_DATA_PATH": os.fspath(compat),
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": os.fspath(args.steam_client_install.resolve()),
            "PROTON_LOG": "0",
            "WINEDEBUG": "-all",
        })
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        try:
            for corpus, baseline, records in baselines:
                corpus_results, corpus_errors = run_corpus(
                    corpus, baseline, records, args.proton, args.decoder, environment,
                    candidates, args.ffmpeg, args.timeout, args.verbose_mismatches,
                )
                results.extend(corpus_results)
                errors.extend({**error, "corpus": corpus.name} for error in corpus_errors)
        except (OSError, RuntimeError) as error:
            print(json.dumps({"status": "error", "error_type": "corpus_run_failed", "detail": str(error)}))
            return 2

    exact = sum(result["status"] == "exact" for result in results)
    mismatches = sum(result["status"] == "mismatch" for result in results)
    unique_sources = len({record["source_sha256"] for _, _, records in baselines for record in records.values()})
    summary = {
        "status": "exact" if not mismatches and not errors else "mismatch",
        "corpora": len(baselines),
        "artifacts": len(results) + len(errors),
        "unique_sources": unique_sources,
        "exact": exact,
        "mismatches": mismatches,
        "decode_errors": len(errors),
    }
    results.sort(key=lambda result: (result["corpus"], result["artifact"]))
    errors.sort(key=lambda error: (error["corpus"], error["artifact"]))
    document = {"schema_version": 1, "summary": summary, "results": results, "errors": errors}
    if args.output:
        write_report(args.output, document)
        summary["output"] = os.fspath(args.output)
    print(json.dumps(summary, sort_keys=True))
    return 1 if mismatches or errors else 0


if __name__ == "__main__":
    sys.exit(main())
