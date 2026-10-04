# -*- coding: UTF-8 -*-
# Local Data Logger - Add-on para NVDA 2026.1 o superior.
#
# Copyright (C) 2026 Agustin Martinez <agustinmartinez550@gmail.com>
#
# Este programa es software libre: usted puede redistribuirlo y/o
# modificarlo bajo los términos de la Licencia Pública General de GNU
# publicada por la Free Software Foundation, en su versión 2 de la
# Licencia.
#
# Este programa se distribuye con la esperanza de que sea útil, pero
# SIN GARANTÍA ALGUNA; ni siquiera la garantía implícita MERCANTIL o
# de APTITUD PARA UN PROPÓSITO PARTICULAR. Vea la Licencia Pública
# General de GNU para más detalles.

"""
Local Data Logger - GlobalPlugin.

Punto de entrada del add-on. Define los atajos de teclado, el anuncio
audible al enfocar campos marcados, la captura de valores y el diálogo
de gestión.
"""

import os
from collections import deque

import addonHandler
import globalPluginHandler
import api
import controlTypes
import ui
import tones
import gui
import wx
from gui.settingsDialogs import NVDASettingsDialog
from scriptHandler import script
from logHandler import log

from . import addonConfig
from .elementRegistry import (
	ElementRegistry,
	buildSignature,
	getContextKey,
	quickKey,
	signaturesMatch,
)
from .fileWriter import writeEntry, getDailyFilePath
from .managementDialog import ManagementDialog
from .settingsPanel import LocalDataLoggerSettingsPanel

addonHandler.initTranslation()


_MAX_CAPTURE_NODES = 5000


def _roles(*names):
	"""Conjunto de roles de controlTypes que existan en esta versión de NVDA."""
	result = set()
	for name in names:
		role = getattr(controlTypes.Role, name, None)
		if role is not None:
			result.add(role)
	return frozenset(result)


# Controles de dos estados: se registra "marcado" / "no marcado".
_CHECKABLE_ROLES = _roles("CHECKBOX", "TOGGLEBUTTON", "SWITCH", "CHECKMENUITEM")
# Controles de opción: se registra "seleccionado" / "no seleccionado".
_RADIO_ROLES = _roles("RADIOBUTTON", "RADIOMENUITEM")
# Controles cuyo valor es lo que escribe o elige el usuario. Su nombre es
# la etiqueta del campo, así que nunca se usa como valor.
_VALUE_ROLES = _roles(
	"EDITABLETEXT", "PASSWORDEDIT", "COMBOBOX", "SPINBUTTON", "SLIDER",
	"LIST", "DATEEDITOR", "TIMEEDITOR",
)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	# Translators: nombre del add-on en Preferencias, Gestos de entrada
	scriptCategory = _("Local Data Logger")

	def __init__(self):
		super().__init__()
		addonConfig.initConfigDefaults()
		self._registry = ElementRegistry()
		self._lastAnnouncedObj = None
		NVDASettingsDialog.categoryClasses.append(LocalDataLoggerSettingsPanel)

	def terminate(self):
		try:
			NVDASettingsDialog.categoryClasses.remove(LocalDataLoggerSettingsPanel)
		except ValueError:
			pass
		self._lastAnnouncedObj = None
		super().terminate()

	def event_gainFocus(self, obj, nextHandler):
		"""
		Notifica al usuario, mediante un beep y un mensaje hablado, cuando
		el foco entra en un objeto marcado para registro.
		"""
		try:
			nextHandler()
		finally:
			try:
				if obj is None or obj is self._lastAnnouncedObj:
					return
				# isMarked descarta en primer lugar, sin coste, los objetos
				# cuyo rol y nombre no coinciden con ninguna marca.
				if not self._registry.isMarked(obj):
					return
				self._lastAnnouncedObj = obj
				if addonConfig.beepEnabled():
					tones.beep(880, 40)
				if addonConfig.announceEnabled():
					# Translators: aviso al enfocar un campo marcado
					ui.message(_("marcado para registro"))
			except Exception as e:
				log.error(f"localDataLogger: error en event_gainFocus: {e}")

	def _extractValue(self, obj):
		"""
		Devuelve el valor exportable de un objeto.

		En campos de entrada (textos, combos, listas...) solo se usa
		'value': su nombre es la etiqueta del campo, no el dato. Las
		casillas devuelven "marcado"/"no marcado" y los botones de opción
		"seleccionado"/"no seleccionado". En el resto (p. ej. textos
		estáticos) se usa 'value' y, si está vacío, el nombre.
		"""
		try:
			role = obj.role
		except Exception:
			role = None
		try:
			states = obj.states or set()
		except Exception:
			states = set()

		if role in _CHECKABLE_ROLES:
			return "marcado" if controlTypes.State.CHECKED in states else "no marcado"
		if role in _RADIO_ROLES:
			checked = controlTypes.State.CHECKED in states or controlTypes.State.SELECTED in states
			return "seleccionado" if checked else "no seleccionado"

		try:
			value = obj.value
		except Exception:
			value = None
		if value:
			return str(value)
		if role in _VALUE_ROLES or controlTypes.State.EDITABLE in states:
			return ""
		try:
			return (obj.name or "").strip()
		except Exception:
			return ""

	@staticmethod
	def _iterObjects(start, maxNodes=_MAX_CAPTURE_NODES):
		"""Recorre en anchura el árbol de objetos a partir de 'start'."""
		queue = deque([start])
		seen = 0
		while queue and seen < maxNodes:
			current = queue.popleft()
			seen += 1
			yield current
			try:
				child = current.firstChild
			except Exception:
				child = None
			while child is not None:
				queue.append(child)
				try:
					child = child.next
				except Exception:
					break

	@staticmethod
	def _captureRoot(focus):
		"""Raíz desde la que buscar los campos: el documento o la ventana superior."""
		try:
			ti = focus.treeInterceptor
			root = ti.rootNVDAObject if ti is not None else None
		except Exception:
			root = None
		if root is not None:
			return root
		root = focus
		try:
			while root.parent is not None:
				root = root.parent
		except Exception:
			pass
		return root

	def _captureCurrentContext(self):
		"""
		Captura los valores de todos los objetos marcados en el contexto
		actual. Devuelve (contexto, [(etiqueta, valor), ...]) o (None, None)
		si no hay foco. Un valor None indica que el campo no se encontró.
		"""
		focus = api.getFocusObject()
		if focus is None:
			return None, None
		context = getContextKey(focus)
		marks = self._registry.getMarksForContext(context)
		if not marks:
			return context, []

		targets = [mark.get("signature") or {} for mark in marks]
		wantedKeys = {(sig.get("role", 0), sig.get("name", "")) for sig in targets}
		exact = [None] * len(marks)
		loose = [None] * len(marks)
		pending = len(marks)

		# Un único recorrido del árbol para todas las marcas. Solo se
		# calcula la firma completa de los objetos con rol y nombre
		# compatibles con alguna marca.
		for candidate in self._iterObjects(self._captureRoot(focus)):
			if quickKey(candidate) not in wantedKeys:
				continue
			sig = buildSignature(candidate)
			for i, target in enumerate(targets):
				if exact[i] is not None:
					continue
				if signaturesMatch(sig, target, strict=True):
					exact[i] = candidate
					pending -= 1
					break
				if loose[i] is None and signaturesMatch(sig, target, strict=False):
					loose[i] = candidate
			if pending == 0:
				break

		results = []
		for i, mark in enumerate(marks):
			found = exact[i] if exact[i] is not None else loose[i]
			value = self._extractValue(found) if found is not None else None
			results.append((mark.get("label") or "", value))
		return context, results

	@script(
		# Translators: descripción del atajo para marcar el objeto enfocado
		description=_("Marca el objeto enfocado para incluirlo en el registro diario."),
		gesture="kb:NVDA+shift+m",
	)
	def script_markFocusedElement(self, gesture):
		focus = api.getFocusObject()
		if focus is None:
			# Translators: error si no hay foco
			ui.message(_("No hay ningún objeto enfocado."))
			return
		if self._registry.isMarked(focus):
			# Translators: aviso si ya estaba marcado
			ui.message(_("Este objeto ya estaba marcado."))
			return
		if self._registry.addElement(focus):
			tones.beep(660, 60)
			tones.beep(990, 60)
			# Translators: confirmación al marcar
			ui.message(_("Objeto marcado para registro."))

	@script(
		# Translators: descripción del atajo para desmarcar
		description=_("Quita la marca del objeto enfocado."),
		gesture="kb:NVDA+shift+u",
	)
	def script_unmarkFocusedElement(self, gesture):
		focus = api.getFocusObject()
		if focus is None:
			ui.message(_("No hay ningún objeto enfocado."))
			return
		if self._registry.removeElement(focus):
			tones.beep(990, 60)
			tones.beep(660, 60)
			# Translators: confirmación al desmarcar
			ui.message(_("Marca eliminada."))
		else:
			# Translators: aviso si no estaba marcado
			ui.message(_("Este objeto no estaba marcado."))

	@script(
		# Translators: descripción del atajo para registrar una gestión
		description=_("Registra la gestión actual: captura los valores de los campos marcados y los añade al archivo del día."),
		gesture="kb:NVDA+shift+r",
	)
	def script_recordEntry(self, gesture):
		context, values = self._captureCurrentContext()
		if context is None:
			ui.message(_("No se pudo determinar el contexto actual."))
			return
		if not values:
			# Translators: aviso si no hay nada que registrar
			ui.message(_("No hay campos marcados para este contexto. Marque al menos uno con NVDA+Shift+M."))
			return

		path = writeEntry(addonConfig.getOutputDir(), context, values)
		if path is None:
			# Translators: error al escribir
			ui.message(_("Error al escribir el archivo. Revise el directorio de salida en el panel de gestión."))
			return
		tones.beep(523, 40)
		tones.beep(659, 40)
		tones.beep(784, 60)
		filename = os.path.basename(path)
		missing = sum(1 for _label, value in values if value is None)
		# Translators: confirmación de registro exitoso
		message = _("Registro guardado: {count} campos en {file}.").format(count=len(values), file=filename)
		if missing:
			# Translators: aviso de campos marcados que no se encontraron al registrar
			message += " " + _("Atención: {missing} campos no se encontraron.").format(missing=missing)
		ui.message(message)

	@script(
		# Translators: descripción del atajo para abrir el panel
		description=_("Abre el panel de gestión de campos marcados."),
		gesture="kb:NVDA+shift+l",
	)
	def script_openManagementDialog(self, gesture):
		wx.CallAfter(self._showManagementDialog)

	def _showManagementDialog(self):
		try:
			dlg = ManagementDialog(
				gui.mainFrame,
				self._registry,
				addonConfig.getOutputDir,
				addonConfig.setOutputDir,
			)
			gui.mainFrame.prePopup()
			try:
				dlg.ShowModal()
			finally:
				gui.mainFrame.postPopup()
				dlg.Destroy()
		except Exception as e:
			log.error(f"localDataLogger: error abriendo el panel: {e}")

	@script(
		# Translators: descripción del atajo para anunciar la ruta del archivo del día
		description=_("Anuncia la ruta del archivo de registro del día actual."),
		gesture="kb:NVDA+shift+p",
	)
	def script_announceDailyFile(self, gesture):
		path = getDailyFilePath(addonConfig.getOutputDir())
		if os.path.isfile(path):
			size = os.path.getsize(path)
			# Translators: anuncio cuando el archivo del día ya existe
			ui.message(_("Archivo del día: {path}. Tamaño: {size} bytes.").format(path=path, size=size))
		else:
			# Translators: anuncio cuando el archivo del día aún no existe
			ui.message(_("Archivo del día (aún no creado): {path}").format(path=path))
