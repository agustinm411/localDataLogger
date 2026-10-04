# -*- coding: UTF-8 -*-

import unittest

import nvdaStubs

nvdaStubs.install()

import elementRegistry  # noqa: E402
from nvdaStubs import FakeObj, Role  # noqa: E402


class SignatureTests(unittest.TestCase):

	def setUp(self):
		window = FakeObj(Role.UNKNOWN, "Formulario")
		self.form = FakeObj(Role.SECTION, "Contacto", window)
		self.phone1 = FakeObj(Role.EDITABLETEXT, "Teléfono", self.form)
		self.phone2 = FakeObj(Role.EDITABLETEXT, "Teléfono", self.form)

	def test_sameNameSiblingsAreDistinct(self):
		a = elementRegistry.buildSignature(self.phone1)
		b = elementRegistry.buildSignature(self.phone2)
		self.assertFalse(elementRegistry.signaturesMatch(a, b))
		self.assertTrue(elementRegistry.signaturesMatch(a, b, strict=False))

	def test_registryMarksBothSiblings(self):
		registry = elementRegistry.ElementRegistry()
		registry.clearAll()
		self.assertTrue(registry.addElement(self.phone1))
		self.assertTrue(registry.addElement(self.phone2))
		self.assertFalse(registry.addElement(self.phone2))
		self.assertTrue(registry.isMarked(self.phone2))
		self.assertTrue(registry.removeElement(self.phone1))
		self.assertFalse(registry.isMarked(self.phone1))
		self.assertTrue(registry.isMarked(self.phone2))

	def test_quickFilter(self):
		registry = elementRegistry.ElementRegistry()
		registry.clearAll()
		self.assertFalse(registry.couldBeMarked(self.phone1))
		registry.addElement(self.phone1)
		self.assertTrue(registry.couldBeMarked(self.phone2))
		self.assertFalse(registry.couldBeMarked(self.form))

	def test_renameAndRemoveAt(self):
		registry = elementRegistry.ElementRegistry()
		registry.clearAll()
		registry.addElement(self.phone1)
		context = registry.getAllContexts()[0]
		self.assertTrue(registry.renameLabel(context, 0, "  Móvil "))
		self.assertEqual(registry.getMarksForContext(context)[0]["label"], "Móvil")
		self.assertFalse(registry.renameLabel(context, 5, "x"))
		self.assertTrue(registry.removeAt(context, 0))
		self.assertEqual(registry.getAllContexts(), [])

	def test_brokenObjectDoesNotRaise(self):
		class Broken:
			@property
			def name(self):
				raise RuntimeError("COM error")

			@property
			def parent(self):
				raise RuntimeError("COM error")

			role = Role.EDITABLETEXT
			previous = None

		sig = elementRegistry.buildSignature(Broken())
		self.assertEqual(sig["name"], "")
		self.assertEqual(sig["ancestors"], [])


if __name__ == "__main__":
	unittest.main()
