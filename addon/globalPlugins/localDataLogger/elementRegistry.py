# -*- coding: UTF-8 -*-
# Copyright (C) 2026 Agustin Martinez. Licencia GNU GPL v2.

"""
Registro persistente de elementos marcados.

Equivalente al "Storage Local" de la propuesta original: guarda la
configuración de los elementos marcados, indexada por el contexto donde
viven (URL para navegadores, ruta del ejecutable mas título para apps
nativas).
"""

import json
import os
import threading
from logHandler import log
import globalVars


_CONFIG_FILENAME = "localDataLogger_marks.json"
_ANCESTOR_DEPTH = 3

# Nombres de proceso conocidos de navegadores web.
# Se usan para distinguir navegadores de aplicaciones nativas.
_BROWSER_APP_NAMES = frozenset({
	"msedge", "chrome", "chromium", "firefox", "opera", "brave",
	"vivaldi", "iexplore", "safari", "browser", "waterfox",
	"palemoon", "basilisk", "seamonkey",
})


def _getConfigPath():
	"""Devuelve la ruta absoluta al JSON de marcas dentro del perfil de NVDA."""
	configDir = globalVars.appArgs.configPath
	return os.path.join(configDir, _CONFIG_FILENAME)


def _safeName(obj):
	"""Nombre del objeto sin espacios sobrantes; "" si no se puede leer."""
	try:
		return (obj.name or "").strip()
	except Exception:
		return ""


def quickKey(obj):
	"""
	Clave barata (rol, nombre) de un objeto. Sirve para descartar
	rápidamente objetos que no pueden coincidir con ninguna marca sin
	calcular el contexto ni la firma completa.
	"""
	try:
		role = int(obj.role)
	except Exception:
		role = 0
	return (role, _safeName(obj))


def buildSignature(obj):
	"""
	Construye una firma estable para un NVDAObject.

	La firma es un diccionario serializable que identifica el objeto dentro
	de su contexto.
	"""
	try:
		role = int(obj.role)
	except Exception:
		role = 0
	name = _safeName(obj)

	ancestors = []
	try:
		parent = obj.parent
	except Exception:
		parent = None
	depth = 0
	while parent is not None and depth < _ANCESTOR_DEPTH:
		pname = _safeName(parent)
		try:
			prole = int(parent.role)
		except Exception:
			prole = 0
		ancestors.append({"name": pname, "role": prole})
		try:
			parent = parent.parent
		except Exception:
			break
		depth += 1

	siblingIndex = 0
	try:
		previous = obj.previous
		while previous is not None:
			if int(previous.role) == role:
				siblingIndex += 1
			previous = previous.previous
	except Exception:
		pass

	return {
		"role": role,
		"name": name,
		"ancestors": ancestors,
		"siblingIndex": siblingIndex,
	}


def signaturesMatch(a, b, strict=True):
	"""
	Compara dos firmas tolerando pequeñas variaciones del árbol.

	En modo estricto también se compara siblingIndex, para distinguir
	campos con el mismo rol, nombre y padre (p. ej. dos campos
	"Teléfono" seguidos). El modo no estricto lo ignora y se usa como
	respaldo al capturar valores, por si la página cambió el orden.
	"""
	if not a or not b:
		return False
	if a.get("role") != b.get("role"):
		return False
	if a.get("name") != b.get("name"):
		return False
	aAnc = a.get("ancestors") or []
	bAnc = b.get("ancestors") or []
	if aAnc and bAnc:
		if aAnc[0] != bAnc[0]:
			return False
	if strict and a.get("siblingIndex", 0) != b.get("siblingIndex", 0):
		return False
	return True


def _isWebUrl(text):
	"""Indica si una cadena tiene aspecto de URL web (incluye un esquema)."""
	if not text:
		return False
	try:
		return "://" in str(text)
	except Exception:
		return False


def _urlFromTreeInterceptor(ti):
	"""
	Extrae la URL de un treeInterceptor de modo navegación.

	Prueba dos fuentes, en orden:
	  1. documentConstantIdentifier: identificador canónico del documento
	     que usa el propio NVDA; en contenido web suele ser la URL.
	  2. rootNVDAObject.value: valor del objeto raíz del documento, que
	     es la única fuente que usaba la versión anterior.

	Devuelve la URL (str) o None.
	"""
	if ti is None:
		return None
	try:
		ident = getattr(ti, "documentConstantIdentifier", None)
		if _isWebUrl(ident):
			return str(ident).strip()
	except Exception:
		pass
	try:
		root = ti.rootNVDAObject
		if root is not None:
			value = getattr(root, "value", None)
			if _isWebUrl(value):
				return str(value).strip()
	except Exception:
		pass
	return None


def _findWebUrl(obj, maxDepth=60):
	"""
	Busca la URL del documento web que contiene a 'obj'.

	Recorre 'obj' y sus ancestros. En cada nivel intenta obtener la URL
	a partir del treeInterceptor asociado y, si el objeto es un documento,
	también de su propio 'value'. Esto cubre los casos en los que el
	treeInterceptor del objeto enfocado no está disponible o no expone la
	URL (modo UIA, iframes, documento aún sin terminar de cargar).

	Devuelve la URL más externa encontrada (la del documento principal),
	para que la clave de contexto sea estable aunque el foco esté dentro
	de un iframe. Devuelve None si no halla ninguna URL.
	"""
	try:
		import controlTypes
		documentRole = int(controlTypes.Role.DOCUMENT)
	except Exception:
		documentRole = None

	bestUrl = None
	current = obj
	depth = 0
	while current is not None and depth < maxDepth:
		depth += 1
		try:
			ti = current.treeInterceptor
		except Exception:
			ti = None
		url = _urlFromTreeInterceptor(ti)
		if url:
			bestUrl = url
		if documentRole is not None:
			try:
				if int(current.role) == documentRole:
					value = getattr(current, "value", None)
					if _isWebUrl(value):
						bestUrl = str(value).strip()
			except Exception:
				pass
		try:
			current = current.parent
		except Exception:
			break
	return bestUrl


def getContextKey(obj):
	"""
	Identifica el contexto del objeto.

	Formatos devueltos:
	  - Navegador con URL real:  "[appName] https://..."
	  - Navegador sin URL real:  "browser://appName/títuloVentana"
	  - Aplicación nativa:       "app://appName/títuloVentana"

	Así fileWriter puede distinguir cuándo mostrar la línea "URL:" (solo
	en navegadores con URL real) y cuándo usar "Aplicación:" sin URL.
	"""
	# Obtener el nombre de la aplicación antes de buscar la URL.
	try:
		appName = obj.appModule.appName if obj.appModule else "unknown"
	except Exception:
		appName = "unknown"

	isBrowser = appName.lower() in _BROWSER_APP_NAMES

	# Buscar la URL del contenido web asociado al objeto enfocado.
	url = _findWebUrl(obj)
	if url:
		if isBrowser:
			# Incluir el nombre del navegador junto a la URL
			return f"[{appName}] {url}"
		# Contenido web en una app no-navegador (p. ej. visores embebidos)
		return url

	# Sin URL: obtener el título de la ventana superior
	try:
		top = obj
		while top.parent is not None:
			top = top.parent
		windowTitle = (top.name or "").strip()
	except Exception:
		windowTitle = ""

	if isBrowser:
		# Navegador conocido pero sin URL web disponible
		# (p.ej. barra de herramientas, nueva pestaña, página de
		# configuración interna, o documento aún sin cargar). Se deja
		# un aviso en el log de NVDA para poder diagnosticar el caso.
		log.debug(
			f"localDataLogger: no se obtuvo URL en '{appName}'; "
			f"se usa el título de ventana '{windowTitle}'"
		)
		return f"browser://{appName}/{windowTitle}"

	return f"app://{appName}/{windowTitle}"


class ElementRegistry:
	"""Gestiona la lista de elementos marcados agrupados por contexto."""

	def __init__(self):
		self._lock = threading.RLock()
		self._data = {}
		self._quickKeys = frozenset()
		self._load()

	def _load(self):
		path = _getConfigPath()
		if not os.path.isfile(path):
			self._data = {}
			self._reindex()
			return
		try:
			with open(path, "r", encoding="utf-8") as f:
				self._data = json.load(f)
			if not isinstance(self._data, dict):
				log.warning(f"localDataLogger: marcas corruptas en {path}, reiniciando")
				self._data = {}
		except (OSError, ValueError) as e:
			log.error(f"localDataLogger: no se pudo leer {path}: {e}")
			self._data = {}
		self._reindex()

	def _reindex(self):
		"""Recalcula el índice (rol, nombre) de todas las marcas."""
		keys = set()
		for entries in self._data.values():
			for entry in entries:
				sig = entry.get("signature") or {}
				keys.add((sig.get("role", 0), sig.get("name", "")))
		self._quickKeys = frozenset(keys)

	def _save(self):
		self._reindex()
		path = _getConfigPath()
		try:
			tmpPath = path + ".tmp"
			with open(tmpPath, "w", encoding="utf-8") as f:
				json.dump(self._data, f, ensure_ascii=False, indent=2)
			os.replace(tmpPath, path)
		except OSError as e:
			log.error(f"localDataLogger: no se pudo guardar {path}: {e}")

	def couldBeMarked(self, obj):
		"""
		Filtro rápido: False si ningún contexto tiene una marca con el
		mismo rol y nombre que el objeto. No calcula contexto ni firma.
		"""
		quickKeys = self._quickKeys
		return bool(quickKeys) and quickKey(obj) in quickKeys

	def addElement(self, obj, label=None):
		"""
		Marca un objeto. Devuelve True si se añadió, False si ya estaba
		marcado.
		"""
		with self._lock:
			context = getContextKey(obj)
			sig = buildSignature(obj)
			lst = self._data.setdefault(context, [])
			for entry in lst:
				if signaturesMatch(entry.get("signature"), sig):
					return False
			finalLabel = label or sig.get("name") or "Campo"
			lst.append({"label": finalLabel, "signature": sig})
			self._save()
			return True

	def removeElement(self, obj):
		"""Quita la marca del objeto. Devuelve True si se quitó."""
		with self._lock:
			if not self.couldBeMarked(obj):
				return False
			context = getContextKey(obj)
			sig = buildSignature(obj)
			lst = self._data.get(context, [])
			for i, entry in enumerate(lst):
				if signaturesMatch(entry.get("signature"), sig):
					return self.removeAt(context, i)
			return False

	def isMarked(self, obj):
		"""Indica si el objeto está marcado en su contexto actual."""
		if not self.couldBeMarked(obj):
			return False
		with self._lock:
			context = getContextKey(obj)
			sig = buildSignature(obj)
			for entry in self._data.get(context, []):
				if signaturesMatch(entry.get("signature"), sig):
					return True
			return False

	def getMarksForContext(self, context):
		"""Devuelve una copia de la lista de marcas para un contexto."""
		with self._lock:
			return [dict(entry) for entry in self._data.get(context, [])]

	def getAllContexts(self):
		"""Devuelve la lista de contextos con al menos una marca."""
		with self._lock:
			return list(self._data.keys())

	def renameLabel(self, context, index, newLabel):
		"""Cambia la etiqueta de la marca en la posición index. Devuelve True si cambió."""
		newLabel = (newLabel or "").strip()
		if not newLabel:
			return False
		with self._lock:
			lst = self._data.get(context, [])
			if not 0 <= index < len(lst):
				return False
			lst[index]["label"] = newLabel
			self._save()
			return True

	def removeAt(self, context, index):
		"""Quita la marca en la posición index de un contexto. Devuelve True si se quitó."""
		with self._lock:
			lst = self._data.get(context, [])
			if not 0 <= index < len(lst):
				return False
			del lst[index]
			if not lst:
				del self._data[context]
			self._save()
			return True

	def clearContext(self, context):
		"""Borra todas las marcas de un contexto. Devuelve cuántas se borraron."""
		with self._lock:
			count = len(self._data.get(context, []))
			if context in self._data:
				del self._data[context]
				self._save()
			return count

	def clearAll(self):
		"""Borra todas las marcas de todos los contextos."""
		with self._lock:
			self._data = {}
			self._save()
