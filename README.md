> [!NOTE]
> This repository fixes an issue in GE‑Proton where audio data isn’t decoded correctly in KONAMI’s PC rhythm games. Pre‑built Proton binaries are available for download on the Releases page.

## Prerequisites

* Tested on: GE‑Proton10‑9
* Verified game: beatmania IIDX INFINITAS

## Problem

Compared to native Windows WMA decoding, Wine’s implementation inserts 40 ms of silence at the start and drops the final 40 ms. Since beatmania triggers very short audio samples like a music sequencer, this delay is immediately noticeable.

### Demo Video

[![demo](https://img.youtube.com/vi/LPJbRCu4_g8/0.jpg)](https://youtu.be/LPJbRCu4_g8?si=I1QBiGFdjWOc2cWN)

You can hear the synth lead stuttering as it plays.

## Analysis

WMA decoding flows through several components:

1. The game uses Media Foundation’s MediaSource API to decode WMA.
2. Wine implements Media Foundation in `winegstreamer.dll`, using GStreamer for decoding.
3. GStreamer employs the libav plugin to decode.
4. FFmpeg performs the actual WMA decode.

### FFmpeg

The commit [19802d170a304f5853d92e01d0513b9e06897d61](https://github.com/FFmpeg/FFmpeg/commit/19802d170a304f5853d92e01d0513b9e06897d61) adds gapless playback support (encoder‑delay correction) for WMA. GE‑Proton10‑9’s FFmpeg lacks this patch, so we must backport it first.

### GStreamer

In MR !3117 ([https://gitlab.freedesktop.org/gstreamer/gstreamer/-/merge\_requests/3117](https://gitlab.freedesktop.org/gstreamer/gstreamer/-/merge_requests/3117)), GStreamer’s libav plugin explicitly disables FFmpeg’s gapless handling by setting the `AV_CODEC_FLAG2_SKIP_MANUAL` flag on WMA decoders. This behavior remains in the latest GStreamer releases, meaning its libav plugin cannot perform true gapless playback.

#### Expected (non‑gapless) Behavior

```text
Input : [        Frame1][Frame2][Frame3][EOS]
Output: [lead‑in + PCM1][  PCM2][  PCM3]
          ↑               ↑       ↑
          one‑to‑one mapping
```

GStreamer expects each input frame to correspond exactly to an output PCM buffer.

#### Gapless Behavior

```text
Input : [Frame1][Frame2][Frame3][EOS] → queue is empty
Output: [  PCM1][  PCM2][  PCM3][DelayFrame]
           ↑                      ↑
     lead‑in removed         no matching input
```

Because there’s no input frame for `DelayFrame`, GStreamer throws an error. This is an architectural limitation in GStreamer.

### Fix

Map `DelayFrame` back to the final Frame3 so no error occurs. The PTS can still be correct; in my use case it works perfectly. Whether this behavior is generally acceptable in GStreamer is unclear.

## Patches

### [`patches/ffmpeg-19802d170a304f5853d92e01d0513b9e06897d61.patch`](https://github.com/atty303/proton-ge-custom/blob/fix-wma-delay/patches/ffmpeg-19802d170a304f5853d92e01d0513b9e06897d61.patch)

FFmpeg’s upstream `n5.0.0` includes this commit, but GE‑Proton currently references `n4.x`. Simply bumping the FFmpeg version breaks the build due to dependency changes outside our scope, so we apply only the WMA patch.

### [`patches/ffmpeg-61c2c9ef8e66920c8ba308e8fa9f36ae602f8245.patch`](./patches/ffmpeg-61c2c9ef8e66920c8ba308e8fa9f36ae602f8245.patch)

Similarly to the above, we will backport gapless support to the WMA9 Pro codec. SDVX uses this codec.

### [`patches/gstreamer-fix-wma-gapless.patch`](https://github.com/atty303/proton-ge-custom/blob/fix-wma-delay/patches/gstreamer-fix-wma-gapless.patch)

* Remove the code that disables gapless support in GStreamer’s libav plugin.
* Allow frames to appear during drain in GStreamer’s audio plugin.

This is a workaround that ignores GStreamer’s architecture; it’s untested outside of Wine and likely to be rejected upstream.
