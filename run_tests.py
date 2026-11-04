"""Manual tests for the pure profile logic; run with `python run_tests.py`."""

import importlib.util
import sys
from pathlib import Path

PROFILES_PATH = (
    Path(__file__).parent / "addon" / "globalPlugins" / "audio_switcher" / "profiles.py"
)
# Load the module by path so the package __init__ (which imports wx/NVDA) never runs.
_spec = importlib.util.spec_from_file_location("profiles", PROFILES_PATH)
profiles = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(profiles)

PLAY = [("{s1}", "Jabra"), ("{s2}", "Realtek")]
CAP = [("{m1}", "Jabra Mic")]


def fakeMatch(active, value):
    devId, _sep, name = value.partition("|") if "|" in value else ("", "", value)
    for candidateId, candidateName in active:
        if devId and candidateId == devId:
            return candidateId
    for candidateId, candidateName in active:
        if name and candidateName == name:
            return candidateId
    return None


def resolve(values):
    return profiles.resolveProfile(values, PLAY, CAP, fakeMatch)


def test_resolve_all_connected():
    r = resolve(
        {"Speaker": "{s1}|Jabra", "Mic": "{m1}|Jabra Mic", "Nvda": "{s2}|Realtek"}
    )
    assert (r.speakerId, r.micId, r.nvdaId, r.missing, r.isEmpty) == (
        "{s1}",
        "{m1}",
        "{s2}",
        [],
        False,
    )


def test_resolve_missing_device_named():
    r = resolve({"Speaker": "{gone}|USB Speaker", "Mic": "", "Nvda": ""})
    assert r.speakerId is None and r.missing == ["USB Speaker"] and not r.isEmpty


def test_resolve_empty_profile():
    assert resolve({"Speaker": "", "Mic": "", "Nvda": ""}).isEmpty


def test_resolve_nvda_default_needs_no_match():
    assert resolve({"Speaker": "", "Mic": "", "Nvda": "default"}).nvdaId == "default"


def test_resolve_matches_by_id_after_rename():
    r = resolve({"Speaker": "{s1}|Old Name", "Mic": "", "Nvda": ""})
    assert r.speakerId == "{s1}"


def test_resolve_name_only_value():
    assert resolve({"Speaker": "Realtek", "Mic": "", "Nvda": ""}).speakerId == "{s2}"


def test_missing_name_falls_back_to_id():
    assert profiles.missingName("{x}|") == "{x}"


def test_current_devices_nvda_default():
    d = profiles.currentDevicesAsProfile(("{s1}", "Jabra"), None, "default", PLAY)
    assert d == {"Speaker": "{s1}|Jabra", "Mic": "", "Nvda": "default"}


def test_current_devices_nvda_known_and_unknown():
    current = profiles.currentDevicesAsProfile
    assert current(None, None, "{s2}", PLAY)["Nvda"] == "{s2}|Realtek"
    assert current(None, None, "{zz}", PLAY)["Nvda"] == "{zz}|"


def test_confspec_has_twelve_keys():
    lines = profiles.profileConfspec().splitlines()
    assert len(lines) == 12 and lines[0] == 'profile1Name = string(default="")'


def main():
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_")]
    failed = 0
    for name, func in tests:
        try:
            func()
            print(f"PASS {name}")
        except Exception as exc:  # report every failure, keep running
            failed += 1
            print(f"FAIL {name}: {exc!r}", file=sys.stderr)
    print(f"{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
