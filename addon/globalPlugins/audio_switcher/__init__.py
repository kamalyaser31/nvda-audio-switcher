import logging
import os
import tempfile
from _ctypes import COMError

import comtypes.client

# Set comtypes code cache directory to a temporary location to avoid permission issues
try:
	temp_cache_dir = os.path.join(tempfile.gettempdir(), "nvda_comtypes_cache")
	if not os.path.exists(temp_cache_dir):
		os.makedirs(temp_cache_dir)
	comtypes.client.gen_dir = temp_cache_dir
except Exception:
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


def getActiveDevices(render=True):
	"""Returns a list of friendly names of active audio devices using pycaw.
	render=True for playback devices, render=False for capture devices.
	"""
	devices = []
	flow = EDataFlow.eRender.value if render else EDataFlow.eCapture.value
	try:
		enumerator = AudioUtilities.GetDeviceEnumerator()
		endpoints = enumerator.EnumAudioEndpoints(flow, DEVICE_STATE.ACTIVE.value)
		count = endpoints.GetCount()
		for i in range(count):
			item = endpoints.Item(i)
			device = AudioUtilities.CreateDevice(item)
			if device:
				devices.append((device.id, device.FriendlyName))
	except (COMError, OSError) as e:
		logging.error(f"Error enumerating audio devices: {e}")
	return devices


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


def findMatchingDeviceId(activeDevices, targetId, targetName):
	if targetId:
		for deviceId, _name in activeDevices:
			if deviceId == targetId:
				return deviceId
	if targetName:
		for deviceId, name in activeDevices:
			if targetName.lower() in name.lower():
				return deviceId
	return None


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


def announceDefaultDevice(render=True):
	currentName = getDefaultDeviceFriendlyName(render)
	if render:
		if currentName:
			# Translators: short message announcing the current default speaker.
			ui.message(_("Speaker: {device}").format(device=currentName))
		else:
			# Translators: short message when there is no default speaker.
			ui.message(_("No speaker"))
	else:
		if currentName:
			# Translators: short message announcing the current default microphone.
			ui.message(_("Mic: {device}").format(device=currentName))
		else:
			# Translators: short message when there is no default microphone.
			ui.message(_("No mic"))


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

		self.speakerDevices = getActiveDevices(render=True)
		self.microphoneDevices = getActiveDevices(render=False)
		currentSpeaker = getDefaultDeviceInfo(render=True)
		currentMicrophone = getDefaultDeviceInfo(render=False)
		currentSpeakerId = currentSpeaker[0] if currentSpeaker else None
		currentMicrophoneId = currentMicrophone[0] if currentMicrophone else None

		self.speakerChoice = sHelper.addLabeledControl(
			_("&Speakers:"),
			wx.Choice,
			choices=self._makeChoices(
				self.speakerDevices,
				currentSpeakerId,
				_("Do not change the default speaker")
			)
		)
		self.speakerChoice.SetSelection(0)

		self.microphoneChoice = sHelper.addLabeledControl(
			_("&Microphones:"),
			wx.Choice,
			choices=self._makeChoices(
				self.microphoneDevices,
				currentMicrophoneId,
				_("Do not change the default microphone")
			)
		)
		self.microphoneChoice.SetSelection(0)

		buttonSizer = wx.StdDialogButtonSizer()
		applyButton = wx.Button(self, wx.ID_OK, _("&Apply"))
		applyButton.SetDefault()
		buttonSizer.AddButton(applyButton)
		buttonSizer.AddButton(wx.Button(self, wx.ID_CANCEL))
		buttonSizer.Realize()
		mainSizer.Add(buttonSizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)

		self.SetSizerAndFit(mainSizer)
		self.CentreOnParent()
		self.speakerChoice.SetFocus()

	@staticmethod
	def _makeChoices(devices, currentId, unchangedLabel):
		choices = [unchangedLabel]
		for deviceId, name in devices:
			if deviceId == currentId:
				# Translators: marks the current device in the quick selection dialog.
				choices.append(_("{device} (current default)").format(device=name))
			else:
				choices.append(name)
		return choices

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


class AudioSwitcherSettingsPanel(SettingsPanel):
	title = _("Audio Switcher")

	def prepareChoices(self, activeDevices):
		"""Prepares values list (id|name) and display choices list for wx.Choice."""
		values = [""]
		choices = [""]
		
		for dev_id, name in activeDevices:
			values.append(f"{dev_id}|{name}")
			choices.append(name)
		return values, choices

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		playbackDevices = getActiveDevices(render=True)
		captureDevices = getActiveDevices(render=False)

		cfg = config.conf["audioSwitcher"]

		# Prepare Speaker Choices
		self.speakerValues, self.speakerChoices = self.prepareChoices(playbackDevices)

		# Prepare Microphone Choices
		self.micValues, self.micChoices = self.prepareChoices(captureDevices)

		# Speaker 1 Selection
		self.speakerDevice1Choice = sHelper.addLabeledControl(
			_("&Speaker 1:"),
			wx.Choice,
			choices=self.speakerChoices
		)
		self.setSelectionOrAdd(self.speakerDevice1Choice, cfg["speakerDevice1"], self.speakerValues)

		# Speaker 2 Selection
		self.speakerDevice2Choice = sHelper.addLabeledControl(
			_("S&peaker 2:"),
			wx.Choice,
			choices=self.speakerChoices
		)
		self.setSelectionOrAdd(self.speakerDevice2Choice, cfg["speakerDevice2"], self.speakerValues)

		# Speaker 3 Selection
		self.speakerDevice3Choice = sHelper.addLabeledControl(
			_("Sp&eaker 3:"),
			wx.Choice,
			choices=self.speakerChoices
		)
		self.setSelectionOrAdd(self.speakerDevice3Choice, cfg["speakerDevice3"], self.speakerValues)

		# Microphone 1 Selection
		self.micDevice1Choice = sHelper.addLabeledControl(
			_("&Microphone 1:"),
			wx.Choice,
			choices=self.micChoices
		)
		self.setSelectionOrAdd(self.micDevice1Choice, cfg["micDevice1"], self.micValues)

		# Microphone 2 Selection
		self.micDevice2Choice = sHelper.addLabeledControl(
			_("M&icrophone 2:"),
			wx.Choice,
			choices=self.micChoices
		)
		self.setSelectionOrAdd(self.micDevice2Choice, cfg["micDevice2"], self.micValues)

		# Microphone 3 Selection
		self.micDevice3Choice = sHelper.addLabeledControl(
			_("Mi&crophone 3:"),
			wx.Choice,
			choices=self.micChoices
		)
		self.setSelectionOrAdd(self.micDevice3Choice, cfg["micDevice3"], self.micValues)

		# Feedback Choices
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

	def setSelectionOrAdd(self, choiceControl, value, valuesList):
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
