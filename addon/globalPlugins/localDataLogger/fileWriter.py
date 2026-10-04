# -*- coding: UTF-8 -*-
# Copyright (C) 2026 Agustin Martinez. Licencia GNU GPL v2.

"""
Escritura de registros a archivos locales diarios en modo append.

Implementa el contrato de la especificación:
  - El archivo del día se llama AAAA-MM-DD.txt.
  - Si ya existe, se hace append; nunca se crea registro(1).txt.
  - El primer bloque del día incluye la cabecera "FECHA: AAAA-MM-DD".
  - La cabecera de contexto ("Aplicación:" y, en navegadores, "URL:") solo
    se escribe cuando difiere de la última cabecera del archivo. Si es la
    misma, solo se añade el bloque de datos de la gestión.
  - Cada gestión empieza con "HORA: HH:MM:SS".
  - No hay tráfico de red.
"""

import datetime
import os
import re
import threading
from logHandler import log


_writeLock = threading.RLock()
_SEPARATOR = "-" * 42
_DATE_PREFIX = "FECHA: "
_TIME_PREFIX = "HORA: "
_HEADER_PREFIXES = ("Aplicación: ", "URL: ")

#: Valor que se escribe cuando un campo marcado no se encontró en pantalla.
NOT_FOUND_VALUE = "[no encontrado]"


def _todayDateString(now=None):
	"""Devuelve la fecha en formato AAAA-MM-DD (hora local)."""
	return (now or datetime.datetime.now()).strftime("%Y-%m-%d")


def getDailyFilePath(outputDir, now=None):
	"""Ruta absoluta al archivo del día dentro de outputDir."""
	return os.path.join(outputDir, f"{_todayDateString(now)}.txt")


def ensureOutputDir(outputDir):
	"""Crea el directorio de salida si no existe. Devuelve True si quedó listo."""
	if not outputDir:
		return False
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
		appName = rest.split("/", 1)[0]
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


def _isHeaderBlock(block):
	"""
	Indica si un bloque (líneas entre separadores) es una cabecera de
	contexto. Las cabeceras solo contienen líneas "Aplicación:" o "URL:".
	Los bloques de datos empiezan con "HORA:" (o, en archivos de la
	versión 1.0.0, con cualquier "etiqueta: valor").
	"""
	if not block or block[0].startswith(_TIME_PREFIX):
		return False
	return all(line.startswith(_HEADER_PREFIXES) for line in block)


def _lastHeaderInText(text):
	"""Devuelve las líneas de la última cabecera de contexto del texto, o None."""
	lastHeader = None
	block = []
	for line in text.splitlines() + [_SEPARATOR]:
		if line == _SEPARATOR:
			if _isHeaderBlock(block):
				lastHeader = block
			block = []
		elif line.startswith(_DATE_PREFIX) and not block:
			continue
		else:
			block.append(line)
	return lastHeader


def _readLastHeader(path):
	"""Lee el archivo del día y devuelve su última cabecera, o None."""
	try:
		with open(path, "r", encoding="utf-8", errors="replace") as f:
			return _lastHeaderInText(f.read())
	except OSError as e:
		log.warning(f"localDataLogger: no se pudo leer {path}: {e}")
		return None


def _formatLabel(label):
	"""Las etiquetas ocupan una sola línea."""
	return " ".join(str(label or "").split()) or "Campo"


def _formatMultiline(value):
	"""
	Conserva los saltos de línea de un valor multilínea pero indenta las
	líneas continuación para distinguirlas del siguiente campo.
	"""
	if value is None:
		return NOT_FOUND_VALUE
	text = str(value)
	if "\n" not in text and "\r" not in text:
		return text
	parts = text.splitlines()
	if not parts:
		return ""
	first = parts[0]
	rest = ["    " + p for p in parts[1:]]
	return "\n".join([first] + rest)


def writeEntry(outputDir, context, fieldValues, now=None):
	"""
	Añade una gestión al archivo del día.

	Parámetros:
	  outputDir: directorio donde reside el archivo diario.
	  context: clave de contexto generada por elementRegistry.getContextKey().
	  fieldValues: lista de tuplas (etiqueta, valor) en el orden en que
	               el usuario marcó los campos. Un valor None indica que el
	               campo no se encontró.
	  now: datetime de la gestión (por defecto, la hora actual).

	Devuelve la ruta al archivo escrito, o None si falló.
	"""
	if not ensureOutputDir(outputDir):
		return None

	now = now or datetime.datetime.now()
	path = getDailyFilePath(outputDir, now)
	headerLines = _contextToLines(context)

	with _writeLock:
		isNewFile = not os.path.isfile(path) or os.path.getsize(path) == 0
		lines = []
		if isNewFile:
			lines.append(f"{_DATE_PREFIX}{_todayDateString(now)}")
		if isNewFile or _readLastHeader(path) != headerLines:
			lines.extend(headerLines)
			lines.append(_SEPARATOR)
		lines.append(f"{_TIME_PREFIX}{now.strftime('%H:%M:%S')}")
		for label, value in fieldValues:
			lines.append(f"{_formatLabel(label)}: {_formatMultiline(value)}")
		lines.append(_SEPARATOR)
		block = "\n".join(lines) + "\n"

		try:
			with open(path, "a", encoding="utf-8") as f:
				f.write(block)
			return path
		except OSError as e:
			log.error(f"localDataLogger: no se pudo escribir {path}: {e}")
			return None
