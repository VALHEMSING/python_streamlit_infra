"""Pruebas de humo de la interfaz Streamlit."""

from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


class AppSmokeTest(unittest.TestCase):
    def test_carga_inicial(self) -> None:
        at = AppTest.from_file(str(APP), default_timeout=90).run()
        self.assertFalse(at.exception)
        self.assertEqual(at.title[0].value, "Sink Tree y optimalidad de rutas")
        self.assertEqual(at.sidebar.radio[0].value, "Saltos mínimos (Johal)")

    def test_cambio_a_multicriterio(self) -> None:
        at = AppTest.from_file(str(APP), default_timeout=90).run()
        at.sidebar.radio[0].set_value("Multicriterio normalizado").run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.sidebar.slider), 3)
        self.assertAlmostEqual(at.sidebar.slider[0].value, 0.5)

    def test_escenario_fallo_primario(self) -> None:
        at = AppTest.from_file(str(APP), default_timeout=90).run()
        at.sidebar.selectbox[0].set_value("C · Fallo de H–D (saltos)")
        at.sidebar.button[0].click().run()
        self.assertFalse(at.exception)

        enlaces = at.session_state["enlaces"]
        fila = enlaces[(enlaces["Origen"] == "H") & (enlaces["Destino"] == "D")]
        self.assertFalse(bool(fila.iloc[0]["Disponible"]))
        self.assertEqual(at.sidebar.radio[0].value, "Saltos mínimos (Johal)")

    def test_escenario_retardo(self) -> None:
        at = AppTest.from_file(str(APP), default_timeout=90).run()
        at.sidebar.selectbox[0].set_value("B · H–D = 40 ms (retardo)")
        at.sidebar.button[0].click().run()
        self.assertFalse(at.exception)

        enlaces = at.session_state["enlaces"]
        fila = enlaces[(enlaces["Origen"] == "H") & (enlaces["Destino"] == "D")]
        self.assertEqual(float(fila.iloc[0]["Retardo_ms"]), 40.0)
        self.assertEqual(at.sidebar.radio[0].value, "Retardo mínimo")


if __name__ == "__main__":
    unittest.main()
