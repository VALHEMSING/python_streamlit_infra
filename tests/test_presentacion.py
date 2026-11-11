"""Pruebas de humo de la presentación interactiva."""

from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

PRESENTACION = Path(__file__).resolve().parents[1] / "presentacion.py"


class PresentacionSmokeTest(unittest.TestCase):
    def test_carga_inicial(self) -> None:
        at = AppTest.from_file(str(PRESENTACION), default_timeout=90).run()
        self.assertFalse(at.exception)
        self.assertEqual(at.title[0].value, "Cómo eliges la mejor ruta")
        self.assertEqual(at.session_state["alpha"], 0.5)

    def test_preset_retardo_con_hd_lento(self) -> None:
        at = AppTest.from_file(str(PRESENTACION), default_timeout=90).run()
        at.sidebar.checkbox(key="hd_lento").set_value(True).run()
        at.sidebar.button(key="preset_retardo").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state["alpha"], 0.0)
        self.assertEqual(at.session_state["beta"], 1.0)
        self.assertIn("Gana SSRC", at.success[-1].value)


if __name__ == "__main__":
    unittest.main()
