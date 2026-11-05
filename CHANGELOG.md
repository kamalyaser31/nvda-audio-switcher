# Changelog

All notable changes to the Audio Switcher add-on will be documented in this file.

## [Unreleased]

### docs: root README
- Added a root `README.md` written for beginners, which is now the source of the English help.

## [2026.5] - 2026-11-04

### feat: audio profiles
- Added three named profiles; each can set the default speaker, the default microphone, and NVDA's output device, and is activated by its own gesture (`script_activateProfile1`-`3`).
- Activation speaks only the profile name; unplugged devices are skipped and named (`Not connected: ...`).
- Added a profile section to the settings panel with a profile chooser and a "Save current devices to profile" button.

### feat: quick dialog switches NVDA output
- Choosing a device in the dialog's NVDA list now also moves NVDA speech to it at once; clearing it returns NVDA to the system default when NVDA was on the cleared device.

### chore: housekeeping
- Dated the 2026.4 release and deleted the merged `feat/nvda-output-toggle` branch.

## [2026.4] - 2026-09-30

### feat: integrate NVDA output toggling and direct settings panel gesture
- Added one-key toggling between primary and secondary NVDA speech output devices (`script_toggleNvdaOutput`).
- Added secondary device selector in `AudioDeviceSelectionDialog` and `AudioSwitcherSettingsPanel`.
- Added direct shortcut to open Audio Switcher settings panel (`script_openSettings`).

### fix: resolve gettext translation function shadowing in secondary device choice
- Fixed variable unpack shadowing `_` translation function causing crash in `AudioDeviceSelectionDialog`.
- Completed comprehensive AST audit confirming zero variable shadowing across codebase.

### fix: code review findings
- Load the add-on's own translations (`addonHandler.initTranslation()`); Arabic strings were never used.
- Settings panel no longer clears speaker/mic slots whose device is disconnected, renamed, or stored in the old name-only format; such devices are listed as "saved, not connected".
- Raised minimum NVDA version to 2025.1 (`config.conf["audio"]["outputDevice"]` does not exist earlier).
- NVDA output toggle: reinitialise tones with the synth so beeps follow the new device, report synth reload failures correctly, and verify the secondary device is connected before switching.
- Core Audio errors now go to the NVDA log.
- Configured slot shortcuts check the device is connected before switching, so an unplugged device reliably reports `Not found`.
- Restored translator comments removed during refactoring.
- Cycling now starts from the first device when the current default is not an active device.
- COM is initialised once at import instead of on every call.
- Quick selection dialog keeps the secondary-output pick on Refresh and is reused instead of opening twice.
- `feedbackType` is bounded to 0–3 in the config spec.

## [2026.3] - 2026-09-24

### feat: add cyclic device switching and instant default mic mute controls
- Added one-key cyclic device switching for speakers (`script_cycleNextSpeaker`) and microphones (`script_cycleNextMicrophone`) with relative position announcements (`1 of 3`).
- Added instant hardware kernel mute toggle (`script_toggleDefaultMicMute`) with distinct audio tones and concise speech feedback (`Mic muted` / `Mic on`).
- Added default microphone mute state query and announcement (`script_announceMicMuteState`).

### refactor: migrate audio backend from pycaw/comtypes to pure Win32 Core Audio
- Created `core_audio.py` implementing pure Win32 Core Audio COM VTables (`MMDeviceEnumerator`, `IMMDeviceCollection`, `IMMDevice`, `IPropertyStore`, `IAudioEndpointVolume`, and `IPolicyConfigClient`).
- Surgically updated `__init__.py` to import audio primitives directly from `core_audio`.
- Completely removed `pycaw/` package and eliminated temporary disk caching (`nvda_comtypes_cache`).
