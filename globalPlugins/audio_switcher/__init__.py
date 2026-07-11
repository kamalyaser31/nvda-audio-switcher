import logging
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
	except Exception as e:
		logging.error(f"Error enumerating audio devices: {e}")
	return devices


def getDefaultDeviceFriendlyName(render=True):
	"""Returns the friendly name of the currently active default audio device.
	render=True for playback devices, render=False for capture devices.
	"""
	flow = EDataFlow.eRender.value if render else EDataFlow.eCapture.value
	try:
		enumerator = AudioUtilities.GetDeviceEnumerator()
		# 0 is eConsole role
		device = enumerator.GetDefaultAudioEndpoint(flow, 0)
		if device:
			dev = AudioUtilities.CreateDevice(device)
			return dev.FriendlyName
	except Exception as e:
		logging.error(f"Error getting default audio device friendly name: {e}")
	return None


def setConfiguredDevice(render=True, slot=1):
	cfg = config.conf["audioSwitcher"]
	if render:
		deviceType = _("speaker")
		deviceKey = f"speakerDevice{slot}"
	else:
		deviceType = _("mic")
		deviceKey = f"micDevice{slot}"

	targetDevice = cfg[deviceKey]
	if not targetDevice:
		# Translators: short message when the requested device slot is empty.
		ui.message(_("Not set"))
		return

	# Find the target device ID by matching its friendly name
	flow = EDataFlow.eRender.value if render else EDataFlow.eCapture.value
	target_id = None
	try:
		enumerator = AudioUtilities.GetDeviceEnumerator()
		endpoints = enumerator.EnumAudioEndpoints(flow, DEVICE_STATE.ACTIVE.value)
		count = endpoints.GetCount()
		for i in range(count):
			item = endpoints.Item(i)
			dev = AudioUtilities.CreateDevice(item)
			if dev and targetDevice.lower() in dev.FriendlyName.lower():
				target_id = dev.id
				break
	except Exception as e:
		logging.error(f"Error searching for device '{targetDevice}': {e}")

	if not target_id:
		# Translators: short message when the configured device is unavailable.
		ui.message(_("Not found"))
		return

	success = True
	try:
		# Set the device as default for all three roles at once
		AudioUtilities.SetDefaultDevice(
			target_id,
			roles=[ERole.eConsole, ERole.eMultimedia, ERole.eCommunications]
		)
	except Exception as e:
		logging.error(f"SetDefaultDevice failed for '{targetDevice}': {e}")
		success = False

	if success:
		feedback = cfg["feedbackType"]
		# 0: Beep + Speech, 1: Speech, 2: Beep, 3: None
		if feedback in (0, 2):
			tones.beep(440, 100)
		if feedback in (0, 1):
			# Translators: short message when a default audio device slot is selected.
			ui.message(_("Done: {deviceType} {slot}").format(deviceType=deviceType, slot=slot))


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


class AudioSwitcherSettingsPanel(SettingsPanel):
	title = _("Audio Switcher")

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		playbackDevices = [name for _, name in getActiveDevices(render=True)]
		captureDevices = [name for _, name in getActiveDevices(render=False)]

		cfg = config.conf["audioSwitcher"]

		self.speakerChoices = [""] + playbackDevices
		for dev in (cfg["speakerDevice1"], cfg["speakerDevice2"], cfg["speakerDevice3"]):
			if dev and dev not in self.speakerChoices:
				self.speakerChoices.append(dev)

		self.micChoices = [""] + captureDevices
		for dev in (cfg["micDevice1"], cfg["micDevice2"], cfg["micDevice3"]):
			if dev and dev not in self.micChoices:
				self.micChoices.append(dev)

		# Speaker 1 Selection
		self.speakerDevice1Choice = sHelper.addLabeledControl(
			_("&Speaker 1:"),
			wx.Choice,
			choices=self.speakerChoices
		)
		self.setSelectionOrAdd(self.speakerDevice1Choice, cfg["speakerDevice1"], self.speakerChoices)

		# Speaker 2 Selection
		self.speakerDevice2Choice = sHelper.addLabeledControl(
			_("S&peaker 2:"),
			wx.Choice,
			choices=self.speakerChoices
		)
		self.setSelectionOrAdd(self.speakerDevice2Choice, cfg["speakerDevice2"], self.speakerChoices)

		# Speaker 3 Selection
		self.speakerDevice3Choice = sHelper.addLabeledControl(
			_("Sp&eaker 3:"),
			wx.Choice,
			choices=self.speakerChoices
		)
		self.setSelectionOrAdd(self.speakerDevice3Choice, cfg["speakerDevice3"], self.speakerChoices)

		# Microphone 1 Selection
		self.micDevice1Choice = sHelper.addLabeledControl(
			_("&Microphone 1:"),
			wx.Choice,
			choices=self.micChoices
		)
		self.setSelectionOrAdd(self.micDevice1Choice, cfg["micDevice1"], self.micChoices)

		# Microphone 2 Selection
		self.micDevice2Choice = sHelper.addLabeledControl(
			_("M&icrophone 2:"),
			wx.Choice,
			choices=self.micChoices
		)
		self.setSelectionOrAdd(self.micDevice2Choice, cfg["micDevice2"], self.micChoices)

		# Microphone 3 Selection
		self.micDevice3Choice = sHelper.addLabeledControl(
			_("Mi&crophone 3:"),
			wx.Choice,
			choices=self.micChoices
		)
		self.setSelectionOrAdd(self.micDevice3Choice, cfg["micDevice3"], self.micChoices)

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

	def setSelectionOrAdd(self, choiceControl, value, choicesList):
		if value in choicesList:
			choiceControl.SetSelection(choicesList.index(value))
		else:
			choiceControl.SetSelection(0)

	def onSave(self):
		cfg = config.conf["audioSwitcher"]
		cfg["speakerDevice1"] = self.speakerChoices[self.speakerDevice1Choice.GetSelection()]
		cfg["speakerDevice2"] = self.speakerChoices[self.speakerDevice2Choice.GetSelection()]
		cfg["speakerDevice3"] = self.speakerChoices[self.speakerDevice3Choice.GetSelection()]
		cfg["micDevice1"] = self.micChoices[self.micDevice1Choice.GetSelection()]
		cfg["micDevice2"] = self.micChoices[self.micDevice2Choice.GetSelection()]
		cfg["micDevice3"] = self.micChoices[self.micDevice3Choice.GetSelection()]
		cfg["feedbackType"] = self.feedbackTypeChoice.GetSelection()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""NVDA Audio Switcher Global Plugin using pycaw."""

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
