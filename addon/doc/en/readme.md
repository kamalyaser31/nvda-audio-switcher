# Audio Switcher

• Author: Kamal Yaser
• Version: 2026.2
• Compatibility: NVDA 2024.1 and later

Audio Switcher is an NVDA add-on for quickly setting configured Windows audio devices as default. It is designed to be simple and lightweight, avoiding the complexity of other audio control add-ons by focusing solely on quick and reliable device switching.

## Features

- Set one of three speaker/output devices as default.
- Set one of three microphone/input devices as default.
- Announce the current default speaker.
- Announce the current default microphone.
- Announce the current default speaker and microphone together.
- Open a compact dialog to change either the default speaker, the default microphone, or both.
- Refresh connected devices from inside the quick selection dialog.
- Optional feedback: beep and speech, speech only, beep only, or none.
- Unique hardware ID matching to prevent conflicts between devices with identical names.
- Numbered labels distinguish connected devices that have identical names.
- Device lists show only audio devices that are currently connected.

## Settings

Open NVDA settings and choose **Audio Switcher**.

Configure:

- Speaker 1
- Speaker 2
- Speaker 3
- Microphone 1
- Microphone 2
- Microphone 3
- Feedback type

The add-on uses the device names shown by Windows. Only connected devices appear in its lists. If a configured device is later disconnected, its shortcut will say `Not found`.

## Input Gestures

Assign shortcuts from NVDA's **Input Gestures** dialog.

Available actions:

- Set speaker 1 as default
- Set speaker 2 as default
- Set speaker 3 as default
- Set microphone 1 as default
- Set microphone 2 as default
- Set microphone 3 as default
- Announce current default speaker
- Announce current default microphone
- Announce current default speaker and microphone
- Choose default audio devices

The quick selection dialog lists connected speakers and microphones separately. Each list starts with a **Do not change** choice, so selecting a device in one list never changes the other device type unless you select it explicitly. **Refresh devices** preserves a selected device while it remains connected and resets only a selection whose device disappeared. Empty lists state that no connected devices are available and are disabled.
