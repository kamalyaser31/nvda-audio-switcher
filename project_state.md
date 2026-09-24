# Audio Switcher - Project State

## Overview
Audio Switcher is an NVDA screen reader add-on created by Kamal Yaser that sets configured or directly selected speakers and microphones as default and announces current defaults.

## Architecture & Tech Stack
- **Version:** 2026.3
- **Runtime:** Python 3 (NVDA 2024.1+ compatible, tested up to NVDA 2026.1).
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
  - Zero external dependencies: no `pycaw`, no `comtypes`, no temp disk cache.

## Current Progress & Release Status
- Migration to pure Win32 Core Audio completed and verified on hardware.
- Added cyclic device switching for speakers and microphones with position announcements.
- Added instant default microphone mute toggle and mute state query.
- Version bumped to 2026.3 across manifest, buildVars, and documentation.
- All 16 legacy `pycaw/` files removed.
- GitHub Release v2026.3 published with `audioSwitcher-2026.3.nvda-addon`.
- Registration issue #11776 submitted to NVDA Add-on Store (`nvaccess/addon-datastore`).
- Local feature branch `feat/nvda-output-toggle`:
  - Integrated NVDA output toggling feature (merged from `audioToggler`/`nvdaOutputToggler`).
  - Unified core audio device discovery and hybrid persistence (`id|name`) in `confspec`.
  - Atomic switching with `synthDriverHandler.handleConfigChange()` and `setSynth()` rollback protection.
  - Secondary output device configuration added to `AudioSwitcherSettingsPanel` with unplugged persistence.
  - Secondary output device selection added to `AudioDeviceSelectionDialog`.
  - Added `script_toggleNvdaOutput` to `GlobalPlugin`.
  - Added `script_openSettings` to `GlobalPlugin` for direct shortcut into NVDA settings panel.
  - `clean-code-guard` verified: all functions in `__init__.py` <= 20 lines.
  - Documentation and translations updated in Arabic and English.
