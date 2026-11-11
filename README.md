# Sink Tree · Optimalidad de rutas

Aplicación interactiva en Python que explica visualmente el **sink tree** (árbol de
sumidero) de una red, sus variables y su modelo matemático. Está basada en la guía
de laboratorio sobre optimalidad y en el artículo de Johal (2008):

> Johal, H. S. (2008). *Optimality Principle Based Sink Tree Methodology for
> Adaptive Static Routing Using Multiple Route Configuration Scheme.*
> WCECS 2008. DOI: 10.1109/WCECS.2008.21.

El subgrafo modela 9 routers y estos 10 enlaces no dirigidos:

```
H–D   D–A   A–B
H–E   E–J   J–C   C–B
H–O   O–N   N–J
```

Rutas estáticas del artículo:

| Ruta | Recorrido | Saltos |
|:--|:--|:--|
| PSRC | H–D–A–B | 3 |
| SSRC | H–E–J–C–B | 4 |
| TSRC | H–O–N–J–C–B | 5 |

Estas tres rutas son configuraciones predefinidas del artículo, no todas las
rutas simples que contiene el subgrafo.

## Qué muestra la app

1. **Datos de entrada.** Tabla editable con retardo `d_ij` (ms), banda `b_ij`
   (Mbps) y disponibilidad `f_ij`. También muestra `d_ref`, `b_ref` y el número
   de enlaces activos.
2. **Modelo y camino óptimo.** Fórmulas de las tres funciones objetivo, grafo
   completo, ruta óptima recalculada con Dijkstra, comparación con las tres rutas
   estáticas y cálculo enlace por enlace.
3. **Sink Tree.** Árbol de siguientes saltos hacia B con flechas, costo acumulado
   por router y tabla de encaminamiento. Detecta empates y explica que el árbol
   puede no ser único cuando dos rutas cuestan lo mismo.
4. **Variables, experimentos y discusión.** Definiciones, los seis experimentos
   obligatorios, cálculos manuales, preguntas de discusión y exportación CSV.
5. **Guía y demo del algoritmo.** La guía, el demo ejecutable con su salida y
   el código fuente, con botones para descargar ambos archivos.

## Estructura

| Archivo | Contenido |
|:--|:--|
| `app.py` | Interfaz Streamlit y figuras Plotly |
| `presentacion.py` | Presentación interactiva: símbolos, uso, caso básico y caso avanzado |
| `model.py` | Grafo, métricas, Dijkstra y sink tree (sin Streamlit) |
| `sink_tree_demo.py` | Demo independiente con la versión básica (BFS) y la avanzada (Dijkstra) |
| `GUIA_SINK_TREE.md` | Guía concisa: teoría, pseudocódigo, comparación y límites |
| `requirements.txt` | Dependencias |
| `tests/test_model.py` | Pruebas de los valores del laboratorio |
| `tests/test_app.py` | Pruebas de humo de la interfaz con `AppTest` |
| `tests/test_presentacion.py` | Pruebas de humo de la presentación con `AppTest` |

## Guía y demo

`GUIA_SINK_TREE.md` resume el problema, la matemática, las implementaciones básica
y avanzada, la comparación, las tres rutas y las limitaciones. `sink_tree_demo.py`
es un archivo autocontenido (solo biblioteca estándar) que imprime los dos árboles
y los cálculos en la terminal:

```bat
python sink_tree_demo.py
```

## Instalación y ejecución (Windows)

Desde la carpeta del proyecto, en CMD o PowerShell:

```bat
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Se abre <http://localhost:8501>. Para la presentación explicativa de los símbolos
y el costo multicriterio (caso básico y caso avanzado):

```bat
python -m streamlit run presentacion.py
``` Si no se abre automáticamente, visita esa
dirección. Mantén la terminal abierta mientras uses la aplicación.

Alternativa con entorno virtual:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Requiere Python 3.10 o superior. Probado con Python 3.14, Streamlit 1.66,
NetworkX 3.7, Plotly 7.1 y pandas 3.1.

## Modelo matemático

Grafo no dirigido `G = (V, E)`, origen `s = H`, destino `t = B`. Una ruta simple
`P` usa solo enlaces disponibles (`f_ij = 1`).

```
min_P  H(P) = Σ_(i,j)∈P h_ij,   h_ij = 1
min_P  D(P) = Σ_(i,j)∈P d_ij
B(P) = min_(i,j)∈P b_ij
```

Costo multicriterio normalizado:

```
C(P) = Σ_(i,j)∈P [ α + β·(d_ij / d_ref) + γ·(b_ref / b_ij) ],
α + β + γ = 1
d_ref = max{d_ij > 0},   b_ref = max{b_ij > 0}
```

Los pesos de pantalla se normalizan dividiendo cada uno entre su suma. Todos los
términos son no negativos, así que el óptimo se obtiene con Dijkstra. La
penalización `b_ref / b_ij` permite usar Dijkstra, pero **no** es el ancho de banda
del camino: ese valor se calcula aparte como `B(P) = min b_ij`.

Sink tree con raíz en B:

```
π(v) = arg min_{u ∈ N(v)} [ c(v,u) + d(u) ]
d(v) = c(v, π(v)) + d(π(v)),   d(B) = 0
E_T  = { (v, π(v)) : v ∈ V \ {B} }
```

Si los costos son no negativos, seguir `π` desde cualquier router llega a B sin
bucles (principio de optimalidad). El árbol fija **un solo siguiente salto** por
router; no es la gráfica completa ni una lista de rutas de respaldo. Cuando dos
rutas empatan en costo, hay más de un sink tree válido. Con los datos iniciales,
por ejemplo, desde O se llega a B en 4 saltos tanto por H como por N; la app
señala ese empate y muestra una de las soluciones.

## Experimentos A–F

Los escenarios se aplican desde la barra lateral.

| Prueba | Acción | Evidencia esperada |
|:--|:--|:--|
| A · Réplica original | Escenario A, objetivo saltos | `H(P1)=3`, `H(P2)=4`, `H(P3)=5`; PSRC es la primera disponible y coincide con la óptima. |
| B · Cambio de retardo | H–D = 40 ms, objetivo retardo | `D(P1)=56`, `D(P2)=29`, `D(P3)=39` ms; la mejor de las tres es SSRC. |
| C · Fallo primario | H–D caído, objetivo saltos | PSRC se descarta; SSRC es la primera disponible (4 saltos). |
| D · Doble fallo | H–D y H–E caídos | TSRC queda como única ruta estática completa si sus enlaces siguen activos. |
| E · Cuello de botella | E–J = 5 Mbps | `B(P2)=5` Mbps; `C(P2)` sube por la penalización de banda, no por los saltos. |
| F · Cambio de pesos | `(1,0,0)`, `(0,1,0)`, `(0,0,1)`, `(0.5,0.35,0.15)` | Anota pesos normalizados, `d_ref`, `b_ref` y calcula `C(P)` a mano. |

Advertencia de la prueba B: el camino de menor retardo sobre **todo** el grafo
puede diferir del mejor de los tres caminos preconfigurados, porque existen
combinaciones adicionales de enlaces. Registra ambos resultados.

Cálculo manual inicial: `D(P1)=8+9+7=24 ms`, `D(P2)=5+10+8+6=29 ms`,
`D(P3)=7+9+9+8+6=39 ms`; `B(P1)=100 Mbps`, `B(P2)=B(P3)=50 Mbps`.
Con `α=0.5`, `β=0.35`, `γ=0.15`, `d_ref=10`, `b_ref=100`:
`C_HD = 0.5 + 0.35(8/10) + 0.15(100/100) = 0.93`.

## Exportación

La sección 4 descarga dos CSV:

- `resultados_rutas.csv`: las tres rutas estáticas y la óptima con `H`, `D`, `B`
  y `C`, más el objetivo activo, `d_ref`, `b_ref` y los pesos normalizados.
- `sink_tree.csv`: tabla de siguientes saltos con costo acumulado y ruta completa.

Los archivos usan BOM UTF-8 para que Excel muestre bien los acentos.

## Pruebas

```bat
python -m unittest discover -s tests -t . -v
```

Las pruebas verifican los valores de los seis experimentos, la optimalidad del
sink tree, los empates, el caso sin ruta y el arranque de la interfaz.

## Notas de alcance

Los retardos, capacidades y la función multicriterio son datos construidos para
el laboratorio; no son resultados experimentales del artículo. La aplicación
didáctica no implementa detección de fallos, instalación de rutas ni temporización
en routers reales.
