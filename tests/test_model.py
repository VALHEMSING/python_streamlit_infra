"""Pruebas del modelo matemático y de los seis experimentos del laboratorio."""

from __future__ import annotations

import math
import unittest

import model as m

PESOS = m.PESOS_BASE


class ModeloBaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.enlaces = m.tabla_enlaces_base()

    def modificar(self, u: str, v: str, **cambios: object) -> None:
        mascara = (
            (self.enlaces["Origen"] == u) & (self.enlaces["Destino"] == v)
        ) | ((self.enlaces["Origen"] == v) & (self.enlaces["Destino"] == u))
        for columna, valor in cambios.items():
            self.enlaces.loc[mascara, columna] = valor

    def test_referencias_iniciales(self) -> None:
        self.assertEqual(m.referencias(self.enlaces), (10.0, 100.0))

    def test_metricas_rutas_estaticas(self) -> None:
        esperado = {
            "PSRC": (3, 24.0, 100.0, 2.790),
            "SSRC": (4, 29.0, 50.0, 3.915),
            "TSRC": (5, 39.0, 50.0, 4.765),
        }
        for nombre, ruta in m.RUTAS_ESTATICAS.items():
            metricas = m.metricas_ruta(self.enlaces, ruta, PESOS)
            saltos, retardo, banda, costo = esperado[nombre]
            self.assertEqual(metricas["saltos"], saltos)
            self.assertAlmostEqual(float(metricas["retardo_ms"]), retardo)
            self.assertAlmostEqual(float(metricas["banda_mbps"]), banda)
            self.assertAlmostEqual(float(metricas["costo_c"]), costo, places=6)
            self.assertTrue(metricas["disponible"])

    def test_costo_multicriterio_hd(self) -> None:
        self.assertAlmostEqual(
            m.costo_ruta(self.enlaces, ("H", "D"), "multicriterio", PESOS),
            0.93,
            places=6,
        )

    def test_ruta_optima_inicial(self) -> None:
        ruta, costo = m.ruta_optima(self.enlaces, "saltos", PESOS)
        self.assertEqual(ruta, ["H", "D", "A", "B"])
        self.assertEqual(costo, 3.0)

    def test_sink_tree_inicial(self) -> None:
        siguiente, distancias, caminos = m.sink_tree(
            self.enlaces, "saltos", PESOS
        )
        fijos = {
            "A": "B",
            "C": "B",
            "D": "A",
            "J": "C",
            "E": "J",
            "H": "D",
            "N": "J",
        }
        for nodo, proximo in fijos.items():
            self.assertEqual(siguiente[nodo], proximo)
        self.assertIn(siguiente["O"], {"H", "N"})
        self.assertEqual(distancias["H"], 3.0)
        self.assertEqual(distancias["O"], 4.0)
        self.assertEqual(len(siguiente), len(m.NODOS) - 1)

        for nodo, camino in caminos.items():
            self.assertEqual(camino[0], nodo)
            self.assertEqual(camino[-1], m.DESTINO)

    def test_cadena_siguiente_salto_es_optima(self) -> None:
        for objetivo in m.OBJETIVOS:
            siguiente, _, _ = m.sink_tree(self.enlaces, objetivo, PESOS)
            ruta = [m.ORIGEN]
            while ruta[-1] != m.DESTINO:
                ruta.append(siguiente[ruta[-1]])
            optima, _ = m.ruta_optima(self.enlaces, objetivo, PESOS)
            self.assertEqual(ruta, optima)

    def test_empate_en_o(self) -> None:
        empates = m.empates_sink_tree(self.enlaces, "saltos", PESOS)
        self.assertEqual(empates.get("O"), ["H", "N"])

    def test_experimento_b_retardo(self) -> None:
        self.modificar("H", "D", Retardo_ms=40.0)
        self.assertEqual(m.referencias(self.enlaces)[0], 40.0)

        p1 = m.metricas_ruta(self.enlaces, m.RUTAS_ESTATICAS["PSRC"], PESOS)
        p2 = m.metricas_ruta(self.enlaces, m.RUTAS_ESTATICAS["SSRC"], PESOS)
        p3 = m.metricas_ruta(self.enlaces, m.RUTAS_ESTATICAS["TSRC"], PESOS)
        self.assertAlmostEqual(float(p1["retardo_ms"]), 56.0)
        self.assertAlmostEqual(float(p2["retardo_ms"]), 29.0)
        self.assertAlmostEqual(float(p3["retardo_ms"]), 39.0)

        ruta, costo = m.ruta_optima(self.enlaces, "retardo", PESOS)
        self.assertEqual(ruta, list(m.RUTAS_ESTATICAS["SSRC"]))
        self.assertEqual(costo, 29.0)

    def test_experimento_c_fallo_primario(self) -> None:
        self.modificar("H", "D", Disponible=False)
        self.assertFalse(
            m.ruta_disponible(self.enlaces, m.RUTAS_ESTATICAS["PSRC"])
        )
        self.assertEqual(m.primera_ruta_disponible(self.enlaces), "SSRC")

        ruta, _ = m.ruta_optima(self.enlaces, "saltos", PESOS)
        self.assertEqual(ruta, list(m.RUTAS_ESTATICAS["SSRC"]))

    def test_experimento_d_doble_fallo(self) -> None:
        self.modificar("H", "D", Disponible=False)
        self.modificar("H", "E", Disponible=False)
        self.assertEqual(m.primera_ruta_disponible(self.enlaces), "TSRC")

        ruta, costo = m.ruta_optima(self.enlaces, "saltos", PESOS)
        self.assertEqual(ruta, list(m.RUTAS_ESTATICAS["TSRC"]))
        self.assertEqual(costo, 5.0)

    def test_experimento_e_cuello_de_botella(self) -> None:
        inicial = m.metricas_ruta(self.enlaces, m.RUTAS_ESTATICAS["SSRC"], PESOS)
        self.modificar("E", "J", Banda_Mbps=5.0)
        actual = m.metricas_ruta(self.enlaces, m.RUTAS_ESTATICAS["SSRC"], PESOS)

        self.assertAlmostEqual(float(actual["banda_mbps"]), 5.0)
        self.assertAlmostEqual(float(actual["retardo_ms"]), 29.0)
        self.assertGreater(
            float(actual["costo_c"]), float(inicial["costo_c"]),
            "La penalización b_ref/b_ij debe subir el costo multicriterio",
        )

    def test_experimento_f_pesos(self) -> None:
        p1 = m.RUTAS_ESTATICAS["PSRC"]
        p2 = m.RUTAS_ESTATICAS["SSRC"]

        self.assertAlmostEqual(
            m.costo_ruta(self.enlaces, p1, "multicriterio", (1.0, 0.0, 0.0)),
            3.0,
        )
        self.assertAlmostEqual(
            m.costo_ruta(self.enlaces, p2, "multicriterio", (1.0, 0.0, 0.0)),
            4.0,
        )
        self.assertAlmostEqual(
            m.costo_ruta(self.enlaces, p2, "multicriterio", (0.0, 1.0, 0.0)),
            2.9,
        )
        self.assertAlmostEqual(
            m.costo_ruta(self.enlaces, p1, "multicriterio", (0.0, 0.0, 1.0)),
            3.0,
        )
        self.assertAlmostEqual(
            m.costo_ruta(self.enlaces, p2, "multicriterio", (0.0, 0.0, 1.0)),
            6.0,
        )

        ruta, _ = m.ruta_optima(self.enlaces, "multicriterio", (0.0, 1.0, 0.0))
        self.assertEqual(ruta, list(p1))
        ruta, _ = m.ruta_optima(self.enlaces, "multicriterio", (0.0, 0.0, 1.0))
        self.assertEqual(ruta, list(p1))

    def test_tabla_comparacion_estados(self) -> None:
        tabla = m.tabla_comparacion(self.enlaces, "saltos", PESOS)
        self.assertIn("✔ primera disponible", set(tabla["Estado"]))
        self.assertIn("★ ruta óptima", set(tabla["Estado"]))

        self.modificar("H", "D", Disponible=False)
        tabla = m.tabla_comparacion(self.enlaces, "saltos", PESOS)
        estados = dict(zip(tabla["Ruta"], tabla["Estado"]))
        self.assertEqual(estados["PSRC"], "✖ enlace caído")
        self.assertEqual(estados["SSRC"], "✔ primera disponible")

    def test_nodo_sin_ruta(self) -> None:
        self.modificar("H", "D", Disponible=False)
        self.modificar("H", "E", Disponible=False)
        self.modificar("H", "O", Disponible=False)

        ruta, costo = m.ruta_optima(self.enlaces, "saltos", PESOS)
        self.assertEqual(ruta, [])
        self.assertTrue(math.isinf(costo))

        siguiente, distancias, _ = m.sink_tree(self.enlaces, "saltos", PESOS)
        self.assertNotIn("H", siguiente)
        self.assertNotIn("H", distancias)

        tabla = m.tabla_sink_tree(
            siguiente, distancias, m.sink_tree(self.enlaces, "saltos", PESOS)[2]
        )
        fila_h = tabla[tabla["Nodo"] == "H"].iloc[0]
        self.assertEqual(fila_h["Siguiente salto"], "sin ruta")


if __name__ == "__main__":
    unittest.main()
