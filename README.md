<<<<<<< HEAD
<<<<<<< ours
> [!CAUTION]
>  **MYSELF (GLORIOUSEGGROLL) AND THIS PROJECT (PROTON-GE) ARE NOT AFFILIATED WITH `hxxps[://]protonge[.]com`. THAT IS A SPAM/FAKE WEBSITE. THERE IS NO EXISTING WEBSITE FOR PROTON-GE OTHER THAN THIS GITHUB REPOSITORY. PROTON-GE DOES NOT COLLECT ANY USER DATA WHAT SO EVER AND IS NOT A COMPANY OR ORGANIZATION OF ANY TYPE.**
=======
> [!INFO]
=======
> [!NOTE]
>>>>>>> 70bb56b5 (Update README.md)
> This repository fixes an issue in GE‑Proton where audio data isn’t decoded correctly in KONAMI’s PC rhythm games. Pre‑built Proton binaries are available for download on the Releases page.
>>>>>>> theirs

## Prerequisites

<<<<<<< ours
> [!WARNING]
> **RUNNING NON-STEAM GAMES WITH GE-PROTON OUTSIDE OF STEAM IS ONLY SUPPORTED USING [UMU](https://github.com/Open-Wine-Components/umu-launcher):**
> 
> Proton runs in a container, which uses a runtime environment and libraries specifically built for use within that container. Not running it as intended results in the container and therefore its runtime not being used, and severely breaks library compatibility. It causes wine to search for libraries on your system instead of those it was built with/intended for within proton. It may work, if enough libraries match, but it is not correct and not supportable due to library differences across distros.
> 
> If you want proton functionality -outside- of proton for non-steam games, umu-launcher is a cli tool that was designed to be able to mimic steam in running the entire containerized runtime environment it needs in order to run proton exactly as steam does without needing steam. Any other method is not supported.
>
>[Lutris](https://lutris.net/) has already integrated UMU as the default backend used when `GE-Proton(Latest)` is selected as a wine runner either globally or for any specific game.
> 
>[Heroic](https://heroicgameslauncher.com/) has also enabled UMU by default when using `GE-Proton`.

> [!IMPORTANT]
> **If you have an issue that happens with my proton-GE build, provided FROM this repository, that does -not- happen on Valve's proton, please DO NOT open a bug report on Valve's bug tracker.**
>
> Instead, open an issue: https://github.com/GloriousEggroll/proton-ge-custom/issues
>
> or contact me on Discord about the issue: https://discord.gg/6y3BdzC

> [!NOTE]
> (1)  Please note, this is a custom build of proton, and is -not- affiliated with Valve's proton.
> 
> (2) Please also note I do not provide the flatpak of proton-GE, and I do not provide the AUR version of proton-GE. I will not assist with those.
> 
> (3) The only version of proton-GE that I provide and will assist with builds of is the one provided within this repository, using the build system documented here.
> 
> (4) I cannot validate the accuracy or functionality of other builds that have not been built using the build system included here.
=======
* Tested on: GE‑Proton10‑9
* Verified game: beatmania IIDX INFINITAS

## Problem

Compared to native Windows WMA decoding, Wine’s implementation inserts 40 ms of silence at the start and drops the final 40 ms. Since beatmania triggers very short audio samples like a music sequencer, this delay is immediately noticeable.

### Demo Video

[![demo](https://img.youtube.com/vi/LPJbRCu4_g8/0.jpg)](https://youtu.be/LPJbRCu4_g8?si=I1QBiGFdjWOc2cWN)

You can hear the synth lead stuttering as it plays.

## Analysis
>>>>>>> theirs

WMA decoding flows through several components:

1. The game uses Media Foundation’s MediaSource API to decode WMA.
2. Wine implements Media Foundation in `winegstreamer.dll`, using GStreamer for decoding.
3. GStreamer employs the libav plugin to decode.
4. FFmpeg performs the actual WMA decode.

### FFmpeg

The commit [19802d170a304f5853d92e01d0513b9e06897d61](https://github.com/FFmpeg/FFmpeg/commit/19802d170a304f5853d92e01d0513b9e06897d61) adds gapless playback support (encoder‑delay correction) for WMA. GE‑Proton10‑9’s FFmpeg lacks this patch, so we must backport it first.

### GStreamer

<<<<<<< HEAD
<<<<<<< ours
- Additional media foundation patches for better video playback support
- AMD FSR patches added directly to fullscreen hack that can be toggled with WINE_FULLSCREEN_FSR=1
- FSR Fake resolution patch details [here](https://github.com/GloriousEggroll/proton-ge-custom/pull/52)
- Nvidia CUDA support for PhysX and NVAPI
- Raw input mouse support
- 'protonfixes' system -- this is an automated system that applies per-game fixes (such as winetricks, envvars, EAC workarounds, overrides, etc).
- Various upstream WINE patches backported
- Various wine-staging patches applied as they become needed
- NTSync enablement if the kernel supports it.
=======
In MR !3117 ([https://gitlab.freedesktop.org/gstreamer/gstreamer/-/merge\_requests/3117](https://gitlab.freedesktop.org/gstreamer/gstreamer/-/merge_requests/3117)), GStreamer’s libav plugin explicitly disables FFmpeg’s gapless handling by setting the `AV_CODEC_FLAG2_SKIP_MANUAL` flag on WMV decoders. This behavior remains in the latest GStreamer releases, meaning its libav plugin cannot perform true gapless playback.
>>>>>>> theirs
=======
In MR !3117 ([https://gitlab.freedesktop.org/gstreamer/gstreamer/-/merge\_requests/3117](https://gitlab.freedesktop.org/gstreamer/gstreamer/-/merge_requests/3117)), GStreamer’s libav plugin explicitly disables FFmpeg’s gapless handling by setting the `AV_CODEC_FLAG2_SKIP_MANUAL` flag on WMA decoders. This behavior remains in the latest GStreamer releases, meaning its libav plugin cannot perform true gapless playback.
>>>>>>> d48ec6c5 (Update README.md)

#### Expected (non‑gapless) Behavior

<<<<<<< ours
- Warframe is problematic with VSync. Turn it off or on in game, do not set to `Auto`
- Warframe needs a set a frame limit in game. Unlimited framerate can cause slowdowns
- Warframe on NVIDIA: you may need to disable GPU Particles in game otherwise the game can freeze randomly. On AMD they work fine

Full patches can be viewed in [protonprep-valve-staging.sh](patches/protonprep-valve-staging.sh).

## Installation

PLEASE NOTE: There are prerequisites for using this version of proton:

1. You must have the proper Vulkan drivers/packages installed on your system. VKD3D on AMD requires Mesa 22.0.0 or higher for the VK_KHR_dynamic_rendering extension. Check [here ](https://github.com/lutris/docs/blob/master/InstallingDrivers.md) for general driver installation guidance.

### Manual

#### Via [`asdf`, the version manager](https://asdf-vm.com/)

There is an unofficial [plugin for installing and managing ProtonGE versions](https://github.com/augustobmoura/asdf-protonge)
with [`asdf` (the universal version manager)](https://asdf-vm.com/), it follows
the same process as the manual installation but makes it a lot easier. Managing
versions by removing and updating to newer versions also becomes easier.

To install by it first [install `asdf`](https://asdf-vm.com/guide/getting-started.html),
and then proceed to add the ProtonGE plugin and install the version you want.
``` bash
asdf plugin add protonge

# Or install a version from a tag (Eg.: GE-Proton8-25)
asdf install protonge latest
```

It's also possible to use the asdf plugin in Flatpak installations, by
customizing the target `compatibilitytools.d` path. For more settings check the
[plugin's official documentation](https://github.com/augustobmoura/asdf-protonge)

After every install you need to restart Steam, and [enable proton-ge-custom](#enabling).

#### Native

This section is for those that use the native version of Steam.

1. Download a release from the [Releases](https://github.com/GloriousEggroll/proton-ge-custom/releases) page.
2. Create a `~/.steam/steam/compatibilitytools.d` directory if it does not exist.
3. Extract the release tarball into `~/.steam/steam/compatibilitytools.d/`.
   * `tar -xf GE-Proton*.tar.gz -C ~/.steam/steam/compatibilitytools.d/`
4. Restart Steam.
5. [Enable proton-ge-custom](#enabling).
  
    
*Terminal example based on Latest Release*
```bash
# make temp working directory
echo "Creating temporary working directory..."
rm -rf /tmp/proton-ge-custom
mkdir /tmp/proton-ge-custom
cd /tmp/proton-ge-custom

# download tarball
echo "Fetching tarball URL..."
tarball_url=$(curl -s https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest | grep browser_download_url | cut -d\" -f4 | grep .tar.gz)
tarball_name=$(basename $tarball_url)
echo "Downloading tarball: $tarball_name..."
curl -# -L $tarball_url -o $tarball_name --no-progress-meter

# download checksum
echo "Fetching checksum URL..."
checksum_url=$(curl -s https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest | grep browser_download_url | cut -d\" -f4 | grep .sha512sum)
checksum_name=$(basename $checksum_url)
echo "Downloading checksum: $checksum_name..."
curl -# -L $checksum_url -o $checksum_name --no-progress-meter

# check tarball with checksum
echo "Verifying tarball $tarball_name with checksum $checksum_name..."
sha512sum -c $checksum_name
# if result is ok, continue

# make steam directory if it does not exist
echo "Creating Steam directory if it does not exist..."
mkdir -p ~/.steam/steam/compatibilitytools.d

# extract proton tarball to steam directory
echo "Extracting $tarball_name to Steam directory..."
tar -xf $tarball_name -C ~/.steam/steam/compatibilitytools.d/
echo "All done :)"
```

The shell code above can be run as a script by pasting the commands in a file and adding the following to the top of the file:
```bash
#!/bin/bash
set -euo pipefail
```

Save the file and make the script runnable by adding the executable bit:
```bash
chmod +x file.sh
```

#### Flatpak

This section is for those that use the Steam flatpak.

##### Flathub

[The unofficial build provided by Flathub](https://github.com/flathub/com.valvesoftware.Steam.CompatibilityTool.Proton-GE) isn't supported by GloriousEggroll nor Valve and wasn't tested with all possible games and cases. It can behave differently from upstream builds. Use at your own risk.

1. [Add the Flathub repository](https://flatpak.org/setup/).
2. Run:
	```bash
	flatpak install com.valvesoftware.Steam.CompatibilityTool.Proton-GE
	```
3. [Enable proton-ge-custom](#enabling).

##### Manual

1. Download a release from the [Releases](https://github.com/GloriousEggroll/proton-ge-custom/releases) page.
2. Create a `~/.var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d/` directory if it does not exist.
3. Extract the release tarball into `~/.var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d/`.
   * `tar -xf GE-ProtonVERSION.tar.gz -C ~/.var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d/`
4. Restart Steam.
5. [Enable proton-ge-custom](#enabling).   

    
*Terminal example based on Latest Release*
```bash
# make temp working directory
echo "Creating temporary working directory..."
rm -rf /tmp/proton-ge-custom
mkdir /tmp/proton-ge-custom
cd /tmp/proton-ge-custom

# download tarball
echo "Fetching tarball URL..."
tarball_url=$(curl -s https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest | grep browser_download_url | cut -d\" -f4 | grep .tar.gz)
tarball_name=$(basename $tarball_url)
echo "Downloading tarball: $tarball_name..."
curl -# -L $tarball_url -o $tarball_name --no-progress-meter

# download checksum
echo "Fetching checksum URL..."
checksum_url=$(curl -s https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest | grep browser_download_url | cut -d\" -f4 | grep .sha512sum)
checksum_name=$(basename $checksum_url)
echo "Downloading checksum: $checksum_name..."
curl -# -L $checksum_url -o $checksum_name --no-progress-meter

# check tarball with checksum
echo "Verifying tarball $tarball_name with checksum $checksum_name..."
sha512sum -c $checksum_name
# if result is ok, continue

# make steam directory if it does not exist
echo "Creating Steam directory if it does not exist..."
mkdir -p ~/.var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d

# extract proton tarball to steam directory
echo "Extracting $tarball_name to Steam directory..."
tar -xf $tarball_name -C ~/.var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d/
echo "All done :)"
```

#### Snap

This section is for those that use the Steam [snap](https://snapcraft.io/steam).

This unofficial build isn't supported by GloriousEggroll nor Valve and wasn't tested with all possible games and cases. It can behave differently from upstream builds. Use at your own risk.

##### Manual

1. Download a release from the [Releases](https://github.com/GloriousEggroll/proton-ge-custom/releases) page.
2. Create a `~/snap/steam/common/.steam/steam/compatibilitytools.d/` directory if it does not exist.
3. Extract the release tarball into `~/snap/steam/common/.steam/steam/compatibilitytools.d/`.
   * `tar -xf GE-ProtonVERSION.tar.gz -C ~/snap/steam/common/.steam/steam/compatibilitytools.d/`
4. Restart Steam.
5. [Enable proton-ge-custom](#enabling).


##### Enabling NTSync
For NTSync to work, your kernel must be version 6.14 or newer and built with `CONFIG_NTSYNC=y` -OR- `CONFIG_NTSYNC=m`.
If using `CONFIG_NTSYNC=m`, a module loading configuration is required followed by a reboot:

/etc/modules-load.d/ntsync.conf
```
ntsync
```
You can also manually enable the module without reboot, just keep in mind the above configuration is needed for it to persist reboot:
```
sudo modprobe ntsync
```
After this, a device `/dev/ntsync` should now exist on your system.

Once NTSYNC is enabled on the system, if you launch a game with GE-Proton10-10 or newer using PROTON_LOG=1, steam will generate a log for the game in your home folder `steam-XXXXXX.log`. Inside that log you should see `wineserver: NTSync up and running!`


## Building

1. Clone this repo by executing:

```sh
git clone --recurse-submodules http://github.com/gloriouseggroll/proton-ge-custom
```

2. Drop any custom patches into patches/, then open patches/protonprep-valve-staging.sh and add a patch line for them under `#WINE CUSTOM PATCHES` in the same way the others are done.

3. Apply all of the patches in patches/ by running:

```sh
./patches/protonprep-valve-staging.sh &> patchlog.txt
=======
```text
Input : [        Frame1][Frame2][Frame3][EOS]
Output: [lead‑in + PCM1][  PCM2][  PCM3]
          ↑               ↑       ↑
          one‑to‑one mapping
>>>>>>> theirs
```

GStreamer expects each input frame to correspond exactly to an output PCM buffer.

#### Gapless Behavior

```text
Input : [Frame1][Frame2][Frame3][EOS] → queue is empty
Output: [  PCM1][  PCM2][  PCM3][DelayFrame]
           ↑                      ↑
     lead‑in removed         no matching input
```

<<<<<<< ours
Build will be placed within the build directory as SOME-BUILD-NAME-HERE.tar.gz.

## Enabling

1. Right click any game in Steam and click `Properties`.
2. At the bottom of the `Compatibility` tab, Check `Force the use of a specific Steam Play compatibility tool`, then select the desired Proton version.
3. Launch the game.

## Modification

Environment variable options:

| Compat config string  | Environment Variable           | Description  |
| :-------------------- | :----------------------------- | :----------- |
|                       | <tt>PROTON_LOG</tt>            | Convenience method for dumping a useful debug log to `$HOME/steam-$APPID.log`. For more thorough logging, use `user_settings.py`. |
|                       | <tt>PROTON_DUMP_DEBUG_COMMANDS</tt> | When running a game, Proton will write some useful debug scripts for that game into `$PROTON_DEBUG_DIR/proton_$USER/`. |
|                       | <tt>PROTON_DEBUG_DIR</tt>      | Root directory for the Proton debug scripts, `/tmp` by default. |
| <tt>wined3d</tt>      | <tt>PROTON_USE_WINED3D</tt>    | Use OpenGL-based wined3d instead of Vulkan-based DXVK for d3d11 and d3d10. This used to be called `PROTON_USE_WINED3D11`, which is now an alias for this same option. |
| <tt>nod3d12</tt>      | <tt>PROTON_NO_D3D12</tt>       | Disables DX12. |
| <tt>nod3d11</tt>      | <tt>PROTON_NO_D3D11</tt>       | Disables DX11. |
| <tt>nod3d10</tt>      | <tt>PROTON_NO_D3D10</tt>       | Disables DX10. |
| <tt>nod3d9</tt>      | <tt>PROTON_NO_D3D9</tt>        | Disables DX9.  |
| <tt>noesync</tt>      | <tt>PROTON_NO_ESYNC</tt>       | Do not use eventfd-based in-process synchronization primitives. |
| <tt>nofsync</tt>      | <tt>PROTON_NO_FSYNC</tt>       | Do not use futex-based in-process synchronization primitives. (Automatically disabled on systems with no `FUTEX_WAIT_MULTIPLE` support.) |
| <tt>nontsync</tt>      | <tt>PROTON_NO_NTSYNC</tt>       | Do not use ntsync kernel module for in-process synchronization primitives. |
| <tt>forcelgadd</tt>   | <tt>PROTON_FORCE_LARGE_ADDRESS_AWARE</tt> | Force Wine to enable the LARGE_ADDRESS_AWARE flag for all executables. |
| <tt>heapdelayfree</tt>| <tt>PROTON_HEAP_DELAY_FREE</tt>| Delay freeing some memory, to work around application use-after-free bugs. |
| <tt>noxim</tt>        | <tt>PROTON_NO_XIM</tt>         | Enabled by default. Do not attempt to use XIM (X Input Methods) support. XIM support is known to cause crashes with libx11 older than version 1.7. |
| <tt>enablenvapi</tt>  | <tt>PROTON_ENABLE_NVAPI</tt>   | Enable NVIDIA's NVAPI GPU support library. |
| <tt>noforcelgadd</tt> |                                | Disable forcelgadd. If both this and `forcelgadd` are set, enabled wins. |
| <tt>oldglstr</tt>     | <tt>PROTON_OLD_GL_STRING</tt>  | Set some driver overrides to limit the length of the GL extension string, for old games that crash on very long extension strings. |
| <tt>cmdlineappend:</tt>|                               | Append the string after the colon as an argument to the game command. May be specified more than once. Escape commas and backslashes with a backslash. |
| <tt>xalia or noxalia</tt>               | <tt>PROTON_USE_XALIA</tt>                 | Enable Xalia, a program that can add a gamepad UI for some keyboard/mouse interfaces, or set to 0 to disable. The default is to enable it dynamically based on window contents. |
| <tt>seccomp</tt>      | <tt>PROTON_USE_SECCOMP</tt>    | Enable seccomp-bpf filter to emulate native syscalls, required for some DRM protections to work. |
| <tt>nowritewatch</tt> | <tt>PROTON_NO_WRITE_WATCH</tt> | Disable support for memory write watches in ntdll. This is a very dangerous hack and should only be applied if you have verified that the game can operate without write watches. This improves performance for some very specific games (e.g. CoreRT-based games). |
|                       | <tt>WINE_FULLSCREEN_FSR</tt>   | Enable AMD FidelityFX Super Resolution (FSR) 1, use in conjunction with `WINE_FULLSCREEN_FSR_STRENGTH`. Only works in Vulkan games (DXVK and VKD3D-Proton included). |
|                       | <tt>WINE_FULLSCREEN_FSR_STRENGTH</tt> | AMD FidelityFX Super Resolution (FSR) strength, the default sharpening of 5 is enough without needing modification, but can be changed with 0-5 if wanted. 0 is the maximum sharpness, higher values mean less sharpening. 2 is the AMD recommended default and is set by GE-Proton by default. |
|                       | <tt>WINE_FULLSCREEN_FSR_CUSTOM_MODE</tt> | Set fake resolution of the screen. This can be useful in games that render in native resolution regardless of the selected resolution. Parameter `WIDTHxHEIGHT` |
|                       | <tt>WINE_DO_NOT_CREATE_DXGI_DEVICE_MANAGER</tt> | Set to 1 to enable. Required for video playback in some games to not be miscolored (usually tinted pink) |
|                       | <tt>COPYPREFIX</tt> | Set to 1 to enable. If -steamdeck is used on steam (or SteamDeck=1 is set), copies the game's prefix and shader cache from the game partition to the local steam steamapps folder. Logic is reversed if -steamdeck not enabled (or SteamDeck=0) |
## Credits

As many of you may or may not already know, there is a Credits section in the README for this Git repository. My proton-ge project contains some of my personal tweaks to Proton, but a large amount of the patches, rebases and fixes come from numerous people's projects. While I tend to get credited for my builds, a lot of the work that goes into it are from other people as well. I'd like to take some time to point a few of these people out of recognition. In future builds, I plan to make clearer and more informative Git commits, as well as attempt to give these people further crediting, as my README may not be sufficient in doing so.

### TKG (Etienne Juvigny)

- https://www.patreon.com/tkglitch
- https://github.com/Frogging-Family/wine-tkg-git

I and many others owe TKG. In regards to both WINE and Proton. He has dedicated a lot of time (2+ years at least) to rebasing WINE and Proton patches, as well as making his own contributions. Before he came along, I did some rebasing work, and mainly only released things for Arch. These days he almost always beats me to rebasing, and it saves myself and others a **lot** of work.

### Guy1524 (Derek Lesho)

- https://github.com/Guy1524

Derek was responsible for the original rawinput patches, as well as several various game fixes in the past, just to name a few: MK11, FFXV, MHW, Steep, AC Odyssey FS fix. He has also done a massive amount of work on media foundation/mfplat, which should be hopefully working very soon.

### Joshie (Joshua Ashton)

- https://github.com/Joshua-Ashton/d9vk

Joshua is the creator of D9VK and also a huge contributor of DXVK. He is also known for his recent DOOM Eternal WINE fixes and also many of the Vulkan tweaks and fixes used, such as FS hack interger scaling.

### doitsujin/ドイツ人 (Philip Rebohle)

- https://github.com/doitsujin/dxvk

Philip is the creator of DXVK and a heavy contributor of VKD3D. He also put up a lot of my bug reporting for Warframe years ago, when DXVK started.

### HansKristian/themaister (Hans-Kristian Arntzen)

- https://github.com/HansKristian-Work

Hans-Kristian is a heavy contributor of VKD3D and he also created a lot of WINE patches that allowed WoW to work.

### flibitijibibo (Ethan Lee)

- https://github.com/sponsors/flibitijibibo
- https://fna-xna.github.io/

Ethan is the creator of FAudio, and he also listened to my Warframe bug reports years ago.

### simmons-public (Chris Simmons)

- https://github.com/simons-public

Chris is the creator of the original Protonfixes project. The portions of Protonfixes I've imported are what allow customizations to be made to prefixes for various Proton games. without Proton fixes many games would still be broken and/or require manual prefix modification. Huge thanks to Chris.

### Sporif (Amine Hassane)

- https://github.com/Sporif

Amine is the current maintainer of dxvk-async. This is a feature that was originally removed from dxvk as it happened around the same time a few overwatch bans happened. It was thought, but never confirmed whether or not this feature caused the bans, so the feature was removed as a safety precaution. It is still safe to use in many single player games, and games that do not have competitive anti-cheats. It has also been confirmed to work safely in Warframe and Path of Exile.

### wine-staging maintainers

I also of course need to thank my fellow wine-staging maintainers: Alistair Leslie-Hughes, Zebediah Figura and Paul Gofman

They have contributed MANY patches to staging, far beyond what I have done, as well as kept up with regular rebasing. A lot of times when bug reports come to me, if it has to do with staging I end up testing and relaying information to these guys in order to get issues resolved.

### Reporters

Additionally, a thank you is owed to Andrew Aeikum (aeikum), and kisak (kisak-valve) for regularly keeping me in the loop with Proton and fsync patches, as well as accepting PRs I've made to fix Proton build system issues, or listening to bug reports on early Proton patches before they reach Proton release.

### Patrons
=======
Because there’s no input frame for `DelayFrame`, GStreamer throws an error. This is an architectural limitation in GStreamer.
>>>>>>> theirs

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
