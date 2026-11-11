"""Laboratorio interactivo: optimalidad, rutas mínimas y Sink Tree.

Ejecutar con:
    python -m streamlit run app.py
"""

from __future__ import annotations

import contextlib
import io
import math
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import model as m
import sink_tree_demo

st.set_page_config(
    page_title="Sink Tree · Optimalidad",
    page_icon="🌐",
    layout="wide",)

ETIQUETAS_OBJETIVO: dict[str, str] = {
    "saltos": "Saltos mínimos (Johal)",
    "retardo": "Retardo mínimo",
    "multicriterio": "Multicriterio normalizado",
}


POSICIONES_BALANCEADAS: dict[str, tuple[float, float]] = {
    "H": (0.0, 0.0),
    "D": (1.4, 1.4),
    "A": (2.8, 1.4),
    "B": (4.2, 0.0),
    "E": (1.4, -1.2),
    "J": (2.8, -1.2),
    "C": (3.7, -0.4),
    "O": (0.0, -1.7),
    "N": (1.4, -2.6),
    "P": (0.35, 2.4),
    "R": (2.1, 2.4),
    "S": (4.2, 2.4),
    "T": (5.6, 1.4),
    "Q": (4.6, -1.8),
    "U": (5.7, -1.2),
}


# ---------------------------------------------------------------------------
# Estado inicial editables (se trasladan a st.session_state en la app)
# ---------------------------------------------------------------------------

ROUTERS_EDITABLES: list[str] = list(POSICIONES_BALANCEADAS.keys())

ENLACES_EDITABLES_INICIALES: list[dict[str, object]] = [
    {"Origen": "H", "Destino": "D", "Retardo_ms": 8.0, "Banda_Mbps": 100.0, "Pérdida_%": 0.0, "Disponible": True},
    {"Origen": "D", "Destino": "A", "Retardo_ms": 9.0, "Banda_Mbps": 100.0, "Pérdida_%": 0.0, "Disponible": True},
    {"Origen": "A", "Destino": "B", "Retardo_ms": 7.0, "Banda_Mbps": 100.0, "Pérdida_%": 0.0, "Disponible": True},
    {"Origen": "H", "Destino": "E", "Retardo_ms": 5.0, "Banda_Mbps": 50.0, "Pérdida_%": 0.0, "Disponible": True},
    {"Origen": "E", "Destino": "J", "Retardo_ms": 10.0, "Banda_Mbps": 50.0, "Pérdida_%": 0.0, "Disponible": True},
    {"Origen": "J", "Destino": "C", "Retardo_ms": 8.0, "Banda_Mbps": 100.0, "Pérdida_%": 0.0, "Disponible": True},
    {"Origen": "C", "Destino": "B", "Retardo_ms": 6.0, "Banda_Mbps": 100.0, "Pérdida_%": 0.0, "Disponible": True},
    {"Origen": "H", "Destino": "O", "Retardo_ms": 7.0, "Banda_Mbps": 50.0, "Pérdida_%": 0.0, "Disponible": True},
    {"Origen": "O", "Destino": "N", "Retardo_ms": 9.0, "Banda_Mbps": 100.0, "Pérdida_%": 0.0, "Disponible": True},
    {"Origen": "N", "Destino": "J", "Retardo_ms": 9.0, "Banda_Mbps": 100.0, "Pérdida_%": 0.0, "Disponible": True},
]


RUTAS_EDITABLES_INICIALES: list[dict[str, object]] = [
    {"Nombre": "PSRC", "Nodos": ("H", "D", "A", "B")},
    {"Nombre": "SSRC", "Nodos": ("H", "E", "J", "C", "B")},
    {"Nombre": "TSRC", "Nodos": ("H", "O", "N", "J", "C", "B")},
]




def _leer_texto(ruta: Path) -> str:
    """Lee un archivo de apoyo sin romper la app si falta."""
    return ruta.read_text(encoding="utf-8") if ruta.exists() else ""


RUTA_BASE = Path(__file__).resolve().parent
RUTA_GUIA = RUTA_BASE / "GUIA_SINK_TREE.md"
RUTA_DEMO = RUTA_BASE / "sink_tree_demo.py"

GUIA_TEXTO = _leer_texto(RUTA_GUIA)
DEMO_TEXTO = _leer_texto(RUTA_DEMO)

# Escenarios de los seis experimentos obligatorios del laboratorio.
ESCENARIOS: dict[str, dict[str, object]] = {
    "A · Réplica original (saltos)": {"objetivo": "saltos"},
    "B · H–D = 40 ms (retardo)": {
        "objetivo": "retardo",
        "retardos": {("H", "D"): 40.0},
    },
    "C · Fallo de H–D (saltos)": {
        "objetivo": "saltos",
        "caidos": [("H", "D")],
    },
    "D · Doble fallo H–D y H–E (saltos)": {
        "objetivo": "saltos",
        "caidos": [("H", "D"), ("H", "E")],
    },
    "E · Cuello de botella E–J = 5 Mbps": {
        "objetivo": "saltos",
        "bandas": {("E", "J"): 5.0},
    },
    "F · Multicriterio (0.5, 0.35, 0.15)": {
        "objetivo": "multicriterio",
        "pesos": (0.5, 0.35, 0.15),
    },
}

COLOR_ARISTA = "#94a3b8"
COLOR_ARISTA_TENUE = "#cbd5e1"
COLOR_CAIDA = "#ef4444"
COLOR_OPTIMA = "#f59e0b"
COLOR_ESTATICA = "#2563eb"
COLOR_ARBOL = "#0d9488"
COLOR_TEXTO = "#0f172a"


# ---------------------------------------------------------------------------
# Estado, escenarios y utilidades
# ---------------------------------------------------------------------------

NODOS_BASE: tuple[str, ...] = tuple(m.NODOS)
POSICIONES_INICIALES: dict[str, tuple[float, float]] = {
    nodo: POSICIONES_BALANCEADAS.get(nodo, (0.0, 0.0)) for nodo in NODOS_BASE
}


def _bump_editor() -> None:
    st.session_state.editor_version = int(
        st.session_state.get("editor_version", 0)
    ) + 1


def _routers_extra() -> list[str]:
    return list(st.session_state.get("routers_extra", []))


def _nodos_actuales() -> list[str]:
    extra = [nodo for nodo in _routers_extra() if nodo not in NODOS_BASE]
    return list(NODOS_BASE) + extra


def _posicion_libre(
    posiciones: dict[str, tuple[float, float]], nodo: str
) -> tuple[float, float]:
    """Posición determinista en espiral para routers creados por el usuario."""
    if nodo in POSICIONES_BALANCEADAS:
        return POSICIONES_BALANCEADAS[nodo]
    xs = [posicion[0] for posicion in posiciones.values()] or [0.0]
    ys = [posicion[1] for posicion in posiciones.values()] or [0.0]
    centro_x = (min(xs) + max(xs)) / 2
    centro_y = (min(ys) + max(ys)) / 2
    indice = len(posiciones)
    angulo = 2.399963229728653 * indice  # espiral áurea
    radio = 2.4 + 0.55 * (indice ** 0.5)
    return (
        centro_x + radio * math.cos(angulo),
        centro_y + radio * math.sin(angulo),
    )


def _posiciones() -> dict[str, tuple[float, float]]:
    posiciones = st.session_state.get("posiciones")
    if not posiciones:
        posiciones = dict(POSICIONES_INICIALES)
        st.session_state.posiciones = posiciones
    for nodo in _nodos_actuales():
        if nodo not in posiciones:
            posiciones[nodo] = _posicion_libre(posiciones, nodo)
    return posiciones


def _agregar_routers(prefijo: str, cantidad: int) -> list[str]:
    """Crea ``cantidad`` routers con nombres tipo R1, R2, ..."""
    base = "".join(
        caracter
        for caracter in (prefijo or "R").strip()
        if caracter.isalnum() or caracter == "_"
    ) or "R"
    usados = set(_nodos_actuales())
    extra = _routers_extra()
    posiciones = dict(_posiciones())
    nuevos: list[str] = []
    numero = 1
    while len(nuevos) < cantidad:
        nombre = f"{base}{numero}"
        numero += 1
        if nombre in usados or nombre in (m.ORIGEN, m.DESTINO):
            continue
        usados.add(nombre)
        extra.append(nombre)
        nuevos.append(nombre)
        posiciones[nombre] = _posicion_libre(posiciones, nombre)
    st.session_state.routers_extra = extra
    st.session_state.posiciones = posiciones
    _bump_editor()
    return nuevos


def _quitar_router(nombre: str) -> bool:
    if nombre in NODOS_BASE:
        return False
    enlaces = st.session_state.enlaces
    mascara = (enlaces["Origen"] == nombre) | (enlaces["Destino"] == nombre)
    st.session_state.enlaces = enlaces.loc[~mascara].reset_index(drop=True)
    st.session_state.routers_extra = [
        nodo for nodo in _routers_extra() if nodo != nombre
    ]
    st.session_state.posiciones.pop(nombre, None)
    if st.session_state.get("origen_router") == nombre:
        st.session_state.origen_pendiente = m.ORIGEN
    _bump_editor()
    return True


def _crear_enlace(
    origen: str,
    destino: str,
    retardo_ms: float,
    banda_mbps: float,
    perdida: float,
    disponible: bool,
) -> str:
    """Crea un enlace nuevo; devuelve un mensaje de error o cadena vacía."""
    if origen == destino:
        return "El origen y el destino deben ser routers distintos."
    enlaces = st.session_state.enlaces
    existe = (
        ((enlaces["Origen"] == origen) & (enlaces["Destino"] == destino))
        | ((enlaces["Origen"] == destino) & (enlaces["Destino"] == origen))
    ).any()
    if existe:
        return f"El enlace {origen}–{destino} ya existe; edítalo en la tabla."
    nuevo = m.agregar_enlace(
        enlaces, origen, destino, retardo_ms, banda_mbps, disponible
    )
    nuevo.loc[nuevo.index[-1], "Pérdida_%"] = perdida
    st.session_state.enlaces = nuevo
    _bump_editor()
    return ""


def _eliminar_enlace(origen: str, destino: str) -> None:
    st.session_state.enlaces = m.quitar_enlace(
        st.session_state.enlaces, origen, destino
    )
    _bump_editor()


def _restablecer_topologia() -> None:
    st.session_state.enlaces = m.tabla_enlaces_base()
    st.session_state.routers_extra = []
    st.session_state.posiciones = dict(POSICIONES_INICIALES)
    st.session_state.origen_pendiente = m.ORIGEN
    _bump_editor()


def _ajustar_enlace(
    enlaces: pd.DataFrame, u: str, v: str, **cambios: object
) -> None:
    mascara = ((enlaces["Origen"] == u) & (enlaces["Destino"] == v)) | (
        (enlaces["Origen"] == v) & (enlaces["Destino"] == u)
    )
    for columna, valor in cambios.items():
        enlaces.loc[mascara, columna] = valor


def _aplicar_escenario(nombre: str) -> None:
    especificacion = ESCENARIOS[nombre]
    enlaces = m.tabla_enlaces_base()

    for (u, v), valor in especificacion.get("retardos", {}).items():  # type: ignore[union-attr]
        _ajustar_enlace(enlaces, u, v, Retardo_ms=valor)
    for (u, v), valor in especificacion.get("bandas", {}).items():  # type: ignore[union-attr]
        _ajustar_enlace(enlaces, u, v, Banda_Mbps=valor)
    for u, v in especificacion.get("caidos", []):  # type: ignore[union-attr]
        _ajustar_enlace(enlaces, u, v, Disponible=False)

    st.session_state.enlaces = enlaces
    st.session_state.routers_extra = []
    st.session_state.posiciones = dict(POSICIONES_INICIALES)
    st.session_state.origen_router = m.ORIGEN
    st.session_state.objetivo_label = ETIQUETAS_OBJETIVO[
        str(especificacion["objetivo"])
    ]
    pesos = especificacion.get("pesos", m.PESOS_BASE)
    st.session_state.alpha, st.session_state.beta, st.session_state.gamma = pesos
    st.session_state.editor_version = int(
        st.session_state.get("editor_version", 0)
    ) + 1


if "enlaces" not in st.session_state:
    st.session_state.enlaces = m.tabla_enlaces_base()
for _clave, _valor in {
    "editor_version": 0,
    "alpha": m.PESOS_BASE[0],
    "beta": m.PESOS_BASE[1],
    "gamma": m.PESOS_BASE[2],
    "objetivo_label": ETIQUETAS_OBJETIVO["saltos"],
    "escenario_selector": next(iter(ESCENARIOS)),
    "routers_extra": [],
    "posiciones": dict(POSICIONES_INICIALES),
    "origen_router": m.ORIGEN,
}.items():
    st.session_state.setdefault(_clave, _valor)

if "escenario_pendiente" in st.session_state:
    _aplicar_escenario(st.session_state.pop("escenario_pendiente"))


def _latex_objetivo(objetivo: str) -> str:
    if objetivo == "saltos":
        return r"\min_{P}\ H(P)=\sum_{(i,j)\in P} h_{ij},\qquad h_{ij}=1"
    if objetivo == "retardo":
        return r"\min_{P}\ D(P)=\sum_{(i,j)\in P} d_{ij}"
    return (
        r"\min_{P}\ C(P)=\sum_{(i,j)\in P}\left[\alpha+\beta\,\frac{d_{ij}}{d_{ref}}"
        r"+\gamma\,\frac{b_{ref}}{b_{ij}}\right],\qquad \alpha+\beta+\gamma=1"
    )


def _fmt_costo(valor: float, objetivo: str) -> str:
    if objetivo == "saltos":
        cantidad = int(round(valor))
        return f"{cantidad} salto" if cantidad == 1 else f"{cantidad} saltos"
    if objetivo == "retardo":
        return f"{valor:.1f} ms"
    return f"C={valor:.3f}"


def _ejecutar_demo() -> str:
    """Captura la salida de sink_tree_demo.main() para mostrarla en la app."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        sink_tree_demo.main()
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Figuras Plotly
# ---------------------------------------------------------------------------


def _segmentos(
    enlaces: pd.DataFrame, activos: bool
) -> tuple[list[float | None], list[float | None]]:
    xs: list[float | None] = []
    ys: list[float | None] = []
    posiciones = _posiciones()
    for _, fila in enlaces.iterrows():
        if bool(fila["Disponible"]) != activos:
            continue
        x1, y1 = posiciones.get(str(fila["Origen"]), (0.0, 0.0))
        x2, y2 = posiciones.get(str(fila["Destino"]), (0.0, 0.0))
        xs.extend([x1, x2, None])
        ys.extend([y1, y2, None])
    return xs, ys


def _base_figura(enlaces: pd.DataFrame, tenue: bool = False) -> go.Figure:
    figura = go.Figure()
    xs, ys = _segmentos(enlaces, activos=True)
    if xs:
        figura.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line=dict(
                    color=COLOR_ARISTA_TENUE if tenue else COLOR_ARISTA,
                    width=1.5 if tenue else 2.4,
                ),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    xs, ys = _segmentos(enlaces, activos=False)
    if xs:
        figura.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line=dict(color=COLOR_CAIDA, width=2.2, dash="dash"),
                opacity=0.8,
                hoverinfo="skip",
                showlegend=False,
            )
        )
    return figura


def _layout(figura: go.Figure) -> go.Figure:
    posiciones = _posiciones()
    xs = [posicion[0] for posicion in posiciones.values()] or [0.0]
    ys = [posicion[1] for posicion in posiciones.values()] or [0.0]
    figura.update_xaxes(
        visible=False,
        range=[min(xs) - 0.55, max(xs) + 0.55],
        fixedrange=True,
    )
    figura.update_yaxes(
        visible=False,
        range=[min(ys) - 0.6, max(ys) + 0.7],
        fixedrange=True,
        scaleanchor="x",
        scaleratio=1,
    )
    figura.update_layout(
        height=520,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        hoverlabel=dict(namelength=-1),
    )
    return figura


def _flecha(figura: go.Figure, u: str, v: str, color: str, ancho: int) -> None:
    posiciones = _posiciones()
    x1, y1 = posiciones.get(u, (0.0, 0.0))
    x2, y2 = posiciones.get(v, (0.0, 0.0))
    figura.add_annotation(
        x=x2,
        y=y2,
        ax=x1,
        ay=y1,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        showarrow=True,
        arrowhead=2,
        arrowsize=1.15,
        arrowwidth=ancho,
        arrowcolor=color,
        text="",
        standoff=25,
        startstandoff=25,
    )


def _etiqueta_enlace(
    figura: go.Figure, u: str, v: str, texto: str, color: str
) -> None:
    posiciones = _posiciones()
    x1, y1 = posiciones.get(u, (0.0, 0.0))
    x2, y2 = posiciones.get(v, (0.0, 0.0))
    dx, dy = x2 - x1, y2 - y1
    largo = (dx * dx + dy * dy) ** 0.5 or 1.0
    normal_x, normal_y = -dy / largo, dx / largo
    figura.add_annotation(
        x=(x1 + x2) / 2 + 0.09 * normal_x,
        y=(y1 + y2) / 2 + 0.09 * normal_y,
        text=texto,
        showarrow=False,
        font=dict(size=10, color=color),
        align="center",
    )


def _nodos(
    figura: go.Figure,
    distancias: dict[str, float] | None = None,
    siguiente: dict[str, str] | None = None,
    objetivo: str | None = None,
    origen: str = m.ORIGEN,
) -> None:
    nodos = _nodos_actuales()
    posiciones = _posiciones()
    relleno: list[str] = []
    borde: list[str] = []
    grosor: list[float] = []
    hover: list[str] = []

    for nodo in nodos:
        if distancias is not None and nodo not in distancias:
            relleno.append("#fee2e2")
            borde.append("#dc2626")
            grosor.append(2.5)
        elif nodo == m.DESTINO:
            relleno.append("#dcfce7")
            borde.append("#16a34a")
            grosor.append(3.0)
        elif nodo == origen:
            relleno.append("#dbeafe")
            borde.append("#2563eb")
            grosor.append(3.0)
        else:
            relleno.append("#f8fafc")
            borde.append("#64748b")
            grosor.append(1.6)

        if distancias is None:
            hover.append(f"Router {nodo}")
        elif nodo == m.DESTINO:
            hover.append(f"{m.DESTINO} · destino (sink)<br>Costo acumulado: 0")
        elif nodo in distancias:
            proximo = siguiente.get(nodo, "—") if siguiente else "—"
            hover.append(
                f"Router {nodo}<br>Siguiente salto: {proximo}"
                f"<br>Costo hasta B: {_fmt_costo(distancias[nodo], objetivo or 'saltos')}"
            )
        else:
            hover.append(f"Router {nodo}<br>Sin ruta hacia B")

    figura.add_trace(
        go.Scatter(
            x=[posiciones[nodo][0] for nodo in nodos],
            y=[posiciones[nodo][1] for nodo in nodos],
            mode="markers+text",
            text=nodos,
            customdata=nodos,
            textposition="middle center",
            textfont=dict(size=13, color=COLOR_TEXTO),
            marker=dict(
                size=48,
                color=relleno,
                line=dict(color=borde, width=grosor),
            ),
            hovertext=hover,
            hovertemplate="%{hovertext}<extra></extra>",
            showlegend=False,
        )
    )

    if distancias is not None:
        for nodo in nodos:
            if nodo in distancias:
                texto = _fmt_costo(distancias[nodo], objetivo or "saltos")
            else:
                texto = "sin ruta"
            desplazamiento = 0.33 if nodo == m.DESTINO else -0.3
            figura.add_annotation(
                x=posiciones[nodo][0],
                y=posiciones[nodo][1] + desplazamiento,
                text=texto,
                showarrow=False,
                font=dict(size=10, color="#64748b"),
            )


def _figura_red(
    enlaces: pd.DataFrame,
    ruta_optima: Sequence[str],
    ruta_estatica: Sequence[str] | None,
    origen: str = m.ORIGEN,
) -> go.Figure:
    figura = _base_figura(enlaces)
    posiciones = _posiciones()

    if ruta_estatica and len(ruta_estatica) >= 2:
        xs: list[float] = []
        ys: list[float] = []
        for u, v in m.pares_ruta(ruta_estatica):
            x1, y1 = posiciones.get(u, (0.0, 0.0))
            x2, y2 = posiciones.get(v, (0.0, 0.0))
            xs.extend([x1, x2, None])  # type: ignore[arg-type]
            ys.extend([y1, y2, None])  # type: ignore[arg-type]
        figura.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line=dict(color=COLOR_ESTATICA, width=3.2, dash="dot"),
                opacity=0.9,
                hoverinfo="skip",
                showlegend=False,
            )
        )

    if ruta_optima and len(ruta_optima) >= 2:
        for u, v in m.pares_ruta(ruta_optima):
            _flecha(figura, u, v, COLOR_OPTIMA, 5)
        for u, v in m.pares_ruta(ruta_optima):
            retardo, banda, _ = m.datos_enlace(enlaces, u, v)
            _etiqueta_enlace(
                figura,
                u,
                v,
                f"{retardo:g} ms · {banda:g} Mbps",
                "#b45309",
            )

    for _, fila in enlaces.iterrows():
        if bool(fila["Disponible"]):
            continue
        u, v = str(fila["Origen"]), str(fila["Destino"])
        _etiqueta_enlace(figura, u, v, "caído", COLOR_CAIDA)

    _nodos(figura, origen=origen)
    return _layout(figura)


def _figura_arbol(
    enlaces: pd.DataFrame,
    siguiente: dict[str, str],
    distancias: dict[str, float],
    objetivo: str,
    origen: str = m.ORIGEN,
) -> go.Figure:
    figura = _base_figura(enlaces, tenue=True)

    for nodo, proximo in siguiente.items():
        _flecha(figura, nodo, proximo, COLOR_ARBOL, 4)

    _nodos(
        figura,
        distancias=distancias,
        siguiente=siguiente,
        objetivo=objetivo,
        origen=origen,
    )
    return _layout(figura)


# ---------------------------------------------------------------------------
# Sección: editor de topología
# ---------------------------------------------------------------------------


def _tabla_enlaces_a_dict_lista(
    tabla: pd.DataFrame,
) -> list[dict[str, object]]:
    """Convierte la tabla de enlaces en una lista de diccionarios planos."""
    return tabla.to_dict(orient="records")


def _dict_lista_a_tabla_enlaces(
    registros: list[dict[str, object]],
) -> pd.DataFrame:
    """Construye una tabla de enlaces desde una lista de diccionarios."""
    if not registros:
        return m.tabla_enlaces_vacia()
    df = pd.DataFrame(registros)
    if "Pérdida_%" not in df.columns:
        df["Pérdida_%"] = 0.0
    if "Disponible" not in df.columns:
        df["Disponible"] = True
    return df[["Origen", "Destino", "Retardo_ms", "Banda_Mbps", "Pérdida_%", "Disponible"]]


def _formatear_error_enlace(mensaje: str) -> str:
    """Devuelve un mensaje legible para errores de edición de enlaces."""
    return f"No se pudo actualizar el enlace: {mensaje}"


def _agregar_enlace_desde_datos(
    enlaces: pd.DataFrame,
    origen: str,
    destino: str,
    retardo_ms: float,
    banda_mbps: float,
    perdida_porcentaje: float,
    disponible: bool,
) -> pd.DataFrame:
    """Devuelve una nueva tabla con el enlace creado o actualizado."""
    return m.crear_o_actualizar_enlace(
        enlaces,
        origen,
        destino,
        retardo_ms,
        banda_mbps,
        perdida_porcentaje,
        disponible,
    )


def _quitar_enlace_nombre(desde_nombre: str) -> None:
    """Elimina el enlace renombrado desde su etiqueta legible."""
    enlaces = st.session_state.get("enlaces", m.tabla_enlaces_base())
    partes = desde_nombre.split("–")
    if len(partes) != 2:
        return
    u, v = partes[0].strip(), partes[1].strip()
    nuevo = m.quitar_enlace(enlaces, u, v)
    st.session_state.enlaces = nuevo
    st.session_state.editor_version = int(st.session_state.editor_version) + 1
    st.rerun()


def _tabla_enlaces_para_editor(
    enlaces: pd.DataFrame,
) -> pd.DataFrame:
    """Devuelve la tabla en el formato que espera el editor de Streamlit."""
    return m.tabla_enlaces_con_perdidas(enlaces)


def _vista_enlaces_con_perdida_para_editor(
    enlaces: pd.DataFrame,
) -> pd.DataFrame:
    """Vista con columna de pérdida para el editor de enlaces."""
    return m.vista_enlaces_mostrar_con_perdida(enlaces)


def _validar_ruta_usuario_datos(
    nombre: str,
    nodos: Sequence[str],
    enlaces: pd.DataFrame,
) -> tuple[bool, str]:
    """Devuelve (es_valida, motivo) para una ruta del usuario."""
    es_valida, motivo = m.validar_lista_nodos(nodos)
    if not es_valida:
        return False, f"{nombre}: {motivo}"
    for u, v in m.pares_ruta(nodos):
        if not m.enlace_presente(enlaces, u, v):
            return False, f"{nombre}: falta el enlace {u}–{v}."
    return True, ""


def _agregar_ruta_usuario(
    enlaces: pd.DataFrame,
    nombre: str,
    nodos: list[str],
    lista_usuario: list[tuple[str, list[str]]] | None = None,
) -> list[tuple[str, list[str]]]:
    """Devuelve la lista actualizada de rutas del usuario."""
    rutas = list_usuario or st.session_state.get("rutas_usuario", [])
    rutas = [(n, r) for (n, r) in rutas if n != nombre]
    rutas.append((nombre, nodos))
    st.session_state.rutas_usuario = rutas
    st.session_state.editor_version = int(st.session_state.editor_version) + 1
    return rutas


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Función objetivo")
    st.radio(
        "Minimizar",
        list(ETIQUETAS_OBJETIVO.values()),
        key="objetivo_label",
        help="Cambia las rutas y el sink tree. Los pesos multicriterio se conservan.",
    )
    objetivo = next(
        clave
        for clave, etiqueta in ETIQUETAS_OBJETIVO.items()
        if etiqueta == st.session_state.objetivo_label
    )

    if objetivo == "multicriterio":
        st.markdown("**Pesos** (se normalizan para sumar 1)")
        st.slider("α · saltos", 0.0, 1.0, step=0.05, key="alpha")
        st.slider("β · retardo", 0.0, 1.0, step=0.05, key="beta")
        st.slider("γ · penalización de banda", 0.0, 1.0, step=0.05, key="gamma")
        suma_bruta = (
            float(st.session_state.alpha)
            + float(st.session_state.beta)
            + float(st.session_state.gamma)
        )
        st.caption(f"α + β + γ = {suma_bruta:.2f}")

    pesos = m.normalizar_pesos(
        float(st.session_state.alpha),
        float(st.session_state.beta),
        float(st.session_state.gamma),
    )
    pesos_invalidos = pesos is None
    if pesos is None:
        pesos = (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
        st.warning(
            "Los pesos suman 0. Para no romper el cálculo se usan pesos "
            "iguales (1/3, 1/3, 1/3)."
        )
    elif objetivo == "multicriterio":
        st.caption(
            f"Normalizados: α={pesos[0]:.3f} · β={pesos[1]:.3f} · γ={pesos[2]:.3f}"
        )

    st.divider()
    st.subheader("Escenarios A–F")
    st.selectbox(
        "Aplicar un escenario",
        list(ESCENARIOS),
        key="escenario_selector",
        help="Restablece los datos base y aplica la configuración del experimento.",
    )
    if st.button("Aplicar escenario", type="primary", width="stretch"):
        st.session_state.escenario_pendiente = st.session_state.escenario_selector
        st.rerun()
    st.caption("También puedes editar la tabla de enlaces a mano.")


# ---------------------------------------------------------------------------
# Encabezado
# ---------------------------------------------------------------------------

st.title("Sink Tree y optimalidad de rutas")
st.markdown(
    "Laboratorio interactivo basado en Johal (2008). El **sink tree** o árbol "
    "de sumidero con raíz en **B** fija, para cada router, su **único siguiente "
    "salto** hacia B cuando las rutas de mínimo costo no empatan. No es la lista "
    "completa de rutas ni un conjunto de respaldos: es un árbol de encaminamiento."
)
st.caption(
    "Python + NetworkX + Streamlit + Plotly · Topología actual: "
    f"{len(_nodos_actuales())} routers y {len(st.session_state.enlaces)} enlaces"
)


# ---------------------------------------------------------------------------
# Sección 1: datos de entrada
# ---------------------------------------------------------------------------

st.header("1 · El grafo G=(V,E) y sus variables de entrada")

st.markdown(
    "Edita **Retardo** $d_{ij}$ (ms), **Banda** $b_{ij}$ (Mbps), **Pérdida** o "
    "**Disponible** $f_{ij}$ directamente en la tabla. Puedes añadir routers y "
    "enlaces: el grafo, el camino óptimo y el sink tree se recalculan con la "
    "topología resultante."
)

nodos_actuales = _nodos_actuales()
st.subheader("Topología dinámica")
met_1, met_2, met_3 = st.columns(3)
met_1.metric("Routers", len(nodos_actuales))
met_2.metric("Routers añadidos", len(_routers_extra()))
met_3.metric("Enlaces", len(st.session_state.enlaces))

with st.expander("Añadir routers", expanded=False):
    col_prefijo, col_cantidad, col_agregar = st.columns([1.2, 0.8, 0.8])
    prefijo = col_prefijo.text_input(
        "Prefijo",
        value="R",
        max_chars=8,
        key="nuevo_router_prefijo",
        help="Los routers nuevos se llamarán R1, R2, ...",
    )
    cantidad = col_cantidad.number_input(
        "Cantidad N",
        min_value=1,
        max_value=20,
        value=1,
        step=1,
        key="nuevo_router_cantidad",
    )
    col_agregar.write("")
    if col_agregar.button("Añadir routers", width="stretch"):
        creados = _agregar_routers(str(prefijo), int(cantidad))
        st.success("Routers añadidos: " + ", ".join(creados))
        st.rerun()
    st.caption(
        "Los routers nuevos se crean **aislados**: no se conectan "
        "automáticamente. Añade sus enlaces en «Añadir o eliminar enlaces»."
    )

    if _routers_extra():
        col_quitar, col_boton = st.columns([1.6, 0.8])
        router_a_quitar = col_quitar.selectbox(
            "Quitar un router añadido",
            _routers_extra(),
            key="router_a_quitar",
        )
        col_boton.write("")
        if col_boton.button("Quitar router", width="stretch"):
            _quitar_router(str(router_a_quitar))
            st.rerun()

with st.expander("Añadir o eliminar enlaces", expanded=False):
    with st.form("form_nuevo_enlace", clear_on_submit=True):
        col_o, col_d = st.columns(2)
        origen_nuevo = col_o.selectbox(
            "Origen", nodos_actuales, key="nuevo_enlace_origen"
        )
        destino_nuevo = col_d.selectbox(
            "Destino",
            nodos_actuales,
            index=min(1, len(nodos_actuales) - 1),
            key="nuevo_enlace_destino",
        )
        col_r, col_b, col_p, col_f = st.columns(4)
        retardo_nuevo = col_r.number_input(
            "Retardo (ms)", min_value=0.1, max_value=10000.0, value=10.0, step=1.0
        )
        banda_nueva = col_b.number_input(
            "Banda (Mbps)", min_value=1.0, max_value=100000.0, value=100.0, step=10.0
        )
        perdida_nueva = col_p.number_input(
            "Pérdida (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.1
        )
        disponible_nuevo = col_f.checkbox("Disponible", value=True)
        crear_enlace = st.form_submit_button(
            "Añadir enlace", type="primary", width="stretch"
        )
    if crear_enlace:
        error_enlace = _crear_enlace(
            str(origen_nuevo),
            str(destino_nuevo),
            float(retardo_nuevo),
            float(banda_nueva),
            float(perdida_nueva),
            bool(disponible_nuevo),
        )
        if error_enlace:
            st.error(error_enlace)
        else:
            st.rerun()

    if len(st.session_state.enlaces):
        etiquetas_enlaces = [
            f"{fila.Origen}–{fila.Destino}"
            + ("" if bool(fila.Disponible) else " (caído)")
            for fila in st.session_state.enlaces.itertuples()
        ]
        opciones_enlaces = {
            etiqueta: (str(fila.Origen), str(fila.Destino))
            for etiqueta, fila in zip(
                etiquetas_enlaces, st.session_state.enlaces.itertuples()
            )
        }
        col_e, col_q = st.columns([1.6, 0.8])
        enlace_a_eliminar = col_e.selectbox(
            "Enlace a eliminar",
            list(opciones_enlaces),
            key="enlace_a_eliminar",
        )
        col_q.write("")
        if col_q.button("Eliminar enlace", width="stretch"):
            u_borrar, v_borrar = opciones_enlaces[str(enlace_a_eliminar)]
            _eliminar_enlace(u_borrar, v_borrar)
            st.rerun()

nodos_actuales = _nodos_actuales()
if "origen_pendiente" in st.session_state:
    st.session_state.origen_router = st.session_state.pop("origen_pendiente")
if st.session_state.get("origen_router") not in nodos_actuales:
    st.session_state.origen_router = (
        m.ORIGEN if m.ORIGEN in nodos_actuales else nodos_actuales[0]
    )
origen_actual = st.selectbox(
    "Router de origen",
    nodos_actuales,
    index=nodos_actuales.index(str(st.session_state.origen_router)),
    key="origen_router",
    help="También puedes hacer clic sobre un router en el grafo de la sección 2.",
)
st.caption(
    "El origen se usa para la ruta óptima y sus métricas. El sink tree sigue "
    "teniendo raíz en B. Los routers nuevos no se conectan solos."
)

enlaces_previos = st.session_state.enlaces
vista = m.vista_enlaces_mostrar_con_perdida(enlaces_previos)
editada = st.data_editor(
    vista,
    key=f"editor_enlaces_{st.session_state.editor_version}",
    hide_index=True,
    num_rows="fixed",
    width="stretch",
    disabled=["Enlace"],
    column_config={
        "Enlace": st.column_config.TextColumn(
            "Enlace", help="Enlace no dirigido del subgrafo"
        ),
        "Retardo_ms": st.column_config.NumberColumn(
            "Retardo (ms)",
            min_value=0.1,
            max_value=10000.0,
            step=1.0,
            format="%.1f",
            help="d_ij: retardo del enlace en milisegundos",
        ),
        "Banda_Mbps": st.column_config.NumberColumn(
            "Banda (Mbps)",
            min_value=1.0,
            max_value=100000.0,
            step=1.0,
            format="%.0f",
            help="b_ij: capacidad del enlace en Mbps",
        ),
        "Pérdida_%": st.column_config.NumberColumn(
            "Pérdida (%)",
            min_value=0.0,
            max_value=100.0,
            step=0.1,
            format="%.1f",
            help="Porcentaje de pérdida estimado del enlace",
        ),
        "Disponible": st.column_config.CheckboxColumn(
            "Disponible", help="f_ij: 1 si el enlace está activo, 0 si está caído"
        ),
    },
)

enlaces = enlaces_previos.copy()
enlaces.loc[editada.index, "Retardo_ms"] = (
    pd.to_numeric(editada["Retardo_ms"], errors="coerce").fillna(0.1).clip(lower=0.1).to_numpy()
)
enlaces.loc[editada.index, "Banda_Mbps"] = (
    pd.to_numeric(editada["Banda_Mbps"], errors="coerce").fillna(1.0).clip(lower=1.0).to_numpy()
)
enlaces.loc[editada.index, "Disponible"] = (
    editada["Disponible"].fillna(False).astype(bool).to_numpy()
)
enlaces.loc[editada.index, "Pérdida_%"] = (
    pd.to_numeric(editada["Pérdida_%"], errors="coerce")
    .fillna(0.0)
    .clip(lower=0.0, upper=100.0)
    .to_numpy()
)
st.session_state.enlaces = enlaces

d_ref, b_ref = m.referencias(enlaces)
activos = int(enlaces["Disponible"].sum())

col_a, col_b, col_c = st.columns(3)
col_a.metric("d_ref (ms)", f"{d_ref:g}", help="Máximo retardo positivo de la tabla")
col_b.metric("b_ref (Mbps)", f"{b_ref:g}", help="Máxima banda positiva de la tabla")
col_c.metric("Enlaces activos", f"{activos} / {len(enlaces)}")

st.caption(
    "d_ref y b_ref son los máximos positivos registrados en la tabla, incluidas "
    "las filas de enlaces caídos. Si cambias un valor, cambia la escala de C(P): "
    "anota d_ref y b_ref al comparar experimentos."
)

if st.button("Restablecer topología base"):
    _restablecer_topologia()
    st.rerun()

st.divider()


# ---------------------------------------------------------------------------
# Sección 2: modelo y camino óptimo
# ---------------------------------------------------------------------------

st.header("2 · Modelo matemático y camino óptimo")

ruta_optima, costo_optimo = m.ruta_optima_desde(
    enlaces, str(origen_actual), m.DESTINO, objetivo, pesos
)
primera = m.primera_ruta_disponible(enlaces)
ruta_estatica: list[str] | None = None
if primera is not None and str(origen_actual) == m.ORIGEN:
    candidata = list(m.RUTAS_ESTATICAS[primera])
    if candidata != ruta_optima:
        ruta_estatica = candidata

col_izq, col_der = st.columns([1.2, 0.8], gap="large")

with col_izq:
    st.markdown(
        "El problema elige una ruta simple $P$ entre "
        f"${origen_actual}$ y ${m.DESTINO}$ usando solo enlaces activos, y "
        "minimiza un costo aditivo:"
    )
    st.latex(
        rf"P^*=\arg\min_{{P\in\mathcal{{P}}({origen_actual},{m.DESTINO})}}\ "
        r"\sum_{(i,j)\in P} w_{ij}"
    )
    st.latex(
        rf"\mathcal{{P}}({origen_actual},{m.DESTINO})=\left\{{(v_0,\dots,v_k):"
        rf"v_0={origen_actual},\ v_k={m.DESTINO},\ "
        r"(v_i,v_{i+1})\in E,\ f_{v_i v_{i+1}}=1\right\}"
    )
    st.markdown("**Función objetivo activa**")
    st.latex(_latex_objetivo(objetivo))
    if objetivo == "saltos":
        st.caption("Cada enlace cuesta h_ij = 1: se minimiza el número de saltos.")
    elif objetivo == "retardo":
        st.caption("Cada enlace cuesta su retardo d_ij en milisegundos.")
    else:
        st.caption(
            f"Con los datos actuales: d_ref = {d_ref:g} ms, b_ref = {b_ref:g} Mbps, "
            f"α = {pesos[0]:.3f}, β = {pesos[1]:.3f}, γ = {pesos[2]:.3f}."
        )
    st.latex(r"d_{ref}=\max\{d_{ij}>0\},\qquad b_{ref}=\max\{b_{ij}>0\}")
    st.markdown("**Principio de optimalidad**")
    st.markdown(
        "Si una ruta hacia B minimiza un costo aditivo no negativo, cada "
        "subcamino también es óptimo desde su propio router. Por eso el sink "
        "tree puede fijar un único siguiente salto por router y seguir siendo "
        "consistente con la ruta completa."
    )
    st.caption(
        "Todos los costos son no negativos; por eso el óptimo se obtiene con "
        "Dijkstra. El término b_ref/b_ij es una penalización por baja capacidad: "
        "no es el ancho de banda del camino, que se calcula aparte como "
        "B(P) = min b_ij."
    )

with col_der:
    st.markdown(
        f"**Resultado desde {origen_actual} hacia {m.DESTINO}**"
    )
    if ruta_optima:
        metricas_opt = m.metricas_ruta(enlaces, ruta_optima, pesos)
        st.markdown(
            f"**Ruta óptima:** {m.formato_secuencia(ruta_optima)}"
        )
        c1, c2 = st.columns(2)
        c1.metric("Saltos H(P)", f"{int(metricas_opt['saltos'])}")
        c2.metric("Retardo D(P)", f"{float(metricas_opt['retardo_ms']):.1f} ms")
        c3, c4 = st.columns(2)
        c3.metric("Banda B(P)", f"{float(metricas_opt['banda_mbps']):.0f} Mbps")
        c4.metric(
            "Costo activo",
            _fmt_costo(costo_optimo, objetivo),
            help="Valor de la función objetivo que minimiza Dijkstra",
        )
    else:
        st.error(
            f"No existe ninguna ruta entre {origen_actual} y {m.DESTINO} con "
            "los enlaces disponibles. Conecta el router o reactiva algún enlace."
        )

st.subheader("Grafo completo y ruta óptima")
figura = _figura_red(enlaces, ruta_optima, ruta_estatica, str(origen_actual))
evento_grafo = st.plotly_chart(
    figura,
    width="stretch",
    config={"displayModeBar": False},
    on_select="rerun",
    selection_mode="points",
    key="grafo_red_seleccion",
)
puntos_grafo = getattr(getattr(evento_grafo, "selection", None), "points", []) or []
if puntos_grafo:
    punto = puntos_grafo[0]
    firma_seleccion = (
        punto.get("curve_number"),
        punto.get("point_number"),
        punto.get("x"),
        punto.get("y"),
    )
    if firma_seleccion == st.session_state.get("grafo_ultima_seleccion"):
        puntos_grafo = []
    else:
        st.session_state.grafo_ultima_seleccion = firma_seleccion
if puntos_grafo:
    nodo_elegido = punto.get("customdata") or punto.get("text")
    if isinstance(nodo_elegido, (list, tuple)):
        nodo_elegido = nodo_elegido[0] if nodo_elegido else None
    nodo_elegido = str(nodo_elegido) if nodo_elegido else ""
    if nodo_elegido not in nodos_actuales:
        posiciones = _posiciones()
        for nodo in nodos_actuales:
            x, y = posiciones.get(nodo, (None, None))
            if (
                x is not None
                and punto.get("x") is not None
                and abs(float(punto["x"]) - x) < 1e-6
                and abs(float(punto["y"]) - y) < 1e-6
            ):
                nodo_elegido = nodo
                break
    if nodo_elegido in nodos_actuales and nodo_elegido != str(origen_actual):
        st.session_state.origen_pendiente = nodo_elegido
        st.rerun()
st.caption(
    f"Azul: origen {origen_actual}; verde: destino {m.DESTINO}. Naranja con "
    "flechas: ruta óptima hacia B; sus etiquetas muestran d_ij y b_ij. Azul "
    "punteada (si difiere): primera ruta estática disponible del artículo. "
    "Rojo discontinuo: enlace caído. **Haz clic en un router para usarlo "
    "como origen.**"
)
if (
    primera is not None
    and ruta_optima
    and list(m.RUTAS_ESTATICAS[primera]) == ruta_optima
):
    st.caption(
        "La primera ruta estática disponible coincide con la ruta óptima, "
        "por eso no se dibuja una línea azul adicional."
    )

st.subheader("Ruta óptima frente a las rutas estáticas")
if str(origen_actual) != m.ORIGEN:
    st.info(
        f"Las rutas estáticas PSRC, SSRC y TSRC parten de {m.ORIGEN}. La tabla "
        f"las compara con la óptima H→{m.DESTINO}; la ruta y las métricas desde "
        f"{origen_actual} aparecen arriba."
    )
comparacion = m.tabla_comparacion(enlaces, objetivo, pesos)
st.dataframe(
    comparacion,
    hide_index=True,
    width="stretch",
    column_config={
        "Ruta": st.column_config.TextColumn("Ruta"),
        "Estado": st.column_config.TextColumn("Estado", width="medium"),
        "Secuencia": st.column_config.TextColumn("Secuencia", width="large"),
        "Saltos": st.column_config.NumberColumn("Saltos", format="%d"),
        "Retardo (ms)": st.column_config.NumberColumn("Retardo (ms)", format="%.1f"),
        "Banda (Mbps)": st.column_config.NumberColumn("Banda (Mbps)", format="%.0f"),
        "C(P)": st.column_config.NumberColumn(
            "C(P)", format="%.3f", help="Costo multicriterio adimensional"
        ),
    },
)
st.caption(
    f"C(P) se evalúa siempre con los pesos multicriterio actuales "
    f"(α={pesos[0]:.2f}, β={pesos[1]:.2f}, γ={pesos[2]:.2f}) para poder comparar "
    f"todas las rutas, aunque el objetivo activo sea otro. Las tres rutas "
    "estáticas son configuraciones predefinidas del artículo, no todas las rutas "
    "simples del grafo."
)
if pesos_invalidos:
    st.warning(
        "Los pesos suman 0: C(P) se calculó con pesos iguales de 1/3 y el "
        "resultado no representa la escala pedida."
    )

if str(origen_actual) == m.ORIGEN and ruta_optima and primera is not None:
    ruta_primera = list(m.RUTAS_ESTATICAS[primera])
    if ruta_primera == ruta_optima:
        st.success(
            f"La primera ruta estática disponible ({primera}) coincide con la "
            "ruta óptima recalculada."
        )
    else:
        costo_primera = m.costo_ruta(enlaces, ruta_primera, objetivo, pesos)
        st.warning(
            f"La primera ruta estática disponible ({primera}) no coincide con la "
            f"óptima. Costo activo: {_fmt_costo(costo_primera, objetivo)} frente a "
            f"{_fmt_costo(costo_optimo, objetivo)}."
        )
        st.markdown(
            f"**Estática:** {m.formato_secuencia(ruta_primera)}  \n"
            f"**Óptima:** {m.formato_secuencia(ruta_optima)}"
        )
elif str(origen_actual) == m.ORIGEN and ruta_optima:
    st.error(
        "Ninguna de las tres rutas estáticas del artículo está completa: todos "
        "sus enlaces deben estar activos. La ruta óptima se calcula solo sobre el grafo."
    )

if ruta_optima:
    with st.expander("Cálculo enlace por enlace de la ruta óptima"):
        desglose = m.desglose_ruta(enlaces, ruta_optima, objetivo, pesos)
        st.dataframe(
            desglose,
            hide_index=True,
            width="stretch",
            column_config={
                "d_ij (ms)": st.column_config.NumberColumn("d_ij (ms)", format="%.1f"),
                "b_ij (Mbps)": st.column_config.NumberColumn(
                    "b_ij (Mbps)", format="%.0f"
                ),
                "w_ij": st.column_config.NumberColumn("w_ij", format="%.4f"),
                "Acumulado": st.column_config.NumberColumn(
                    "Acumulado", format="%.4f"
                ),
            },
        )
        st.caption(
            f"Costo total de la ruta = {costo_optimo:.4f}. Para saltos, w_ij = 1; "
            "para retardo, w_ij = d_ij; para multicriterio, w_ij es la expresión "
            "normalizada con α, β y γ."
        )

st.divider()


# ---------------------------------------------------------------------------
# Sección 3: Sink Tree
# ---------------------------------------------------------------------------

st.header("3 · Sink Tree T_B: siguientes saltos hacia B")

siguiente, distancias, caminos = m.sink_tree(enlaces, objetivo, pesos)
tabla_arbol = m.tabla_sink_tree(
    siguiente, distancias, caminos, _nodos_actuales()
)
empates = m.empates_sink_tree(enlaces, objetivo, pesos)

st.markdown(
    "Un sink tree se construye con la función de siguiente salto $\\pi(v)$: cada "
    "router elige el vecino que minimiza el costo restante hasta B. La distancia "
    "$d(v)$ satisface la ecuación de optimalidad de Bellman:"
)
st.latex(
    r"\pi(v)=\arg\min_{u\in N(v)}\left[c(v,u)+d(u)\right],\qquad "
    r"d(v)=c\bigl(v,\pi(v)\bigr)+d\bigl(\pi(v)\bigr),\qquad d(B)=0"
)
st.latex(
    r"T_B=(V',E_T),\qquad E_T=\{(v,\pi(v)):v\in V'\setminus\{B\}\},\qquad |E_T|=|V'|-1"
)
st.caption(
    "V' es el conjunto de routers con ruta hacia B; si todos son alcanzables, "
    "V' = V. Si todos los costos son no negativos, seguir π desde cualquier "
    "router llega a B sin bucles. El árbol fija un solo siguiente salto por "
    "router: no es la gráfica completa ni una lista de rutas de respaldo."
)

col_arbol_1, col_arbol_2 = st.columns(2)
alcanzables = len(distancias)
col_arbol_1.metric(
    "Routers con ruta hacia B", f"{alcanzables} / {len(_nodos_actuales())}"
)
col_arbol_2.metric("Aristas del árbol", f"{max(alcanzables - 1, 0)}")

figura_arbol = _figura_arbol(
    enlaces, siguiente, distancias, objetivo, str(origen_actual)
)
st.plotly_chart(figura_arbol, width="stretch", config={"displayModeBar": False})
st.caption(
    "Flechas verdes: siguiente salto π(v) hacia B. El texto bajo cada router es "
    "el costo acumulado d(v) con la función objetivo activa. Azul: origen H; "
    "verde: destino B; rojo: router sin ruta hacia B con los enlaces actuales."
)

if empates:
    detalle = "; ".join(
        f"{nodo}: {' o '.join(vecinos)}" for nodo, vecinos in empates.items()
    )
    st.info(
        f"Empates de costo: {detalle}. Cualquier elección produce un sink tree "
        "válido; el dibujo muestra una de las soluciones óptimas. Si dos rutas "
        "cuestan lo mismo, el siguiente salto puede cambiar sin aumentar el costo."
    )

st.subheader("Tabla de siguientes saltos")
formato_acumulado = "%d" if objetivo == "saltos" else ("%.2f" if objetivo == "retardo" else "%.3f")
st.dataframe(
    tabla_arbol,
    hide_index=True,
    width="stretch",
    column_config={
        "Costo acumulado": st.column_config.NumberColumn(
            "Costo acumulado", format=formato_acumulado
        ),
    },
)
st.caption(
    "Cada fila responde: «desde este router, ¿cuál es el siguiente salto y cuánto "
    "cuesta el resto del camino hasta B?». El destino B no tiene siguiente salto. "
    "Prueba a cambiar un enlace y observa cuántas filas cambian."
)

st.divider()


# ---------------------------------------------------------------------------
# Sección 4: variables, experimentos, discusión y exportación
# ---------------------------------------------------------------------------

st.header("4 · Variables, experimentos y exportación")

tab_variables, tab_experimentos, tab_discusion = st.tabs(
    ["Variables y modelo", "Experimentos A–F", "Discusión"]
)

with tab_variables:
    st.markdown(
        """
| Símbolo | Definición | Unidad |
|:--|:--|:--|
| $G=(V,E)$ | Grafo no dirigido de routers y enlaces | — |
| $V$ | Routers base (H, D, A, B, E, J, C, O, N) y routers añadidos | — |
| $E$ | Enlaces disponibles ($f_{ij}=1$) | — |
| $s=H,\\ t=B$ | Origen y destino (sumidero) | — |
| $P=(s=v_0,\\dots,v_k=t)$ | Ruta simple origen–destino | — |
| $h_{ij}$ | Costo por salto, $h_{ij}=1$ | saltos |
| $d_{ij}$ | Retardo del enlace | ms |
| $b_{ij}$ | Capacidad del enlace | Mbps |
| $f_{ij}$ | Disponibilidad: 1 activo, 0 caído | booleano |
| $H(P)$ | Número de saltos de la ruta | saltos |
| $D(P)$ | Retardo acumulado de la ruta | ms |
| $B(P)=\\min b_{ij}$ | Ancho de banda del camino | Mbps |
| $C(P)$ | Costo multicriterio normalizado | adimensional |
| $\\alpha,\\beta,\\gamma$ | Pesos de saltos, retardo y penalización de banda | adimensional |
| $\\pi(v)$ | Siguiente salto de $v$ hacia B | — |
| $T_B$ | Sink tree con raíz en B | — |
| $d(v)$ | Costo acumulado desde $v$ hasta B | según objetivo |
| $d_{ref},b_{ref}$ | Máximos positivos de la tabla para normalizar | ms, Mbps |
"""
    )
    st.markdown("**Formulación completa del costo multicriterio**")
    st.latex(
        r"C(P)=\sum_{(i,j)\in P}\left[\alpha+\beta\,\frac{d_{ij}}{d_{ref}}"
        r"+\gamma\,\frac{b_{ref}}{b_{ij}}\right],\qquad \alpha+\beta+\gamma=1"
    )
    st.markdown(
        "Los pesos de pantalla se normalizan dividiendo cada uno entre su suma. "
        "Todos los términos son no negativos y se minimizan. La penalización "
        "$b_{ref}/b_{ij}$ permite usar Dijkstra; el ancho de banda del camino "
        "$B(P)=\\min b_{ij}$ se informa por separado y **no** es equivalente a esa "
        "penalización."
    )

with tab_experimentos:
    st.markdown(
        "Aplica cada escenario desde la barra lateral. Para cada prueba anota la "
        "función objetivo, $d_{ref}$, $b_{ref}$, $\\alpha,\\beta,\\gamma$ y los "
        "valores calculados; así el experimento es reproducible."
    )
    st.markdown(
        """
| Prueba | Acción | Evidencia esperada |
|:--|:--|:--|
| **A** · Réplica original | Escenario A; objetivo saltos | $H(P_1)=3$, $H(P_2)=4$, $H(P_3)=5$; PSRC es la primera disponible y coincide con el óptimo. |
| **B** · Cambio de retardo | Escenario B (H–D = 40 ms); objetivo retardo | $D(P_1)=56$ ms, $D(P_2)=29$ ms, $D(P_3)=39$ ms. La mejor de las tres es SSRC; compárala con el óptimo global, que puede diferir. |
| **C** · Fallo primario | Escenario C (H–D caído); objetivo saltos | PSRC queda descartada; SSRC es la primera disponible (4 saltos). Compárala con la ruta óptima recalculada. |
| **D** · Doble fallo | Escenario D (H–D y H–E caídos); objetivo saltos | TSRC queda como ruta estática completa si O–N–J–C–B sigue activa. El sink tree se reconstruye desde B. |
| **E** · Cuello de botella | Escenario E (E–J = 5 Mbps); objetivo saltos | $B(P_2)=\\min(50,5,100,100)=5$ Mbps. $C(P_2)$ sube por la penalización $b_{ref}/b_{ij}$, no porque cambie el número de saltos. |
| **F** · Cambios de pesos | Escenario F; prueba (1,0,0), (0,1,0), (0,0,1) y (0.5,0.35,0.15) | Anota $\\alpha,\\beta,\\gamma$ normalizados y $d_{ref},b_{ref}$; calcula $C(P)$ a mano y contrasta con la tabla. |
"""
    )
    st.warning(
        "En la prueba B, el camino de menor retardo sobre **todo** el grafo puede "
        "no ser el mejor de los tres caminos preconfigurados: hay combinaciones "
        "adicionales de enlaces. Registra ambos resultados."
    )
    with st.expander("Ejemplo de cálculo manual obligatorio"):
        st.markdown(
            "Con los datos iniciales, para $P_1=H\\!-\\!D\\!-\\!A\\!-\\!B$: "
            "$d_{HD}=8$ ms, $d_{DA}=9$ ms y $d_{AB}=7$ ms."
        )
        st.latex(
            r"H(P_1)=3,\qquad D(P_1)=8+9+7=24\ \text{ms},\qquad "
            r"B(P_1)=\min(100,100,100)=100\ \text{Mbps}"
        )
        st.markdown(
            "Para $P_2=H\\!-\\!E\\!-\\!J\\!-\\!C\\!-\\!B$: $D(P_2)=5+10+8+6=29$ ms, "
            "$B(P_2)=\\min(50,50,100,100)=50$ Mbps. Para "
            "$P_3=H\\!-\\!O\\!-\\!N\\!-\\!J\\!-\\!C\\!-\\!B$: "
            "$D(P_3)=7+9+9+8+6=39$ ms y $B(P_3)=50$ Mbps."
        )
        st.markdown(
            "Costo multicriterio del enlace H–D con "
            "$\\alpha=0.5$, $\\beta=0.35$, $\\gamma=0.15$, "
            "$d_{ref}=10$ ms y $b_{ref}=100$ Mbps:"
        )
        st.latex(
            r"C_{HD}=0.5+0.35\left(\frac{8}{10}\right)"
            r"+0.15\left(\frac{100}{100}\right)=0.93"
        )
        st.caption(
            "Repite para todas las aristas y suma: C(P1) = 2.790, C(P2) = 3.915, "
            "C(P3) = 4.765 con los datos iniciales."
        )

with tab_discusion:
    st.markdown(
        """
1. ¿Por qué el camino de menos saltos puede no ser el de menor retardo?
2. ¿Cuándo una ruta de respaldo comparte un punto único de fallo con otra?
   Identifica el segmento J–C–B.
3. ¿Por qué el árbol hacia B puede cambiar al modificar un único enlace?
4. ¿En qué difieren una tabla estática preconfigurada y el recálculo dinámico?
5. ¿Qué consecuencias tiene cambiar los pesos sin justificar su escala y significado?
6. ¿Qué faltaría para desplegar el procedimiento en routers reales
   (detección de fallos, instalación de rutas, temporización)?
"""
    )
    st.info(
        "El sink tree no almacena todas las rutas: cada router solo necesita su "
        "siguiente salto. Esa es su ventaja de escalabilidad y también su límite: "
        "un solo árbol no describe por sí mismo rutas alternativas."
    )

st.subheader("Exportar resultados")

export_rutas = comparacion.copy()
export_rutas.insert(0, "Objetivo", ETIQUETAS_OBJETIVO[objetivo])
export_rutas["d_ref (ms)"] = d_ref
export_rutas["b_ref (Mbps)"] = b_ref
export_rutas["alpha"] = round(pesos[0], 4)
export_rutas["beta"] = round(pesos[1], 4)
export_rutas["gamma"] = round(pesos[2], 4)

export_arbol = tabla_arbol.copy()
export_arbol.insert(0, "Objetivo", ETIQUETAS_OBJETIVO[objetivo])
export_arbol["d_ref (ms)"] = d_ref
export_arbol["b_ref (Mbps)"] = b_ref
export_arbol["alpha"] = round(pesos[0], 4)
export_arbol["beta"] = round(pesos[1], 4)
export_arbol["gamma"] = round(pesos[2], 4)

col_descarga_1, col_descarga_2 = st.columns(2)
col_descarga_1.download_button(
    "Descargar resultados de rutas (CSV)",
    data=export_rutas.to_csv(index=False).encode("utf-8-sig"),
    file_name="resultados_rutas.csv",
    mime="text/csv",
    width="stretch",
)
col_descarga_2.download_button(
    "Descargar sink tree (CSV)",
    data=export_arbol.to_csv(index=False).encode("utf-8-sig"),
    file_name="sink_tree.csv",
    mime="text/csv",
    width="stretch",
)
st.caption(
    "Los CSV incluyen el objetivo activo, d_ref, b_ref y los pesos normalizados "
    "para que cada experimento sea trazable."
)

st.divider()


# ---------------------------------------------------------------------------
# Sección 5: guía y demo independiente
# ---------------------------------------------------------------------------

st.header("5 · Guía y demo del algoritmo")
st.markdown(
    "Esta sección reúne la guía y el código independiente. La **guía** explica "
    "el problema, la matemática, las dos implementaciones, la comparación y las "
    "limitaciones. El **demo** ejecuta BFS y Dijkstra y muestra los dos árboles, "
    "los costos y las tres rutas."
)
st.markdown(
    "- **Básica:** BFS desde B, costo 1 por enlace.\n"
    "- **Avanzada:** Dijkstra desde B con costo multicriterio.\n"
    "- **Diferencia clave:** en O, la básica elige H y la avanzada elige N; "
    "ambas rutas tienen 4 saltos, pero distinto costo."
)

col_descarga_guia, col_descarga_demo = st.columns(2)
if GUIA_TEXTO:
    col_descarga_guia.download_button(
        "Descargar guía (.md)",
        data=GUIA_TEXTO.encode("utf-8"),
        file_name="GUIA_SINK_TREE.md",
        mime="text/markdown",
        width="stretch",
    )
else:
    col_descarga_guia.warning("No se encontró GUIA_SINK_TREE.md en la carpeta.")

if DEMO_TEXTO:
    col_descarga_demo.download_button(
        "Descargar demo (.py)",
        data=DEMO_TEXTO.encode("utf-8"),
        file_name="sink_tree_demo.py",
        mime="text/x-python",
        width="stretch",
    )
else:
    col_descarga_demo.warning("No se encontró sink_tree_demo.py en la carpeta.")

tab_guia, tab_demo, tab_codigo = st.tabs(["Guía", "Demo", "Código"])

with tab_guia:
    st.caption(
        "Contenido de la guía. También puedes descargarla con el botón de arriba."
    )
    if GUIA_TEXTO:
        st.markdown(GUIA_TEXTO)
    else:
        st.error("Falta GUIA_SINK_TREE.md en la carpeta del proyecto.")

with tab_demo:
    st.markdown(
        "El demo es autocontenido: solo usa la biblioteca estándar de Python y "
        "no necesita Streamlit ni NetworkX. Ejecútalo aquí o desde la terminal "
        "con el comando que aparece abajo."
    )
    st.code("python sink_tree_demo.py", language="bash")
    if st.button("Ejecutar demo", type="primary", width="stretch"):
        st.session_state.demo_salida = _ejecutar_demo()
    salida_demo = st.session_state.get("demo_salida")
    if salida_demo:
        st.code(salida_demo, language="text")
    else:
        st.info(
            "Pulsa «Ejecutar demo» para ver el árbol básico, el árbol avanzado, "
            "los costos por enlace y las métricas de las tres rutas."
        )
    st.caption(
        "La salida muestra el empate de O en la versión básica y el cambio a "
        "O → N en la versión avanzada. También imprime C(P1), C(P2) y C(P3)."
    )

with tab_codigo:
    st.caption(
        "Código completo de sink_tree_demo.py: implementación básica con BFS, "
        "avanzada con Dijkstra y salida de resultados."
    )
    if DEMO_TEXTO:
        st.code(DEMO_TEXTO, language="python")
    else:
        st.error("Falta sink_tree_demo.py en la carpeta del proyecto.")

st.divider()
st.caption(
    "Referencia: Johal, H. S. (2008). Optimality Principle Based Sink Tree "
    "Methodology for Adaptive Static Routing Using Multiple Route Configuration "
    "Scheme. WCECS 2008. DOI: 10.1109/WCECS.2008.21. Los retardos, capacidades y "
    "la función multicriterio son construcciones de laboratorio; no son los "
    "resultados experimentales del artículo."
)
