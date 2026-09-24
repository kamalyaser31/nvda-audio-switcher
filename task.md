# Audio Switcher - Task Management

## Current Task: Release Version 2026.3 with Pure Core Audio, Device Cycling & Mic Mute

- [x] Analyze `nvda-powerbox` audio manager architecture.
- [x] Design pure ctypes COM VTable backend (`core_audio.py`).
- [x] Conduct architecture grilling interview (/grill-me) and resolve design decisions.
- [x] Implement `core_audio.py` with zero dependencies.
- [x] Surgically update `__init__.py` to replace `pycaw`/`comtypes`.
- [x] Delete `pycaw/` bundle and remove temporary cache directory logic.
- [x] Conduct rigorous `clean-code-guard` audit (decouple subroutines to ≤ 20 lines, eliminate broad catches and defensive clutter).
- [x] Brainstorm and design new features (/brainstorming: Bounded Path):
  - [x] One-key cyclic device switching for speakers and microphones (`script_cycleNextSpeaker`, `script_cycleNextMicrophone`).
  - [x] Instant hardware kernel mute toggle for default microphone (`script_toggleDefaultMicMute`).
  - [x] Default microphone mute state query and announcement (`script_announceMicMuteState`).
- [x] Verify live device enumeration, default queries, cycling, and mic muting on hardware.
- [x] Bump version to 2026.3 in `buildVars.py` and `addon/manifest.ini`.
- [x] Update documentation in Arabic (`addon/doc/ar/readme.md`) and English (`addon/doc/en/readme.md`).
- [x] Update project state files (`CHANGELOG.md`, `project_state.md`, `task.md`).
- [x] Push commits to origin/master.
- [x] Publish GitHub Release `v2026.3` with attached `audioSwitcher-2026.3.nvda-addon`.
- [x] Submit registration issue to NVDA Add-on Store (`nvaccess/addon-datastore` issue #11776).
