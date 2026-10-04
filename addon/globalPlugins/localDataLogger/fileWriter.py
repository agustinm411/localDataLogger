# -*- coding: UTF-8 -*-
# Copyright (C) 2026 Agustin Martinez. Licencia GNU GPL v2.

"""
Escritura de registros a archivos locales diarios en modo append.

Implementa el contrato de la especificación:
  - El archivo del día se llama AAAA-MM-DD.txt.
  - Si ya existe, se hace append; nunca se crea registro(1).txt.
  - El primer bloque del día incluye la cabecera "FECHA: AAAA-MM-DD".
  - En navegadores: muestra "Aplicación:" y "URL:" con la dirección real.
  - En apps nativas: muestra solo "Aplicación:", sin línea "URL:".
  - No hay tráfico de red.
"""

import datetime
import os
import re
import threading
from logHandler import log


_writeLock = threading.RLock()
_SEPARATOR = "-" * 42


def _todayDateString():
	"""Devuelve la fecha de hoy en formato AAAA-MM-DD (hora local)."""
	return datetime.date.today().strftime("%Y-%m-%d")


def getDailyFilePath(outputDir):
	"""Ruta absoluta al archivo del día dentro de outputDir."""
	return os.path.join(outputDir, f"{_todayDateString()}.txt")


def ensureOutputDir(outputDir):
	"""Crea el directorio de salida si no existe. Devuelve True si quedó listo."""
	try:
		os.makedirs(outputDir, exist_ok=True)
		return True
	except OSError as e:
		log.error(f"localDataLogger: no se pudo crear {outputDir}: {e}")
		return False


def _contextToLines(context):
	"""
	Convierte la clave de contexto en las líneas de encabezado para el log.

	Reglas:
	  - "[appName] url"          → navegador con URL real:
	                                "Aplicación: appName" + "URL: url"
	  - "browser://appName/..."  → navegador sin URL disponible:
	                                "Aplicación: appName"  (sin línea URL)
	  - "app://appName/título"   → aplicación nativa:
	                                "Aplicación: appName - título"  (sin URL)
	  - Cualquier otro valor      → compatibilidad con datos anteriores:
	                                "URL: <valor>" tal cual.
	"""
	# Formato "[appName] url" — navegador con URL real
	m = re.match(r'^\[([^\]]+)\]\s+(.+)$', context, re.DOTALL)
	if m:
		appName = m.group(1).strip()
		url = m.group(2).strip()
		return [f"Aplicación: {appName}", f"URL: {url}"]

	# Formato "browser://appName/..." — navegador sin URL real
	if context.startswith("browser://"):
		rest = context[len("browser://"):]
		appName = rest.split("/", 1)[0] if "/" in rest else rest
		return [f"Aplicación: {appName}"]

	# Formato "app://appName/títuloVentana" — aplicación nativa
	if context.startswith("app://"):
		rest = context[len("app://"):]
		parts = rest.split("/", 1)
		appName = parts[0]
		windowTitle = parts[1] if len(parts) > 1 else ""
		if windowTitle:
			return [f"Aplicación: {appName} - {windowTitle}"]
		return [f"Aplicación: {appName}"]

	# Cualquier otro valor (compatibilidad con el formato anterior)
	return [f"URL: {context}"]


def writeEntry(outputDir, url, fieldValues):
	"""
	Añade una gestión al archivo del día.

	Parámetros:
	  outputDir: directorio donde reside el archivo diario.
	  url: clave de contexto generada por elementRegistry.getContextKey().
	  fieldValues: lista de tuplas (etiqueta, valor) en el orden en que
	               el usuario marcó los campos.

	Devuelve la ruta al archivo escrito, o None si falló.

	Si el archivo del día no existe, escribe la línea "FECHA: AAAA-MM-DD"
	como primer renglón. Si ya existe, no se repite: la fecha es global
	del archivo, no de cada gestión.
	"""
	if not ensureOutputDir(outputDir):
		return None

	path = getDailyFilePath(outputDir)
	isNewFile = not os.path.isfile(path)

	lines = []
	if isNewFile:
		lines.append(f"FECHA: {_todayDateString()}")
	lines.extend(_contextToLines(url))
	lines.append(_SEPARATOR)
	for label, value in fieldValues:
		safeValue = _formatMultiline(value)
		lines.append(f"{label}: {safeValue}")
	lines.append(_SEPARATOR)

	block = "\n".join(lines) + "\n"

	with _writeLock:
		try:
			with open(path, "a", encoding="utf-8") as f:
				f.write(block)
			return path
		except OSError as e:
			log.error(f"localDataLogger: no se pudo escribir {path}: {e}")
			return None


def _formatMultiline(value):
	"""
	Conserva los saltos de línea de un valor multilínea pero indenta las
	líneas continuación para distinguirlas del siguiente campo.
	"""
	if value is None:
		return ""
	text = str(value)
	if "\n" not in text:
		return text
	parts = text.splitlines()
	if not parts:
		return ""
	first = parts[0]
	rest = ["    " + p for p in parts[1:]]
	return "\n".join([first] + rest)
