# -*- coding: UTF-8 -*-

import datetime
import os
import tempfile
import unittest

import nvdaStubs

nvdaStubs.install()

import fileWriter  # noqa: E402

SEP = "-" * 42
WEB_A = "[chrome] https://ejemplo.com/a"
WEB_B = "[chrome] https://ejemplo.com/b"


def at(h, m, s):
	return datetime.datetime(2026, 10, 4, h, m, s)


class WriteEntryTests(unittest.TestCase):

	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.dir = self.tmp.name

	def tearDown(self):
		self.tmp.cleanup()

	def read(self):
		with open(os.path.join(self.dir, "2026-10-04.txt"), encoding="utf-8") as f:
			return f.read()

	def test_newFileHasDateHeaderAndTime(self):
		fileWriter.writeEntry(self.dir, WEB_A, [("Nombre", "Juan")], now=at(10, 0, 1))
		self.assertEqual(self.read(), "\n".join([
			"FECHA: 2026-10-04",
			"Aplicación: chrome",
			"URL: https://ejemplo.com/a",
			SEP,
			"HORA: 10:00:01",
			"Nombre: Juan",
			SEP,
		]) + "\n")

	def test_sameContextDoesNotRepeatHeader(self):
		fileWriter.writeEntry(self.dir, WEB_A, [("Nombre", "Juan")], now=at(10, 0, 1))
		fileWriter.writeEntry(self.dir, WEB_A, [("Nombre", "María")], now=at(10, 5, 0))
		text = self.read()
		self.assertEqual(text.count("URL: "), 1)
		self.assertEqual(text.count("FECHA: "), 1)
		self.assertTrue(text.endswith("\n".join([
			"Nombre: Juan", SEP, "HORA: 10:05:00", "Nombre: María", SEP,
		]) + "\n"))

	def test_headerComparedOnlyWithLastOne(self):
		fileWriter.writeEntry(self.dir, WEB_A, [("x", "1")], now=at(10, 0, 0))
		fileWriter.writeEntry(self.dir, WEB_B, [("x", "2")], now=at(10, 1, 0))
		fileWriter.writeEntry(self.dir, WEB_A, [("x", "3")], now=at(10, 2, 0))
		fileWriter.writeEntry(self.dir, WEB_A, [("x", "4")], now=at(10, 3, 0))
		text = self.read()
		self.assertEqual(text.count("URL: https://ejemplo.com/a"), 2)
		self.assertEqual(text.count("URL: https://ejemplo.com/b"), 1)

	def test_dataLineLikeHeaderIsNotTakenAsHeader(self):
		fileWriter.writeEntry(self.dir, WEB_A, [("URL", "https://otra.com")], now=at(10, 0, 0))
		fileWriter.writeEntry(self.dir, WEB_A, [("URL", "https://otra.com")], now=at(10, 1, 0))
		self.assertEqual(self.read().count("Aplicación: chrome"), 1)

	def test_legacyFormatFileIsUnderstood(self):
		legacy = "\n".join([
			"FECHA: 2026-10-04",
			"Aplicación: chrome",
			"URL: https://ejemplo.com/a",
			SEP,
			"Nombre: Juan",
			SEP,
		]) + "\n"
		with open(os.path.join(self.dir, "2026-10-04.txt"), "w", encoding="utf-8") as f:
			f.write(legacy)
		fileWriter.writeEntry(self.dir, WEB_A, [("Nombre", "Ana")], now=at(11, 0, 0))
		self.assertEqual(self.read().count("URL: "), 1)

	def test_nativeAppHeader(self):
		fileWriter.writeEntry(self.dir, "app://notepad/Sin título", [("a", "b")], now=at(9, 0, 0))
		self.assertIn("Aplicación: notepad - Sin título\n" + SEP, self.read())

	def test_notFoundAndMultilineValues(self):
		fileWriter.writeEntry(
			self.dir, WEB_A,
			[("Falta", None), ("Notas", "línea 1\nlínea 2"), ("Etiqueta\nrota", "")],
			now=at(9, 0, 0),
		)
		text = self.read()
		self.assertIn("Falta: [no encontrado]\n", text)
		self.assertIn("Notas: línea 1\n    línea 2\n", text)
		self.assertIn("Etiqueta rota: \n", text)

	def test_invalidOutputDir(self):
		self.assertIsNone(fileWriter.writeEntry("", WEB_A, [("a", "b")]))


if __name__ == "__main__":
	unittest.main()
