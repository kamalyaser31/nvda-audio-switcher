"""Pure profile logic: no NVDA imports, so run_tests.py can load it standalone."""

from typing import NamedTuple

PROFILE_COUNT = 3
FIELDS = ("Name", "Speaker", "Mic", "Nvda")
DEVICE_FIELDS = ("Speaker", "Mic", "Nvda")
NVDA_DEFAULT = "default"


class Resolution(NamedTuple):
    speakerId: object
    micId: object
    nvdaId: object
    missing: list
    isEmpty: bool


def profileKey(n, field):
    return f"profile{n}{field}"


def profileConfspec():
    return "\n".join(
        f'{profileKey(n, field)} = string(default="")'
        for n in range(1, PROFILE_COUNT + 1)
        for field in FIELDS
    )


def missingName(value):
    devId, _sep, name = value.partition("|")
    if not _sep:
        return value
    return name or devId


def _resolveDevice(value, active, match, missing):
    """Return the matched device ID, or None after recording a missing device."""
    if not value:
        return None
    devId = match(active, value)
    if not devId:
        missing.append(missingName(value))
    return devId


def resolveProfile(values, playback, capture, match):
    if not any(values.get(field) for field in DEVICE_FIELDS):
        return Resolution(None, None, None, [], True)
    missing = []
    speakerId = _resolveDevice(values.get("Speaker"), playback, match, missing)
    micId = _resolveDevice(values.get("Mic"), capture, match, missing)
    nvdaValue = values.get("Nvda")
    if nvdaValue == NVDA_DEFAULT:
        # NVDA resolves "default" itself, so no connection check is needed.
        nvdaId = NVDA_DEFAULT
    else:
        nvdaId = _resolveDevice(nvdaValue, playback, match, missing)
    return Resolution(speakerId, micId, nvdaId, missing, False)


def _deviceValue(info):
    return f"{info[0]}|{info[1]}" if info else ""


def currentDevicesAsProfile(speaker, mic, nvdaOutputId, playback):
    if not nvdaOutputId or nvdaOutputId == NVDA_DEFAULT:
        nvdaValue = NVDA_DEFAULT
    else:
        name = next((n for devId, n in playback if devId == nvdaOutputId), "")
        nvdaValue = f"{nvdaOutputId}|{name}"
    return {
        "Speaker": _deviceValue(speaker),
        "Mic": _deviceValue(mic),
        "Nvda": nvdaValue,
    }
