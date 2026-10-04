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

import globalPluginHandler
import api
import ui
import tones
import config
import gui
import wx
from scriptHandler import script
from logHandler import log

from .elementRegistry import ElementRegistry, getContextKey
from .fileWriter import writeEntry, getDailyFilePath
from .managementDialog import ManagementDialog


_CONFIG_SECTION = "localDataLogger"
_CONFIG_KEY_OUTPUT_DIR = "outputDir"
_CONFIG_KEY_ANNOUNCE_MARKED = "announceMarked"
_CONFIG_KEY_BEEP_MARKED = "beepMarked"


def _defaultOutputDir():
	"""Directorio por defecto para los registros: ~/Documents/LocalDataLogger."""
	home = os.path.expanduser("~")
	docs = os.path.join(home, "Documents")
	base = docs if os.path.isdir(docs) else home
	return os.path.join(base, "LocalDataLogger")


def _initConfigDefaults():
	"""Garantiza que la sección del add-on existe en config.conf."""
	confSpec = {
		_CONFIG_KEY_OUTPUT_DIR: f'string(default="{_defaultOutputDir()}")',
		_CONFIG_KEY_ANNOUNCE_MARKED: "boolean(default=True)",
		_CONFIG_KEY_BEEP_MARKED: "boolean(default=True)",
	}
	config.conf.spec[_CONFIG_SECTION] = confSpec


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	# Translators: nombre del add-on en Preferencias, Gestos de entrada
	scriptCategory = _("Local Data Logger")

	def __init__(self):
		super().__init__()
		_initConfigDefaults()
		self._registry = ElementRegistry()
		self._lastAnnouncedObj = None

	def terminate(self):
		super().terminate()

	def _getOutputDir(self):
		try:
			return config.conf[_CONFIG_SECTION][_CONFIG_KEY_OUTPUT_DIR]
		except Exception:
			return _defaultOutputDir()

	def _setOutputDir(self, path):
		try:
			config.conf[_CONFIG_SECTION][_CONFIG_KEY_OUTPUT_DIR] = path
		except Exception as e:
			log.error(f"localDataLogger: no se pudo guardar outputDir: {e}")

	def _announceEnabled(self):
		try:
			return bool(config.conf[_CONFIG_SECTION][_CONFIG_KEY_ANNOUNCE_MARKED])
		except Exception:
			return True

	def _beepEnabled(self):
		try:
			return bool(config.conf[_CONFIG_SECTION][_CONFIG_KEY_BEEP_MARKED])
		except Exception:
			return True

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
				if not self._registry.isMarked(obj):
					return
				self._lastAnnouncedObj = obj
				if self._beepEnabled():
					tones.beep(880, 40)
				if self._announceEnabled():
					# Translators: aviso al enfocar un campo marcado
					ui.message(_("marcado para registro"))
			except Exception as e:
				log.error(f"localDataLogger: error en event_gainFocus: {e}")

	def _extractValue(self, obj):
		"""Devuelve el valor exportable de un objeto (input, textarea, etiqueta)."""
		if obj is None:
			return ""
		try:
			value = getattr(obj, "value", None)
			if value:
				return str(value)
		except Exception:
			pass
		try:
			import controlTypes
			states = getattr(obj, "states", set()) or set()
			if controlTypes.State.CHECKED in states:
				return "marcado"
			if controlTypes.State.SELECTED in states:
				return "seleccionado"
		except Exception:
			pass
		try:
			name = (obj.name or "").strip()
			if name:
				return name
		except Exception:
			pass
		return ""

	def _captureCurrentContext(self):
		"""
		Captura los valores de todos los objetos marcados en el contexto
		actual. Devuelve (url, [(etiqueta, valor), ...]) o (None, None) si
		no hay nada que registrar.
		"""
		focus = api.getFocusObject()
		if focus is None:
			return None, None
		context = getContextKey(focus)
		marks = self._registry.getMarksForContext(context)
		if not marks:
			return context, []

		try:
			ti = focus.treeInterceptor
			root = ti.rootNVDAObject if ti is not None else None
		except Exception:
			root = None
		if root is None:
			root = focus
			try:
				while root.parent is not None:
					root = root.parent
			except Exception:
				pass

		from .elementRegistry import buildSignature, signaturesMatch

		def iterObjects(start, maxNodes=5000):
			queue = [start]
			seen = 0
			while queue and seen < maxNodes:
				current = queue.pop(0)
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

		results = []
		for mark in marks:
			targetSig = mark.get("signature")
			label = mark.get("label") or ""
			found = None
			for candidate in iterObjects(root):
				if signaturesMatch(buildSignature(candidate), targetSig):
					found = candidate
					break
			value = self._extractValue(found) if found is not None else ""
			results.append((label, value))

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

		outputDir = self._getOutputDir()
		path = writeEntry(outputDir, context, values)
		if path is None:
			# Translators: error al escribir
			ui.message(_("Error al escribir el archivo. Revise el directorio de salida en el panel de gestión."))
			return
		tones.beep(523, 40)
		tones.beep(659, 40)
		tones.beep(784, 60)
		filename = os.path.basename(path)
		# Translators: confirmación de registro exitoso
		ui.message(_("Registro guardado: {count} campos en {file}.").format(count=len(values), file=filename))

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
				self._getOutputDir,
				self._setOutputDir,
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
		path = getDailyFilePath(self._getOutputDir())
		exists = os.path.isfile(path)
		if exists:
			size = os.path.getsize(path)
			# Translators: anuncio cuando el archivo del día ya existe
			ui.message(_("Archivo del día: {path}. Tamaño: {size} bytes.").format(path=path, size=size))
		else:
			# Translators: anuncio cuando el archivo del día aún no existe
			ui.message(_("Archivo del día (aún no creado): {path}").format(path=path))
