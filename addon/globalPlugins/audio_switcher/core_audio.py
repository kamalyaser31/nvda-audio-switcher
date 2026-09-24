# -*- coding: utf-8 -*-
"""Pure Win32 Core Audio implementation using ctypes and COM VTables.

Replaces pycaw and comtypes with direct zero-dependency Windows API calls.
"""

import ctypes
from ctypes import wintypes
import logging

log = logging.getLogger(__name__)

ole32 = ctypes.WinDLL("ole32", use_last_error=True)

ole32.CoCreateInstance.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
ole32.CoCreateInstance.restype = ctypes.c_long

ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
ole32.CoTaskMemFree.restype = None

ole32.PropVariantClear.argtypes = [ctypes.c_void_p]
ole32.PropVariantClear.restype = ctypes.c_long


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [
        ("fmtid", GUID),
        ("pid", wintypes.DWORD),
    ]


class PROPVARIANT(ctypes.Structure):
    _fields_ = [
        ("vt", wintypes.WORD),
        ("wReserved1", wintypes.WORD),
        ("wReserved2", wintypes.WORD),
        ("wReserved3", wintypes.WORD),
        ("pwszVal", wintypes.LPWSTR),
        ("_pad", ctypes.c_ubyte * 8),
    ]


# COM CLSIDs and IIDs
_CLSID_MMDeviceEnumerator = GUID(
    0xBCDE0395,
    0xE52F,
    0x467C,
    (ctypes.c_ubyte * 8)(0x8E, 0x3D, 0xC4, 0x57, 0x92, 0x91, 0x69, 0x2E),
)
_IID_IMMDeviceEnumerator = GUID(
    0xA95664D2,
    0x9614,
    0x4F35,
    (ctypes.c_ubyte * 8)(0xA7, 0x46, 0xDE, 0x8D, 0xB6, 0x36, 0x17, 0xE6),
)
_CLSID_CPolicyConfigClient = GUID(
    0x870AF99C,
    0x171D,
    0x4F9E,
    (ctypes.c_ubyte * 8)(0xAF, 0x0D, 0xE6, 0x3D, 0xF4, 0x0C, 0x2B, 0xC9),
)
_IID_IPolicyConfig = GUID(
    0xF8679F50,
    0x850A,
    0x41CF,
    (ctypes.c_ubyte * 8)(0x9C, 0x72, 0x43, 0x0F, 0x29, 0x02, 0x90, 0xC8),
)
_IID_IAudioEndpointVolume = GUID(
    0x5CDF2C82,
    0x841E,
    0x4546,
    (ctypes.c_ubyte * 8)(0x97, 0x22, 0x0C, 0xF7, 0x40, 0x78, 0x22, 0x9A),
)
_PKEY_Device_FriendlyName = PROPERTYKEY(
    GUID(
        0xA45C254E,
        0xDF1C,
        0x4EFD,
        (ctypes.c_ubyte * 8)(0x80, 0x20, 0x67, 0xD1, 0x46, 0xA8, 0x50, 0xE0),
    ),
    14,
)


def _release(p_interface):
    if not p_interface or not p_interface.value:
        return
    vtbl = ctypes.cast(
        p_interface.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
    ).contents
    proto = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
    proto(vtbl[2])(p_interface)


def _get_enumerator():
    ole32.CoInitialize(None)
    p_enum = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(
        ctypes.byref(_CLSID_MMDeviceEnumerator),
        None,
        1,  # CLSCTX_INPROC_SERVER
        ctypes.byref(_IID_IMMDeviceEnumerator),
        ctypes.byref(p_enum),
    )
    if hr != 0 or not p_enum.value:
        log.error("Failed to create MMDeviceEnumerator: hr=0x%08X", hr & 0xFFFFFFFF)
        return None
    return p_enum


def _get_device_id(p_device):
    vtbl = ctypes.cast(
        p_device.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
    ).contents
    proto = ctypes.WINFUNCTYPE(
        ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)
    )
    p_id = wintypes.LPWSTR()
    hr = proto(vtbl[5])(p_device, ctypes.byref(p_id))
    if hr != 0 or not p_id.value:
        return ""
    dev_id = str(p_id.value)
    ole32.CoTaskMemFree(ctypes.cast(p_id, ctypes.c_void_p))
    return dev_id


def _read_friendly_name_from_store(p_store):
    vtbl_store = ctypes.cast(
        p_store.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
    ).contents
    proto_get = ctypes.WINFUNCTYPE(
        ctypes.c_long,
        ctypes.c_void_p,
        ctypes.POINTER(PROPERTYKEY),
        ctypes.POINTER(PROPVARIANT),
    )
    pv = PROPVARIANT()
    name = ""
    if (
        proto_get(vtbl_store[5])(
            p_store, ctypes.byref(_PKEY_Device_FriendlyName), ctypes.byref(pv)
        )
        == 0
    ):
        if pv.vt == 31 and pv.pwszVal:  # VT_LPWSTR
            name = str(pv.pwszVal)
        ole32.PropVariantClear(ctypes.byref(pv))
    return name


def _get_device_name(p_device):
    vtbl = ctypes.cast(
        p_device.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
    ).contents
    proto_open = ctypes.WINFUNCTYPE(
        ctypes.c_long, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)
    )
    p_store = ctypes.c_void_p()
    # 0 = STGM_READ
    if (
        proto_open(vtbl[4])(p_device, 0, ctypes.byref(p_store)) != 0
        or not p_store.value
    ):
        return ""
    try:
        return _read_friendly_name_from_store(p_store)
    finally:
        _release(p_store)


def _extract_devices_from_collection(p_col):
    vtbl_col = ctypes.cast(
        p_col.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
    ).contents
    proto_count = ctypes.WINFUNCTYPE(
        ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)
    )
    count = ctypes.c_uint(0)
    proto_count(vtbl_col[3])(p_col, ctypes.byref(count))

    proto_item = ctypes.WINFUNCTYPE(
        ctypes.c_long,
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.POINTER(ctypes.c_void_p),
    )
    devices = []
    for i in range(count.value):
        p_dev = ctypes.c_void_p()
        if proto_item(vtbl_col[4])(p_col, i, ctypes.byref(p_dev)) == 0 and p_dev.value:
            try:
                dev_id = _get_device_id(p_dev)
                dev_name = _get_device_name(p_dev)
                if dev_id and dev_name:
                    devices.append((dev_id, dev_name))
            finally:
                _release(p_dev)
    return devices


def getActiveDevices(render=True):
    """Return list of (device_id, friendly_name) for active audio endpoints."""
    p_enum = _get_enumerator()
    if not p_enum:
        return []

    p_col = ctypes.c_void_p()
    try:
        vtbl_enum = ctypes.cast(
            p_enum.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        proto_enum = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_int,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
        )
        flow = 0 if render else 1
        if (
            proto_enum(vtbl_enum[3])(p_enum, flow, 1, ctypes.byref(p_col)) != 0
            or not p_col.value
        ):
            return []
        return _extract_devices_from_collection(p_col)
    except OSError as exc:
        log.error("Error enumerating audio devices: %s", exc)
        return []
    finally:
        _release(p_col)
        _release(p_enum)


def getDefaultDeviceInfo(render=True):
    """Return (device_id, friendly_name) of current default audio device or None."""
    p_enum = _get_enumerator()
    if not p_enum:
        return None

    p_dev = ctypes.c_void_p()
    try:
        vtbl = ctypes.cast(
            p_enum.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        proto = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_void_p),
        )
        flow = 0 if render else 1
        if proto(vtbl[4])(p_enum, flow, 0, ctypes.byref(p_dev)) != 0 or not p_dev.value:
            return None

        dev_id = _get_device_id(p_dev)
        dev_name = _get_device_name(p_dev)
        return (dev_id, dev_name) if (dev_id and dev_name) else None
    except OSError as exc:
        log.error("Error getting default audio device: %s", exc)
        return None
    finally:
        _release(p_dev)
        _release(p_enum)


def _create_policy_config():
    ole32.CoInitialize(None)
    p_policy = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(
        ctypes.byref(_CLSID_CPolicyConfigClient),
        None,
        23,  # CLSCTX_ALL
        ctypes.byref(_IID_IPolicyConfig),
        ctypes.byref(p_policy),
    )
    if hr != 0 or not p_policy.value:
        log.error(
            "CoCreateInstance failed for IPolicyConfigClient: hr=0x%08X",
            hr & 0xFFFFFFFF,
        )
        return None
    return p_policy


def setDefaultDevice(device_id):
    """Set device_id as default audio endpoint across all standard roles."""
    p_policy = _create_policy_config()
    if not p_policy:
        return False

    success = True
    try:
        vtbl = ctypes.cast(
            p_policy.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        proto_set = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, wintypes.LPCWSTR, wintypes.DWORD
        )
        for role in (0, 1, 2):  # eConsole, eMultimedia, eCommunications
            res = proto_set(vtbl[13])(p_policy, device_id, role)
            if res != 0:
                log.error(
                    "SetDefaultEndpoint failed for role %s: hr=0x%08X",
                    role,
                    res & 0xFFFFFFFF,
                )
                success = False
    except OSError as exc:
        log.error("SetDefaultDevice failed for '%s': %s", device_id, exc)
        success = False
    finally:
        _release(p_policy)
    return success


def _get_default_endpoint_volume(render=False):
    p_enum = _get_enumerator()
    if not p_enum:
        return None
    p_dev = ctypes.c_void_p()
    p_vol = ctypes.c_void_p()
    try:
        vtbl_enum = ctypes.cast(
            p_enum.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        proto_default = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_void_p),
        )
        flow = 0 if render else 1
        if (
            proto_default(vtbl_enum[4])(p_enum, flow, 0, ctypes.byref(p_dev)) != 0
            or not p_dev.value
        ):
            return None

        vtbl_dev = ctypes.cast(
            p_dev.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        proto_activate = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        )
        if (
            proto_activate(vtbl_dev[3])(
                p_dev,
                ctypes.byref(_IID_IAudioEndpointVolume),
                1,
                None,
                ctypes.byref(p_vol),
            )
            != 0
        ):
            return None
        return p_vol
    except OSError as exc:
        log.error("Error activating endpoint volume: %s", exc)
        return None
    finally:
        _release(p_dev)
        _release(p_enum)


def getDefaultMicMute():
    """Return True if default mic is muted, False if unmuted, or None on error."""
    p_vol = _get_default_endpoint_volume(render=False)
    if not p_vol:
        return None
    try:
        vtbl_vol = ctypes.cast(
            p_vol.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        proto_get = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL)
        )
        is_muted = wintypes.BOOL()
        if proto_get(vtbl_vol[15])(p_vol, ctypes.byref(is_muted)) == 0:
            return bool(is_muted.value)
        return None
    except OSError as exc:
        log.error("Error querying mic mute: %s", exc)
        return None
    finally:
        _release(p_vol)


def toggleDefaultMicMute():
    """Toggle mute state of default microphone. Return new mute state (bool) or None."""
    p_vol = _get_default_endpoint_volume(render=False)
    if not p_vol:
        return None
    try:
        vtbl_vol = ctypes.cast(
            p_vol.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        proto_get = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL)
        )
        proto_set = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, wintypes.BOOL, ctypes.c_void_p
        )
        is_muted = wintypes.BOOL()
        if proto_get(vtbl_vol[15])(p_vol, ctypes.byref(is_muted)) != 0:
            return None
        new_state = not bool(is_muted.value)
        if proto_set(vtbl_vol[14])(p_vol, wintypes.BOOL(new_state), None) == 0:
            return new_state
        return None
    except OSError as exc:
        log.error("Error toggling mic mute: %s", exc)
        return None
    finally:
        _release(p_vol)


def cycleNextDevice(render=True):
    """Cycle to next active audio device, set as default, and return (device, index, total)."""
    devices = getActiveDevices(render)
    if not devices:
        return None, 0, 0
    if len(devices) == 1:
        return devices[0], 1, 1

    current = getDefaultDeviceInfo(render)
    current_id = current[0] if current else None

    current_idx = 0
    for idx, (dev_id, _name) in enumerate(devices):
        if dev_id == current_id:
            current_idx = idx
            break

    next_idx = (current_idx + 1) % len(devices)
    target = devices[next_idx]
    if setDefaultDevice(target[0]):
        return target, next_idx + 1, len(devices)
    return None, next_idx + 1, len(devices)
