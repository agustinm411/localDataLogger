# -*- coding: UTF-8 -*-
"""
Sustitutos mínimos de los módulos de NVDA, para probar sin NVDA la lógica
que no depende de la interfaz (fileWriter y elementRegistry).
"""

import enum
import logging
import os
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_DIR = os.path.join(ROOT, "addon", "globalPlugins", "localDataLogger")


class Role(enum.IntEnum):
	UNKNOWN = 0
	EDITABLETEXT = 8
	DOCUMENT = 52
	SECTION = 86


def install():
	if "logHandler" not in sys.modules:
		logHandler = types.ModuleType("logHandler")
		logHandler.log = logging.getLogger("localDataLogger-tests")
		sys.modules["logHandler"] = logHandler
	if "globalVars" not in sys.modules:
		globalVars = types.ModuleType("globalVars")
		globalVars.appArgs = types.SimpleNamespace(configPath=tempfile.mkdtemp())
		sys.modules["globalVars"] = globalVars
	if "controlTypes" not in sys.modules:
		controlTypes = types.ModuleType("controlTypes")
		controlTypes.Role = Role
		sys.modules["controlTypes"] = controlTypes
	if PACKAGE_DIR not in sys.path:
		sys.path.insert(0, PACKAGE_DIR)


class FakeObj:
	"""NVDAObject mínimo: rol, nombre y relaciones de árbol."""

	def __init__(self, role, name="", parent=None):
		self.role = role
		self.name = name
		self.parent = parent
		self.previous = None
		self.next = None
		self.firstChild = None
		self.treeInterceptor = None
		self.appModule = types.SimpleNamespace(appName="notepad")
		if parent is not None:
			last = parent.firstChild
			if last is None:
				parent.firstChild = self
			else:
				while last.next is not None:
					last = last.next
				last.next = self
				self.previous = last
