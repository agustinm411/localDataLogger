# -*- coding: UTF-8 -*-
# Copyright (C) 2026 Agustin Martinez. Licencia GNU GPL v2.

"""
Configuración del add-on en nvda.ini (sección [localDataLogger]).
"""

import os

import config
from logHandler import log


SECTION = "localDataLogger"
KEY_OUTPUT_DIR = "outputDir"
KEY_ANNOUNCE_MARKED = "announceMarked"
KEY_BEEP_MARKED = "beepMarked"


def defaultOutputDir():
	"""Directorio por defecto para los registros: ~/Documents/LocalDataLogger."""
	home = os.path.expanduser("~")
	docs = os.path.join(home, "Documents")
	base = docs if os.path.isdir(docs) else home
	return os.path.join(base, "LocalDataLogger")


def initConfigDefaults():
	"""
	Registra la especificación de la sección del add-on en config.conf.

	El directorio por defecto se resuelve en tiempo de ejecución (valor
	vacío en el spec) para no incrustar rutas de Windows con barras
	invertidas dentro de la especificación de configobj.
	"""
	config.conf.spec[SECTION] = {
		KEY_OUTPUT_DIR: 'string(default="")',
		KEY_ANNOUNCE_MARKED: "boolean(default=True)",
		KEY_BEEP_MARKED: "boolean(default=True)",
	}


def _get(key, default):
	try:
		return config.conf[SECTION][key]
	except Exception:
		return default


def _set(key, value):
	try:
		config.conf[SECTION][key] = value
	except Exception as e:
		log.error(f"localDataLogger: no se pudo guardar {key}: {e}")


def getOutputDir():
	return (_get(KEY_OUTPUT_DIR, "") or "").strip() or defaultOutputDir()


def setOutputDir(path):
	_set(KEY_OUTPUT_DIR, path)


def announceEnabled():
	return bool(_get(KEY_ANNOUNCE_MARKED, True))


def setAnnounceEnabled(value):
	_set(KEY_ANNOUNCE_MARKED, bool(value))


def beepEnabled():
	return bool(_get(KEY_BEEP_MARKED, True))


def setBeepEnabled(value):
	_set(KEY_BEEP_MARKED, bool(value))
