# -*- coding: UTF-8 -*-
# Copyright (C) 2026 Agustin Martinez. Licencia GNU GPL v2.

"""
Empaqueta el contenido de addon/ en localDataLogger<versión>.nvda-addon.

Uso: python build.py [--output DIRECTORIO]
"""

import argparse
import configparser
import os
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.join(ROOT, "addon")
_EXCLUDED_DIRS = {"__pycache__"}
_EXCLUDED_EXTS = {".pyc", ".pyo"}


def readManifest():
	parser = configparser.ConfigParser()
	with open(os.path.join(ADDON_DIR, "manifest.ini"), encoding="utf-8") as f:
		parser.read_string("[manifest]\n" + f.read())
	section = parser["manifest"]
	return section["name"].strip('"'), section["version"].strip('"')


def build(outputDir):
	name, version = readManifest()
	os.makedirs(outputDir, exist_ok=True)
	target = os.path.join(outputDir, f"{name}{version}.nvda-addon")
	with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
		for dirPath, dirNames, fileNames in os.walk(ADDON_DIR):
			dirNames[:] = sorted(d for d in dirNames if d not in _EXCLUDED_DIRS)
			for fileName in sorted(fileNames):
				if os.path.splitext(fileName)[1] in _EXCLUDED_EXTS:
					continue
				fullPath = os.path.join(dirPath, fileName)
				zf.write(fullPath, os.path.relpath(fullPath, ADDON_DIR))
	return target


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--output", default=ROOT, help="Directorio de salida (por defecto, la raíz del repositorio).")
	args = parser.parse_args()
	print(build(args.output))
