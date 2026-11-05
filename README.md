# Audio Switcher

Changing your speaker or microphone in Windows takes many steps through menus, and it is slow with a screen reader. Audio Switcher lets you change them with one key from anywhere.

- Author: Kamal Yaser
- Version: 2026.5
- Works with: NVDA 2025.1 and later

## Problems it solves

- You want to move from your headset to your desk speakers without opening Windows sound settings.
- You use one set of devices for meetings and another for everyday work, and you want to switch all of them at once.
- You want NVDA to speak through one device while other sound plays through another.
- You want to mute your microphone quickly and be sure whether it is muted.
- You want to know which speaker or microphone is in use now.

## Installing

1. Open the [releases page](https://github.com/kamalyaser31/nvda-audio-switcher/releases).
2. Download the newest file that ends in `.nvda-addon`.
3. Open the file and confirm that you want to install it.
4. Restart NVDA.

You can also install it from the NVDA Add-on Store.

## How to use it

The add-on has no keys set when you install it. You choose your own keys:

1. Open the NVDA menu, then Preferences, then Input Gestures.
2. Open the Audio Switcher category.
3. Choose a command, press Add, and press the key you want.

Then set up your devices:

1. Open the NVDA menu, then Preferences, then Settings.
2. Choose Audio Switcher.
3. Choose your devices, then press OK.

Only connected devices appear in the lists. A device you saved stays in the settings after you unplug it, and is marked "saved, not connected".

## Profiles

A profile changes the speaker, the microphone, and NVDA's own output together with one key. There are three profiles.

To set up a profile:

1. Open the Audio Switcher settings.
2. In the Profile list, choose Profile 1, 2, or 3.
3. Type a name for it, such as Headset.
4. Choose its speaker, microphone, and NVDA output. Leave a list on "No change" if that device should stay as it is.
5. Press OK.

To save the devices you use now, press "Save current devices to profile". This only fills in the fields. Nothing is saved until you press OK or Apply.

When you press the key for a profile, you hear only its name. If one of its devices is unplugged, the other devices still change, and you hear which device is not connected.

## The quick dialog

The command "Choose default audio devices" opens a short dialog with three lists: speakers, microphones, and NVDA's secondary output.

Each list starts with an option that changes nothing, so you change only what you choose. Choosing a device in the NVDA list saves it as the secondary device and moves NVDA speech to it right away. Choosing "None (Clear)" removes the secondary device, and NVDA goes back to the system default if it was using that device.

Press "Refresh devices" if you plug in a device while the dialog is open.

## All commands

Find these in the Audio Switcher category of Input Gestures:

- Activate profile 1
- Activate profile 2
- Activate profile 3
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

The Feedback type setting chooses what you get after a change: a beep and speech, speech only, a beep only, or nothing. Errors are always spoken.

## Reporting a problem

1. Press NVDA+F1 to open the NVDA log.
2. Find the lines that mention AudioSwitcher, an audio device, or SetDefaultDevice.
3. Copy those lines.
4. Post them on the [issues page](https://github.com/kamalyaser31/nvda-audio-switcher/issues), and say what you did and what you expected.

These lines hold only the names and IDs of your audio devices, so they are safe to share.

## For developers

From the repository folder, run `python run_tests.py` for the tests and `scons` to build the add-on. The history of changes is in the [changelog](https://github.com/kamalyaser31/nvda-audio-switcher/blob/master/CHANGELOG.md). Contributions are welcome through [pull requests](https://github.com/kamalyaser31/nvda-audio-switcher/pulls).

## Developer

- **Developer:** Kamal Yaser
- **Email:** [kamalyaser31@gmail.com](mailto:kamalyaser31@gmail.com)
- **Telegram:** [@kamalyaser31](https://t.me/kamalyaser31)

## License

This add-on is released under the GNU General Public License, version 2 (GPL v2).
