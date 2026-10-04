# -*- coding: UTF-8 -*-
# Copyright (C) 2026 Agustin Martinez. Licencia GNU GPL v2.

"""
Diálogo de gestión de elementos marcados.

Equivale al "Panel de Control" de la propuesta: lista los campos marcados
agrupados por contexto, permite renombrarlos, quitarlos individualmente
o en masa, y abrir el directorio de registros en el explorador del sistema.
"""

import os
import subprocess
import sys

import addonHandler
import wx
from gui import guiHelper

from .fileWriter import ensureOutputDir

addonHandler.initTranslation()


class ManagementDialog(wx.Dialog):
	"""Diálogo modal de gestión de campos marcados."""

	def __init__(self, parent, registry, getOutputDir, setOutputDir):
		# Translators: título del diálogo de gestión
		super().__init__(parent, title=_("Local Data Logger - Gestión de campos"))
		self._registry = registry
		self._getOutputDir = getOutputDir
		self._setOutputDir = setOutputDir

		mainSizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(self, sizer=mainSizer)

		# Translators: etiqueta del combo de contextos
		contextLabel = _("&Contexto (URL o ventana):")
		self._contextChoice = helper.addLabeledControl(
			contextLabel, wx.Choice, choices=self._getContextChoices()
		)
		self._contextChoice.Bind(wx.EVT_CHOICE, self._onContextChange)
		if self._contextChoice.GetCount() > 0:
			self._contextChoice.SetSelection(0)

		# Translators: etiqueta de la lista de campos
		fieldsLabel = _("Campos &marcados:")
		self._fieldsList = helper.addLabeledControl(
			fieldsLabel,
			wx.ListBox,
			style=wx.LB_SINGLE,
			size=(500, 200),
		)

		buttonRow = guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		# Translators: botón para renombrar la etiqueta de un campo
		self._renameBtn = buttonRow.addButton(self, label=_("&Renombrar etiqueta..."))
		self._renameBtn.Bind(wx.EVT_BUTTON, self._onRename)
		# Translators: botón para quitar un campo individual
		self._removeBtn = buttonRow.addButton(self, label=_("&Quitar campo"))
		self._removeBtn.Bind(wx.EVT_BUTTON, self._onRemove)
		# Translators: botón para quitar todos los campos del contexto
		self._clearContextBtn = buttonRow.addButton(self, label=_("&Vaciar este contexto"))
		self._clearContextBtn.Bind(wx.EVT_BUTTON, self._onClearContext)
		# Translators: botón para quitar todas las marcas
		self._clearAllBtn = buttonRow.addButton(self, label=_("&Vaciar TODO"))
		self._clearAllBtn.Bind(wx.EVT_BUTTON, self._onClearAll)
		helper.addItem(buttonRow)

		# Translators: etiqueta de la ruta de salida
		outputLabel = _("Directorio donde se guardan los registros diarios:")
		helper.addItem(wx.StaticText(self, label=outputLabel))
		pathRow = wx.BoxSizer(wx.HORIZONTAL)
		self._outputCtrl = wx.TextCtrl(self, value=self._getOutputDir() or "")
		self._outputCtrl.SetMinSize((400, -1))
		pathRow.Add(self._outputCtrl, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=5)
		# Translators: botón para elegir directorio
		browseBtn = wx.Button(self, label=_("E&xaminar..."))
		browseBtn.Bind(wx.EVT_BUTTON, self._onBrowse)
		pathRow.Add(browseBtn, proportion=0)
		helper.addItem(pathRow, flag=wx.EXPAND)

		# Translators: botón para abrir el directorio de registros
		openFolderBtn = wx.Button(self, label=_("&Abrir directorio de registros"))
		openFolderBtn.Bind(wx.EVT_BUTTON, self._onOpenFolder)
		helper.addItem(openFolderBtn)

		closeRow = guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		# Translators: botón para cerrar el diálogo
		closeBtn = closeRow.addButton(self, id=wx.ID_CLOSE, label=_("&Cerrar"))
		closeBtn.Bind(wx.EVT_BUTTON, self._onClose)
		self.SetEscapeId(wx.ID_CLOSE)
		self.Bind(wx.EVT_CLOSE, self._onClose)
		helper.addItem(closeRow)

		self.SetSizer(mainSizer)
		mainSizer.Fit(self)
		self.CenterOnScreen()
		self._refreshFields()

	def _getContextChoices(self):
		return self._registry.getAllContexts()

	def _currentContext(self):
		if self._contextChoice.GetCount() == 0:
			return None
		sel = self._contextChoice.GetSelection()
		if sel == wx.NOT_FOUND:
			return None
		return self._contextChoice.GetString(sel)

	def _refreshContexts(self):
		previous = self._currentContext()
		self._contextChoice.Clear()
		for ctx in self._getContextChoices():
			self._contextChoice.Append(ctx)
		if previous and previous in self._registry.getAllContexts():
			idx = self._contextChoice.FindString(previous)
			if idx != wx.NOT_FOUND:
				self._contextChoice.SetSelection(idx)
		elif self._contextChoice.GetCount() > 0:
			self._contextChoice.SetSelection(0)
		self._refreshFields()

	def _refreshFields(self):
		self._fieldsList.Clear()
		ctx = self._currentContext()
		if ctx is None:
			return
		for entry in self._registry.getMarksForContext(ctx):
			label = entry.get("label") or ""
			sig = entry.get("signature") or {}
			name = sig.get("name") or ""
			display = label if (not name or label == name) else f"{label}  [{name}]"
			self._fieldsList.Append(display)

	def _onContextChange(self, evt):
		self._refreshFields()

	def _onRename(self, evt):
		ctx = self._currentContext()
		sel = self._fieldsList.GetSelection()
		if ctx is None or sel == wx.NOT_FOUND:
			return
		marks = self._registry.getMarksForContext(ctx)
		if sel >= len(marks):
			return
		current = marks[sel].get("label") or ""
		# Translators: solicitud al renombrar
		dlg = wx.TextEntryDialog(
			self,
			_("Nueva etiqueta para este campo:"),
			_("Renombrar campo"),
			value=current,
		)
		try:
			if dlg.ShowModal() == wx.ID_OK:
				if self._registry.renameLabel(ctx, sel, dlg.GetValue()):
					self._refreshFields()
					self._fieldsList.SetSelection(sel)
		finally:
			dlg.Destroy()

	def _onRemove(self, evt):
		ctx = self._currentContext()
		sel = self._fieldsList.GetSelection()
		if ctx is None or sel == wx.NOT_FOUND:
			return
		self._registry.removeAt(ctx, sel)
		if not self._registry.getMarksForContext(ctx):
			self._refreshContexts()
		else:
			self._refreshFields()

	def _onClearContext(self, evt):
		ctx = self._currentContext()
		if ctx is None:
			return
		# Translators: confirmación al vaciar un contexto
		msg = _("¿Desea quitar todos los campos marcados para «{context}»?").format(context=ctx)
		if wx.MessageBox(msg, _("Confirmar"), wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
			return
		self._registry.clearContext(ctx)
		self._refreshContexts()

	def _onClearAll(self, evt):
		# Translators: confirmación al vaciar todo
		msg = _("¿Desea quitar todas las marcas de todos los contextos? Esta acción no se puede deshacer.")
		if wx.MessageBox(msg, _("Confirmar"), wx.YES_NO | wx.ICON_WARNING, self) != wx.YES:
			return
		self._registry.clearAll()
		self._refreshContexts()

	def _onBrowse(self, evt):
		current = self._outputCtrl.GetValue() or os.path.expanduser("~")
		# Translators: título del selector de directorio
		dlg = wx.DirDialog(self, _("Directorio para los registros diarios"), defaultPath=current)
		try:
			if dlg.ShowModal() == wx.ID_OK:
				path = dlg.GetPath()
				self._outputCtrl.SetValue(path)
				self._setOutputDir(path)
		finally:
			dlg.Destroy()

	def _onOpenFolder(self, evt):
		path = self._outputCtrl.GetValue().strip()
		if not path or not os.path.isdir(path):
			# Translators: error si el directorio no existe
			wx.MessageBox(
				_("El directorio indicado no existe. Seleccione uno válido con «Examinar...»."),
				_("Directorio no encontrado"),
				wx.OK | wx.ICON_ERROR,
				self,
			)
			return
		try:
			if sys.platform == "win32":
				os.startfile(path)
			else:
				subprocess.Popen(["xdg-open", path])
		except OSError:
			pass

	def _onClose(self, evt):
		path = self._outputCtrl.GetValue().strip()
		if path and path != self._getOutputDir():
			if not ensureOutputDir(path):
				# Translators: error si no se puede usar el directorio indicado
				wx.MessageBox(
					_("No se puede crear ni usar el directorio «{path}». Indique otro o déjelo vacío para usar el directorio por defecto.").format(path=path),
					_("Directorio no válido"),
					wx.OK | wx.ICON_ERROR,
					self,
				)
				self._outputCtrl.SetFocus()
				return
		# Un valor vacío restablece el directorio por defecto.
		self._setOutputDir(path)
		self.EndModal(wx.ID_CLOSE)
