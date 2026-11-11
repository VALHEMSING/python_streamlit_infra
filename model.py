"""Núcleo matemático del laboratorio de Sink Tree y optimalidad de rutas.

El módulo no depende de Streamlit: construye el grafo a partir de la tabla de
enlaces, evalúa las funciones objetivo y calcula el árbol de siguientes saltos
hacia el destino B.

Referencia:
    Johal, H. S. (2008). Optimality Principle Based Sink Tree Methodology for
    Adaptive Static Routing Using Multiple Route Configuration Scheme.
    WCECS 2008. DOI: 10.1109/WCECS.2008.21.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import networkx as nx
import pandas as pd

# ---------------------------------------------------------------------------
# Topología del subgrafo del artículo
# ---------------------------------------------------------------------------

NODOS: tuple[str, ...] = ("H", "D", "A", "B", "E", "J", "C", "O", "N")
ORIGEN = "H"
DESTINO = "B"

# Segundo grupo de routers que la app puede añadir al modelo dinámico.
NODOS_EXTENDIDOS: tuple[str, ...] = ("P", "R", "S", "T", "Q", "U")

# Posiciones fijas para que el dibujo sea legible y reproducible.
POSICIONES: dict[str, tuple[float, float]] = {
    "H": (0.0, 0.2),
    "D": (1.2, 1.5),
    "A": (2.4, 1.5),
    "B": (3.7, 0.2),
    "E": (1.2, -0.8),
    "J": (2.4, -0.8),
    "C": (3.3, -0.2),
    "O": (0.1, -1.7),
    "N": (1.2, -2.0),
}

# (origen, destino, retardo_ms, banda_mbps)
ENLACES_BASE: tuple[tuple[str, str, float, float], ...] = (
    ("H", "D", 8.0, 100.0),
    ("D", "A", 9.0, 100.0),
    ("A", "B", 7.0, 100.0),
    ("H", "E", 5.0, 50.0),
    ("E", "J", 10.0, 50.0),
    ("J", "C", 8.0, 100.0),
    ("C", "B", 6.0, 100.0),
    ("H", "O", 7.0, 50.0),
    ("O", "N", 9.0, 100.0),
    ("N", "J", 9.0, 100.0),
)

# Rutas estáticas preconfiguradas en el artículo, ordenadas por prioridad.
RUTAS_ESTATICAS: dict[str, tuple[str, ...]] = {
    "PSRC": ("H", "D", "A", "B"),
    "SSRC": ("H", "E", "J", "C", "B"),
    "TSRC": ("H", "O", "N", "J", "C", "B"),
}

OBJETIVOS: tuple[str, str, str] = ("saltos", "retardo", "multicriterio")

COLUMNAS_ENLACES: tuple[str, ...] = (
    "Origen",
    "Destino",
    "Retardo_ms",
    "Banda_Mbps",
    "Disponible",
)

COLUMNAS_ENLACES_EDITOR: tuple[str, ...] = (
    "Origen",
    "Destino",
    "Retardo_ms",
    "Banda_Mbps",
    "Pérdida_%",
    "Disponible",
)

# Pesos multicriterio de referencia del laboratorio (suman 1).
PESOS_BASE: tuple[float, float, float] = (0.5, 0.35, 0.15)


# ---------------------------------------------------------------------------
# Tabla de enlaces
# ---------------------------------------------------------------------------


def tabla_enlaces_base() -> pd.DataFrame:
    """Devuelve una copia nueva de la tabla de enlaces del artículo."""
    return pd.DataFrame(
        [
            {
                "Origen": origen,
                "Destino": destino,
                "Retardo_ms": retardo,
                "Banda_Mbps": banda,
                "Disponible": True,
                "Pérdida_%": 0.0,
            }
            for origen, destino, retardo, banda in ENLACES_BASE
        ],
        columns=list(COLUMNAS_ENLACES_EDITOR),
    )


def tabla_enlaces_vacia() -> pd.DataFrame:
    """Tabla inicial para el editor de topología (sin enlaces)."""
    return pd.DataFrame(
        {
            "Origen": pd.Series(dtype=str),
            "Destino": pd.Series(dtype=str),
            "Retardo_ms": pd.Series(dtype=float),
            "Banda_Mbps": pd.Series(dtype=float),
            "Disponible": pd.Series(dtype=bool),
        },
        columns=list(COLUMNAS_ENLACES),
    )


def agregar_enlace(
    enlaces: pd.DataFrame,
    origen: str,
    destino: str,
    retardo_ms: float,
    banda_mbps: float,
    disponible: bool = True,
) -> pd.DataFrame:
    """Devuelve una nueva tabla con el enlace añadido (sin duplicados)."""
    if (
        ((enlaces["Origen"] == origen) & (enlaces["Destino"] == destino))
        | ((enlaces["Origen"] == destino) & (enlaces["Destino"] == origen))
    ).any():
        return enlaces
    nuevo = pd.DataFrame(
        {
            "Origen": [origen],
            "Destino": [destino],
            "Retardo_ms": [retardo_ms],
            "Banda_Mbps": [banda_mbps],
            "Disponible": [disponible],
        }
    )
    return pd.concat([enlaces, nuevo], ignore_index=True)


def quitar_enlace(
    enlaces: pd.DataFrame, origen: str, destino: str
) -> pd.DataFrame:
    """Devuelve una nueva tabla sin el enlace indicado, si existe."""
    mascara = (
        (enlaces["Origen"] == origen) & (enlaces["Destino"] == destino)
    ) | (
        (enlaces["Origen"] == destino) & (enlaces["Destino"] == origen)
    )
    if not mascara.any():
        return enlaces
    return enlaces.loc[~mascara].reset_index(drop=True)



def agregar_perdida_enlace(
    enlaces: pd.DataFrame, origen: str, destino: str, perdida: float
) -> pd.DataFrame:
    """Devuelve una tabla donde ese enlace tiene la pérdida indicada."""
    resultado = enlaces.copy()
    if "Pérdida_%" not in resultado.columns:
        resultado["Pérdida_%"] = 0.0
    mascara = (
        (resultado["Origen"] == origen) & (resultado["Destino"] == destino)
    ) | (
        (resultado["Origen"] == destino) & (resultado["Destino"] == origen)
    )
    if not mascara.any():
        return resultado
    resultado.loc[mascara, "Pérdida_%"] = perdida
    return resultado


def nombre_enlace(origen: str, destino: str) -> str:
    """Etiqueta legible de un enlace no dirigido."""
    return f"{origen}–{destino}"


def vista_enlaces(enlaces: pd.DataFrame) -> pd.DataFrame:
    """Tabla que se muestra al estudiante (sin columnas internas)."""
    vista = pd.DataFrame(
        {
            "Enlace": [
                nombre_enlace(origen, destino)
                for origen, destino in zip(enlaces["Origen"], enlaces["Destino"])
            ],
            "Retardo_ms": enlaces["Retardo_ms"].to_numpy(),
            "Banda_Mbps": enlaces["Banda_Mbps"].to_numpy(),
            "Disponible": enlaces["Disponible"].to_numpy(),
            "Pérdida_%": (
                enlaces["Pérdida_%"].to_numpy()
                if "Pérdida_%" in enlaces.columns
                else [0.0] * len(enlaces)
            ),
        }
    )
    return vista


def vista_enlaces_mostrar_con_perdida(enlaces: pd.DataFrame) -> pd.DataFrame:
    """Vista idéntica a ``vista_enlaces``, pero con la columna pérdida visible."""
    vista = pd.DataFrame(
        {
            "Enlace": [
                nombre_enlace(origen, destino)
                for origen, destino in zip(enlaces["Origen"], enlaces["Destino"])
            ],
            "Retardo_ms": enlaces["Retardo_ms"].to_numpy(),
            "Banda_Mbps": enlaces["Banda_Mbps"].to_numpy(),
            "Pérdida_%": (
                enlaces["Pérdida_%"].to_numpy()
                if "Pérdida_%" in enlaces.columns
                else [0.0] * len(enlaces)
            ),
            "Disponible": enlaces["Disponible"].to_numpy(),
        }
    )
    return vista


def tabla_enlaces_usuario_agregar(nombre: str) -> str:
    """Prefijo numérico legible para una ruta definida por el usuario."""
    return f"U{nombre}"




def datos_enlace(enlaces: pd.DataFrame, u: str, v: str) -> tuple[float, float, bool]:
    """Retardo, banda y disponibilidad del enlace {u, v}."""
    fila = enlaces[
        ((enlaces["Origen"] == u) & (enlaces["Destino"] == v))
        | ((enlaces["Origen"] == v) & (enlaces["Destino"] == u))
    ]
    if fila.empty:
        # Un enlace eliminado de la topología se trata como no disponible.
        return (0.0, 0.0, False)
    dato = fila.iloc[0]
    return (
        float(dato["Retardo_ms"]),
        float(dato["Banda_Mbps"]),
        bool(dato["Disponible"]),
    )


def generar_identificador_nodo() -> str:
    """Prefijo de dos letras que no está en NODOS base."""
    return "Y"


def validar_lista_nodos(nodos: Sequence[str]) -> tuple[bool, str]:
    """Devuelve (es_valida, motivo) para usar en Streamlit."""
    if not nodos:
        return False, "La lista está vacía."
    if len(nodos) != len(set(nodos)):
        return False, "Hay nodos repetidos."
    if nodos[0] != ORIGEN:
        return False, f"La ruta debe empezar por {ORIGEN}."
    if nodos[-1] != DESTINO:
        return False, f"La ruta debe terminar en {DESTINO}."
    if any(nota not in NODOS and nota not in NODOS_EXTENDIDOS for nota in nodos):
        return False, "Uno o varios routers no están en el grafo."
    return True, ""


def pares_ruta(ruta: Sequence[str]) -> list[tuple[str, str]]:
    """Pares consecutivos de una ruta."""
    return list(zip(ruta, ruta[1:]))


def formato_secuencia(ruta: Sequence[str]) -> str:
    """Ruta como H → D → A → B."""
    return " → ".join(ruta) if ruta else "—"


def _positivo(valor: object) -> float | None:
    """Convierte a float un valor finito y positivo; si no, devuelve None."""
    try:
        numero = float(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numero) or numero <= 0:
        return None
    return numero


def referencias(enlaces: pd.DataFrame) -> tuple[float, float]:
    """d_ref y b_ref: máximos positivos registrados en la tabla actual.

    Se consideran todas las filas, incluidas las de enlaces caídos, porque la
    escala de normalización depende de los datos registrados, no de la
    conectividad del momento.
    """
    retardos = [valor for valor in map(_positivo, enlaces["Retardo_ms"]) if valor]
    bandas = [valor for valor in map(_positivo, enlaces["Banda_Mbps"]) if valor]
    d_ref = max(retardos) if retardos else 1.0
    b_ref = max(bandas) if bandas else 1.0
    return float(d_ref), float(b_ref)


# ---------------------------------------------------------------------------
# Pesos y funciones objetivo
# ---------------------------------------------------------------------------


def normalizar_pesos(
    alpha: float, beta: float, gamma: float
) -> tuple[float, float, float] | None:
    """Normaliza los pesos para que sumen 1.

    Devuelve None si la suma no es estrictamente positiva.
    """
    total = float(alpha) + float(beta) + float(gamma)
    if not math.isfinite(total) or total <= 0:
        return None
    return (float(alpha) / total, float(beta) / total, float(gamma) / total)


def peso_objetivo(
    objetivo: str,
    retardo: float,
    banda: float,
    d_ref: float,
    b_ref: float,
    pesos: tuple[float, float, float],
) -> float:
    """Costo w_ij de una arista según la función objetivo activa.

    - saltos: h_ij = 1
    - retardo: d_ij
    - multicriterio: α + β·(d_ij/d_ref) + γ·(b_ref/b_ij)
    """
    if objetivo == "saltos":
        return 1.0
    if objetivo == "retardo":
        return max(float(retardo), 0.0)
    if objetivo != "multicriterio":
        raise ValueError(f"Objetivo desconocido: {objetivo!r}")
    alpha, beta, gamma = pesos
    if d_ref <= 0 or b_ref <= 0:
        raise ValueError("d_ref y b_ref deben ser positivos")
    return (
        alpha
        + beta * max(float(retardo), 0.0) / d_ref
        + gamma * b_ref / max(float(banda), 1e-9)
    )


def costo_objetivo_secuencia(
    enlaces: pd.DataFrame,
    ruta: Sequence[str],
    objetivo: str,
    pesos: tuple[float, float, float],
    **restricciones: object,
) -> float | None:
    """Costo C(P) si la ruta satisface las restricciones simples.

    ``restricciones`` puede incluir:

    - ``banda_minima_mbps``: el ancho de banda del camino no puede ser menor
      que este valor.
    - ``retardo_maximo_ms``: el retardo acumulado no puede ser mayor que este
      valor.
    - ``perdida_maxima_porcentaje``: porcentaje máximo de pérdida de paquetes
      aceptable en el camino.

    Si alguna restricción no se cumple, devuelve ``None``.
    """
    metricas = metricas_ruta(enlaces, ruta, pesos)
    disponibles = {k: v for k, v in restricciones.items() if v is not None}
    if "banda_minima_mbps" in disponibles:
        umbral = float(disponibles["banda_minima_mbps"])
        if float(metricas["banda_mbps"]) < umbral:
            return None
    if "retardo_maximo_ms" in disponibles:
        umbral = float(disponibles["retardo_maximo_ms"])
        if float(metricas["retardo_ms"]) > umbral:
            return None
    if "perdida_maxima_porcentaje" in disponibles:
        umbral = float(disponibles["perdida_maxima_porcentaje"])
        if float(metricas["perdida_porcentaje_o_estimacion"] if "perdida_porcentaje_o_estimacion" in metricas else 0.0) > umbral:
            return None
    return float(metricas["costo_c"])


def ruta_cumple_restricciones(
    enlaces: pd.DataFrame,
    ruta: Sequence[str],
    restricciones: dict[str, object],
    pesos: tuple[float, float, float] = PESOS_BASE,
) -> tuple[bool, list[str]]:
    """Devuelve (cumple, motivos) para la ruta indicada."""
    metricas = metricas_ruta(enlaces, ruta, pesos)
    motivos: list[str] = []

    if restricciones.get("banda_minima_mbps") is not None:
        umbral = float(restricciones["banda_minima_mbps"])
        if float(metricas["banda_mbps"]) < umbral:
            motivos.append(
                f"banda mínima {umbral:g} Mbps no se alcanza "
                f"({float(metricas['banda_mbps']):g} Mbps)"
            )

    if restricciones.get("retardo_maximo_ms") is not None:
        umbral = float(restricciones["retardo_maximo_ms"])
        if float(metricas["retardo_ms"]) > umbral:
            motivos.append(
                f"retardo máximo {umbral:g} ms superado "
                f"({float(metricas['retardo_ms']):g} ms)"
            )

    if restricciones.get("perdida_maxima_porcentaje") is not None:
        umbral = float(restricciones["perdida_maxima_porcentaje"])
        perdida = float(metricas["perdida_porcentaje"])
        if perdida > umbral:
            motivos.append(
                f"pérdida máxima {umbral:g}% superada "
                f"({perdida:g}% estimado)"
            )

    return not motivos, motivos


# ---------------------------------------------------------------------------
# Grafo y rutas
# ---------------------------------------------------------------------------


def construir_grafo(
    enlaces: pd.DataFrame,
    objetivo: str = "saltos",
    pesos: tuple[float, float, float] = PESOS_BASE,
) -> nx.Graph:
    """Construye G=(V,E) usando solo enlaces disponibles.

    El atributo ``peso`` de cada arista es w_ij para el objetivo activo, de
    modo que Dijkstra pueda minimizarlo directamente.
    """
    if objetivo not in OBJETIVOS:
        raise ValueError(f"Objetivo desconocido: {objetivo!r}")

    d_ref, b_ref = referencias(enlaces)
    grafo = nx.Graph()
    grafo.add_nodes_from(NODOS)

    for _, fila in enlaces.iterrows():
        if not bool(fila["Disponible"]):
            continue
        retardo = max(float(fila["Retardo_ms"]), 0.0)
        banda = float(fila["Banda_Mbps"])
        if banda <= 0 or not math.isfinite(banda):
            continue
        grafo.add_edge(
            str(fila["Origen"]),
            str(fila["Destino"]),
            retardo=retardo,
            banda=banda,
            peso=peso_objetivo(objetivo, retardo, banda, d_ref, b_ref, pesos),
        )

    grafo.graph.update(d_ref=d_ref, b_ref=b_ref, objetivo=objetivo)
    return grafo


def enlaces_en_ruta(
    enlaces: pd.DataFrame | Sequence[tuple[str, str, str, float, float]],
    u: str,
    v: str,
) -> bool:
    """True si el enlace no dirigido {u, v} está presente en la tabla."""
    if isinstance(enlaces, Sequence):
        enlaces = m.tabla_enlaces_base()
    return bool(
        ((enlaces["Origen"] == u) & (enlaces["Destino"] == v))
        | ((enlaces["Origen"] == v) & (enlaces["Destino"] == u))
    ).any()


def ruta_disponible(enlaces: pd.DataFrame, ruta: Sequence[str]) -> bool:
    """True si todos los enlaces de la ruta están activos."""
    if len(ruta) < 2:
        return False
    return all(datos_enlace(enlaces, u, v)[2] for u, v in pares_ruta(ruta))


def primera_ruta_disponible(enlaces: pd.DataFrame) -> str | None:
    """Primera ruta estática disponible según la prioridad del artículo."""
    for nombre, ruta in RUTAS_ESTATICAS.items():
        if ruta_disponible(enlaces, ruta):
            return nombre
    return None


def costo_ruta(
    enlaces: pd.DataFrame,
    ruta: Sequence[str],
    objetivo: str,
    pesos: tuple[float, float, float],
) -> float:
    """Costo total de una ruta con la función objetivo indicada."""
    if len(ruta) < 2:
        return 0.0
    d_ref, b_ref = referencias(enlaces)
    total = 0.0
    for u, v in pares_ruta(ruta):
        retardo, banda, _ = datos_enlace(enlaces, u, v)
        total += peso_objetivo(objetivo, retardo, banda, d_ref, b_ref, pesos)
    return total


def metricas_ruta(
    enlaces: pd.DataFrame,
    ruta: Sequence[str],
    pesos: tuple[float, float, float] = PESOS_BASE,
    perdida_por_enlace: dict[tuple[str, str], float] | None = None,
) -> dict[str, float | int | bool]:
    """H(P), D(P), B(P), C(P), pérdida estimada y disponibilidad de una ruta.

    C(P) se evalúa siempre con la fórmula multicriterio, incluso si el
    objetivo activo es otro, para poder comparar todas las rutas.

    Si ``perdida_por_enlace`` se proporciona, la clave ``perdida_porcentaje``
    guarda el porcentaje de pérdida estimado como el máximo por enlace del
    camino.
    """
    if len(ruta) < 2:
        return {
            "saltos": 0,
            "retardo_ms": 0.0,
            "banda_mbps": 0.0,
            "costo_c": 0.0,
            "perdida_porcentaje": 0.0,
            "disponible": False,
        }

    retardos: list[float] = []
    bandas: list[float] = []
    perdidas: list[float] = []
    disponible = True
    perdida_por_enlace = perdida_por_enlace or {}
    for u, v in pares_ruta(ruta):
        retardo, banda, activo = datos_enlace(enlaces, u, v)
        retardos.append(retardo)
        bandas.append(banda)
        disponible = disponible and activo
        perdidas.append(
            float(
                perdida_por_enlace.get((u, v))
                or perdida_por_enlace.get((v, u))
                or 0.0
            )
        )

    max_perdida = max(perdidas) if perdidas else 0.0

    return {
        "saltos": len(ruta) - 1,
        "retardo_ms": float(sum(retardos)),
        "banda_mbps": float(min(bandas)),
        "costo_c": float(
            costo_ruta(enlaces, ruta, "multicriterio", pesos)
        ),
        "perdida_porcentaje": float(max_perdida),
        "disponible": disponible,
    }


def metadatos_ruta(
    enlaces: pd.DataFrame,
    ruta: Sequence[str],
) -> dict[str, object]:
    """Metadatos básicos de una ruta para el editor."""
    saltos = len(ruta) - 1 if len(ruta) >= 2 else 0
    disponibles = []
    for u, v in pares_ruta(ruta):
        _, _, activo = datos_enlace(enlaces, u, v)
        disponibles.append(activo)
    todos_disponibles = all(disponibles) if disponibles else False
    return {
        "saltos": saltos,
        "disponible": todos_disponibles,
        "enlaces_activos": int(sum(disponibles)),
        "enlaces_totales": len(disponibles),
    }


def ruta_optima(
    enlaces: pd.DataFrame,
    objetivo: str,
    pesos: tuple[float, float, float] = PESOS_BASE,
) -> tuple[list[str], float]:
    """Ruta H→B que minimiza la función objetivo. ([], inf) si no existe."""
    grafo = construir_grafo(enlaces, objetivo, pesos)
    if not nx.has_path(grafo, ORIGEN, DESTINO):
        return [], math.inf
    ruta = nx.dijkstra_path(grafo, ORIGEN, DESTINO, weight="peso")
    costo = nx.dijkstra_path_length(grafo, ORIGEN, DESTINO, weight="peso")
    return list(ruta), float(costo)


def ruta_optima_desde(
    enlaces: pd.DataFrame,
    origen: str,
    destino: str,
    objetivo: str,
    pesos: tuple[float, float, float] = PESOS_BASE,
) -> tuple[list[str], float]:
    """Ruta origen→destino que minimiza la función objetivo.

    Devuelve ([], inf) si no existe camino entre esos dos routers.
    """
    grafo = construir_grafo(enlaces, objetivo, pesos)
    if origen not in grafo or destino not in grafo:
        return [], math.inf
    if not nx.has_path(grafo, origen, destino):
        return [], math.inf
    ruta = nx.dijkstra_path(grafo, origen, destino, weight="peso")
    costo = nx.dijkstra_path_length(grafo, origen, destino, weight="peso")
    return list(ruta), float(costo)


def sink_tree(
    enlaces: pd.DataFrame,
    objetivo: str,
    pesos: tuple[float, float, float] = PESOS_BASE,
) -> tuple[dict[str, str], dict[str, float], dict[str, list[str]]]:
    """Árbol de siguientes saltos hacia B.

    Devuelve (π, d, caminos):
    - π[v]: siguiente salto desde v hacia B.
    - d[v]: costo acumulado desde v hasta B.
    - caminos[v]: ruta completa v→B (en ese orden).

    Se calcula con un único Dijkstra desde el sumidero sobre G no dirigido.
    """
    grafo = construir_grafo(enlaces, objetivo, pesos)
    distancias, caminos_desde_b = nx.single_source_dijkstra(
        grafo, DESTINO, weight="peso"
    )

    siguiente: dict[str, str] = {}
    caminos: dict[str, list[str]] = {}
    for nodo, camino in caminos_desde_b.items():
        caminos[nodo] = list(reversed(camino))
        if nodo != DESTINO and len(camino) >= 2:
            siguiente[nodo] = camino[-2]

    return siguiente, dict(distancias), caminos


def sink_tree_desde(
    enlaces: pd.DataFrame,
    origen: str,
    destino: str,
    objetivo: str,
    pesos: tuple[float, float, float] = PESOS_BASE,
) -> tuple[dict[str, str], dict[str, float], dict[str, list[str]]]:
    """Árbol de siguientes saltos hacia un destino arbitrario.

    Si el grafo no contiene el destino o no hay camino desde ese destino, se
    devuelve un árbol vacío.
    """
    grafo = construir_grafo(enlaces, objetivo, pesos)
    if destino not in grafo:
        return {}, {}, {}
    distancias, caminos_desde_destino = nx.single_source_dijkstra(
        grafo, destino, weight="peso"
    )
    siguiente: dict[str, str] = {}
    caminos: dict[str, list[str]] = {}
    for nodo, camino in caminos_desde_destino.items():
        caminos[nodo] = list(reversed(camino))
        if nodo != destino and len(camino) >= 2:
            siguiente[nodo] = camino[-2]
    return siguiente, dict(distancias), caminos


def empates_sink_tree(
    enlaces: pd.DataFrame,
    objetivo: str,
    pesos: tuple[float, float, float] = PESOS_BASE,
) -> dict[str, list[str]]:
    """Nodos con más de un siguiente salto igualmente óptimo.

    Sirve para explicar que un sink tree no siempre es único: si dos vecinos
    ofrecen el mismo costo total, cualquier elección produce un árbol válido.
    """
    grafo = construir_grafo(enlaces, objetivo, pesos)
    distancias, _ = nx.single_source_dijkstra(grafo, DESTINO, weight="peso")
    empates: dict[str, list[str]] = {}
    for nodo in grafo.nodes():
        if nodo == DESTINO or nodo not in distancias:
            continue
        candidatos = []
        for vecino in grafo.neighbors(nodo):
            if vecino not in distancias:
                continue
            costo = distancias[vecino] + grafo[nodo][vecino]["peso"]
            if math.isclose(costo, distancias[nodo], rel_tol=1e-9, abs_tol=1e-9):
                candidatos.append(vecino)
        if len(candidatos) > 1:
            empates[nodo] = sorted(candidatos)
    return empates


def tabla_sink_tree(
    siguiente: dict[str, str],
    distancias: dict[str, float],
    caminos: dict[str, list[str]],
    nodos: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Tabla de siguientes saltos ordenada por cercanía al destino.

    ``nodos`` permite incluir routers añadidos dinámicamente; si se omite, se
    usan los del artículo más los que aparezcan en los caminos calculados.
    """
    if nodos is None:
        extras = sorted(nodo for nodo in caminos if nodo not in NODOS)
        nodos_referencia = list(NODOS) + extras
    else:
        nodos_referencia = list(dict.fromkeys(nodos))
    if DESTINO not in nodos_referencia:
        nodos_referencia.append(DESTINO)

    alcanzables = [
        nodo for nodo in nodos_referencia
        if nodo == DESTINO or nodo in siguiente
    ]
    alcanzables.sort(
        key=lambda nodo: (distancias.get(nodo, math.inf), nodos_referencia.index(nodo))
    )

    filas: list[dict[str, object]] = []
    for nodo in alcanzables:
        if nodo == DESTINO:
            filas.append(
                {
                    "Nodo": nodo,
                    "Siguiente salto": "— (destino)",
                    "Costo acumulado": 0.0,
                    "Ruta hacia B": DESTINO,
                }
            )
        else:
            filas.append(
                {
                    "Nodo": nodo,
                    "Siguiente salto": siguiente[nodo],
                    "Costo acumulado": round(distancias[nodo], 3),
                    "Ruta hacia B": formato_secuencia(caminos[nodo]),
                }
            )

    for nodo in nodos_referencia:
        if nodo not in alcanzables:
            filas.append(
                {
                    "Nodo": nodo,
                    "Siguiente salto": "sin ruta",
                    "Costo acumulado": None,
                    "Ruta hacia B": "—",
                }
            )

    return pd.DataFrame(
        filas,
        columns=["Nodo", "Siguiente salto", "Costo acumulado", "Ruta hacia B"],
    )


def tabla_sink_tree_desde(
    siguiente: dict[str, str],
    distancias: dict[str, float],
    caminos: dict[str, list[str]],
    origen: str,
    destino: str,
    nodos: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Tabla de siguientes saltos hacia un destino arbitrario."""
    if nodos is None:
        extras = sorted(nodo for nodo in caminos if nodo not in NODOS)
        nodos_referencia = list(NODOS) + extras
    else:
        nodos_referencia = list(dict.fromkeys(nodos))
    if destino not in nodos_referencia:
        nodos_referencia.append(destino)

    alcanzables = [
        nodo for nodo in nodos_referencia
        if nodo == destino or nodo in siguiente
    ]
    alcanzables.sort(
        key=lambda nodo: (distancias.get(nodo, math.inf), nodos_referencia.index(nodo))
    )

    filas: list[dict[str, object]] = []
    for nodo in alcanzables:
        if nodo == destino:
            filas.append(
                {
                    "Nodo": nodo,
                    "Siguiente salto": "— (destino)",
                    "Costo acumulado": 0.0,
                    "Ruta hacia destino": destino,
                }
            )
        else:
            filas.append(
                {
                    "Nodo": nodo,
                    "Siguiente salto": siguiente[nodo],
                    "Costo acumulado": round(distancias[nodo], 3),
                    "Ruta hacia destino": formato_secuencia(caminos[nodo]),
                }
            )

    for nodo in nodos_referencia:
        if nodo not in alcanzables:
            filas.append(
                {
                    "Nodo": nodo,
                    "Siguiente salto": "sin ruta",
                    "Costo acumulado": None,
                    "Ruta hacia destino": "—",
                }
            )

    columnas = [
        "Nodo",
        "Siguiente salto",
        "Costo acumulado",
        "Ruta hacia destino",
    ]
    return pd.DataFrame(filas, columns=columnas)


def tabla_comparacion(
    enlaces: pd.DataFrame,
    objetivo: str,
    pesos: tuple[float, float, float] = PESOS_BASE,
    restricciones: dict[str, object] | None = None,
    rutas_usuario: list[tuple[str, list[str]]] | None = None,
    columna_perdida: bool = True,
    columna_restricciones: bool = True,
) -> pd.DataFrame:
    """Compara las tres rutas estáticas y las rutas del usuario con la óptima.

    Si ``restricciones`` se proporciona, también informa cuáles rutas las
    cumplen.
    """
    restricciones = restricciones or {}
    primera = primera_ruta_disponible(enlaces)
    filas: list[dict[str, object]] = []

    rutas_usuario = rutas_usuario or getattr(
        getattr(enlaces, "_app_ctx", None), "rutas_usuario", None
    )

    for nombre, ruta in RUTAS_ESTATICAS.items():
        disponible = ruta_disponible(enlaces, ruta)
        metricas = metricas_ruta(enlaces, ruta, pesos)
        if not disponible:
            estado = "✖ enlace caído"
        elif nombre == primera:
            estado = "✔ primera disponible"
        else:
            estado = "○ respaldo disponible"
        fila: dict[str, object] = {
            "Tipo": "artículo",
            "Ruta": nombre,
            "Estado": estado,
            "Secuencia": formato_secuencia(ruta),
            "Saltos": metricas["saltos"],
            "Retardo (ms)": round(float(metricas["retardo_ms"]), 3),
            "Banda (Mbps)": round(float(metricas["banda_mbps"]), 3),
            "C(P)": round(float(metricas["costo_c"]), 4),
        }
        if columna_perdida:
            fila["Pérdida (%)"] = round(float(metricas["perdida_porcentaje"]), 2)
        filas.append(fila)

    if rutas_usuario:
        for nombre, ruta_usuario in rutas_usuario:
            disponible = ruta_disponible(enlaces, ruta_usuario)
            metricas = metricas_ruta(enlaces, ruta_usuario, pesos)
            if not disponible:
                estado = "✖ enlace caído"
            else:
                estado = "✔ definida por el usuario"
            fila = {
                "Tipo": "usuario",
                "Ruta": nombre,
                "Estado": estado,
                "Secuencia": formato_secuencia(ruta_usuario),
                "Saltos": metricas["saltos"],
                "Retardo (ms)": round(float(metricas["retardo_ms"]), 3),
                "Banda (Mbps)": round(float(metricas["banda_mbps"]), 3),
                "C(P)": round(float(metricas["costo_c"]), 4),
            }
            if columna_perdida:
                fila["Pérdida (%)"] = round(float(metricas["perdida_porcentaje"]), 2)
            filas.append(fila)

    ruta_opt, _ = ruta_optima(enlaces, objetivo, pesos)
    if ruta_opt:
        metricas = metricas_ruta(enlaces, ruta_opt, pesos)
        fila = {
            "Tipo": "óptima",
            "Ruta": "Óptima (Dijkstra)",
            "Estado": "★ ruta óptima",
            "Secuencia": formato_secuencia(ruta_opt),
            "Saltos": metricas["saltos"],
            "Retardo (ms)": round(float(metricas["retardo_ms"]), 3),
            "Banda (Mbps)": round(float(metricas["banda_mbps"]), 3),
            "C(P)": round(float(metricas["costo_c"]), 4),
        }
        if columna_perdida:
            fila["Pérdida (%)"] = round(float(metricas["perdida_porcentaje"]), 2)
        filas.append(fila)
    else:
        fila = {
            "Tipo": "óptima",
            "Ruta": "Óptima (Dijkstra)",
            "Estado": "sin ruta",
            "Secuencia": "—",
            "Saltos": None,
            "Retardo (ms)": None,
            "Banda (Mbps)": None,
            "C(P)": None,
        }
        if columna_perdida:
            fila["Pérdida (%)"] = None
        filas.append(fila)

    columnas = [
        "Tipo",
        "Ruta",
        "Estado",
        "Secuencia",
        "Saltos",
        "Retardo (ms)",
        "Banda (Mbps)",
        "C(P)",
    ]
    if columna_perdida:
        columnas.append("Pérdida (%)")

    if columna_restricciones and restricciones:
        columna_cumple: list[object] = []
        for fila in filas:
            secuencia = fila["Secuencia"]
            if secuencia in ("—",):
                columna_cumple.append(None)
                continue
            cumple, _motivos = ruta_cumple_restricciones(
                enlaces,
                [n for n in secuencia.split(" → ")],
                restricciones,
                pesos,
            )
            columna_cumple.append("✔" if cumple else "✖")
        columnas.append("Cumple restricciones")
        for fila, cumple in zip(filas, columna_cumple):
            fila["Cumple restricciones"] = cumple

    return pd.DataFrame(filas, columns=columnas)


def desglose_ruta(
    enlaces: pd.DataFrame,
    ruta: Sequence[str],
    objetivo: str,
    pesos: tuple[float, float, float] = PESOS_BASE,
) -> pd.DataFrame:
    """Costo contribuido por cada enlace de la ruta, con acumulado."""
    d_ref, b_ref = referencias(enlaces)
    acumulado = 0.0
    filas: list[dict[str, object]] = []
    for u, v in pares_ruta(ruta):
        retardo, banda, _ = datos_enlace(enlaces, u, v)
        peso = peso_objetivo(objetivo, retardo, banda, d_ref, b_ref, pesos)
        acumulado += peso
        filas.append(
            {
                "Enlace": nombre_enlace(u, v),
                "d_ij (ms)": round(retardo, 3),
                "b_ij (Mbps)": round(banda, 3),
                "w_ij": round(peso, 4),
                "Acumulado": round(acumulado, 4),
            }
        )
    return pd.DataFrame(
        filas,
        columns=["Enlace", "d_ij (ms)", "b_ij (Mbps)", "w_ij", "Acumulado"],
    )
