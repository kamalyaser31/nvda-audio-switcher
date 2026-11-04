# Audio Profiles - Design

Status: approved by Kamal on 2026-11-03 (not implemented yet).
Target version: 2026.5.

## Intent

Switching from one setup to another (for example headset to desk speakers)
takes up to three separate keys today: speaker slot, microphone slot, and the
NVDA output toggle. A profile does all of it with one key and announces only
the profile name.

## Goals

- Three fixed profiles. Each has a name, a speaker, a microphone, and an NVDA
  output device.
- Each of the three device fields is optional and starts as "No change".
- The NVDA field offers: No change, System default, then the connected
  playback devices.
- One script per profile, listed in NVDA's Input Gestures dialog with no
  default gesture (same as the existing slots).
- Profiles are created and edited in the existing Audio Switcher settings panel.
- A "Save current devices" button fills the selected profile with the current
  Windows default speaker, microphone, and NVDA output device.
- On activation, the add-on announces the profile name only. Failures are
  announced in detail.

## Non-goals

- An open number of profiles (rejected: NVDA Input Gestures lists only scripts
  defined in advance).
- A cycling key between profiles.
- Switching profiles automatically when a device is plugged in.

## Anti-goals

- A profile must never stop at the first missing device. It applies every
  connected device and names the missing ones.
- The settings panel must not grow by fifteen Tab stops.

## Approaches

1. **Profile chooser, then one set of fields (chosen).** A combo box selects
   Profile 1, 2, or 3. Below it are the fields of the selected profile:
   name, speaker, microphone, NVDA output, and "Save current devices". This
   adds six Tab stops. It costs a little more code, because edits to all
   three profiles are held in memory while the user switches the chooser.
2. **All profiles laid out in full.** This is simpler code, but it adds fifteen
   controls to a panel that is already long. Rejected for screen-reader use.
3. **A separate profiles dialog.** Rejected: Kamal chose the settings panel.

## Decided by Kamal

- Three profiles, with names.
- NVDA output is optional per profile.
- One shortcut per profile.
- Missing device: apply the rest and warn.
- Managed in the settings panel, with the chooser layout.
- A "Save current devices" button.
- Activation announces the profile name only.
- The NVDA field options are No change, System default, and the connected
  devices.

## Builder's calls (Claude's proposals, open to correction)

- **Config keys**: add flat keys to `confspec`, matching the existing style:
  `profile{n}Name`, `profile{n}Speaker`, `profile{n}Mic`, and
  `profile{n}Nvda`, for n = 1 to 3. All are `string(default="")`.
  - `""` means "No change".
  - Speaker and Mic use the existing `id|name` format.
  - Nvda is `""`, `"default"`, or `id|name`.
- **Empty name**: the name falls back to "Profile {n}".
- **Empty profile** (all three fields "No change"): announce
  "{name} is not configured" and change nothing.
- **Apply order**: speaker, then microphone, then NVDA output. NVDA goes last
  because `safeSetNvdaOutputDevice` reloads the synth.
- **Device matching**: reuse `findMatchingDeviceId` against `getActiveDevices`
  for every field, so a renamed or reconnected device still matches by ID.
- **NVDA "default"**: call `safeSetNvdaOutputDevice("default")` with no
  connection check.
- **Feedback** follows `feedbackType`:
  - The beep and the speech honour the same setting as the other commands.
  - Full success: the speech is the profile name, for example "Headset".
  - Partial success: the profile name, then "Not connected: <device names>".
  - Total failure: the failure messages only, with no tone. This matches
    `provideFeedback` and every other command in the add-on.
- **Settings panel**: when the chooser changes, the current field values are
  stored in a small in-memory dict and the fields are reloaded from it. All
  three profiles are written in `onSave`, so the panel still has one save path.
  If a saved device is unplugged, it keeps the existing
  "(saved, not connected)" label.
- **"Save current devices"**: it reads `getDefaultDeviceInfo` for render and
  capture and `config.conf["audio"]["outputDevice"]`. It only fills the
  fields; nothing is written until OK or Apply.
- **NVDA output toggle**: unchanged. It reads the current output device, so it
  works the same after a profile has set one.
- **Code size**: keep the existing limit of 20 lines or fewer per function.
  Put the profile logic in small module-level functions beside
  `applyDeviceSelections`.

## Also in 2026.5: quick dialog switches NVDA output (decided by Kamal)

Today, choosing a device in the NVDA field of `AudioDeviceSelectionDialog`
only saves it as `nvdaSecondaryOutput`. From 2026.5:

- **Choosing a device:** it is saved as the secondary device, as today. NVDA
  speech also moves to it at once.
  - In `_applySecondaryDevice`, call `safeSetNvdaOutputDevice` with the ID
    matched by `findMatchingDeviceId`. This reuses the connection check and the
    rollback.
- **Choosing "None":** the secondary device is cleared. If NVDA is on that
  device, NVDA goes back to `"default"`.
- **Choosing "No change":** nothing happens, as today.
- **Feedback:** use the existing `provideFeedback` lists. Success adds
  "NVDA: <device>". Failure adds "Failed to switch NVDA audio output".
- **Order:** apply the NVDA switch after the speaker and the microphone, for
  the same synth-reload reason as profiles.

Test case: open the quick dialog, choose a device in the NVDA field, and press
OK. Expect NVDA to speak from that device at once. Then press the NVDA output
toggle. Expect NVDA to go back to the system default.

## Left to the builder

- Exact translator comments and message wording.
- Whether profile helpers live in `__init__.py` or in a new small
  `profiles.py`. Prefer the new module if `__init__.py` passes about 800 lines.

## Delivery

- Bump the version to 2026.5 in `buildVars.py` and `addon/manifest.ini`.
- Update the Arabic and English readmes, and `CHANGELOG.md`.
- Update the Arabic `.po` file with `msgmerge`, then compile it with `msgfmt`.
- Test live in portable NVDA (`E:\nvda 2026.1`), following the NVDACli steps
  in the workspace `AGENTS.md`. Do not merge to `master` until Kamal confirms
  it works in his installed NVDA.

## Test cases for Kamal

1. Set up a profile with all three devices. Activate it. Expect the name only.
2. Unplug one device, then activate the profile. Expect the name, then
   "Not connected" with that device's name. The other devices still switch.
3. Activate an empty profile. Expect "not configured".
4. Use "Save current devices", then change the chooser and change it back.
   Expect the values to remain. Press Cancel. Expect nothing to be saved.
5. Activate a profile that sets the NVDA output. Then use the NVDA output
   toggle. Expect it to go back to the system default.
