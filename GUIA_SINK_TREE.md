# Sink Tree: información y código

El **sink tree** es un árbol de caminos mínimos con raíz en el destino **B**. Para
cada router fija un único siguiente salto hacia B. Se construye con un algoritmo
de caminos mínimos: **BFS** si todos los enlaces cuestan lo mismo, o **Dijkstra**
si los costos son no negativos y distintos.

No es un algoritmo único ni una lista de rutas de respaldo. Es una estructura de
encaminamiento: una flecha por router.

> Los retardos, capacidades y pesos son datos ilustrativos. La fórmula
> multicriterio es una extensión docente; no se ha verificado en el artículo de
> Johal y no debe atribuírsele.

**Referencia:** Johal, H. S. (2008). *Optimality Principle Based Sink Tree
Methodology for Adaptive Static Routing Using Multiple Route Configuration
Scheme.* WCECS 2008. DOI: 10.1109/WCECS.2008.21.

---

## 1. Qué es y para qué sirve

La red se representa con un grafo no dirigido `G = (V, E)`:

- `V`: routers.
- `E`: enlaces.
- `s = H`: origen.
- `t = B`: destino o sumidero.

Una ruta `P` es una secuencia de routers conectados, por ejemplo
`H → D → A → B`. Si tiene `N` routers y no repite ninguno, tiene `N − 1` enlaces.

El sink tree `T_B` cumple:

1. B es la raíz.
2. Cada router alcanzable tiene exactamente un camino hacia B.
3. No hay ciclos.
4. Cada router guarda solo `π(v)`, su siguiente salto.

Se llama *sink* porque B absorbe todo el tráfico: las flechas apuntan hacia B. En
una red real, el router H no necesita guardar `H–D–A–B`; solo guarda “para B,
salir por D”. D guarda “salir por A”, y A guarda “salir por B”.

**No es:** un algoritmo, la gráfica completa, una lista de todas las rutas ni un
mecanismo de respaldo.

---

## 2. Fundamento

El principio de optimalidad de Bellman dice:

> Si una ruta de `s` a `t` es óptima, cada subcamino también es óptimo desde su
> propio nodo hasta `t`.

Por eso cada router puede elegir su siguiente salto con una decisión local:

```text
π(v) = arg min_{u ∈ N(v)} [ c(v,u) + d(u) ]
d(v) = c(v, π(v)) + d(π(v))
d(B) = 0
```

- `N(v)`: vecinos de `v`.
- `c(v,u)`: costo del enlace.
- `d(u)`: costo acumulado desde `u` hasta B.
- `d(B) = 0`.

Si los costos son positivos, seguir `π` desde cualquier router llega a B sin
ciclos. Si dos vecinos empatan, hay más de un sink tree válido.

Johal (2008) utiliza el principio de optimalidad y el sink tree en una metodología
de rutas estáticas adaptativas. La fórmula multicriterio es una ampliación de
este laboratorio.

---

## 3. Variables y fórmulas

| Símbolo | Significado | Ejemplo `H → D → A → B` |
|:--|:--|:--|
| `G=(V,E)` | Grafo de routers y enlaces | 9 routers, 10 enlaces |
| `P` | Ruta simple | H → D → A → B |
| `N` | Routers de la ruta | 4 |
| `h_ij` | Costo por salto; vale 1 | 1 por enlace |
| `d_ij` | Retardo del enlace | H–D = 8 ms |
| `b_ij` | Capacidad del enlace | H–D = 100 Mbps |
| `f_ij` | Disponibilidad: 1 activo, 0 caído | `f_HD = 1` |
| `H(P)` | Número de saltos | 3 |
| `D(P)` | Retardo acumulado | 24 ms |
| `B(P)` | Capacidad mínima de la ruta | 100 Mbps |
| `C(P)` | Costo multicriterio | 2.790 |
| `α, β, γ` | Pesos de saltos, retardo y capacidad | 0.5, 0.35, 0.15 |
| `π(v)` | Siguiente salto hacia B | `π(H) = D` |
| `T_B` | Sink tree con raíz en B | árbol completo |
| `d(v)` | Costo acumulado desde `v` hasta B | 3 saltos desde H |
| `d_ref, b_ref` | Máximos para normalizar | 10 ms, 100 Mbps |

### Métricas

```text
H(P) = Σ h_ij = N − 1
D(P) = Σ d_ij
B(P) = min b_ij
C(P) = Σ [ α + β·(d_ij / d_ref) + γ·(b_ref / b_ij) ]
```

- `H(P)` cuenta enlaces, no routers.
- `D(P)` suma retardos.
- `B(P)` toma el mínimo: la ruta no puede transportar más que su enlace más
  estrecho. Las capacidades no se suman.
- `C(P)` suma un costo por enlace y se minimiza. Es adimensional.

### Problema de optimización

```text
P* = arg min_{P ∈ P(H,B)} Σ_{(i,j) ∈ P} w_ij

sujeto a: f_ij = 1 para todo enlace (i,j) de P
```

El sink tree resuelve el mismo problema para cada origen `v`. Cada ruta óptima
`v → B` aporta la arista `(v, π(v))`; la unión de todas es `T_B`.

| Modelo | Costo `w_ij` | Minimiza | Uso |
|:--|:--|:--|:--|
| Saltos | `1` | `H(P)` | Topología simple; primera aproximación |
| Retardo | `d_ij` | `D(P)` | Voz, video, tráfico interactivo |
| Multicriterio | `α + β(d_ij/d_ref) + γ(b_ref/b_ij)` | `C(P)` | Varias métricas a la vez |

### Costo multicriterio

- `α`: costo fijo por enlace. Un `α` alto favorece rutas con menos saltos.
- `β`: importancia del retardo.
- `γ`: penalización por baja capacidad.
- Los pesos se normalizan para que sumen 1.
- `d_ref` es el mayor retardo positivo de la tabla; `b_ref`, la mayor capacidad.
- `b_ref / b_ij` vale 1 en el enlace más rápido y crece si el enlace es más
  estrecho. Es una penalización, **no** el ancho de banda de la ruta.

Ejemplo con `α=0.5`, `β=0.35`, `γ=0.15`, `d_ref=10 ms`, `b_ref=100 Mbps`:

| Enlace | `d_ij` | `b_ij` | `w_ij` |
|:--|--:|--:|--:|
| H–D | 8 | 100 | `0.5 + 0.35(8/10) + 0.15(100/100) = 0.930` |
| D–A | 9 | 100 | `0.5 + 0.35(9/10) + 0.15(100/100) = 0.965` |
| A–B | 7 | 100 | `0.5 + 0.35(7/10) + 0.15(100/100) = 0.895` |

```text
C(P1) = 0.930 + 0.965 + 0.895 = 2.790
C(P2) = 0.975 + 1.150 + 0.930 + 0.860 = 3.915
C(P3) = 1.045 + 0.965 + 0.965 + 0.930 + 0.860 = 4.765
```

Si cambia `d_ref` o `b_ref`, todos los costos cambian de escala. Hay que anotar
los pesos y las referencias al comparar resultados.

---

## 4. Implementación básica: BFS

### Pasos

1. Representar routers y enlaces como un grafo no dirigido.
2. Identificar el destino B.
3. Asignar costo 1 a cada enlace disponible.
4. Ejecutar BFS desde B.
5. Registrar el padre de cada nodo como su siguiente salto.
6. Construir el árbol con las aristas `(v, π(v))`.

### Pseudocódigo

```text
función BFS_sink_tree(grafo, B):
    distancia[B] = 0
    siguiente = {}
    cola = [B]

    mientras cola no esté vacía:
        v = sacar el primero de la cola
        para cada vecino u de v:
            si u no está en distancia:
                distancia[u] = distancia[v] + 1
                siguiente[u] = v
                agregar u al final de la cola

    devolver distancia, siguiente
```

BFS explora por niveles. La primera vez que descubre un router es por el camino
con menos saltos. El padre en ese árbol es su siguiente salto hacia B. Como el
grafo es no dirigido, basta con ejecutar BFS una vez desde B para obtener las
rutas de todos los routers.

### Traza

| Router | Saltos a B | Siguiente salto |
|:--|--:|:--|
| B | 0 | — |
| A | 1 | B |
| C | 1 | B |
| D | 2 | A |
| J | 2 | C |
| H | 3 | D |
| E | 3 | J |
| N | 3 | J |
| O | 4 | H o N (empate) |

Complejidad: `O(V + E)` en tiempo y `O(V)` en memoria.

---

## 5. Implementación avanzada: Dijkstra multicriterio

Contar solo saltos ignora el retardo y la capacidad. Una ruta con menos saltos
puede ser más lenta o atravesar un cuello de botella.

### Pasos

1. Recolectar `d_ij`, `b_ij` y `f_ij`.
2. Calcular `d_ref = max(d_ij)` y `b_ref = max(b_ij)`.
3. Normalizar `α, β, γ` para que sumen 1.
4. Calcular `w_ij` de cada enlace.
5. Ejecutar Dijkstra desde B con esos costos.
6. Usar el padre de cada nodo como `π(v)` y construir el árbol.

```text
w_ij = α + β·(d_ij / d_ref) + γ·(b_ref / b_ij)
```

Los costos son no negativos, así que Dijkstra es aplicable.

### Pseudocódigo

```text
función Dijkstra_sink_tree(grafo, B):
    para cada nodo v:
        distancia[v] = infinito
    distancia[B] = 0
    siguiente = {}
    cola = [(0, B)]

    mientras cola no esté vacía:
        (costo_actual, v) = extraer el de menor costo
        si costo_actual > distancia[v]:
            continuar

        para cada (u, w) en vecinos(v):
            nuevo = costo_actual + w
            si nuevo < distancia[u]:
                distancia[u] = nuevo
                siguiente[u] = v
                insertar (nuevo, u) en la cola

    devolver distancia, siguiente
```

La cola de prioridad entrega siempre el router con menor costo acumulado. Si una
entrada vieja aparece con un costo mayor que el ya registrado, se ignora. Cuando
`nuevo` mejora `distancia[u]`, se actualiza y se registra `v` como padre.

### Costos del ejemplo

| Enlace | `d_ij` | `b_ij` | `w_ij` |
|:--|--:|--:|--:|
| H–D | 8 | 100 | 0.9300 |
| D–A | 9 | 100 | 0.9650 |
| A–B | 7 | 100 | 0.8950 |
| H–E | 5 | 50 | 0.9750 |
| E–J | 10 | 50 | 1.1500 |
| J–C | 8 | 100 | 0.9300 |
| C–B | 6 | 100 | 0.8600 |
| H–O | 7 | 50 | 1.0450 |
| O–N | 9 | 100 | 0.9650 |
| N–J | 9 | 100 | 0.9650 |

### Árbol resultante

| Router | Siguiente salto | Costo acumulado |
|:--|:--|--:|
| B | — | 0.0000 |
| C | B | 0.8600 |
| A | B | 0.8950 |
| J | C | 1.7900 |
| D | A | 1.8600 |
| N | J | 2.7550 |
| H | D | 2.7900 |
| E | J | 2.9400 |
| O | N | 3.7200 |

Diferencia con la versión básica:

```text
Básico:    O → H   (4 saltos)
Avanzado:  O → N   (costo 3.720)
```

`O → H` cuesta `1.045 + 2.790 = 3.835`; `O → N` cuesta
`0.965 + 2.755 = 3.720`. El árbol cambia porque el objetivo ya no es solo el
número de saltos.

Complejidad: `O((V + E) log V)` con cola de prioridad.

---

## 6. Comparación

| Aspecto | Básica | Avanzada |
|:--|:--|:--|
| Objetivo | Menos saltos | Menor retardo o menor `C(P)` |
| Datos | Topología y disponibilidad | Además `d_ij`, `b_ij`, pesos y referencias |
| Algoritmo | BFS | Dijkstra |
| Complejidad | `O(V + E)` | `O((V + E) log V)` |
| Ventaja | Simple y rápida | Considera retardo y capacidad |
| Límite | Ignora calidad del enlace | Pesos y referencias subjetivos |

Ambas calculan un solo siguiente salto por router, producen un árbol sin ciclos y
no crean respaldos por sí mismas.

---

## 7. Tres rutas y respaldos

| Ruta | Secuencia | `H(P)` | `D(P)` | `B(P)` | `C(P)` |
|:--|:--|--:|--:|--:|--:|
| PSRC | H → D → A → B | 3 | 24 ms | 100 Mbps | 2.790 |
| SSRC | H → E → J → C → B | 4 | 29 ms | 50 Mbps | 3.915 |
| TSRC | H → O → N → J → C → B | 5 | 39 ms | 50 Mbps | 4.765 |

Con los datos base, PSRC gana por saltos, retardo y costo multicriterio. Si
`H–D = 40 ms`, `D(P1) = 56 ms` y el objetivo retardo prefiere SSRC (29 ms).
El costo multicriterio cambia porque `d_ref` pasa a 40 ms: `C(P1) = 2.440` y
`C(P2) = 3.154`; con `α = 0.5`, el multicriterio sigue prefiriendo P1. La función
objetivo decide.

El camino de menor retardo sobre todo el grafo puede no ser una de las tres rutas
preconfiguradas, porque existen otras combinaciones de enlaces.

### Fallos

- Si cae `H–D`, PSRC deja de estar disponible y SSRC pasa a ser la primera ruta
  estática completa.
- Si también cae `H–E`, TSRC queda como única ruta estática completa si
  `O–N–J–C–B` sigue activa.
- SSRC y TSRC comparten `J–C–B`. Si ese segmento falla, fallan ambas.

Un sink tree no crea respaldos. Para tenerlos se necesita:

1. Calcular o configurar caminos alternativos.
2. Configurar rutas primarias, secundarias y terciarias.
3. Detectar fallos.
4. Seleccionar la ruta de reemplazo.
5. Instalarla y converger.

Una ruta estática no se activa automáticamente porque un enlace se caiga. Su
comportamiento depende de la configuración, la distancia administrativa y el
sistema de enrutamiento.

---

## 8. Limitaciones y conclusiones

- Los datos son ilustrativos, no resultados experimentales.
- La fórmula multicriterio es una extensión docente.
- `C(P)` es un puntaje; la capacidad real de la ruta es `B(P)`.
- El árbol es único solo si no hay empates.
- Un solo árbol no ofrece respaldos, balanceo ni rutas disjuntas.
- BFS requiere costos unitarios; Dijkstra, costos no negativos.
- El modelo no implementa detección de fallos, temporización ni instalación de
  rutas en routers reales.

Conclusiones:

1. El sink tree es un árbol de caminos mínimos con raíz en el destino; no es un
   algoritmo único.
2. BFS resuelve la versión de menos saltos.
3. Dijkstra resuelve la versión de retardo o multicriterio.
4. El principio de optimalidad explica por qué basta un siguiente salto por
   router.
5. Para desplegarlo en una red real hacen falta un plano de control, detección de
   fallos y rutas de respaldo.

---

## Ejecución

```bash
python sink_tree_demo.py
python -m streamlit run app.py
```
