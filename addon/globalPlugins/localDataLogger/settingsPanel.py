# -*- coding: UTF-8 -*-
# Copyright (C) 2026 Agustin Martinez. Licencia GNU GPL v2.

"""
Panel de opciones del add-on en NVDA > Preferencias > Opciones.
"""

import addonHandler
import wx
from gui import guiHelper
from gui.settingsDialogs import SettingsPanel

from . import addonConfig

addonHandler.initTranslation()


class LocalDataLoggerSettingsPanel(SettingsPanel):
	# Translators: título de la categoría en el diálogo de opciones de NVDA
	title = _("Local Data Logger")

	def makeSettings(self, settingsSizer):
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		# Translators: casilla para el pitido al enfocar un campo marcado
		self._beepCheck = helper.addItem(
			wx.CheckBox(self, label=_("&Pitido al enfocar un campo marcado"))
		)
		self._beepCheck.SetValue(addonConfig.beepEnabled())
		# Translators: casilla para el anuncio al enfocar un campo marcado
		self._announceCheck = helper.addItem(
			wx.CheckBox(self, label=_("&Anunciar «marcado para registro» al enfocar un campo marcado"))
		)
		self._announceCheck.SetValue(addonConfig.announceEnabled())

	def onSave(self):
		addonConfig.setBeepEnabled(self._beepCheck.GetValue())
		addonConfig.setAnnounceEnabled(self._announceCheck.GetValue())
