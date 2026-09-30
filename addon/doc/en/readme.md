# Audio Switcher

• Author: Kamal Yaser
• Version: 2026.4
• Compatibility: NVDA 2025.1 and later

Audio Switcher is an NVDA add-on for quickly setting configured Windows audio devices as default. It is designed to be simple and lightweight, avoiding the complexity of other audio control add-ons by focusing solely on quick and reliable device switching.

## Features

- Cycle to the next playback device (speaker) with one key, announcing its name and relative position.
- Cycle to the next recording device (microphone) with one key, announcing its name and relative position.
- Instant hardware kernel mute toggle for the default microphone with distinct audio tones and concise speech.
- Announce current default microphone mute state without altering it.
- Toggle NVDA audio output between Primary (System Default) and a configured secondary output device with a single keystroke.
- Set one of three speaker/output devices as default.
- Set one of three microphone/input devices as default.
- Announce the current default speaker.
- Announce the current default microphone.
- Announce the current default speaker and microphone together.
- Open a compact dialog to change the default speaker, default microphone, or NVDA secondary device.
- Refresh connected devices from inside the quick selection dialog.
- Optional feedback: beep and speech, speech only, beep only, or none.
- Pure Win32 Core Audio implementation via ctypes with zero external dependencies and no temporary cache files.
- Unique hardware ID matching to prevent conflicts between devices with identical names.
- Numbered labels distinguish connected devices that have identical names.
- Device lists show only audio devices that are currently connected; saved devices that are unplugged stay in the settings.


## Settings

Open NVDA settings and choose **Audio Switcher**.

Configure:

- Speaker 1
- Speaker 2
- Speaker 3
- Microphone 1
- Microphone 2
- Microphone 3
- NVDA Secondary Output Device
- Feedback type

The add-on uses the device names shown by Windows. Only connected devices appear in its lists. If a configured device is later disconnected, its shortcut will say `Not found`, and it stays saved in the settings, listed as `(saved, not connected)`.

## Input Gestures

Assign shortcuts from NVDA's **Input Gestures** dialog.

Available actions:

- Set speaker 1 as default
- Set speaker 2 as default
- Set speaker 3 as default
- Set microphone 1 as default
- Set microphone 2 as default
- Set microphone 3 as default
- Cycle to next playback device (speaker)
- Cycle to next recording device (microphone)
- Toggle mute for default microphone
- Announce whether default microphone is muted
- Toggle NVDA audio output between Primary and secondary device
- Announce current default speaker
- Announce current default microphone
- Announce current default speaker and microphone
- Choose default audio devices
- Open Audio Switcher settings

The quick selection dialog lists connected speakers and microphones separately, along with the NVDA secondary output device. Each list starts with a **Do not change** choice, so selecting a device in one list never changes the other device type unless you select it explicitly. **Refresh devices** preserves a selected device while it remains connected and resets only a selection whose device disappeared. Empty lists state that no connected devices are available and are disabled.
