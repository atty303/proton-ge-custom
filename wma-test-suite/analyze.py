#!/usr/bin/env python3
"""Build a reproducible FFmpeg PCM baseline for an external ASF/WMA corpus."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


SCHEMA_VERSION = 1
READ_SIZE = 1024 * 1024


def command_environment(library_path: str | None) -> dict[str, str]:
    env = os.environ.copy()
    if library_path:
        current = env.get("LD_LIBRARY_PATH")
        env["LD_LIBRARY_PATH"] = library_path if not current else f"{library_path}:{current}"
    return env


def tool_version(command: str, env: dict[str, str]) -> dict[str, Any]:
    result = subprocess.run(
        [command, "-version"], check=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, env=env, text=True,
    )
    lines = result.stdout.splitlines()
    return {
        "command": command,
        "version": lines[0] if lines else "unknown",
        "libraries": [line.strip() for line in lines if line.startswith("libav") or line.startswith("libswresample")],
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(READ_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path, ffprobe: str, env: dict[str, str]) -> dict[str, Any]:
    result = subprocess.run(
        [
            ffprobe, "-v", "error", "-show_entries",
            "format=format_name,duration,size,bit_rate:"
            "stream=index,codec_name,codec_long_name,codec_type,codec_tag_string,codec_tag,"
            "sample_fmt,sample_rate,channels,channel_layout,bits_per_sample,start_pts,start_time,"
            "duration_ts,duration,time_base,bit_rate,extradata_size",
            "-of", "json", os.fspath(path),
        ],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True,
    )
    return json.loads(result.stdout)


def decode_pcm(
    path: Path, stream_index: int, sample_rate: int, channels: int,
    ffmpeg: str, env: dict[str, str],
) -> dict[str, Any]:
    process = subprocess.Popen(
        [
            ffmpeg, "-v", "error", "-nostdin", "-i", os.fspath(path),
            "-map", f"0:{stream_index}", "-vn", "-sn", "-dn",
            "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1",
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
    )
    assert process.stdout is not None
    assert process.stderr is not None

    digest = hashlib.sha256()
    frame_size = channels * 2
    zero_frame = bytes(frame_size)
    carry = b""
    pcm_bytes = 0
    frames = 0
    leading_zero_frames = 0
    trailing_zero_frames = 0
    found_nonzero = False

    while chunk := process.stdout.read(READ_SIZE):
        digest.update(chunk)
        pcm_bytes += len(chunk)
        data = carry + chunk
        complete_size = len(data) - len(data) % frame_size
        for offset in range(0, complete_size, frame_size):
            is_zero = data[offset:offset + frame_size] == zero_frame
            frames += 1
            if not found_nonzero:
                if is_zero:
                    leading_zero_frames += 1
                else:
                    found_nonzero = True
            if is_zero:
                trailing_zero_frames += 1
            else:
                trailing_zero_frames = 0
        carry = data[complete_size:]

    stderr = process.stderr.read().decode("utf-8", "replace")
    returncode = process.wait()
    if returncode:
        raise RuntimeError(f"ffmpeg exited with {returncode}: {stderr.strip()}")
    if carry:
        raise RuntimeError(f"PCM output has {len(carry)} trailing byte(s), frame size is {frame_size}")

    return {
        "format": "s16le",
        "sample_rate": sample_rate,
        "channels": channels,
        "frame_size": frame_size,
        "bytes": pcm_bytes,
        "frames": frames,
        "duration_seconds": frames / sample_rate,
        "sha256": digest.hexdigest(),
        "leading_zero_frames": leading_zero_frames,
        "trailing_zero_frames": trailing_zero_frames,
    }


def analyze_artifact(path: Path, ffmpeg: str, ffprobe: str, env: dict[str, str]) -> list[dict[str, Any]]:
    source_size = path.stat().st_size
    source_hash = file_sha256(path)
    try:
        info = probe(path, ffprobe, env)
    except Exception as error:
        return [{
            "status": "error",
            "error_type": "probe_failed",
            "error": str(error).replace(os.fspath(path), path.name),
            "artifact": path.name,
            "source_bytes": source_size,
            "source_sha256": source_hash,
        }]
    format_info = info.get("format", {})
    records: list[dict[str, Any]] = []

    for stream in info.get("streams", []):
        if stream.get("codec_type") != "audio":
            continue
        stream_index = int(stream["index"])
        sample_rate = int(stream["sample_rate"])
        channels = int(stream["channels"])
        base = {
            "status": "complete",
            "error_type": None,
            "artifact": path.name,
            "source_bytes": source_size,
            "source_sha256": source_hash,
            "container": format_info,
            "stream": stream,
        }
        try:
            base["pcm"] = decode_pcm(path, stream_index, sample_rate, channels, ffmpeg, env)
        except Exception as error:  # preserve the other artifacts in a partial report
            base["status"] = "error"
            base["error_type"] = "decode_failed"
            base["error"] = str(error).replace(os.fspath(path), path.name)
        records.append(base)

    if not records:
        records.append({
            "status": "error",
            "error_type": "audio_stream_missing",
            "artifact": path.name,
            "source_bytes": source_size,
            "source_sha256": source_hash,
            "container": format_info,
        })
    return records


def write_json_atomic(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(document, output, indent=2, sort_keys=True)
            output.write("\n")
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path, help="Directory containing external .wma/.asf artifacts")
    parser.add_argument("--output", required=True, type=Path, help="JSON baseline to create")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--library-path", help="Prepend a directory to LD_LIBRARY_PATH for both tools")
    parser.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 1))
    args = parser.parse_args()

    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    artifacts = sorted((*args.corpus.glob("*.wma"), *args.corpus.glob("*.asf")))
    if not artifacts:
        parser.error(f"no .wma or .asf artifacts found in {args.corpus}")

    env = command_environment(args.library_path)
    tools = {
        "ffmpeg": tool_version(args.ffmpeg, env),
        "ffprobe": tool_version(args.ffprobe, env),
    }
    records: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = [executor.submit(analyze_artifact, path, args.ffmpeg, args.ffprobe, env) for path in artifacts]
        for future in concurrent.futures.as_completed(futures):
            records.extend(future.result())
    records.sort(key=lambda record: (record["artifact"], int(record.get("stream", {}).get("index", -1))))

    errors = sum(record["status"] != "complete" for record in records)
    codecs: dict[str, int] = {}
    for record in records:
        codec = record.get("stream", {}).get("codec_name", "unknown")
        codecs[codec] = codecs.get(codec, 0) + 1
    document = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete" if not errors else "partial",
        "error_type": None if not errors else "artifact_failed",
        "canonical_pcm": {
            "format": "signed 16-bit little-endian interleaved PCM",
            "sample_rate": "preserve input",
            "channels": "preserve input",
            "timeline_padding": "disabled",
        },
        "tools": tools,
        "summary": {
            "artifacts": len(artifacts),
            "audio_streams": len(records),
            "errors": errors,
            "codecs": dict(sorted(codecs.items())),
        },
        "artifacts": records,
    }
    write_json_atomic(args.output, document)
    print(json.dumps({"status": document["status"], "output": os.fspath(args.output), **document["summary"]}))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
