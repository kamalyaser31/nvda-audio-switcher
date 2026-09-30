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
"""


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
        msg = _("Done: {deviceType} {slot}").format(deviceType=devType, slot=slot)
        provideFeedback([msg])
    else:
        provideFeedback([], [_("Failed to set device")])


def setConfiguredDevice(render=True, slot=1):
    devType, targetValue = _resolveConfiguredSlot(render, slot)
    if not targetValue:
        ui.message(_("Not set"))
        return
    targetId, targetName = parseDeviceConfig(targetValue)
    if targetId and setDefaultDevice(targetId):
        _reportSlotFeedback(devType, slot, True)
        return
    target_id = findMatchingDeviceId(getActiveDevices(render), targetId, targetName)
    if not target_id:
        ui.message(_("Not found"))
        return
    _reportSlotFeedback(devType, slot, setDefaultDevice(target_id))


def getDefaultDeviceMessage(render=True):
    currentName = getDefaultDeviceFriendlyName(render)
    if render:
        if currentName:
            return _("Speaker: {device}").format(device=currentName)
        return _("No speaker")
    if currentName:
        return _("Mic: {device}").format(device=currentName)
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
            _("Default speaker: {device}")
            if isSpeaker
            else _("Default microphone: {device}")
        )
        success.append(template.format(device=name))
    else:
        failure.append(
            _("Failed to set speaker") if isSpeaker else _("Failed to set microphone")
        )


def _applySecondaryDevice(secondaryDevice, success):
    if secondaryDevice is None:
        return
    config.conf["audioSwitcher"]["nvdaSecondaryOutput"] = secondaryDevice
    if secondaryDevice:
        _id, name = parseDeviceConfig(secondaryDevice)
        success.append(_("NVDA secondary: {device}").format(device=name))
    else:
        success.append(_("NVDA secondary device cleared"))


def applyDeviceSelections(speaker, microphone, secondaryDevice=None):
    success = []
    failure = []
    _applyEndpoint(speaker, True, success, failure)
    _applyEndpoint(microphone, False, success, failure)
    _applySecondaryDevice(secondaryDevice, success)
    provideFeedback(success, failure)


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


class AudioSwitcherSettingsPanel(SettingsPanel):
    title = _("Audio Switcher")

    def makeSettings(self, settingsSizer):
        sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
        playback = getActiveDevices(render=True)
        capture = getActiveDevices(render=False)
        # (config key, wx.Choice, values) for every device control.
        self.deviceControls = []
        speakerLabels = (_("&Speaker 1:"), _("S&peaker 2:"), _("Sp&eaker 3:"))
        micLabels = (_("&Microphone 1:"), _("M&icrophone 2:"), _("Mi&crophone 3:"))
        speakerEmpty = "" if playback else _("No connected speakers")
        micEmpty = "" if capture else _("No connected microphones")
        self._addSlotControls(sHelper, "speaker", speakerLabels, playback, speakerEmpty)
        self._addSlotControls(sHelper, "mic", micLabels, capture, micEmpty)
        self._addDeviceControl(
            sHelper,
            "nvdaSecondaryOutput",
            _("NVDA Secondary &Output Device:"),
            playback,
            _("None (Not configured)"),
        )
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

    def onSave(self):
        cfg = config.conf["audioSwitcher"]
        for key, choice, values in self.deviceControls:
            cfg[key] = values[choice.GetSelection()]
        cfg["feedbackType"] = self.feedbackTypeChoice.GetSelection()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    """NVDA Audio Switcher Global Plugin using pure Win32 Core Audio."""

    scriptCategory = _("Audio Switcher")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Load and register config spec
        config.conf.spec.update(
            config.ConfigObj(confspec.splitlines(), encoding="utf-8")
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
