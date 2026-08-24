# WMA decode test suite

This directory is independent from the Wine and GE-Proton upstream test trees. It builds reproducible
PCM baselines from an external ASF/WMA corpus without copying game assets into the repository.

## Canonical PCM

Each audio stream is decoded to interleaved signed 16-bit little-endian PCM while preserving its input
sample rate and channel count. The JSON report records source and PCM SHA-256 digests, decoded byte and
frame counts, and exact leading/trailing zero-frame counts. FFmpeg timeline padding is not enabled.

The FFmpeg runtime library versions are recorded in the report. `--library-path` can select a compatible
FFmpeg build, but the GE-Proton libraries themselves disable the local `file` and `pipe` protocols and
therefore cannot be substituted directly under the host `ffmpeg`/`ffprobe` executables. The Media
Foundation candidate runner below exercises those bundled libraries through Wine's byte-stream path.

```text
python3 wma-test-suite/analyze.py CORPUS --output REPORT.json --library-path PROTON_LIBDIR
```

The corpus and report are local diagnostic artifacts. INFINITAS assets must not be committed or attached
to a public issue. A distributable regression fixture should be synthesized from the observed container
and codec parameters.

## Self-test

The self-test generates a temporary WMAV2-in-ASF fixture and removes it on completion.

```text
python3 -m unittest discover -s wma-test-suite/tests -v
```

## Proton Media Foundation candidate

`mf_decode.c` is a minimal Windows Media Foundation Source Reader client. The Makefile builds 64-bit
`mf-decode.exe` and 32-bit `mf-decode32.exe`. Run the matching executable under the Proton build being
tested to write the candidate S16LE PCM. This is not a Windows-native reference decoder; it is the
system under test that will be compared with the FFmpeg baseline above. A direct Wine invocation must
include the Proton distribution's matching FFmpeg and Wine library directories in `LD_LIBRARY_PATH`;
the Proton launcher normally supplies that runtime environment.

```text
make -C wma-test-suite
```

The executable accepts an input ASF/WMA path and an output PCM path:

```text
mf-decode.exe INPUT.wma OUTPUT.s16le
```

Compare that candidate with a baseline record. A shorter candidate is decoded again and classified as
`candidate_prefix` only if every candidate byte equals the beginning of the FFmpeg reference.

```text
python3 wma-test-suite/compare_pcm.py REPORT.json CORPUS ARTIFACT.wma CANDIDATE.s16le
```

## Passive ASF capture

The experimental Proton build captures ASF input that `winedmo` already reads when
`WINEDMO_ASF_DUMP_DIR` names an output directory. The recorder tees the normal aligned input buffers;
it does not seek or read the game stream solely for capture. Hashing and file I/O run on a writer
thread. A recording is published only after every source block has been observed, otherwise the
manifest records a `partial` result with an `error_type` instead of publishing a truncated ASF file.

The recorder accepts any ASF container with at least one audio stream, including WMAV2 and WMA Pro.
It can only capture an asset that the application actually opens through this `winedmo` path, so a
WMA Pro song must be selected and allowed to reach decode. Each completed file is named from the
container, first audio codec, content hash, and byte length. `manifest.jsonl` records all audio streams
without recording the original game path.

The experiment is bounded to 64 MiB per ASF, 256 MiB queued in memory, and 2 GiB saved per process.
Files and the manifest are created with user-only permissions. Treat the output as private game data
and keep it outside the repository.

The fixture-capture build intentionally contains only the 2048 RT work-queue handle limit, the 90-second
WinHTTP response timeout, this passive recorder, and opt-in diagnostic logging. It contains no experimental
decoder or EOS/drain change. Leaving `WINEDMO_ASF_DUMP_DIR` unset disables the recorder completely.

For the known Konamate launch path, create a private directory outside this repository and export the
variable for the launched Proton process:

```text
mkdir -p "$HOME/infinitas-wma-fixtures"
WINEDMO_ASF_DUMP_DIR="$HOME/infinitas-wma-fixtures" ./dist/konamate-x86_64-unknown-linux-gnu run infinitas --profile gamescope
```

After the song has loaded, wait for `manifest.jsonl` to contain a `complete` record before stopping the
process. Only the artifact named by that record is a usable fixture. A `partial` record is diagnostic
evidence and must not be used as an ASF input.

## Queue and media diagnostics

The measurement build adds a dedicated `wmadiag` Wine debug channel. It is disabled during normal use.
Enable it together with `PROTON_LOG` to record RT work-queue allocation, reuse, release, high-water and
exhaustion events; Source Reader stream media types and queue policy; demuxer container and codec metadata;
and passive-capture eligibility or skip reasons. The diagnostic events do not include the game asset path
or encoded audio content.

```text
PROTON_LOG=1 WINEDEBUG=+wmadiag WINEDMO_ASF_DUMP_DIR="$HOME/infinitas-wma-fixtures" ./dist/konamate-x86_64-unknown-linux-gnu run infinitas --profile gamescope
```

`event=queue_summary status=complete` is the normal-run completion marker. If the process crashes or the
marker is absent, treat the queue recording as partial. `event=queue_allocate status=exhausted` is direct
evidence that the 2048 limit was reached. Compare `active`, `high_water`, `total`, `slot`, and the paired
`media_source_queue` / `source_reader_queue` / `source_reader_destroy` events to distinguish a high
concurrency peak from successful handle reuse.

For a song that produces no artifact, inspect `event=demuxer`, `event=demuxer_stream`,
`event=source_reader_stream`, and `event=capture status=skipped`. A Source Reader event without a matching
winedmo demuxer event indicates that the media was handled outside this demuxer path; no corresponding
Source Reader event indicates that this Media Foundation path was not reached during the recorded window.
