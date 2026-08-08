import logging
import os
import tempfile
from _ctypes import COMError

import comtypes.client

# Set comtypes code cache directory to a temporary location to avoid permission issues
try:
	temp_cache_dir = os.path.join(tempfile.gettempdir(), "nvda_comtypes_cache")
	os.makedirs(temp_cache_dir, exist_ok=True)
	comtypes.client.gen_dir = temp_cache_dir
except OSError as error:
	logging.warning("Unable to prepare the comtypes cache: %s", error)
	comtypes.client.gen_dir = None

import wx
import globalPluginHandler
import gui
import config
import ui
import tones
from gui.settingsDialogs import SettingsPanel, NVDASettingsDialog
from scriptHandler import script
from .pycaw.constants import DEVICE_STATE, EDataFlow, ERole
from .pycaw.utils import AudioUtilities

confspec = """
[audioSwitcher]
micDevice1 = string(default="")
micDevice2 = string(default="")
micDevice3 = string(default="")
speakerDevice1 = string(default="")
speakerDevice2 = string(default="")
speakerDevice3 = string(default="")
feedbackType = integer(default=0)
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


def _getActiveEndpoints(flow):
	enumerator = AudioUtilities.GetDeviceEnumerator()
	endpoints = enumerator.EnumAudioEndpoints(flow, DEVICE_STATE.ACTIVE.value)
	return endpoints, endpoints.GetCount()


def getActiveDevices(render=True):
	"""Returns a list of friendly names of active audio devices using pycaw.
	render=True for playback devices, render=False for capture devices.
	"""
	devices = []
	flow = EDataFlow.eRender.value if render else EDataFlow.eCapture.value
	try:
		endpoints, count = _getActiveEndpoints(flow)
	except (COMError, OSError) as error:
		logging.error("Error enumerating audio devices: %s", error)
		return devices

	for index in range(count):
		try:
			item = endpoints.Item(index)
			device = AudioUtilities.CreateDevice(item)
			if device:
				devices.append((device.id, device.FriendlyName))
		except (COMError, OSError) as error:
			logging.error("Error reading audio device %s: %s", index, error)
	return devices


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


def getDefaultDeviceInfo(render=True):
	"""Return the ID and friendly name of the active default audio device.
	render=True for playback devices, render=False for capture devices.
	"""
	flow = EDataFlow.eRender.value if render else EDataFlow.eCapture.value
	try:
		enumerator = AudioUtilities.GetDeviceEnumerator()
		# 0 is eConsole role
		device = enumerator.GetDefaultAudioEndpoint(flow, 0)
		if device:
			dev = AudioUtilities.CreateDevice(device)
			return dev.id, dev.FriendlyName
	except (COMError, OSError) as e:
		logging.error(f"Error getting default audio device information: {e}")
	return None


def getDefaultDeviceFriendlyName(render=True):
	deviceInfo = getDefaultDeviceInfo(render)
	return deviceInfo[1] if deviceInfo else None


def setDefaultDevice(deviceId):
	"""Set an audio endpoint as default for every role used by the add-on."""
	try:
		AudioUtilities.SetDefaultDevice(
			deviceId,
			roles=[ERole.eConsole, ERole.eMultimedia, ERole.eCommunications]
		)
		return True
	except (COMError, OSError) as e:
		logging.error(f"SetDefaultDevice failed for device '{deviceId}': {e}")
		return False


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


def _getOnlyDeviceId(deviceIds):
	return deviceIds[0] if len(deviceIds) == 1 else None


def findMatchingDeviceId(activeDevices, targetId, targetName):
	if targetId:
		for deviceId, _name in activeDevices:
			if deviceId == targetId:
				return deviceId
	if not targetName:
		return None
	targetNameKey = targetName.casefold()
	exactMatch = _getOnlyDeviceId([
		deviceId
		for deviceId, name in activeDevices
		if name.casefold() == targetNameKey
	])
	if exactMatch:
		return exactMatch
	return _getOnlyDeviceId([
		deviceId
		for deviceId, name in activeDevices
		if targetNameKey in name.casefold()
	])


def setConfiguredDevice(render=True, slot=1):
	cfg = config.conf["audioSwitcher"]
	if render:
		deviceType = _("speaker")
		deviceKey = f"speakerDevice{slot}"
	else:
		deviceType = _("mic")
		deviceKey = f"micDevice{slot}"

	targetValue = cfg[deviceKey]
	if not targetValue:
		# Translators: short message when the requested device slot is empty.
		ui.message(_("Not set"))
		return

	targetId, targetName = parseDeviceConfig(targetValue)

	activeDevices = getActiveDevices(render)
	target_id = findMatchingDeviceId(activeDevices, targetId, targetName)

	if not target_id:
		# Translators: short message when the configured device is unavailable.
		ui.message(_("Not found"))
		return

	if setDefaultDevice(target_id):
		# Translators: short message when a default audio device slot is selected.
		message = _("Done: {deviceType} {slot}").format(
			deviceType=deviceType,
			slot=slot
		)
		provideFeedback([message])
	else:
		# Translators: short message when setting default device fails.
		provideFeedback([], [_("Failed to set device")])


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
		getDefaultDeviceMessage(render=False)
	]
	ui.message("; ".join(messages))


def applyDeviceSelections(speaker, microphone):
	successMessages = []
	failureMessages = []
	if speaker:
		deviceId, name = speaker
		if setDefaultDevice(deviceId):
			# Translators: confirms a speaker selected in the quick dialog.
			successMessages.append(_("Default speaker: {device}").format(device=name))
		else:
			failureMessages.append(_("Failed to set speaker"))
	if microphone:
		deviceId, name = microphone
		if setDefaultDevice(deviceId):
			# Translators: confirms a microphone selected in the quick dialog.
			message = _("Default microphone: {device}").format(device=name)
			successMessages.append(message)
		else:
			failureMessages.append(_("Failed to set microphone"))
	provideFeedback(successMessages, failureMessages)


class AudioDeviceSelectionDialog(wx.Dialog):
	"""Choose connected speakers and microphones without changing saved slots."""

	def __init__(self, parent):
		super().__init__(parent, title=_("Choose default audio devices"))
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=mainSizer)

		self.speakerDevices = []
		self.microphoneDevices = []

		self.speakerChoice = sHelper.addLabeledControl(
			_("&Speakers:"),
			wx.Choice,
			choices=[]
		)

		self.microphoneChoice = sHelper.addLabeledControl(
			_("&Microphones:"),
			wx.Choice,
			choices=[]
		)

		buttonSizer = wx.StdDialogButtonSizer()
		refreshButton = wx.Button(self, label=_("&Refresh devices"))
		refreshButton.Bind(wx.EVT_BUTTON, self._onRefresh)
		buttonSizer.AddButton(refreshButton)
		applyButton = wx.Button(self, wx.ID_OK, _("&Apply"))
		applyButton.SetDefault()
		buttonSizer.AddButton(applyButton)
		buttonSizer.AddButton(wx.Button(self, wx.ID_CANCEL))
		buttonSizer.Realize()
		mainSizer.Add(buttonSizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)

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
			self.microphoneChoice,
			self.microphoneDevices
		)
		self.speakerDevices = getActiveDevices(render=True)
		self.microphoneDevices = getActiveDevices(render=False)
		self._updateSpeakerChoice(speakerId)
		self._updateMicrophoneChoice(microphoneId)

	def _updateSpeakerChoice(self, selectedId):
		current = getDefaultDeviceInfo(render=True)
		currentId = current[0] if current else None
		choices = self._makeChoices(
			self.speakerDevices,
			currentId,
			_("Do not change the default speaker"),
			_("No connected speakers")
		)
		self._replaceChoices(
			self.speakerChoice,
			choices,
			self.speakerDevices,
			selectedId
		)

	def _updateMicrophoneChoice(self, selectedId):
		current = getDefaultDeviceInfo(render=False)
		currentId = current[0] if current else None
		choices = self._makeChoices(
			self.microphoneDevices,
			currentId,
			_("Do not change the default microphone"),
			_("No connected microphones")
		)
		self._replaceChoices(
			self.microphoneChoice,
			choices,
			self.microphoneDevices,
			selectedId
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
		"""Return explicitly selected endpoints; index zero means no change."""
		return (
			self._getSelection(self.speakerChoice, self.speakerDevices),
			self._getSelection(self.microphoneChoice, self.microphoneDevices)
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


class AudioSwitcherSettingsPanel(SettingsPanel):
	title = _("Audio Switcher")

	def _prepareDeviceChoices(self, activeDevices, emptyLabel):
		"""Prepares values list (id|name) and display choices list for wx.Choice."""
		values = [""]
		if not activeDevices:
			return values, [emptyLabel]
		choices = [""] + getDisambiguatedDeviceNames(activeDevices)

		for dev_id, name in activeDevices:
			values.append(f"{dev_id}|{name}")
		return values, choices

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		playbackDevices = getActiveDevices(render=True)
		captureDevices = getActiveDevices(render=False)
		cfg = config.conf["audioSwitcher"]
		self.speakerValues, self.speakerChoices = self._prepareDeviceChoices(
			playbackDevices,
			_("No connected speakers")
		)
		self.micValues, self.micChoices = self._prepareDeviceChoices(
			captureDevices,
			_("No connected microphones")
		)
		self._addSpeakerSettings(sHelper, cfg)
		self._addMicrophoneSettings(sHelper, cfg)
		self._addFeedbackSettings(sHelper, cfg)

	def _addSpeakerSettings(self, sHelper, cfg):
		definitions = (
			(_("&Speaker 1:"), cfg["speakerDevice1"]),
			(_("S&peaker 2:"), cfg["speakerDevice2"]),
			(_("Sp&eaker 3:"), cfg["speakerDevice3"])
		)
		(
			self.speakerDevice1Choice,
			self.speakerDevice2Choice,
			self.speakerDevice3Choice
		) = self._addDeviceChoices(
			sHelper,
			self.speakerChoices,
			self.speakerValues,
			definitions
		)

	def _addMicrophoneSettings(self, sHelper, cfg):
		definitions = (
			(_("&Microphone 1:"), cfg["micDevice1"]),
			(_("M&icrophone 2:"), cfg["micDevice2"]),
			(_("Mi&crophone 3:"), cfg["micDevice3"])
		)
		(
			self.micDevice1Choice,
			self.micDevice2Choice,
			self.micDevice3Choice
		) = self._addDeviceChoices(
			sHelper,
			self.micChoices,
			self.micValues,
			definitions
		)

	def _addDeviceChoices(self, sHelper, choices, values, definitions):
		choiceControls = []
		for label, configuredValue in definitions:
			choice = sHelper.addLabeledControl(label, wx.Choice, choices=choices)
			self._selectConfiguredDevice(choice, configuredValue, values)
			choiceControls.append(choice)
		return choiceControls

	def _addFeedbackSettings(self, sHelper, cfg):
		self.feedbackChoices = [
			_("Beep and Speech"),
			_("Speech Only"),
			_("Beep Only"),
			_("None")
		]
		self.feedbackTypeChoice = sHelper.addLabeledControl(
			_("Feedback &Type:"),
			wx.Choice,
			choices=self.feedbackChoices
		)
		self.feedbackTypeChoice.SetSelection(cfg["feedbackType"])

	def _selectConfiguredDevice(self, choiceControl, value, valuesList):
		choiceControl.Enable(len(valuesList) > 1)
		if value in valuesList:
			choiceControl.SetSelection(valuesList.index(value))
		else:
			choiceControl.SetSelection(0)

	def onSave(self):
		cfg = config.conf["audioSwitcher"]
		cfg["speakerDevice1"] = self.speakerValues[self.speakerDevice1Choice.GetSelection()]
		cfg["speakerDevice2"] = self.speakerValues[self.speakerDevice2Choice.GetSelection()]
		cfg["speakerDevice3"] = self.speakerValues[self.speakerDevice3Choice.GetSelection()]
		cfg["micDevice1"] = self.micValues[self.micDevice1Choice.GetSelection()]
		cfg["micDevice2"] = self.micValues[self.micDevice2Choice.GetSelection()]
		cfg["micDevice3"] = self.micValues[self.micDevice3Choice.GetSelection()]
		cfg["feedbackType"] = self.feedbackTypeChoice.GetSelection()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""NVDA Audio Switcher Global Plugin using pycaw."""
	scriptCategory = _("Audio Switcher")

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# Load and register config spec
		config.conf.spec.update(config.ConfigObj(confspec.splitlines(), encoding="utf-8"))
		# Append settings panel
		NVDASettingsDialog.categoryClasses.append(AudioSwitcherSettingsPanel)

	def terminate(self, *args, **kwargs):
		super().terminate(*args, **kwargs)
		if AudioSwitcherSettingsPanel in NVDASettingsDialog.categoryClasses:
			NVDASettingsDialog.categoryClasses.remove(AudioSwitcherSettingsPanel)

	@script(
		# Translators: description in Input Gestures dialog.
		description=_("Choose default audio devices.")
	)
	def script_chooseDefaultAudioDevices(self, gesture):
		wx.CallAfter(self._showAudioDeviceSelectionDialog)

	def _showAudioDeviceSelectionDialog(self):
		gui.mainFrame.prePopup()
		try:
			dialog = AudioDeviceSelectionDialog(gui.mainFrame)
			try:
				if dialog.ShowModal() != wx.ID_OK:
					return
				speaker, microphone = dialog.getSelections()
			finally:
				dialog.Destroy()
		finally:
			gui.mainFrame.postPopup()
		applyDeviceSelections(speaker, microphone)

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
