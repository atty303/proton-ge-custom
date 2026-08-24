#!/usr/bin/env python3
"""Compare a candidate S16LE file with one FFmpeg baseline artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


READ_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(READ_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def read_exact(source: Any, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = source.read(size - len(chunks))
        if not chunk:
            break
        chunks.extend(chunk)
    return bytes(chunks)


def first_difference(left: bytes, right: bytes) -> int | None:
    for index, (left_byte, right_byte) in enumerate(zip(left, right)):
        if left_byte != right_byte:
            return index
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("artifact")
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()

    document = json.loads(args.baseline.read_text(encoding="utf-8"))
    matches = [record for record in document["artifacts"] if record["artifact"] == args.artifact]
    if len(matches) != 1:
        parser.error(f"expected one baseline record for {args.artifact}, found {len(matches)}")
    record = matches[0]
    pcm = record["pcm"]
    candidate_size = args.candidate.stat().st_size
    candidate_hash = sha256_file(args.candidate)
    result: dict[str, Any] = {
        "status": "exact" if candidate_size == pcm["bytes"] and candidate_hash == pcm["sha256"] else "mismatch",
        "artifact": args.artifact,
        "candidate_bytes": candidate_size,
        "candidate_sha256": candidate_hash,
        "reference_bytes": pcm["bytes"],
        "reference_sha256": pcm["sha256"],
        "frame_size": pcm["frame_size"],
    }
    if result["status"] == "exact":
        print(json.dumps(result, sort_keys=True))
        return 0

    artifact_path = args.corpus / args.artifact
    process = subprocess.Popen(
        [
            args.ffmpeg, "-v", "error", "-nostdin", "-i", os.fspath(artifact_path),
            "-map", f"0:{record['stream']['index']}", "-vn", "-sn", "-dn",
            "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1",
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    offset = 0
    mismatch_byte: int | None = None
    reference_ended = False
    with args.candidate.open("rb") as candidate:
        while chunk := candidate.read(READ_SIZE):
            reference = read_exact(process.stdout, len(chunk))
            difference = first_difference(chunk, reference)
            if difference is not None:
                mismatch_byte = offset + difference
                break
            if len(reference) != len(chunk):
                reference_ended = True
                mismatch_byte = offset + len(reference)
                break
            offset += len(chunk)

    if mismatch_byte is not None:
        process.terminate()
        process.communicate()
        result["kind"] = "content_mismatch" if not reference_ended else "reference_prefix"
        result["first_mismatch_byte"] = mismatch_byte
        result["first_mismatch_frame"] = mismatch_byte // pcm["frame_size"]
    else:
        extra_reference = process.stdout.read(1)
        process.stdout.read()
        stderr = process.stderr.read().decode("utf-8", "replace")
        returncode = process.wait()
        if returncode:
            result["kind"] = "reference_decode_failed"
            result["error"] = stderr.strip().replace(os.fspath(artifact_path), args.artifact)
        elif extra_reference:
            result["kind"] = "candidate_prefix"
            result["missing_bytes"] = pcm["bytes"] - candidate_size
            result["missing_frames"] = (pcm["bytes"] - candidate_size) // pcm["frame_size"]
        else:
            result["kind"] = "content_mismatch"
    print(json.dumps(result, sort_keys=True))
    return 1


if __name__ == "__main__":
    sys.exit(main())
