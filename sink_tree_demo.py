"""Demostración didáctica del sink tree: versión básica y versión avanzada.

Este archivo no depende de Streamlit ni de NetworkX. Se puede ejecutar solo:

    python sink_tree_demo.py

La versión básica usa BFS porque todos los enlaces cuestan 1 salto.
La versión avanzada usa Dijkstra porque los costos multicriterio son no
negativos pero distintos entre enlaces.

Los datos son ilustrativos y coinciden con el subgrafo del laboratorio.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import heapq
import math


# ---------------------------------------------------------------------------
# Datos de la red
# ---------------------------------------------------------------------------

NODOS = ("H", "D", "A", "B", "E", "J", "C", "O", "N")
DESTINO = "B"


@dataclass(frozen=True)
class Enlace:
    """Enlace no dirigido con sus métricas."""

    u: str
    v: str
    retardo: float  # d_ij, en ms
    banda: float  # b_ij, en Mbps
    activo: bool = True  # f_ij


ENLACES: tuple[Enlace, ...] = (
    Enlace("H", "D", 8.0, 100.0),
    Enlace("D", "A", 9.0, 100.0),
    Enlace("A", "B", 7.0, 100.0),
    Enlace("H", "E", 5.0, 50.0),
    Enlace("E", "J", 10.0, 50.0),
    Enlace("J", "C", 8.0, 100.0),
    Enlace("C", "B", 6.0, 100.0),
    Enlace("H", "O", 7.0, 50.0),
    Enlace("O", "N", 9.0, 100.0),
    Enlace("N", "J", 9.0, 100.0),
)

# Pesos del modelo multicriterio. Suman 1.
ALPHA, BETA, GAMMA = 0.5, 0.35, 0.15

# Referencias de normalización: máximos positivos de la tabla.
D_REF = max(enlace.retardo for enlace in ENLACES)
B_REF = max(enlace.banda for enlace in ENLACES)

# Las tres rutas estáticas del artículo, de mayor a menor prioridad.
RUTAS: dict[str, tuple[str, ...]] = {
    "PSRC": ("H", "D", "A", "B"),
    "SSRC": ("H", "E", "J", "C", "B"),
    "TSRC": ("H", "O", "N", "J", "C", "B"),
}

# Acceso rápido a los datos de un enlace no dirigido.
DATOS_ENLACE = {
    tuple(sorted((enlace.u, enlace.v))): enlace for enlace in ENLACES
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def costo_enlace(retardo: float, banda: float) -> float:
    """Costo multicriterio w_ij de un enlace.

    w_ij = α + β·(d_ij / d_ref) + γ·(b_ref / b_ij)
    """
    if banda <= 0:
        raise ValueError("La banda debe ser positiva")
    return (
        ALPHA
        + BETA * retardo / D_REF
        + GAMMA * B_REF / banda
    )


def pares(ruta: tuple[str, ...] | list[str]) -> list[tuple[str, str]]:
    """Pares consecutivos de una ruta."""
    return list(zip(ruta, ruta[1:]))


def construir_adyacencia() -> dict[str, list[str]]:
    """Grafo no dirigido con solo los enlaces activos (versión básica)."""
    grafo: dict[str, list[str]] = {nodo: [] for nodo in NODOS}
    for enlace in ENLACES:
        if not enlace.activo:
            continue
        grafo[enlace.u].append(enlace.v)
        grafo[enlace.v].append(enlace.u)
    return grafo


def construir_grafo_ponderado() -> dict[str, list[tuple[str, float]]]:
    """Grafo no dirigido con el costo w_ij de cada enlace (versión avanzada)."""
    grafo: dict[str, list[tuple[str, float]]] = {nodo: [] for nodo in NODOS}
    for enlace in ENLACES:
        if not enlace.activo:
            continue
        peso = costo_enlace(enlace.retardo, enlace.banda)
        grafo[enlace.u].append((enlace.v, peso))
        grafo[enlace.v].append((enlace.u, peso))
    return grafo


def metricas_ruta(ruta: tuple[str, ...] | list[str]) -> dict[str, float | int]:
    """Calcula H(P), D(P), B(P) y C(P) de una ruta."""
    datos = [DATOS_ENLACE[tuple(sorted((u, v)))] for u, v in pares(ruta)]
    return {
        "saltos": len(ruta) - 1,
        "retardo": sum(enlace.retardo for enlace in datos),
        "banda": min(enlace.banda for enlace in datos),
        "costo": sum(
            costo_enlace(enlace.retardo, enlace.banda) for enlace in datos
        ),
    }


# ---------------------------------------------------------------------------
# Versión básica: BFS con costo 1 por enlace
# ---------------------------------------------------------------------------


def sink_tree_basico(
    grafo: dict[str, list[str]], destino: str = DESTINO
) -> tuple[dict[str, int], dict[str, str]]:
    """Calcula distancias y siguientes saltos con BFS desde el destino.

    Al recorrer el grafo no dirigido desde B, el padre de cada nodo en el
    árbol BFS es precisamente su siguiente salto hacia B.
    """
    distancia: dict[str, int] = {destino: 0}
    siguiente: dict[str, str] = {}
    cola: deque[str] = deque([destino])

    while cola:
        v = cola.popleft()
        for u in grafo[v]:
            if u in distancia:
                continue
            distancia[u] = distancia[v] + 1
            siguiente[u] = v
            cola.append(u)

    return distancia, siguiente


def empates_basico(
    grafo: dict[str, list[str]], distancia: dict[str, int]
) -> dict[str, list[str]]:
    """Nodos donde más de un vecino ofrece el mismo mínimo de saltos."""
    empates: dict[str, list[str]] = {}
    for v, vecinos in grafo.items():
        if v == DESTINO or v not in distancia:
            continue
        candidatos = [
            u
            for u in vecinos
            if u in distancia and distancia[u] + 1 == distancia[v]
        ]
        if len(candidatos) > 1:
            empates[v] = candidatos
    return empates


# ---------------------------------------------------------------------------
# Versión avanzada: Dijkstra con costo multicriterio
# ---------------------------------------------------------------------------


def sink_tree_avanzado(
    grafo: dict[str, list[tuple[str, float]]], destino: str = DESTINO
) -> tuple[dict[str, float], dict[str, str]]:
    """Calcula distancias y siguientes saltos con Dijkstra desde B.

    El padre de cada nodo en el árbol de caminos mínimos es su siguiente
    salto hacia B. Se exige que todos los costos sean no negativos.
    """
    distancia: dict[str, float] = {nodo: math.inf for nodo in grafo}
    distancia[destino] = 0.0
    siguiente: dict[str, str] = {}
    cola: list[tuple[float, str]] = [(0.0, destino)]

    while cola:
        costo_actual, v = heapq.heappop(cola)
        if costo_actual > distancia[v] + 1e-12:
            continue  # entrada vieja de la cola de prioridad
        for u, peso in grafo[v]:
            nuevo = costo_actual + peso
            if nuevo + 1e-12 < distancia[u]:
                distancia[u] = nuevo
                siguiente[u] = v
                heapq.heappush(cola, (nuevo, u))

    return distancia, siguiente


# ---------------------------------------------------------------------------
# Salida de resultados
# ---------------------------------------------------------------------------


def imprimir_tabla(
    distancia: dict[str, float],
    siguiente: dict[str, str],
    formato: str,
    unidad: str = "",
) -> None:
    """Imprime la tabla de encaminamiento ordenada por costo."""
    alcanzables = [
        nodo
        for nodo in NODOS
        if nodo in distancia and math.isfinite(distancia[nodo])
    ]
    alcanzables.sort(key=lambda nodo: (distancia[nodo], NODOS.index(nodo)))

    print(f"{'Router':<8}{'Siguiente salto':<18}{'Costo hasta B':>14}")
    print("-" * 40)
    for nodo in alcanzables:
        proximo = "— (destino)" if nodo == DESTINO else siguiente.get(nodo, "—")
        valor = formato.format(distancia[nodo])
        if unidad:
            palabra = unidad if distancia[nodo] != 1 else unidad.rstrip("s")
            valor = f"{valor} {palabra}"
        print(f"{nodo:<8}{proximo:<18}{valor:>14}")


def main() -> None:
    print("=" * 72)
    print("SINK TREE: VERSIÓN BÁSICA Y VERSIÓN AVANZADA")
    print("=" * 72)

    print("\n1. GRAFO G=(V,E)")
    print(f"   Routers: {', '.join(NODOS)}")
    print(f"   Destino (sumidero): {DESTINO}")
    print(f"   Enlaces: {len(ENLACES)}")
    print(f"   d_ref = {D_REF:g} ms · b_ref = {B_REF:g} Mbps")
    print(f"   α={ALPHA} · β={BETA} · γ={GAMMA}")

    # ------------------------------------------------------------------
    print("\n2. VERSIÓN BÁSICA: BFS, cada enlace cuesta 1 salto")
    grafo_basico = construir_adyacencia()
    distancia_b, siguiente_b = sink_tree_basico(grafo_basico)
    imprimir_tabla(distancia_b, siguiente_b, "{:g}", unidad="saltos")

    empates = empates_basico(grafo_basico, distancia_b)
    for nodo, candidatos in empates.items():
        elegido = siguiente_b[nodo]
        print(
            f"\n   Empate en {nodo}: {' o '.join(candidatos)} ofrecen el mismo "
            f"costo. La tabla elige {elegido}; cualquiera es válido."
        )

    # ------------------------------------------------------------------
    print("\n3. COSTOS MULTICRITERIO w_ij")
    print(f"{'Enlace':<10}{'d_ij (ms)':>12}{'b_ij (Mbps)':>14}{'w_ij':>10}")
    print("-" * 46)
    for enlace in ENLACES:
        peso = costo_enlace(enlace.retardo, enlace.banda)
        print(
            f"{enlace.u}–{enlace.v:<7}{enlace.retardo:>12g}"
            f"{enlace.banda:>14g}{peso:>10.4f}"
        )

    print("\n4. VERSIÓN AVANZADA: Dijkstra con w_ij")
    grafo_avanzado = construir_grafo_ponderado()
    distancia_a, siguiente_a = sink_tree_avanzado(grafo_avanzado)
    imprimir_tabla(distancia_a, siguiente_a, "{:.4f}")

    diferencias = {
        nodo: (siguiente_b.get(nodo), siguiente_a.get(nodo))
        for nodo in NODOS
        if nodo != DESTINO
        and siguiente_b.get(nodo) != siguiente_a.get(nodo)
    }
    print("\n   Diferencias entre ambos árboles:")
    if diferencias:
        for nodo, (basico, avanzado) in diferencias.items():
            print(
                f"   - {nodo}: básico → {basico}; avanzado → {avanzado}. "
                "El cambio se debe a que el costo ya no es solo el número de saltos."
            )
    else:
        print("   Ninguna: ambos objetivos eligen los mismos siguientes saltos.")

    # ------------------------------------------------------------------
    print("\n5. LAS TRES RUTAS DEL ARTÍCULO")
    print(
        f"{'Ruta':<7}{'Secuencia':<26}{'H(P)':>6}{'D(P)':>9}"
        f"{'B(P)':>9}{'C(P)':>9}"
    )
    print("-" * 66)
    for nombre, ruta in RUTAS.items():
        met = metricas_ruta(ruta)
        print(
            f"{nombre:<7}{' → '.join(ruta):<26}{met['saltos']:>6}"
            f"{met['retardo']:>8g}ms{met['banda']:>8g}M{met['costo']:>9.3f}"
        )

    print(
        "\n   Lectura: con los datos base, PSRC gana por saltos y también "
        "por costo multicriterio.\n"
        "   Si H–D sube a 40 ms, el objetivo retardo prefiere SSRC (29 ms), "
        "aunque C(P) puede cambiar\n"
        "   porque d_ref también cambia. Por eso hay que declarar siempre la "
        "función objetivo."
    )

    print("\n6. LIMITACIONES DEL EJEMPLO")
    print("   - Los datos son ilustrativos, no resultados experimentales.")
    print("   - Un sink tree da un solo siguiente salto por router.")
    print("   - No crea rutas de respaldo ni detecta fallos por sí mismo.")
    print("   - La fórmula multicriterio es una extensión docente del laboratorio.")


if __name__ == "__main__":
    main()
