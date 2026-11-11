"""Presentación interactiva: símbolos, uso y costo multicriterio.

Explica en lenguaje sencillo la tabla de símbolos y la formulación completa del
costo multicriterio. Muestra cada fórmula junto a su versión sustituida con los
valores de la tabla, con tres casos resueltos (PSRC, SSRC y TSRC), y termina con
un caso básico (solo saltos) y un caso avanzado (saltos + retardo + banda) que
puedes manipular.

Ejecutar con:
    python -m streamlit run presentacion.py
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import model as m

st.set_page_config(
    page_title="Explicar el costo multicriterio",
    page_icon="🎓",
    layout="wide",
)

COLOR_SALTOS = "#94a3b8"
COLOR_RETARDO = "#f59e0b"
COLOR_BANDA = "#0d9488"
COLOR_GANADORA = "#16a34a"
COLOR_OTRA = "#cbd5e1"

# Ruta de referencia del artículo, usada en todos los cálculos manuales.
PSRC = m.RUTAS_ESTATICAS["PSRC"]


# ---------------------------------------------------------------------------
# Utilidades de cálculo y presentación
# ---------------------------------------------------------------------------


def _enlaces_avanzados(hd_lento: bool) -> pd.DataFrame:
    """Tabla base del artículo, con H–D degradado si se pidió."""
    enlaces = m.tabla_enlaces_base()
    if hd_lento:
        mascara = (enlaces["Origen"] == "H") & (enlaces["Destino"] == "D")
        enlaces.loc[mascara, "Retardo_ms"] = 40.0
    return enlaces


def _componentes(
    enlaces: pd.DataFrame,
    ruta: Sequence[str],
    pesos: tuple[float, float, float],
    d_ref: float,
    b_ref: float,
) -> tuple[float, float, float]:
    """Parte del costo C(P) que aporta cada criterio: α·H, β·Σd/d_ref, γ·Σb_ref/b."""
    suma_retardo = 0.0
    suma_banda = 0.0
    for u, v in m.pares_ruta(ruta):
        retardo, banda, _ = m.datos_enlace(enlaces, u, v)
        suma_retardo += retardo / d_ref
        suma_banda += b_ref / banda
    return (
        pesos[0] * (len(ruta) - 1),
        pesos[1] * suma_retardo,
        pesos[2] * suma_banda,
    )


def _resultados(
    enlaces: pd.DataFrame, pesos: tuple[float, float, float]
) -> list[dict[str, object]]:
    """Métricas y desglose de las tres rutas estáticas."""
    d_ref, b_ref = m.referencias(enlaces)
    filas: list[dict[str, object]] = []
    for nombre, ruta in m.RUTAS_ESTATICAS.items():
        metricas = m.metricas_ruta(enlaces, ruta, pesos)
        c_alpha, c_beta, c_gamma = _componentes(
            enlaces, ruta, pesos, d_ref, b_ref
        )
        filas.append(
            {
                "Ruta": nombre,
                "Secuencia": m.formato_secuencia(ruta),
                "H": int(metricas["saltos"]),
                "D": float(metricas["retardo_ms"]),
                "B": float(metricas["banda_mbps"]),
                "C": float(m.costo_ruta(enlaces, ruta, "multicriterio", pesos)),
                "c_alpha": c_alpha,
                "c_beta": c_beta,
                "c_gamma": c_gamma,
            }
        )
    return filas


def _sustitucion_ruta(
    enlaces: pd.DataFrame,
    ruta: Sequence[str],
    pesos: tuple[float, float, float],
    d_ref: float,
    b_ref: float,
) -> dict[str, float | str]:
    """Cadenas con los números puestos para H(P), D(P), B(P) y C(P)."""
    retardos: list[float] = []
    bandas: list[float] = []
    costos: list[float] = []
    for u, v in m.pares_ruta(ruta):
        retardo, banda, _ = m.datos_enlace(enlaces, u, v)
        retardos.append(retardo)
        bandas.append(banda)
        costos.append(
            m.peso_objetivo("multicriterio", retardo, banda, d_ref, b_ref, pesos)
        )
    return {
        "saltos": f"{len(ruta)} − 1 = {len(ruta) - 1} saltos",
        "retardo": " + ".join(f"{valor:g}" for valor in retardos)
        + f" = {sum(retardos):g} ms",
        "banda": "min("
        + ", ".join(f"{valor:g}" for valor in bandas)
        + f") = {min(bandas):g} Mbps",
        "cadena": " + ".join(f"{valor:.3f}" for valor in costos),
        "costo": float(sum(costos)),
    }


def _latex_costo_ruta(
    enlaces: pd.DataFrame,
    ruta: Sequence[str],
    pesos: tuple[float, float, float],
    d_ref: float,
    b_ref: float,
    nombre: str,
) -> str:
    """C(P) expandido enlace por enlace, listo para st.latex."""
    terminos: list[tuple[str, str, float, float, float]] = []
    for u, v in m.pares_ruta(ruta):
        retardo, banda, _ = m.datos_enlace(enlaces, u, v)
        terminos.append(
            (
                u,
                v,
                retardo,
                banda,
                m.peso_objetivo(
                    "multicriterio", retardo, banda, d_ref, b_ref, pesos
                ),
            )
        )

    lineas = [
        r"\begin{aligned}",
        rf"C(\text{{{nombre}}}) &= "
        + " + ".join(f"w_{{{u}{v}}}" for u, v, _, _, _ in terminos)
        + r" \\",
    ]
    for u, v, retardo, banda, costo in terminos:
        lineas.append(
            rf"w_{{{u}{v}}} &= {pesos[0]:.2f} + {pesos[1]:.2f}\cdot"
            rf"\frac{{{retardo:g}\ \text{{ms}}}}{{{d_ref:g}\ \text{{ms}}}}"
            rf" + {pesos[2]:.2f}\cdot"
            rf"\frac{{{b_ref:g}\ \text{{Mbps}}}}{{{banda:g}\ \text{{Mbps}}}}"
            rf" = {costo:.3f} \\"
        )
    lineas.append(
        rf"C(\text{{{nombre}}}) &= "
        + " + ".join(f"{termino[4]:.3f}" for termino in terminos)
        + rf" = {sum(termino[4] for termino in terminos):.3f}"
    )
    lineas.append(r"\end{aligned}")
    return "\n".join(lineas)


def _aplicar_pesos(alpha: float, beta: float, gamma: float) -> None:
    """Callback de los botones de preset (corre antes del rerun)."""
    st.session_state.alpha = alpha
    st.session_state.beta = beta
    st.session_state.gamma = gamma


for _clave, _valor in {
    "alpha": m.PESOS_BASE[0],
    "beta": m.PESOS_BASE[1],
    "gamma": m.PESOS_BASE[2],
    "hd_lento": False,
}.items():
    st.session_state.setdefault(_clave, _valor)


# ---------------------------------------------------------------------------
# Barra lateral: controles que se usan en el caso avanzado
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Controles")
    st.caption(
        "Los usarás en el **caso avanzado**. Mueve los pesos y observa cómo "
        "cambia la ruta ganadora."
    )

    st.markdown("**Pesos** (los normalizo para que sumen 1)")
    st.slider("α · saltos", 0.0, 1.0, step=0.05, key="alpha")
    st.slider("β · retardo", 0.0, 1.0, step=0.05, key="beta")
    st.slider("γ · banda", 0.0, 1.0, step=0.05, key="gamma")

    st.divider()
    st.checkbox(
        "Simular H–D lento (40 ms)",
        key="hd_lento",
        help="Degrada el enlace H–D para mostrar que el ganador puede cambiar.",
    )

    st.divider()
    st.markdown("**Atajos rápidos**")
    st.button(
        "Solo saltos · (1, 0, 0)",
        key="preset_saltos",
        on_click=_aplicar_pesos,
        args=(1.0, 0.0, 0.0),
        width="stretch",
    )
    st.button(
        "Solo retardo · (0, 1, 0)",
        key="preset_retardo",
        on_click=_aplicar_pesos,
        args=(0.0, 1.0, 0.0),
        width="stretch",
    )
    st.button(
        "Solo banda · (0, 0, 1)",
        key="preset_banda",
        on_click=_aplicar_pesos,
        args=(0.0, 0.0, 1.0),
        width="stretch",
    )
    st.button(
        "Equilibrado · (0.5, 0.35, 0.15)",
        key="preset_equilibrado",
        on_click=_aplicar_pesos,
        args=m.PESOS_BASE,
        width="stretch",
    )
    st.caption(
        "Sugerencia: activa «H–D lento» y pulsa **Solo retardo**: la red no "
        "cambia de forma, pero la mejor ruta sí."
    )


# ---------------------------------------------------------------------------
# Datos y parámetros vigentes
# ---------------------------------------------------------------------------

enlaces_base = m.tabla_enlaces_base()
d_ref_base, b_ref_base = m.referencias(enlaces_base)
enlaces = _enlaces_avanzados(bool(st.session_state.hd_lento))
d_ref, b_ref = m.referencias(enlaces)
d_hd, b_hd, _ = m.datos_enlace(enlaces, "H", "D")
d_he, b_he, _ = m.datos_enlace(enlaces, "H", "E")

pesos = m.normalizar_pesos(
    float(st.session_state.alpha),
    float(st.session_state.beta),
    float(st.session_state.gamma),
)
pesos_invalidos = pesos is None
if pesos is None:
    pesos = (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)

resultados = _resultados(enlaces, pesos)
ganadora = min(resultados, key=lambda fila: float(fila["C"]))
w_hd = m.peso_objetivo("multicriterio", d_hd, b_hd, d_ref, b_ref, pesos)
w_he = m.peso_objetivo("multicriterio", d_he, b_he, d_ref, b_ref, pesos)
ruta_global, costo_global = m.ruta_optima(enlaces, "multicriterio", pesos)


# ---------------------------------------------------------------------------
# Encabezado
# ---------------------------------------------------------------------------

st.title("Cómo eliges la mejor ruta")
st.markdown(
    "Tienes 9 routers y 10 enlaces, y quieres llevar el tráfico de H a B. Una "
    "ruta no es buena solo por tener **pocos saltos**: también importa si sus "
    "enlaces son **lentos** o **estrechos**. El **costo multicriterio** te da "
    "una regla simple: le pones un precio a cada enlace y sumas."
)
st.caption(
    "Subgrafo de Johal (2008): 9 routers "
    "y 10 enlaces · sales de H y llegas a B"
)


# ---------------------------------------------------------------------------
# 1 · La idea en una frase
# ---------------------------------------------------------------------------

st.header("1 · La idea en una frase")

st.info(
    "**Cada enlace tiene un precio; la ruta que suma el precio más pequeño gana.** "
    "Ese precio combina, en un solo número, los saltos, el retardo y el ancho de "
    "banda. Así puedes comparar rutas de calidad muy distinta con una sola regla."
)

col_1, col_2, col_3 = st.columns(3)
col_1.markdown(
    "**① Le pones un precio a cada enlace**\n\n"
    "Cada tramo te cuesta un poco por existir, otro poco por su retardo y otro "
    "por lo estrecho que sea."
)
col_2.markdown(
    "**② El precio de la ruta es la suma**\n\n"
    "Si una ruta usa tres enlaces, su costo es la suma de esos tres precios. "
    "No hay nada más que sumar."
)
col_3.markdown(
    "**③ Ganas con la más barata**\n\n"
    "Comparas las rutas posibles entre H y B y eliges la de menor costo. "
    "No tienes que adivinar."
)

st.divider()


# ---------------------------------------------------------------------------
# 2 · Los símbolos, en lenguaje sencillo
# ---------------------------------------------------------------------------

st.header("2 · Los símbolos, en lenguaje sencillo")
st.markdown(
    "No necesitas memorizar la tabla: te basta con ver los símbolos en **cuatro "
    "grupos**, y cada grupo te responde una pregunta distinta."
)

tab_mapa, tab_enlace, tab_ruta, tab_decision = st.tabs(
    [
        "¿Cuál es el mapa?",
        "¿Cuánto cuesta un enlace?",
        "¿Cuánto mide una ruta?",
        "¿Qué decide el router?",
    ]
)

with tab_mapa:
    st.markdown(
        """
| Símbolo | En palabras | Unidad | En este ejemplo |
|:--|:--|:--|:--|
| $G=(V,E)$ | El mapa completo: routers unidos por enlaces. | — | 9 routers, 10 enlaces |
| $V$ | Los routers, es decir, los puntos del mapa. | — | H, D, A, B, E, J, C, O, N |
| $E$ | Los enlaces, es decir, los caminos entre routers. | — | H–D, D–A, A–B, … |
| $s=H$ | El **origen**: de dónde sale el tráfico. | — | H |
| $t=B$ | El **destino** o sumidero: a dónde va todo. | — | B |
| $P$ | Una **ruta simple**: routers conectados, sin repetir ninguno. | — | H → D → A → B |
"""
    )
    st.caption(
        "Cuando veas una ruta con 4 routers, cuenta 3 enlaces: por eso H(P) = 3. "
        "A B le llamamos sumidero porque absorbe todo el tráfico: todas las "
        "flechas apuntan a él."
    )

with tab_enlace:
    st.markdown(
        """
| Símbolo | En palabras | Unidad | En este ejemplo |
|:--|:--|:--|:--|
| $h_{ij}$ | Precio del tramo cuando **solo contamos saltos**. Vale 1. | saltos | 1 salto |
| $d_{ij}$ | Cuánto **tarda** el tramo. | ms | H–D = 8 ms |
| $b_{ij}$ | Cuánto **cabe** por el tramo (capacidad). | Mbps | H–D = 100 Mbps |
| $f_{ij}$ | Interruptor del enlace: 1 activo, 0 caído. Si vale 0, la ruta no puede usarlo. | booleano | 1 (activo) |
"""
    )
    st.caption(
        "El enlace es tu unidad mínima de decisión: todo lo que mides (retardo, "
        "banda, disponibilidad) vive en el enlace, no en el router."
    )

with tab_ruta:
    st.markdown(
        """
| Símbolo | En palabras | Unidad | En $P_1$ = H–D–A–B |
|:--|:--|:--|:--|
| $H(P)$ | **Cuántos saltos** tiene la ruta. | saltos | 3 saltos |
| $D(P)$ | **Suma de los retardos** de sus enlaces. | ms | 8 + 9 + 7 = 24 ms |
| $B(P)=\\min b_{ij}$ | **Ancho de banda de la ruta**: el enlace más estrecho manda (cuello de botella). | Mbps | min(100, 100, 100) = 100 Mbps |
| $C(P)$ | **Precio total** de la ruta: un solo número para comparar. | adimensional | 2.790 (adimensional) |
"""
    )
    st.caption(
        "Ojo: las capacidades no las sumas. Una ruta nunca transporta más que su "
        "enlace más angosto; por eso B(P) es un mínimo y no una suma."
    )

with tab_decision:
    st.markdown(
        """
| Símbolo | En palabras | Unidad | En este ejemplo |
|:--|:--|:--|:--|
| $\\alpha,\\beta,\\gamma$ | Cuánto **pesa** cada criterio: saltos, retardo y banda. Se normalizan para sumar 1. | adimensional | 0.50 / 0.35 / 0.15 |
| $d_{ref}$ | El **retardo mayor** de la tabla: sirve de regla de tres para comparar. | ms | 10 ms |
| $b_{ref}$ | La **banda mayor** de la tabla: sirve de regla de tres para comparar. | Mbps | 100 Mbps |
| $\\pi(v)$ | La **única decisión** que guarda el router $v$: por qué vecino salir hacia B. | — | π(H) = D |
| $T_B$ | Todas esas decisiones juntas: un **árbol** con raíz en B, sin ciclos. | — | 8 flechas |
| $d(v)$ | Lo que cuesta el **resto del camino** desde $v$ hasta B. | según objetivo | 3 saltos desde H |
"""
    )
    st.caption(
        "π(v) y T_B son la parte de encaminamiento: cada router no guarda la ruta "
        "completa, solo su siguiente salto. En la app principal puedes ver ese "
        "árbol dibujado."
    )

st.divider()


# ---------------------------------------------------------------------------
# 3 · Cómo se usa, paso a paso
# ---------------------------------------------------------------------------

st.header("3 · Cómo lo usas, paso a paso")
st.markdown(
    r"""
1. **Mira la tabla de enlaces.** Cada fila te da $d_{ij}$, $b_{ij}$ y $f_{ij}$. Si $f_{ij}=0$, ese enlace no existe para tu ruta.
2. **Fija las referencias.** $d_{ref}$ es el retardo más grande de la tabla y $b_{ref}$ la banda más grande. Así pones retardos y bandas en una misma escala.
3. **Reparte el peso.** $\alpha$ para saltos, $\beta$ para retardo, $\gamma$ para banda. Normalizas para que sumen 1: lo que importa es la proporción, no el valor absoluto.
4. **Ponle precio a cada enlace.** Aplicas la fórmula de $w_{ij}$ con los datos de ese tramo.
5. **Suma a lo largo de la ruta.** El resultado es $C(P)$, y eliges la suma más pequeña. Con una computadora, Dijkstra hace los pasos 4 y 5 de golpe.
"""
)

st.markdown("**La fórmula, completa**")
st.latex(
    r"C(P)=\sum_{(i,j)\in P}\left[\alpha+\beta\,\frac{d_{ij}\ [\text{ms}]}{d_{ref}\ [\text{ms}]}"
    r"+\gamma\,\frac{b_{ref}\ [\text{Mbps}]}{b_{ij}\ [\text{Mbps}]}\right],\qquad "
    r"\alpha+\beta+\gamma=1"
)
st.caption(
    "Cada enlace te aporta α (un peaje fijo), β por su retardo relativo y γ por "
    "lo estrecho que es. Como pagas α en cada enlace, un α alto castiga las rutas "
    "con muchos saltos."
)

col_a, col_b, col_c = st.columns(3)
col_a.markdown(
    "**α · peaje por enlace**\n\n"
    "Lo pagas una vez por tramo. Si lo subes, favoreces rutas cortas, con menos routers."
)
col_b.markdown(
    "**β · peaje por retardo**\n\n"
    "Compara $d_{ij}$ con el enlace más lento de la tabla. Si lo subes, favoreces rutas rápidas."
)
col_c.markdown(
    "**γ · peaje por estrechez**\n\n"
    "Vale 1 en el enlace más ancho y crece si el enlace es más angosto. Si lo subes, evitas cuellos de botella."
)

alpha_w, beta_w, gamma_w = pesos
aporte_alpha = alpha_w
aporte_beta = beta_w * d_hd / d_ref
aporte_gamma = gamma_w * b_ref / b_hd

st.markdown("**Así lees $w_{HD}$ con los controles que tienes ahora**")
st.latex(
    rf"w_{{HD}} = {alpha_w:.2f} + {beta_w:.2f}\cdot"
    rf"\frac{{{d_hd:g}\ \text{{ms}}}}{{{d_ref:g}\ \text{{ms}}}}"
    rf" + {gamma_w:.2f}\cdot"
    rf"\frac{{{b_ref:g}\ \text{{Mbps}}}}{{{b_hd:g}\ \text{{Mbps}}}} = {w_hd:.3f}"
)
st.markdown(
    f"Lo lees así: «usar H–D te cuesta **{w_hd:.2f} unidades**: "
    f"{aporte_alpha:.2f} por el salto, {aporte_beta:.2f} por su retardo y "
    f"{aporte_gamma:.2f} por su banda». Las tres partes suman el precio del enlace."
)
st.caption(
    "Fíjate en que ningún término tiene unidades: divides el retardo entre d_ref y "
    "la banda al revés. Por eso C(P) es un puntaje adimensional y lo puedes sumar."
)

st.divider()


# ---------------------------------------------------------------------------
# 4 · Las mismas fórmulas, con los números de la tabla
# ---------------------------------------------------------------------------

st.header("4 · Las mismas fórmulas, con los números de tu tabla")
st.markdown(
    "Las fórmulas de la sección 2 están escritas con letras. Aquí tienes **la "
    "misma fórmula al lado de su versión sustituida** con los valores de la "
    "tabla: primero el mapa (vértices y aristas), después las constantes, y al "
    "final esos cálculos resueltos como casos PSRC, SSRC y TSRC. Cada número va "
    "con la unidad de su variable. Si mueves los controles, todo se recalcula."
)

sustituciones = {
    nombre: _sustitucion_ruta(enlaces, ruta, pesos, d_ref, b_ref)
    for nombre, ruta in m.RUTAS_ESTATICAS.items()
}

st.markdown("**① El mapa: los vértices y las aristas de la tabla**")
vertices_latex = ",\\ ".join(m.NODOS)
st.latex(
    rf"G=(V,E),\qquad V=\{{{vertices_latex}\}}"
    rf"\quad(\lvert V\rvert={len(m.NODOS)})"
)
aristas = [
    m.nombre_enlace(str(origen), str(destino))
    for origen, destino in zip(enlaces["Origen"], enlaces["Destino"])
]
st.markdown(
    f"**Aristas (enlaces) — {len(aristas)}:** " + ", ".join(aristas)
)
filas_aristas = []
for _, fila in enlaces.iterrows():
    u, v = str(fila["Origen"]), str(fila["Destino"])
    retardo, banda, activo = m.datos_enlace(enlaces, u, v)
    filas_aristas.append(
        {
            "Arista": m.nombre_enlace(u, v),
            "Extremos {i, j}": f"{{{u}, {v}}}",
            "d_ij": f"{retardo:g} ms",
            "b_ij": f"{banda:g} Mbps",
            "f_ij": "1 (activo)" if activo else "0 (caído)",
            "¿En PSRC?": (
                "sí"
                if (u, v) in m.pares_ruta(PSRC) or (v, u) in m.pares_ruta(PSRC)
                else "—"
            ),
        }
    )
st.dataframe(pd.DataFrame(filas_aristas), hide_index=True, width="stretch")
st.caption(
    f"Cada extremo es un par no ordenado {{i, j}}: el enlace funciona en los "
    f"dos sentidos. Son {len(aristas)} aristas para {len(m.NODOS)} vértices. "
    "Cada celda lleva la unidad de su variable: ms, Mbps y el booleano 1/0; la "
    "columna «Arista» es la misma que usarás al sumar $w_{ij}$."
)

st.markdown("**② Las referencias salen de la propia tabla**")
st.latex(
    rf"d_{{ref}}=\max\{{d_{{ij}}>0\}}={d_ref:g}\ \text{{ms}}"
    rf"\qquad b_{{ref}}=\max\{{b_{{ij}}>0\}}={b_ref:g}\ \text{{Mbps}}"
)
st.latex(
    rf"\alpha+\beta+\gamma={pesos[0]:.2f}+{pesos[1]:.2f}+{pesos[2]:.2f}=1"
)
st.caption(
    f"El retardo más grande de la tabla es {d_ref:g} ms y la banda más grande "
    f"es {b_ref:g} Mbps. Al dividir entre ellos, todos los términos quedan sin "
    "unidades y se pueden sumar."
)

st.markdown("**③ El precio de un enlace: fórmula y caso H–E**")
st.caption("General, con la unidad de cada variable entre corchetes")
st.latex(
    r"w_{ij}=\alpha+\beta\,\frac{d_{ij}\ [\text{ms}]}{d_{ref}\ [\text{ms}]}"
    r"+\gamma\,\frac{b_{ref}\ [\text{Mbps}]}{b_{ij}\ [\text{Mbps}]}"
)
st.caption("Con los números de H–E")
st.latex(
    rf"w_{{HE}}={pesos[0]:.2f}+{pesos[1]:.2f}\cdot"
    rf"\frac{{{d_he:g}\ \text{{ms}}}}{{{d_ref:g}\ \text{{ms}}}}"
    rf"+{pesos[2]:.2f}\cdot"
    rf"\frac{{{b_ref:g}\ \text{{Mbps}}}}{{{b_he:g}\ \text{{Mbps}}}}"
    rf"={w_he:.3f}"
)
st.caption(
    f"H–E es de {b_he:g} Mbps: como es más angosto que b_ref = {b_ref:g} Mbps, "
    f"su término de banda vale {pesos[2] * b_ref / b_he:.3f}. Ese es el castigo "
    "por cuello de botella que ves en la tabla."
)

st.markdown("**④ Las métricas de una ruta: fórmula general y los tres casos**")
col_h, col_d, col_b = st.columns(3, gap="large")
with col_h:
    st.latex(r"H(P)=\sum_{(i,j)\in P}h_{ij}=\lvert P\rvert-1")
with col_d:
    st.latex(r"D(P)=\sum_{(i,j)\in P}d_{ij}")
with col_b:
    st.latex(r"B(P)=\min_{(i,j)\in P}b_{ij}")
st.markdown(
    "| Ruta | Secuencia | $H(P)$ | $D(P)$ | $B(P)$ |\n"
    "|:--|:--|:--|:--|:--|\n"
    + "\n".join(
        f"| {nombre} | {m.formato_secuencia(ruta)} | "
        f"{sustituciones[nombre]['saltos']} | "
        f"{sustituciones[nombre]['retardo']} | "
        f"{sustituciones[nombre]['banda']} |"
        for nombre, ruta in m.RUTAS_ESTATICAS.items()
    )
)
st.caption(
    "Los saltos se cuentan con 1 por enlace; el retardo se suma; la banda NO se "
    "suma: se toma el mínimo, porque ese es el cuello de botella de la ruta."
)

st.markdown("**⑤ El costo de la ruta: fórmula general y el caso PSRC**")
st.latex(
    r"C(P)=\sum_{(i,j)\in P}\left[\alpha+\beta\,\frac{d_{ij}\ [\text{ms}]}{d_{ref}\ [\text{ms}]}"
    r"+\gamma\,\frac{b_{ref}\ [\text{Mbps}]}{b_{ij}\ [\text{Mbps}]}\right]"
)
st.markdown(
    f"En palabras: para cada enlace de la ruta sumas **{pesos[0]:.2f}** por "
    f"usarlo, **{pesos[1]:.2f}** por su retardo medido contra {d_ref:g} ms, y "
    f"**{pesos[2]:.2f}** por lo estrecho que sea frente a {b_ref:g} Mbps."
)
st.latex(_latex_costo_ruta(enlaces, PSRC, pesos, d_ref, b_ref, "PSRC"))
st.markdown(
    "**Los tres casos, de un vistazo**\n\n"
    "| Ruta | Suma de $w_{ij}$ | $C(P)$ |\n"
    "|:--|:--|--:|\n"
    + "\n".join(
        f"| {nombre} | {sustituciones[nombre]['cadena']} | "
        f"{float(sustituciones[nombre]['costo']):.3f} |"
        for nombre in m.RUTAS_ESTATICAS
    )
)
st.caption(
    f"Con los controles de ahora el menor es {ganadora['Ruta']} "
    f"({float(ganadora['C']):.3f}). $C(P)$ no lleva unidad: es un puntaje "
    "adimensional, y la suma de PSRC es la misma que verás en la tabla de "
    "acumulados del caso avanzado."
)

costos_rutas = [
    float(sustituciones[nombre]["costo"]) for nombre in m.RUTAS_ESTATICAS
]
st.markdown("**⑥ La ruta elegida: el mínimo de esos costos**")
st.latex(r"P^{*}=\arg\min_{P\in\mathcal{P}(H,B)}\ C(P)")
st.latex(
    rf"P^{{*}}=\arg\min\{{C(\text{{PSRC}}),C(\text{{SSRC}}),"
    rf"C(\text{{TSRC}})\}}=\arg\min\{{{costos_rutas[0]:.3f},\ "
    rf"{costos_rutas[1]:.3f},\ {costos_rutas[2]:.3f}\}}"
    rf"=\text{{{ganadora['Ruta']}}}"
)
st.caption(
    "Este mínimo es entre las tres rutas del artículo; con Dijkstra sobre todo "
    "el grafo puede aparecer otra más barata. La comparación completa está en "
    "el caso avanzado."
)

st.markdown("**⑦ La decisión del router: fórmula y caso de H**")
st.latex(
    r"\pi(v)=\arg\min_{u\in N(v)}\left[c(v,u)+d(u)\right],\qquad d(B)=0"
)
grafo_mc = m.construir_grafo(enlaces, "multicriterio", pesos)
siguiente, distancias, _ = m.sink_tree(enlaces, "multicriterio", pesos)
opciones_h: list[dict[str, object]] = []
for vecino in sorted(grafo_mc.neighbors(m.ORIGEN)):
    if vecino not in distancias:
        continue
    costo_enlace = float(grafo_mc[m.ORIGEN][vecino]["peso"])
    resto = float(distancias[vecino])
    opciones_h.append(
        {
            "Vecino u": vecino,
            "c(H,u)": round(costo_enlace, 3),
            "d(u)": round(resto, 3),
            "c + d": round(costo_enlace + resto, 3),
        }
    )
if opciones_h:
    st.dataframe(pd.DataFrame(opciones_h), hide_index=True, width="stretch")
if "H" in siguiente:
    elegido = siguiente["H"]
    costo_elegido = float(grafo_mc[m.ORIGEN][elegido]["peso"])
    resto_elegido = float(distancias[elegido])
    opciones_latex = ",\\ ".join(
        f"({fila['c(H,u)']:.3f}+{fila['d(u)']:.3f}={fila['c + d']:.3f})"
        for fila in opciones_h
    )
    st.latex(rf"\pi(H)=\arg\min\{{{opciones_latex}\}}=\text{{{elegido}}}")
    st.latex(
        rf"d(H)=c(H,{elegido})+d({elegido})={costo_elegido:.3f}+"
        rf"{resto_elegido:.3f}={costo_elegido + resto_elegido:.3f}"
    )
    st.caption(
        f"En palabras: H solo guarda «para B, sal por {elegido}»; el resto del "
        f"camino ya está resuelto por d({elegido}) = {resto_elegido:.3f}. Por "
        f"eso d(H) = {costo_elegido + resto_elegido:.3f} es el costo de la ruta "
        "óptima completa."
    )
st.caption(
    "El árbol T_B tiene una flecha por router distinto de B "
    f"({len(siguiente)} en este caso); en la app principal lo ves dibujado."
)

st.divider()


# ---------------------------------------------------------------------------
# 5 · Caso básico
# ---------------------------------------------------------------------------

st.header("5 · Caso básico: solo saltos (lo mínimo)")
st.markdown(
    "Si lo único que te importa es **cuántos routers atraviesas**, cada enlace te "
    "vale exactamente 1 y la fórmula se reduce a contar:"
)
st.latex(r"H(P)=\sum_{(i,j)\in P} h_{ij}=|P|-1,\qquad h_{ij}=1")

st.markdown(
    f"""
| Ruta | Recorrido | Saltos $H(P)$ | Cuenta |
|:--|:--|--:|:--|
| PSRC | H → D → A → B | 3 | 1 + 1 + 1 |
| SSRC | H → E → J → C → B | 4 | 1 + 1 + 1 + 1 |
| TSRC | H → O → N → J → C → B | 5 | 1 + 1 + 1 + 1 + 1 |
"""
)

st.success(
    "**Gana PSRC (H–D–A–B) con 3 saltos.** Este es tu criterio mínimo: no "
    "necesitas medir retardos ni capacidades, solo conocer la topología y qué "
    "enlaces están activos."
)

st.markdown(
    "**Cuándo te alcanza:** cuando todos los enlaces son parecidos y solo quieres "
    "llegar con el menor número de routers. Es tu primera aproximación y la más "
    "fácil de explicar."
)
st.warning(
    "**Qué te deja fuera:** un enlace de 40 ms y 5 Mbps te cuenta igual que uno de "
    "1 ms y 1 Gbps. Con los datos iniciales, si H–D pasa a 40 ms, PSRC **sigue "
    "ganando por saltos** (3 contra 4), aunque su retardo sube a 56 ms frente a "
    "los 29 ms de SSRC. Los saltos no ven ese problema: para eso tienes el caso "
    "avanzado."
)

st.divider()


# ---------------------------------------------------------------------------
# 6 · Caso avanzado
# ---------------------------------------------------------------------------

st.header("6 · Caso avanzado: saltos + retardo + banda")
st.markdown(
    "Aquí cada enlace tiene **tres precios en uno**. Con los controles de la "
    "barra izquierda cambias los pesos y el retardo de H–D sin tocar el código."
)

col_ref_1, col_ref_2, col_ref_3 = st.columns(3)
col_ref_1.metric("d_ref", f"{d_ref:g} ms", help="Retardo máximo de la tabla")
col_ref_2.metric("b_ref", f"{b_ref:g} Mbps", help="Banda máxima de la tabla")
col_ref_3.metric(
    "Pesos normalizados",
    f"{pesos[0]:.2f} / {pesos[1]:.2f} / {pesos[2]:.2f}",
    help="α / β / γ después de dividir entre su suma",
)
if pesos_invalidos:
    st.warning(
        "Tus pesos suman 0. Para no romper el cálculo aplico pesos iguales "
        "(1/3, 1/3, 1/3); el resultado no representa la escala que pediste."
    )

st.markdown("**Precio de cada enlace con los valores actuales**")
filas_enlaces = []
for _, fila in enlaces.iterrows():
    u, v = str(fila["Origen"]), str(fila["Destino"])
    retardo, banda, activo = m.datos_enlace(enlaces, u, v)
    en_ruta = (u, v) in m.pares_ruta(PSRC) or (v, u) in m.pares_ruta(PSRC)
    filas_enlaces.append(
        {
            "Enlace": m.nombre_enlace(u, v),
            "d_ij (ms)": retardo,
            "b_ij (Mbps)": banda,
            "w_ij": m.peso_objetivo(
                "multicriterio", retardo, banda, d_ref, b_ref, pesos
            ),
            "¿En PSRC?": "sí" if en_ruta else "—",
            "Activo": "sí" if activo else "no",
        }
    )
st.dataframe(
    pd.DataFrame(filas_enlaces),
    hide_index=True,
    width="stretch",
    column_config={
        "d_ij (ms)": st.column_config.NumberColumn("d_ij (ms)", format="%.1f"),
        "b_ij (Mbps)": st.column_config.NumberColumn("b_ij (Mbps)", format="%.0f"),
        "w_ij": st.column_config.NumberColumn("w_ij", format="%.3f"),
    },
)
st.caption(
    "Compara w_ij entre enlaces: el más caro es el que más castigan tus pesos "
    "actuales. Los enlaces de PSRC están marcados para que sigas la suma de abajo."
)

col_izq, col_der = st.columns(2, gap="large")

with col_izq:
    st.markdown("**PSRC, enlace por enlace**")
    desglose = m.desglose_ruta(enlaces, PSRC, "multicriterio", pesos)
    st.dataframe(
        desglose,
        hide_index=True,
        width="stretch",
        column_config={
            "d_ij (ms)": st.column_config.NumberColumn("d_ij (ms)", format="%.1f"),
            "b_ij (Mbps)": st.column_config.NumberColumn("b_ij (Mbps)", format="%.0f"),
            "w_ij": st.column_config.NumberColumn("w_ij", format="%.3f"),
            "Acumulado": st.column_config.NumberColumn("Acumulado", format="%.3f"),
        },
    )
    st.caption(
        "La última fila del acumulado es C(PSRC): exactamente la suma de los "
        "precios de sus tres enlaces."
    )

with col_der:
    st.markdown("**Las tres rutas del artículo**")
    tabla_rutas = pd.DataFrame(
        [
            {
                "Ruta": ("★ " if fila["Ruta"] == ganadora["Ruta"] else "")
                + str(fila["Ruta"]),
                "Secuencia": fila["Secuencia"],
                "Saltos": fila["H"],
                "Retardo (ms)": round(float(fila["D"]), 1),
                "Banda (Mbps)": round(float(fila["B"]), 0),
                "C(P)": round(float(fila["C"]), 3),
            }
            for fila in resultados
        ]
    )
    st.dataframe(
        tabla_rutas,
        hide_index=True,
        width="stretch",
        column_config={
            "Saltos": st.column_config.NumberColumn("Saltos", format="%d"),
            "Retardo (ms)": st.column_config.NumberColumn("Retardo (ms)", format="%.1f"),
            "Banda (Mbps)": st.column_config.NumberColumn("Banda (Mbps)", format="%.0f"),
            "C(P)": st.column_config.NumberColumn("C(P)", format="%.3f"),
        },
    )
    st.caption(
        "Ojo: las tres rutas son configuraciones predefinidas del artículo, no "
        "todas las rutas simples del grafo."
    )

st.success(
    f"**Gana {ganadora['Ruta']}** ({ganadora['Secuencia']}) con "
    f"C = {float(ganadora['C']):.3f}: "
    f"{float(ganadora['c_alpha']):.3f} por saltos + "
    f"{float(ganadora['c_beta']):.3f} por retardo + "
    f"{float(ganadora['c_gamma']):.3f} por banda."
)

figura = go.Figure()
for nombre, clave, color in (
    ("Saltos", "c_alpha", COLOR_SALTOS),
    ("Retardo", "c_beta", COLOR_RETARDO),
    ("Banda", "c_gamma", COLOR_BANDA),
):
    figura.add_bar(
        y=[
            f"{fila['Ruta']} · C = {float(fila['C']):.3f}" for fila in resultados
        ],
        x=[float(fila[clave]) for fila in resultados],
        name=nombre,
        orientation="h",
        marker_color=color,
        hovertemplate=f"%{{y}}<br>{nombre}: %{{x:.3f}}<extra></extra>",
    )
figura.update_layout(
    barmode="stack",
    height=340,
    margin=dict(l=8, r=8, t=8, b=8),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    xaxis_title="Costo C(P) — adimensional",
    yaxis=dict(autorange="reversed"),
)
st.plotly_chart(figura, width="stretch", config={"displayModeBar": False})
st.caption(
    "Cada barra es una ruta y cada color, un criterio. La barra más corta gana. "
    "Aquí ves de dónde sale tu costo: no de una sola métrica, sino de la suma."
)

if ruta_global:
    st.info(
        "**Comparación con el grafo completo:** la mejor ruta que calcula "
        f"Dijkstra es {m.formato_secuencia(ruta_global)} con C = {costo_global:.3f}. "
        "Puede coincidir o no con una de las tres rutas del artículo; por eso te "
        "doy las dos versiones."
    )

st.markdown("**Qué cambia al mover los pesos**")
st.markdown(
    "- Con **solo saltos** (1, 0, 0), la ruta más corta gana aunque sea lenta o estrecha.\n"
    "- Con **solo retardo** (0, 1, 0) y H–D en 40 ms, SSRC pasa al primer lugar: "
    "misma red, distinto criterio.\n"
    "- Con **solo banda** (0, 0, 1), PSRC gana porque todos sus enlaces son de "
    "100 Mbps y su penalización es 1 en cada tramo.\n"
    "- Con el reparto **equilibrado** (0.5, 0.35, 0.15), compensas las tres cosas."
)
st.caption(
    "Tienes estos atajos en la barra lateral. Cambia uno y observa la tabla, la "
    "barra y el mensaje del ganador: ese es el argumento central del método."
)

st.warning(
    "**C(P) no es el ancho de banda de la ruta.** El término γ·b_ref/b_ij es solo "
    "una penalización que te permite comparar y usar Dijkstra. La capacidad real "
    "del camino la informas aparte como B(P) = min b_ij. Y si cambias d_ref o "
    "b_ref, cambias la escala de todos los costos: anótalos al comparar escenarios."
)

st.markdown("**¿Cuál de los dos casos uso?**")
st.markdown(
    """
| Situación | Caso | Qué necesitas |
|:--|:--|:--|
| Todos los enlaces son parecidos o solo te importa llegar con pocos saltos | Básico: $H(P)$ | Topología y disponibilidad |
| Hay enlaces lentos o estrechos y debes justificar tu elección | Avanzado: $C(P)$ | $d_{ij}$, $b_{ij}$, pesos, $d_{ref}$ y $b_{ref}$ |
"""
)

st.divider()


# ---------------------------------------------------------------------------
# 7 · Preguntas frecuentes
# ---------------------------------------------------------------------------

st.header("7 · Preguntas frecuentes")

with st.expander("¿Por qué el ancho de banda no se suma?"):
    st.markdown(
        "Porque una ruta no puede transportar más que su enlace más angosto. Si un "
        "tramo es de 5 Mbps y el resto de 100 Mbps, tu ruta completa queda limitada "
        "a 5 Mbps: es un cuello de botella, no un total."
    )

with st.expander("¿Por qué pagas α en cada enlace?"):
    st.markdown(
        "Porque α representa lo que te cuesta atravesar un tramo. Una ruta de 3 "
        "enlaces paga 3α y una de 5 paga 5α; por eso, si subes α, favoreces las "
        "rutas con menos saltos. Es tu forma de meter el criterio «saltos» en la "
        "misma suma."
    )

with st.expander("¿Los pesos son objetivos?"):
    st.markdown(
        "No: son una decisión tuya como operador de la red. Lo que sí es objetivo "
        "es el cálculo una vez que fijas los pesos y las referencias. Por eso "
        "conviene que documentes α, β, γ, d_ref y b_ref junto con tus resultados."
    )

with st.expander("¿Qué pasa con el sink tree?"):
    st.markdown(
        "El mismo costo por enlace te permite calcular π(v) y el árbol T_B: cada "
        "router elige el vecino que minimiza el costo restante hasta B. En la app "
        "principal del proyecto (app.py) puedes ver ese árbol dibujado y su tabla "
        "de rutas."
    )

st.caption(
    "Estos son datos ilustrativos de laboratorio basados en Johal (2008). La "
    "fórmula multicriterio es una extensión docente: no la atribuyas al artículo."
)
