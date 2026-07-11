# Audio Switcher

Audio Switcher is an NVDA add-on for quickly setting configured Windows audio devices as default.

## Features

- Set one of three speaker/output devices as default.
- Set one of three microphone/input devices as default.
- Announce the current default speaker.
- Announce the current default microphone.
- Optional feedback: beep and speech, speech only, beep only, or none.

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

The add-on uses the device names shown by Windows. If a device is disconnected, its shortcut will say `Not found`.

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

## Messages

- `Done: speaker 1`
- `Done: mic 1`
- `Not set`
- `Not found`
- `Speaker: device name`
- `Mic: device name`
- `No speaker`
- `No mic`

## Requirements

- NVDA 2024.1 or later
- Windows audio devices supported by the Windows Core Audio API
