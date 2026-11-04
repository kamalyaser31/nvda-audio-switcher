import wx
import addonHandler
import globalPluginHandler
import gui
import config
import ui
import tones
import synthDriverHandler
from logHandler import log
from gui.settingsDialogs import SettingsPanel, NVDASettingsDialog
from scriptHandler import script
from .core_audio import (
    getActiveDevices,
    getDefaultDeviceInfo,
    setDefaultDevice,
    getDefaultMicMute,
    toggleDefaultMicMute,
    cycleNextDevice,
)
from . import profiles

addonHandler.initTranslation()

confspec = """
[audioSwitcher]
micDevice1 = string(default="")
micDevice2 = string(default="")
micDevice3 = string(default="")
speakerDevice1 = string(default="")
speakerDevice2 = string(default="")
speakerDevice3 = string(default="")
feedbackType = integer(default=0, min=0, max=3)
nvdaSecondaryOutput = string(default="")
""" + profiles.profileConfspec() + "\n"


def parseDeviceConfig(value):
    """Returns (device_id, friendly_name) from config string."""
    if not value:
        return "", ""
    if "|" in value:
        parts = value.split("|", 1)
        return parts[0], parts[1]
    # Backward compatibility: if no '|', treat it as friendly name (for old config)
    return "", value


def getDisambiguatedDeviceNames(devices):
    """Number duplicate friendly names while preserving device order."""
    nameCounts = {}
    for _deviceId, name in devices:
        nameKey = name.casefold()
        nameCounts[nameKey] = nameCounts.get(nameKey, 0) + 1

    nameIndexes = {}
    displayNames = []
    for _deviceId, name in devices:
        nameKey = name.casefold()
        if nameCounts[nameKey] == 1:
            displayNames.append(name)
            continue
        nameIndexes[nameKey] = nameIndexes.get(nameKey, 0) + 1
        displayNames.append(f"{name} ({nameIndexes[nameKey]})")
    return displayNames


def getDeviceSelectionIndex(devices, deviceId):
    for index, (candidateId, _name) in enumerate(devices, start=1):
        if candidateId == deviceId:
            return index
    return 0


def getDefaultDeviceFriendlyName(render=True):
    deviceInfo = getDefaultDeviceInfo(render)
    return deviceInfo[1] if deviceInfo else None


def provideFeedback(successMessages, failureMessages=()):
    """Report successful changes by preference and always report failures."""
    feedback = config.conf["audioSwitcher"]["feedbackType"]
    # 0: Beep + Speech, 1: Speech, 2: Beep, 3: None
    if successMessages and feedback in (0, 2):
        tones.beep(440, 100)
    spokenMessages = list(failureMessages)
    if feedback in (0, 1):
        spokenMessages = list(successMessages) + spokenMessages
    if spokenMessages:
        ui.message("; ".join(spokenMessages))


def _findDeviceByName(activeDevices, targetName):
    key = targetName.casefold()
    exact = [devId for devId, name in activeDevices if name.casefold() == key]
    if len(exact) == 1:
        return exact[0]
    partial = [devId for devId, name in activeDevices if key in name.casefold()]
    return partial[0] if len(partial) == 1 else None


def findMatchingDeviceId(activeDevices, targetId, targetName):
    if targetId:
        for devId, _name in activeDevices:
            if devId == targetId:
                return devId
    return _findDeviceByName(activeDevices, targetName) if targetName else None


def _resolveConfiguredSlot(render, slot):
    cfg = config.conf["audioSwitcher"]
    devType = _("speaker") if render else _("mic")
    key = f"speakerDevice{slot}" if render else f"micDevice{slot}"
    return devType, cfg[key]


def _reportSlotFeedback(devType, slot, success):
    if success:
        # Translators: short message when a default audio device slot is selected.
        msg = _("Done: {deviceType} {slot}").format(deviceType=devType, slot=slot)
        provideFeedback([msg])
    else:
        # Translators: short message when setting default device fails.
        provideFeedback([], [_("Failed to set device")])


def setConfiguredDevice(render=True, slot=1):
    devType, targetValue = _resolveConfiguredSlot(render, slot)
    if not targetValue:
        # Translators: short message when the requested device slot is empty.
        ui.message(_("Not set"))
        return
    targetId, targetName = parseDeviceConfig(targetValue)
    # Always check the device is connected: IPolicyConfig is undocumented and
    # may accept the ID of an unplugged endpoint without switching audio.
    target_id = findMatchingDeviceId(getActiveDevices(render), targetId, targetName)
    if not target_id:
        # Translators: short message when the configured device is unavailable.
        ui.message(_("Not found"))
        return
    _reportSlotFeedback(devType, slot, setDefaultDevice(target_id))


def getDefaultDeviceMessage(render=True):
    currentName = getDefaultDeviceFriendlyName(render)
    if render:
        if currentName:
            # Translators: short message announcing the current default speaker.
            return _("Speaker: {device}").format(device=currentName)
        # Translators: short message when there is no default speaker.
        return _("No speaker")
    if currentName:
        # Translators: short message announcing the current default microphone.
        return _("Mic: {device}").format(device=currentName)
    # Translators: short message when there is no default microphone.
    return _("No mic")


def announceDefaultDevice(render=True):
    ui.message(getDefaultDeviceMessage(render))


def announceBothDefaultDevices():
    messages = [
        getDefaultDeviceMessage(render=True),
        getDefaultDeviceMessage(render=False),
    ]
    ui.message("; ".join(messages))


def _handleCycleFailure(render, total):
    if total == 0:
        ui.message(
            _("No connected speakers") if render else _("No connected microphones")
        )
    else:
        provideFeedback([], [_("Failed to set device")])


def cycleDeviceWithFeedback(render=True):
    target, index, total = cycleNextDevice(render)
    if not target:
        _handleCycleFailure(render, total)
        return
    if total == 1:
        template = (
            _("Only one speaker: {device}") if render else _("Only one mic: {device}")
        )
        ui.message(template.format(device=target[1]))
        return
    template = (
        _("Speaker: {device} ({index} of {total})")
        if render
        else _("Mic: {device} ({index} of {total})")
    )
    provideFeedback([template.format(device=target[1], index=index, total=total)])


def toggleMicMuteWithFeedback():
    new_state = toggleDefaultMicMute()
    if new_state is None:
        ui.message(_("No mic"))
        return
    feedback = config.conf["audioSwitcher"]["feedbackType"]
    if feedback in (0, 2):
        tones.beep(350 if new_state else 600, 70)
    if feedback in (0, 1):
        ui.message(_("Mic muted") if new_state else _("Mic on"))


def announceMicMuteState():
    is_muted = getDefaultMicMute()
    if is_muted is None:
        ui.message(_("No mic"))
        return
    ui.message(_("Mic muted") if is_muted else _("Mic on"))


def getNvdaCurrentOutputDeviceId():
    try:
        devId = config.conf["audio"]["outputDevice"]
        return devId if devId else "default"
    except (KeyError, AttributeError):
        return "default"


def _reloadSynth():
    try:
        return bool(synthDriverHandler.setSynth(synthDriverHandler.getSynth().name))
    except Exception as e:
        log.error("AudioSwitcher: setSynth failed: %s", e)
        return False


def forceSynthReload():
    """Reopen the synth and tones players so they pick up the new output device."""
    tones.terminate()
    try:
        return _reloadSynth()
    finally:
        tones.initialize()


def safeSetNvdaOutputDevice(newDeviceId):
    oldId = getNvdaCurrentOutputDeviceId()
    try:
        config.conf["audio"]["outputDevice"] = newDeviceId
        if forceSynthReload():
            return True
        raise RuntimeError("Synth reload failed")
    except Exception as e:
        log.error("AudioSwitcher: Failed to switch NVDA output: %s", e)
        try:
            config.conf["audio"]["outputDevice"] = oldId
            forceSynthReload()
        except Exception as rollbackErr:
            log.critical("AudioSwitcher: Rollback failed: %s", rollbackErr)
        return False


def _playNvdaOutputFeedback(deviceName):
    feedback = config.conf["audioSwitcher"]["feedbackType"]
    if feedback in (0, 2):
        tones.beep(660, 80)
    if feedback in (0, 1):
        ui.message(_("NVDA: {device}").format(device=deviceName))


def _reportNvdaToggleError(message):
    feedback = config.conf["audioSwitcher"]["feedbackType"]
    if feedback in (0, 2):
        tones.beep(220, 100)
    ui.message(message)


def _getNvdaDisplayName(newId, active, fallbackName):
    if newId == "default":
        return _("Primary Device (System Default)")
    return next((name for dev_id, name in active if dev_id == newId), fallbackName)


def _switchToDefaultOutput():
    if safeSetNvdaOutputDevice("default"):
        _playNvdaOutputFeedback(_("Primary Device (System Default)"))
    else:
        _reportNvdaToggleError(_("Failed to switch NVDA audio output"))


def _switchToSecondaryOutput(targetId, targetName):
    # NVDA falls back to the default device silently on a stale ID, so verify
    # the device is connected before switching.
    active = getActiveDevices(render=True)
    matchedId = findMatchingDeviceId(active, targetId, targetName)
    if not matchedId:
        _reportNvdaToggleError(_("NVDA secondary device not connected"))
        return
    if safeSetNvdaOutputDevice(matchedId):
        _playNvdaOutputFeedback(_getNvdaDisplayName(matchedId, active, targetName))
    else:
        _reportNvdaToggleError(_("Failed to switch NVDA audio output"))


def toggleNvdaOutputWithFeedback():
    cfgValue = config.conf["audioSwitcher"]["nvdaSecondaryOutput"]
    targetId, targetName = parseDeviceConfig(cfgValue)
    if not targetId and not targetName:
        _reportNvdaToggleError(_("No secondary device configured for NVDA"))
        return
    if getNvdaCurrentOutputDeviceId() != "default":
        _switchToDefaultOutput()
    else:
        _switchToSecondaryOutput(targetId, targetName)


def _applyEndpoint(endpoint, isSpeaker, success, failure):
    if not endpoint:
        return
    deviceId, name = endpoint
    if setDefaultDevice(deviceId):
        template = (
            # Translators: confirms a speaker selected in the quick dialog.
            _("Default speaker: {device}")
            if isSpeaker
            # Translators: confirms a microphone selected in the quick dialog.
            else _("Default microphone: {device}")
        )
        success.append(template.format(device=name))
    else:
        failure.append(
            _("Failed to set speaker") if isSpeaker else _("Failed to set microphone")
        )


def _moveNvdaOutput(newId, displayName, success, failure):
    # Already there: skip the synth reload so speech is not cut for nothing.
    if newId == getNvdaCurrentOutputDeviceId() or safeSetNvdaOutputDevice(newId):
        success.append(_("NVDA: {device}").format(device=displayName))
    else:
        failure.append(_("Failed to switch NVDA audio output"))


def _moveNvdaToChosen(secondaryDevice, success, failure):
    active = getActiveDevices(render=True)
    targetId, targetName = parseDeviceConfig(secondaryDevice)
    matchedId = findMatchingDeviceId(active, targetId, targetName)
    if not matchedId:
        failure.append(_("NVDA secondary device not connected"))
        return
    displayName = _getNvdaDisplayName(matchedId, active, targetName)
    _moveNvdaOutput(matchedId, displayName, success, failure)


def _isNvdaOnDevice(configValue):
    if not configValue:
        return False
    targetId, targetName = parseDeviceConfig(configValue)
    # Name-only values from old configs carry no ID, so resolve them first.
    active = getActiveDevices(render=True)
    matchedId = findMatchingDeviceId(active, targetId, targetName)
    return getNvdaCurrentOutputDeviceId() in {targetId, matchedId} - {"", None}


def _applySecondaryDevice(secondaryDevice, success, failure):
    """Save the secondary device and move NVDA speech to it at once."""
    if secondaryDevice is None:
        return
    cfg = config.conf["audioSwitcher"]
    oldValue = cfg["nvdaSecondaryOutput"]
    cfg["nvdaSecondaryOutput"] = secondaryDevice
    if secondaryDevice:
        _moveNvdaToChosen(secondaryDevice, success, failure)
        return
    success.append(_("NVDA secondary device cleared"))
    # Leave NVDA where it is unless it was speaking on the device just cleared.
    if _isNvdaOnDevice(oldValue):
        primary = _("Primary Device (System Default)")
        _moveNvdaOutput("default", primary, success, failure)


def applyDeviceSelections(speaker, microphone, secondaryDevice=None):
    success = []
    failure = []
    _applyEndpoint(speaker, True, success, failure)
    _applyEndpoint(microphone, False, success, failure)
    _applySecondaryDevice(secondaryDevice, success, failure)
    provideFeedback(success, failure)


def matchConfigured(active, value):
    return findMatchingDeviceId(active, *parseDeviceConfig(value))


def profileName(n):
    name = config.conf["audioSwitcher"][profiles.profileKey(n, "Name")].strip()
    # Translators: name of a profile left unnamed; {n} is its number.
    return name or _("Profile {n}").format(n=n)


def readProfile(n):
    cfg = config.conf["audioSwitcher"]
    return {
        field: cfg[profiles.profileKey(n, field)] for field in profiles.DEVICE_FIELDS
    }


def _applyProfileEndpoint(deviceId, failureMessage, failures):
    if deviceId is None:
        return False
    if setDefaultDevice(deviceId):
        return True
    failures.append(failureMessage)
    return False


def _applyProfileNvda(nvdaId, failures):
    if nvdaId is None:
        return False
    # Already there: skip the synth reload so speech is not cut for nothing.
    if nvdaId == getNvdaCurrentOutputDeviceId():
        return True
    if safeSetNvdaOutputDevice(nvdaId):
        return True
    failures.append(_("Failed to switch NVDA audio output"))
    return False


def _resolveProfile(n):
    return profiles.resolveProfile(
        readProfile(n),
        getActiveDevices(render=True),
        getActiveDevices(render=False),
        matchConfigured,
    )


def activateProfile(n):
    name = profileName(n)
    res = _resolveProfile(n)
    if res.isEmpty:
        # Translators: spoken when a profile with no devices is activated.
        ui.message(_("{name} is not configured").format(name=name))
        return
    failures = []
    applied = [
        _applyProfileEndpoint(res.speakerId, _("Failed to set speaker"), failures),
        _applyProfileEndpoint(res.micId, _("Failed to set microphone"), failures),
        _applyProfileNvda(res.nvdaId, failures),
    ]
    if res.missing:
        # Translators: lists profile devices that are unplugged.
        missingMsg = _("Not connected: {devices}")
        failures.insert(0, missingMsg.format(devices=", ".join(res.missing)))
    provideFeedback([name] if any(applied) else [], failures)


class AudioDeviceSelectionDialog(wx.Dialog):
    """Choose connected speakers and microphones without changing saved slots."""

    def _buildButtonSizer(self):
        buttonSizer = wx.StdDialogButtonSizer()
        refreshButton = wx.Button(self, label=_("&Refresh devices"))
        refreshButton.Bind(wx.EVT_BUTTON, self._onRefresh)
        buttonSizer.AddButton(refreshButton)
        applyButton = wx.Button(self, wx.ID_OK, _("&Apply"))
        applyButton.SetDefault()
        buttonSizer.AddButton(applyButton)
        buttonSizer.AddButton(wx.Button(self, wx.ID_CANCEL))
        buttonSizer.Realize()
        return buttonSizer

    def __init__(self, parent):
        super().__init__(parent, title=_("Choose default audio devices"))
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=mainSizer)
        self.speakerDevices = []
        self.microphoneDevices = []
        self.speakerChoice = sHelper.addLabeledControl(
            _("&Speakers:"), wx.Choice, choices=[]
        )
        self.microphoneChoice = sHelper.addLabeledControl(
            _("&Microphones:"), wx.Choice, choices=[]
        )
        self.nvdaSecondaryChoice = sHelper.addLabeledControl(
            _("NVDA Secondary &Output:"), wx.Choice, choices=[]
        )
        mainSizer.Add(self._buildButtonSizer(), flag=wx.ALIGN_RIGHT | wx.ALL, border=10)
        self._refreshDeviceChoices()
        self.SetSizerAndFit(mainSizer)
        self.CentreOnParent()
        self.speakerChoice.SetFocus()

    def _onRefresh(self, event):
        self._refreshDeviceChoices()
        self.Fit()
        # Translators: spoken after refreshing the quick device-selection dialog.
        ui.message(_("Audio devices refreshed"))

    def _refreshDeviceChoices(self):
        speakerId = self._getSelectedDeviceId(self.speakerChoice, self.speakerDevices)
        microphoneId = self._getSelectedDeviceId(
            self.microphoneChoice, self.microphoneDevices
        )
        self.speakerDevices = getActiveDevices(render=True)
        self.microphoneDevices = getActiveDevices(render=False)
        self._updateSpeakerChoice(speakerId)
        self._updateMicrophoneChoice(microphoneId)
        self._updateNvdaSecondaryChoice()

    def _updateNvdaSecondaryChoice(self):
        previous = self._getSecondaryValue()
        configured = config.conf["audioSwitcher"]["nvdaSecondaryOutput"]
        targetId, _targetName = parseDeviceConfig(configured)
        choices = [_("Do not change"), _("None (Clear)")]
        self.nvdaSecondaryValues = [None, ""]
        names = getDisambiguatedDeviceNames(self.speakerDevices)
        for (dev_id, name), displayName in zip(self.speakerDevices, names):
            self.nvdaSecondaryValues.append(f"{dev_id}|{name}")
            if dev_id == targetId:
                template = _("{device} (current secondary)")
                choices.append(template.format(device=displayName))
            else:
                choices.append(displayName)
        self.nvdaSecondaryChoice.Set(choices)
        values = self.nvdaSecondaryValues
        self.nvdaSecondaryChoice.SetSelection(
            values.index(previous) if previous in values else 0
        )

    def _getSecondaryValue(self):
        selIndex = self.nvdaSecondaryChoice.GetSelection()
        values = getattr(self, "nvdaSecondaryValues", [])
        return values[selIndex] if 0 < selIndex < len(values) else None

    def _updateSpeakerChoice(self, selectedId):
        current = getDefaultDeviceInfo(render=True)
        currentId = current[0] if current else None
        choices = self._makeChoices(
            self.speakerDevices,
            currentId,
            _("Do not change the default speaker"),
            _("No connected speakers"),
        )
        self._replaceChoices(
            self.speakerChoice, choices, self.speakerDevices, selectedId
        )

    def _updateMicrophoneChoice(self, selectedId):
        current = getDefaultDeviceInfo(render=False)
        currentId = current[0] if current else None
        choices = self._makeChoices(
            self.microphoneDevices,
            currentId,
            _("Do not change the default microphone"),
            _("No connected microphones"),
        )
        self._replaceChoices(
            self.microphoneChoice, choices, self.microphoneDevices, selectedId
        )

    @staticmethod
    def _makeChoices(devices, currentId, unchangedLabel, emptyLabel):
        if not devices:
            return [emptyLabel]
        choices = [unchangedLabel]
        displayNames = getDisambiguatedDeviceNames(devices)
        for (deviceId, _name), displayName in zip(devices, displayNames):
            if deviceId == currentId:
                # Translators: marks the current device in the quick selection dialog.
                label = _("{device} (current default)").format(device=displayName)
                choices.append(label)
            else:
                choices.append(displayName)
        return choices

    @staticmethod
    def _replaceChoices(choice, labels, devices, selectedId):
        choice.Set(labels)
        choice.Enable(bool(devices))
        choice.SetSelection(getDeviceSelectionIndex(devices, selectedId))

    def getSelections(self):
        """Return explicitly selected endpoints and optional secondary device update."""
        return (
            self._getSelection(self.speakerChoice, self.speakerDevices),
            self._getSelection(self.microphoneChoice, self.microphoneDevices),
            self._getSecondaryValue(),
        )

    @staticmethod
    def _getSelection(choice, devices):
        selection = choice.GetSelection()
        if selection <= 0:
            return None
        return devices[selection - 1]

    @staticmethod
    def _getSelectedDeviceId(choice, devices):
        selection = AudioDeviceSelectionDialog._getSelection(choice, devices)
        return selection[0] if selection else None


def _findConfiguredIndex(activeDevices, targetId, targetName):
    for index, (devId, name) in enumerate(activeDevices, start=1):
        if devId == targetId or (not targetId and name == targetName):
            return index
    return 0


def buildDeviceChoices(activeDevices, configuredValue, noneLabel):
    """Return (values, labels, selection), keeping a saved but absent device."""
    targetId, targetName = parseDeviceConfig(configuredValue)
    values = [""] + [f"{devId}|{name}" for devId, name in activeDevices]
    labels = [noneLabel] + getDisambiguatedDeviceNames(activeDevices)
    selection = _findConfiguredIndex(activeDevices, targetId, targetName)
    if configuredValue and not selection:
        template = _("{device} (saved, not connected)")
        values.append(configuredValue)
        labels.append(template.format(device=targetName or targetId))
        selection = len(values) - 1
    return values, labels, selection


def buildNvdaProfileChoices(playback, value):
    """Like buildDeviceChoices, with "System default" inserted after "No change"."""
    isDefault = value == profiles.NVDA_DEFAULT
    # Translators: profile field option that leaves the device unchanged.
    noChange = _("No change")
    built = buildDeviceChoices(playback, "" if isDefault else value, noChange)
    values, labels, selection = built
    values.insert(1, profiles.NVDA_DEFAULT)
    # Translators: profile option that sends NVDA speech to the Windows default.
    labels.insert(1, _("System default"))
    if isDefault:
        selection = 1
    elif selection:
        selection += 1
    return values, labels, selection


class AudioSwitcherSettingsPanel(SettingsPanel):
    title = _("Audio Switcher")
    speakerLabels = (_("&Speaker 1:"), _("S&peaker 2:"), _("Sp&eaker 3:"))
    micLabels = (_("&Microphone 1:"), _("M&icrophone 2:"), _("Mi&crophone 3:"))

    def makeSettings(self, settingsSizer):
        sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
        playback = getActiveDevices(render=True)
        capture = getActiveDevices(render=False)
        self.deviceControls = []  # (config key, wx.Choice, values) per control.
        speakerEmpty = "" if playback else _("No connected speakers")
        micEmpty = "" if capture else _("No connected microphones")
        self._addSlotControls(
            sHelper, "speaker", self.speakerLabels, playback, speakerEmpty
        )
        self._addSlotControls(sHelper, "mic", self.micLabels, capture, micEmpty)
        self._addDeviceControl(
            sHelper,
            "nvdaSecondaryOutput",
            _("NVDA Secondary &Output Device:"),
            playback,
            _("None (Not configured)"),
        )
        self._addProfileSettings(sHelper, playback, capture)
        self._addFeedbackSettings(sHelper)

    def _addSlotControls(self, sHelper, prefix, labels, devices, noneLabel):
        for slot, label in enumerate(labels, start=1):
            key = f"{prefix}Device{slot}"
            self._addDeviceControl(sHelper, key, label, devices, noneLabel)

    def _addDeviceControl(self, sHelper, key, label, devices, noneLabel):
        configured = config.conf["audioSwitcher"][key]
        values, labels, selection = buildDeviceChoices(devices, configured, noneLabel)
        choice = sHelper.addLabeledControl(label, wx.Choice, choices=labels)
        choice.SetSelection(selection)
        choice.Enable(len(values) > 1)
        self.deviceControls.append((key, choice, values))

    def _addFeedbackSettings(self, sHelper):
        self.feedbackChoices = [
            _("Beep and Speech"),
            _("Speech Only"),
            _("Beep Only"),
            _("None"),
        ]
        self.feedbackTypeChoice = sHelper.addLabeledControl(
            _("Feedback &Type:"), wx.Choice, choices=self.feedbackChoices
        )
        feedback = config.conf["audioSwitcher"]["feedbackType"]
        self.feedbackTypeChoice.SetSelection(feedback)

    def _addProfileSettings(self, sHelper, playback, capture):
        self.profilePlayback = playback
        self.profileCapture = capture
        cfg = config.conf["audioSwitcher"]
        # Edits of all profiles live here until onSave, so switching the
        # chooser keeps them and Cancel discards them.
        self.profileEdits = {
            n: {field: cfg[profiles.profileKey(n, field)] for field in profiles.FIELDS}
            for n in range(1, profiles.PROFILE_COUNT + 1)
        }
        self.profileChoiceValues = {}
        self._createProfileControls(sHelper)
        self._shownProfile = 1
        self._loadProfileFields(1)

    def _createProfileControls(self, sHelper):
        names = [
            _("Profile {n}").format(n=n) for n in range(1, profiles.PROFILE_COUNT + 1)
        ]
        add = sHelper.addLabeledControl
        self.profileChooser = add(_("P&rofile:"), wx.Choice, choices=names)
        self.profileChooser.SetSelection(0)
        self.profileChooser.Bind(wx.EVT_CHOICE, self._onProfileChosen)
        self.profileNameEdit = add(_("Profile &name:"), wx.TextCtrl)
        self.profileSpeaker = add(_("Profile spea&ker:"), wx.Choice, choices=[])
        self.profileMic = add(_("Profile microp&hone:"), wx.Choice, choices=[])
        self.profileNvda = add(_("Profile NVDA o&utput:"), wx.Choice, choices=[])
        saveButton = sHelper.addItem(
            wx.Button(self, label=_("Save current &devices to profile"))
        )
        saveButton.Bind(wx.EVT_BUTTON, self._onSaveCurrentDevices)

    def _profileChoices(self):
        return (
            ("Speaker", self.profileSpeaker),
            ("Mic", self.profileMic),
            ("Nvda", self.profileNvda),
        )

    def _setProfileChoice(self, field, choice, built):
        values, labels, selection = built
        choice.Set(labels)
        choice.SetSelection(selection)
        choice.Enable(len(values) > 1)
        self.profileChoiceValues[field] = values

    def _loadProfileFields(self, n):
        edits = self.profileEdits[n]
        noChange = _("No change")
        self.profileNameEdit.SetValue(edits["Name"])
        self._setProfileChoice(
            "Speaker",
            self.profileSpeaker,
            buildDeviceChoices(self.profilePlayback, edits["Speaker"], noChange),
        )
        self._setProfileChoice(
            "Mic",
            self.profileMic,
            buildDeviceChoices(self.profileCapture, edits["Mic"], noChange),
        )
        self._setProfileChoice(
            "Nvda",
            self.profileNvda,
            buildNvdaProfileChoices(self.profilePlayback, edits["Nvda"]),
        )
        self._shownProfile = n

    def _storeProfileFields(self):
        edits = self.profileEdits[self._shownProfile]
        edits["Name"] = self.profileNameEdit.GetValue().strip()
        for field, choice in self._profileChoices():
            edits[field] = self.profileChoiceValues[field][choice.GetSelection()]

    def _onProfileChosen(self, event):
        self._storeProfileFields()
        self._loadProfileFields(self.profileChooser.GetSelection() + 1)

    def _onSaveCurrentDevices(self, event):
        self._storeProfileFields()
        # A device may have been plugged in after the panel opened.
        self.profilePlayback = getActiveDevices(render=True)
        self.profileCapture = getActiveDevices(render=False)
        current = profiles.currentDevicesAsProfile(
            getDefaultDeviceInfo(render=True),
            getDefaultDeviceInfo(render=False),
            getNvdaCurrentOutputDeviceId(),
            self.profilePlayback,
        )
        self.profileEdits[self._shownProfile].update(current)
        self._loadProfileFields(self._shownProfile)
        # Translators: spoken after the profile fields are filled with current devices.
        ui.message(_("Current devices filled in"))

    def onSave(self):
        cfg = config.conf["audioSwitcher"]
        for key, choice, values in self.deviceControls:
            cfg[key] = values[choice.GetSelection()]
        cfg["feedbackType"] = self.feedbackTypeChoice.GetSelection()
        self._storeProfileFields()
        for n, edits in self.profileEdits.items():
            for field in profiles.FIELDS:
                cfg[profiles.profileKey(n, field)] = edits[field]


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    """NVDA Audio Switcher Global Plugin using pure Win32 Core Audio."""

    scriptCategory = _("Audio Switcher")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Load and register config spec
        config.conf.spec.update(
            # list_values=False keeps "integer(default=0, min=0, max=3)" a
            # single string, as NVDA does for its own spec.
            config.ConfigObj(confspec.splitlines(), encoding="utf-8", list_values=False)
        )
        # Append settings panel
        NVDASettingsDialog.categoryClasses.append(AudioSwitcherSettingsPanel)

    def terminate(self, *args, **kwargs):
        super().terminate(*args, **kwargs)
        if AudioSwitcherSettingsPanel in NVDASettingsDialog.categoryClasses:
            NVDASettingsDialog.categoryClasses.remove(AudioSwitcherSettingsPanel)

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Open Audio Switcher settings.")
    )
    def script_openSettings(self, gesture):
        wx.CallAfter(
            gui.mainFrame.popupSettingsDialog,
            NVDASettingsDialog,
            AudioSwitcherSettingsPanel,
        )

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Choose default audio devices.")
    )
    def script_chooseDefaultAudioDevices(self, gesture):
        wx.CallAfter(self._showAudioDeviceSelectionDialog)

    _selectionDialog = None

    def _showAudioDeviceSelectionDialog(self):
        if self._selectionDialog:
            self._selectionDialog.Raise()
            return
        gui.mainFrame.prePopup()
        try:
            self._selectionDialog = AudioDeviceSelectionDialog(gui.mainFrame)
            selections = self._runSelectionDialog(self._selectionDialog)
        finally:
            self._selectionDialog = None
            gui.mainFrame.postPopup()
        if selections:
            applyDeviceSelections(*selections)

    @staticmethod
    def _runSelectionDialog(dialog):
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            return dialog.getSelections()
        finally:
            dialog.Destroy()

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Set speaker 1 as default.")
    )
    def script_setSpeaker1(self, gesture):
        setConfiguredDevice(render=True, slot=1)

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Set speaker 2 as default.")
    )
    def script_setSpeaker2(self, gesture):
        setConfiguredDevice(render=True, slot=2)

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Set speaker 3 as default.")
    )
    def script_setSpeaker3(self, gesture):
        setConfiguredDevice(render=True, slot=3)

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Set microphone 1 as default.")
    )
    def script_setMicrophone1(self, gesture):
        setConfiguredDevice(render=False, slot=1)

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Set microphone 2 as default.")
    )
    def script_setMicrophone2(self, gesture):
        setConfiguredDevice(render=False, slot=2)

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Set microphone 3 as default.")
    )
    def script_setMicrophone3(self, gesture):
        setConfiguredDevice(render=False, slot=3)

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Announce current default speaker.")
    )
    def script_announceDefaultSpeaker(self, gesture):
        announceDefaultDevice(render=True)

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Announce current default microphone.")
    )
    def script_announceDefaultMicrophone(self, gesture):
        announceDefaultDevice(render=False)

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Announce current default speaker and microphone.")
    )
    def script_announceBothDefaultDevices(self, gesture):
        announceBothDefaultDevices()

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Cycle to next playback device (speaker).")
    )
    def script_cycleNextSpeaker(self, gesture):
        cycleDeviceWithFeedback(render=True)

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Cycle to next recording device (microphone).")
    )
    def script_cycleNextMicrophone(self, gesture):
        cycleDeviceWithFeedback(render=False)

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Toggle mute for default microphone.")
    )
    def script_toggleDefaultMicMute(self, gesture):
        toggleMicMuteWithFeedback()

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Announce whether default microphone is muted.")
    )
    def script_announceMicMuteState(self, gesture):
        announceMicMuteState()

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Toggle NVDA audio output between Primary and secondary device.")
    )
    def script_toggleNvdaOutput(self, gesture):
        toggleNvdaOutputWithFeedback()

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Activate profile 1.")
    )
    def script_activateProfile1(self, gesture):
        activateProfile(1)

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Activate profile 2.")
    )
    def script_activateProfile2(self, gesture):
        activateProfile(2)

    @script(
        # Translators: description in Input Gestures dialog.
        description=_("Activate profile 3.")
    )
    def script_activateProfile3(self, gesture):
        activateProfile(3)
