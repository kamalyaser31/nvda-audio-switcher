# Changelog

All notable changes to the Audio Switcher add-on will be documented in this file.

## [Unreleased]

### feat: integrate NVDA output toggling and direct settings panel gesture
- Added one-key toggling between primary and secondary NVDA speech output devices (`script_toggleNvdaOutput`).
- Added secondary device selector in `AudioDeviceSelectionDialog` and `AudioSwitcherSettingsPanel`.
- Added direct shortcut to open Audio Switcher settings panel (`script_openSettings`).
- Implemented Fast-Path direct device execution in `setConfiguredDevice` and `toggleNvdaOutputWithFeedback`, eliminating redundant active device scans.

### fix: resolve gettext translation function shadowing in secondary device choice
- Fixed variable unpack shadowing `_` translation function causing crash in `AudioDeviceSelectionDialog`.
- Completed comprehensive AST audit confirming zero variable shadowing across codebase.

## [2026.3] - 2026-09-24

### feat: add cyclic device switching and instant default mic mute controls
- Added one-key cyclic device switching for speakers (`script_cycleNextSpeaker`) and microphones (`script_cycleNextMicrophone`) with relative position announcements (`1 of 3`).
- Added instant hardware kernel mute toggle (`script_toggleDefaultMicMute`) with distinct audio tones and concise speech feedback (`Mic muted` / `Mic on`).
- Added default microphone mute state query and announcement (`script_announceMicMuteState`).

### refactor: migrate audio backend from pycaw/comtypes to pure Win32 Core Audio
- Created `core_audio.py` implementing pure Win32 Core Audio COM VTables (`MMDeviceEnumerator`, `IMMDeviceCollection`, `IMMDevice`, `IPropertyStore`, `IAudioEndpointVolume`, and `IPolicyConfigClient`).
- Surgically updated `__init__.py` to import audio primitives directly from `core_audio`.
- Completely removed `pycaw/` package and eliminated temporary disk caching (`nvda_comtypes_cache`).
