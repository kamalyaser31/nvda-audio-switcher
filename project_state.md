# Audio Switcher - Project State

## Overview
Audio Switcher is an NVDA screen reader add-on created by Kamal Yaser that sets configured or directly selected speakers and microphones as default and announces current defaults.

## Architecture & Tech Stack
- **Version:** 2026.5 (merged into local `master`, not pushed or published; 2026.4 is the published release)
- **Runtime:** Python 3 (NVDA 2025.1+ required, tested up to NVDA 2026.1).
- **Core Audio Backend (`core_audio.py`):** Pure Win32 Core Audio using standard `ctypes` and raw COM VTables:
  - `MMDeviceEnumerator`: audio endpoint enumeration (`getActiveDevices`) and default device queries (`getDefaultDeviceInfo`).
  - `IPropertyStore`: device friendly name extraction (`PKEY_Device_FriendlyName`).
  - `IAudioEndpointVolume`: instant hardware kernel mute querying (`getDefaultMicMute`) and toggling (`toggleDefaultMicMute`).
  - `IPolicyConfigClient`: default audio endpoint selection across `eConsole`, `eMultimedia`, and `eCommunications` roles (`setDefaultDevice`).
  - `cycleNextDevice`: cyclic device progression with position tracking.
  - Explicit COM reference releasing (`IUnknown::Release`) for memory safety.
- **UI & Integration (`__init__.py`):**
  - `GlobalPlugin`: NVDA scripts and gestures.
  - `AudioDeviceSelectionDialog`: wxPython quick selection dialog.
  - `AudioSwitcherSettingsPanel`: NVDA settings categories panel.
- **Profiles (`profiles.py`):** pure logic with no NVDA imports (`resolveProfile`, `currentDevicesAsProfile`, `profileConfspec`), tested by `run_tests.py` at the root. Config keys `profile{n}Name|Speaker|Mic|Nvda` for n = 1-3; `""` means no change, `Nvda` may be `"default"`.
  - Zero external dependencies: no `pycaw`, no `comtypes`, no temp disk cache.

## Current Progress & Release Status
- Migration to pure Win32 Core Audio completed and verified on hardware.
- Added cyclic device switching for speakers and microphones with position announcements.
- Added instant default microphone mute toggle and mute state query.
- Version bumped to 2026.3 across manifest, buildVars, and documentation.
- All 16 legacy `pycaw/` files removed.
- GitHub Release v2026.3 published with `audioSwitcher-2026.3.nvda-addon`.
- Registration issue #11776 submitted to NVDA Add-on Store (`nvaccess/addon-datastore`).
- 2026.4 published (store #11897, 2026-09-30); branch `feat/nvda-output-toggle` deleted.
- 2026.5 implemented on `feat/profiles` (three profiles; quick dialog NVDA field switches output), built as `audioSwitcher-2026.5.nvda-addon`; live-tested in portable NVDA 2026.2, confirmed by Kamal in his installed NVDA, and merged into `master` on 2026-11-04. Design and plan in `docs/superpowers/`.
- Decision: open number of profiles rejected, because NVDA Input Gestures lists only scripts defined in advance; three fixed profiles instead.
- 2026.4 contents (from `feat/nvda-output-toggle`):
  - Integrated NVDA output toggling feature (merged from `audioToggler`/`nvdaOutputToggler`).
  - Unified core audio device discovery and hybrid persistence (`id|name`) in `confspec`.
  - Atomic switching: reinitialises `tones` and reloads the running synth via `setSynth()`, with rollback on failure.
  - Secondary output device configuration added to `AudioSwitcherSettingsPanel`; all saved devices persist while unplugged.
  - Secondary output device selection added to `AudioDeviceSelectionDialog`.
  - Added `script_toggleNvdaOutput` to `GlobalPlugin`.
  - Added `script_openSettings` to `GlobalPlugin` for direct shortcut into NVDA settings panel.
  - Fixed variable shadowing bug in `_updateNvdaSecondaryChoice` where `_` masked gettext `_()` translation function causing dialog crash.
  - Code review fixes (2026-09-30): add-on translations now load, saved slots survive disconnection, minimum NVDA 2025.1, connection checks before switching, Core Audio errors routed to the NVDA log, version bumped to 2026.4.
  - `clean-code-guard` verified: all functions in `__init__.py` <= 20 lines.
  - Documentation and translations updated in Arabic and English.
