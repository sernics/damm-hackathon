# Preguntas Bloqueantes — Para llevar a los mentores de DDI

Las 7 preguntas que, sin respuesta, nos fuerzan a (a) inventar datos placeholder y bajar la credibilidad del pitch, o (b) construir la arquitectura equivocada y tener que rehacer trabajo.

Cada pregunta está explicada en lenguaje plano, con la razón operativa, el coste de no tener respuesta, y un párrafo concreto que puedes copiar/pegar al hablar con el mentor.

> **Actualización — primera sesión con mentor (2026-05-09):** mira la sección "Respuestas del mentor" justo abajo para el estado por pregunta. Después lee cada pregunta en su sección si necesitas el contexto completo.

---

## Sesión con mentor 2 (2026-05-09, segunda reunión) — actualizaciones grandes

La segunda sesión corrigió varias asunciones y añadió estructura nueva. Log completo en [`10_mentor_session_2.md`](10_mentor_session_2.md). Deltas clave por pregunta:

- **Q1 (dimensiones de camión)**: Siguen sin medidas exactas en L x A x H ni kg. Pero: los palets se pueden **arrastrar de un hueco intermedio al trasero** (las divisiones internas son articuladas), y solo **2-4 paradas con palet entero** por ruta son realistas. **El peso NO es restricción dura** — modelar en cajas, no en kg.
- **Q3 (retornables)**: Sigue pendiente la aclaración sobre los `3ENV0xxx`.
- **Q4 (flexibilidad de picking)**: Re-layout = cambiar el **mapeo SKU↔Ubicación**, NO mover estanterías. El picking se puede romper hoy: "barrido global alfabético + carro dedicado por cliente prioritario" es una adaptación viable, no un moonshot.
- **Q5 (camión/ruta)**: **El binomio conductor-camión es estable** (no se reasigna a diario). El jefe de tráfico asigna ruta a un (conductor, camión) ya fijado. **Restricción de carnet** (nivel 1/2/3) sobre qué camiones puede llevar cada conductor.
- **Q6 (tiempos)**: Primer camión sale a las 06:00 (duro). La hora de regreso es **blanda**, sin deadline fijo.
- **Q7 (compatibilidad)**: "Cajas sobre barriles" es **penalización blanda, no prohibición dura**.
- **Dirección del pitch**: El mentor explícitamente plantea el problema como **equilibrio entre coste de picking y coste de reparto, no minimizar solo reparto**.

Nuevos compromisos arquitectónicos después de esta sesión:

1. Función de coste conjunta (almacén + reparto), no solo reparto.
2. Cajas como unidad, no kg.
3. Paradas con palet entero limitadas a 4 por ruta.
4. Categoría de carnet como restricción dura camión-conductor.
5. Super-paradas por cluster de clientes en el routing (patrón "aparcar y caminar").
6. "Que cualquier conductor rinda como un veterano en cualquier ruta" como titular del pitch.

Follow-ups abiertos añadidos a QUESTIONS.md como Q43-Q48 (valores exactos del carnet, acceso al maestro de conductores, distancia interior del cliente, qué significa "400 son las básicas", confirmar 4 alturas por palet, estatus retornable de los 3ENV).

---

## Respuestas del mentor — sesión 1 (2026-05-09)

### Q1 — Dimensiones de camión: `[PARCIAL]`
No nos dan medidas en metros ni kg. Pero sale una regla operativa nueva grande (ver Q4) y una regla de bolsillo: **~60 cajas por palet**. Falta seguimiento para L x A x H, kg máximo, doble altura y disposición de las lonas.

### Q2 — Orden real de visita / Prioridad Viaje: `[RESPONDIDA — y es mala noticia]`
El campo `Nº Prioridad VIAJE` existe pero **DDI no nos lo puede enseñar**: "esa ruta no la podemos ver, para comparar". Y literal: "no tiene visto tampoco ningún registro de cuál fue el orden real que hizo en la ruta para saber cómo lo hacían". O sea: **el baseline histórico no se puede reconstruir**. El conductor decide en autónomo cada mañana basándose en experiencia. Implicación: no podemos construir una comparativa "hoy vs. optimizado" desde datos reales — tenemos que inventarnos un baseline sensato (p.ej. orden geográfico naive o el orden de filas como proxy) y ser transparentes en el pitch.

### Q3 — Retornable lleno vs vacío: `[RESPONDIDA]`
"Las cajas son apilables y ocupan lo mismo vacías que llenas, lo único que pesan menos. Y los barriles igual." Aclaración importante: **lo único retornable son cajas de vidrio y barriles**. Latas, productos de limpieza, licores → NO retornables. Esto contradice nuestra hipótesis sobre los `3ENV0xxx` (que habíamos clasificado como envases retornables individuales): o el mentor simplificó, o esos `3ENV0xxx` van englobados dentro de "cajas" en su cabeza. **Pregunta de seguimiento obligada** (añadida a QUESTIONS.md).

### Q4 — Flexibilidad de picking: `[RESPONDIDA — abre la puerta]`
Hoy el orden alfabético por `Ubicación` es obligatorio "porque hemos optimizado el tipo del almacén, no del repartidor". **Pero**: "se puede desconfigurar el layout del almacén para que sea un poco más eficiente". El mentor sugiere él mismo una idea: **palets dedicados a clientes grandes geográficamente cercanos** ("cliente de 30 cajas, y otro de 20, y están cerca → puedes hacer un palé solo con eso"). Nuestra Opción 1 (zona de staging) y Opción 3 (re-layout parcial / palets dedicados) están sobre la mesa. Opción 2 (un viaje por cliente) queda implícitamente descartada.

### Q5 — Mapeo camión / ruta: `[PARCIAL — con una corrección importante]`
Un conductor hace **1–2 transportes al día, NO 9** — corrige el supuesto previo (lo que vimos en los datos deben ser casos límite, abonos o ruido). **9–20 clientes por transporte.** Si hace dos transportes en un día, recarga el mismo camión. Muy revelador: **la asignación camión↔ruta la hace manualmente el jefe de tráfico, sin herramienta**. Eso es una *segunda* oportunidad de optimización que merece la pena meter en el pitch. Sigue sin confirmar si existe el maestro vehículo↔ruta en SAP.

### Q6 — Tiempos: `[PARCIAL]`
- **Tiempo de picking: 50–60 min por camión (6 u 8 palets).**
- **Tiempo de descarga: aproximadamente 1.5× el tiempo de carga en el peor caso, depende mucho del cliente.**
- No hay timestamps SAP disponibles.
- Regalo útil: **los operarios de almacén son personas distintas de los conductores** — picking y conducción ocurren en paralelo, no en secuencia. Esto relaja muchísimo la restricción de "hora de cierre": el conductor no espera al picker, y el picker no espera al conductor.

### Q7 — Reglas de compatibilidad: `[RESPONDIDA SOMERAMENTE]`
"El orden del almacén ya está pensado para eso, no le pongo un barril encima de servilletas". El mentor básicamente dice que no nos preocupemos, las restricciones de compatibilidad ya están absorbidas en dónde vive cada SKU en el almacén. Flojo si queremos una lista rigurosa, pero suficiente para defenderlo en el pitch citando esa frase.

---

## Implicaciones en el plan (cambios después de esta sesión)

1. **Cambia la estrategia de baseline** (por Q2). No podemos comparar contra "la ruta real de hoy" porque no existe registro. En su lugar:
   - Usaremos un baseline sintético "geográfico naive" (TSP de mínima distancia, ignorando ventanas y carga) como "equivalente al hoy".
   - Usaremos el orden de filas en `Detalle_entrega.csv` como proxy *secundario* y dejaremos claro que "parece el orden sugerido por SAP, pero operaciones confirma que no es lo que mide".
   - Convertimos esa **ausencia de baseline en un *talking point* del pitch** — "descubrimos que DDI hoy no mide el orden real de visita, así que el paso uno para medir impacto es instrumentar esa telemetría".
2. **Decisión de arquitectura** (por Q4). Nos comprometemos con un híbrido: el picker mantiene un único barrido, pero deja en un pequeño número de bahías de staging (una por "cluster de entregas"), y promovemos clientes grandes-y-cercanos a **palets mixtos dedicados** siguiendo la propia sugerencia del mentor. Es exactamente el patrón de "palet mosaico" que ya vemos en las fotos del almacén.
3. **Modelo de retornables se simplifica** (por Q3). Para el cálculo de balance de volumen, tratamos *solo cajas de vidrio y barriles* como retornables. Reclasificamos nuestro mapeo de `3ENV0xxx` como "a confirmar". `0LM*` (limpieza), `0LI*` (licores), `0CF*` (café), latas — todos one-way.
4. **Restricción de cut-off se relaja** (por Q6). Con 50–60 min de picking corriendo en paralelo a la conducción, no necesitamos modelar un "tiene que estar hecho a la hora X" duro en el solver — el final de dispatch lo limita el volumen del camión × paradas, no la capacidad del almacén.
5. **Nueva oportunidad de optimización para el pitch** (por Q5). La asignación manual camión↔ruta del jefe de tráfico es ella misma una optimización que podemos demostrar como extensión "gratuita" — un pequeño problema de assignment encima del modelo de routing+packing. Barato de añadir, impacto visible.
6. **Q1 sigue parcialmente bloqueando**. Podemos seguir construyendo con las dimensiones placeholder, pero queremos una llamada de 5 min con cualquiera que conozca los camiones para fijar las dimensiones de la caja antes del pitch.

---

---

## 1. Dimensiones internas y reglas de cada tipo de camión

### Qué pedimos

Mollet opera 11 camiones de 6 palets, 4 camiones de 8 palets y 1 furgoneta de 3 palets. Para cada uno de esos tres tipos necesitamos:
- **Largo x ancho x alto interior** de la caja, en metros.
- **Carga máxima útil** en kg.
- Si se pueden **apilar dos palets en vertical** dentro del camión (un palet sobre otro), o si solo se apilan cajas sobre un palet de base.
- Disposición de las **lonas laterales**: cuántas secciones corredizas tiene cada lado y cuánto mide aproximadamente cada sección.

### Por qué lo necesitamos

El plan de carga es un problema 3D. No podemos colocar palets y pilas de cajas dentro de una caja sin saber las dimensiones reales de esa caja. Y peor: "doble altura de palet sobre palet" duplica el volumen efectivo del camión. Si asumimos una sola altura cuando realmente hay dos, la mitad de las rutas saldrán inviables por volumen y las redirigiremos al vehículo equivocado. Si asumimos dos alturas cuando solo hay una, propondremos planes que aplastan el palet inferior bajo el de arriba.

La disposición de las lonas importa porque el conductor abre las cortinas **por secciones**. Si la lona tiene 3 secciones y los productos de una parada están repartidos por las 3, el conductor abre 3 paneles en cada parada — más lento y más expuesto al clima/robo. Queremos alinear los bloques de cliente con las secciones de lona, pero no podemos si no sabemos cuántas hay.

### Coste si no la tenemos

Usamos los placeholders de [`05_fleet.md`](05_fleet.md) (estimaciones razonables basadas en camiones europeos de tonelaje medio). Lo que entreguemos lleva la coletilla "sujeto a confirmación de las dimensiones reales" — y si en el pitch nos preguntan por un camión concreto, hay que admitir que no lo sabemos.

### Frase concreta para el mentor

> "Para los camiones de Mollet — los de 6 palets, los de 8 palets y la furgoneta de 3 — ¿podríais darnos las dimensiones interiores de la caja (largo, ancho, alto en metros), la carga máxima útil en kg, y decirnos si se pueden apilar dos palets en vertical? Y también, ¿cuántas secciones corredizas tiene la lona por cada lado y cuánto miden?"

---

## 2. El campo "Nº Prioridad VIAJE", o confirmación de que el orden de filas en el CSV = orden real de visita

### Qué pedimos

Dentro de SAP, cada asignación (cliente, transporte) lleva un campo numérico llamado **`Nº Prioridad VIAJE`** — el orden de visita sugerido dentro de una ruta. El sistema lo tiene. No lo vemos en los CSVs que recibimos.

Necesitamos una de las dos cosas:
- El `Nº Prioridad VIAJE` expuesto como columna en `Detalle_entrega.csv` (o un dump puntual), O
- Confirmación de alguien de operaciones de que "el orden en que aparecen las líneas en este archivo es el orden real en el que el conductor entregó".

### Por qué lo necesitamos

Para demostrar que nuestra solución es *mejor*, necesitamos un baseline contra el que comparar — es decir, *qué hace el conductor hoy*. Si no podemos reconstruir el orden real de visita histórico, no tenemos contra qué comparar. Hemos inferido de los datos que el orden de filas en `Detalle_entrega.csv` parece geográficamente coherente (las zonas progresan monotónicamente en los transportes que probamos), pero es una hipótesis. Si resulta que el orden de filas es solo un `ORDER BY` por defecto de SAP y no el orden real, estaremos comparando nuestro óptimo contra una ficción.

### Coste si no la tenemos

Dos opciones, ambas malas. Opción A: damos por buena la hipótesis y un mentor crítico nos pilla en el pitch. Opción B: comparamos contra un "orden puramente geográfico" generado sintéticamente desde coordenadas — defendible, pero es un hombre de paja, no el proceso real.

Todo el criterio de "aplicabilidad real al contexto Damm" (30 % de la nota) depende de que entendamos lo que hacen hoy. Si ni siquiera podemos describir el orden de visita actual, esa parte del pitch queda débil.

### Frase concreta para el mentor

> "Necesitamos saber qué orden de visita siguió cada transporte históricamente. Dos preguntas: (1) ¿Está guardado a nivel línea el campo `Nº Prioridad VIAJE`? ¿Podríamos tenerlo como columna en los datos de `Detalle_entrega`? (2) Si no, ¿el orden de filas en `Detalle_entrega.csv` es el orden real de entrega o es simplemente el orden por defecto de SAP?"

---

## 3. Si un retornable vacío ocupa el mismo espacio físico que el lleno

### Qué pedimos

Alrededor del 60 % de lo que se entrega vuelve como retornable: cajas plásticas vacías (`CJ13`, `CJ15`, …), barriles inox vacíos (`BRL30V`, `BRL20V`, …), envases individuales vacíos (`3ENV0xxx`). 45 de estos SKUs retornables no tienen entrada en el maestro dimensional `ZM040`. Necesitamos saber si ocupan las mismas dimensiones exteriores que sus llenos y aproximadamente cuánto pesan vacíos.

En concreto:
- ¿Un `BRL30V` vacío (barril 30 L devuelto) ocupa el mismo perímetro exterior que un `ED30` lleno?
- ¿Una `CJ13` vacía (caja plástica) ocupa el mismo espacio exterior que una caja llena de `ED13`?
- Los `3ENV0xxx` (envases individuales retornables — botellas/vidrios) ¿vuelven apilados, paletizados, en bandejas?

### Por qué lo necesitamos

El camión **no se vacía durante la ruta**. Va intercambiando lleno → vacío en cada parada. Si lleno y vacío ocupan el mismo espacio, el intercambio es neutro en volumen y podemos tratar el hueco de cada cliente como "salió lleno, entró vacío" — limpio. Si los vacíos encajan más compactos (p.ej. 3 cajas vacías encajan en el espacio de 2 llenas), entonces el camión tiene espacio libre creciente que podemos usar para otra cosa.

Es el corazón de la parte de logística inversa del reto. Sin saber la respuesta, no podemos calcular con precisión el espacio disponible del camión en cada punto de la ruta.

### Coste si no la tenemos

Usamos la heurística de [`06_returnables.md`](06_returnables.md): vacío = mismo volumen que lleno. Probablemente correcto para cajas y barriles (mismo contenedor físico). Menos seguro para `3ENV0xxx` (envases individuales). Si nos equivocamos, el cálculo de espacio se desvía algún porcentaje a lo largo de la ruta.

### Frase concreta para el mentor

> "Cuando un cliente devuelve los vacíos — barriles vacíos, cajas plásticas vacías, envases individuales vacíos — ¿ocupan el mismo espacio físico que sus equivalentes llenos? Los retornables 3ENV0xxx (los envases individuales pequeños) cuando vuelven, ¿van paletizados o sueltos? ¿Y aproximadamente cuánto pesa un barril de 30 L vacío?"

---

## 4. Cuán flexible es el picking de almacén

### Qué pedimos

Hoy, cuando se prepara un transporte, un trabajador (el preparador / picker) recorre el almacén con una carretilla, recogiendo productos **por orden alfabético de ubicación**. Por eso la `Hoja Carga` está ordenada por `Ubicación` (`AA02A1 → AA03A1 → AA04A1 → … → ZCG`). La ventaja es que es exactamente **un único** paseo por el almacén. La desventaja es que el camión termina cargado por referencia (todas las Estrellas juntas, todos los barriles juntos), no por cliente — que es exactamente el problema que esta hackathon intenta resolver.

La pregunta es: ¿cuánto margen tenemos para cambiar este flujo de picking? Tres alternativas plausibles:

1. **Picking + zona de staging**: el picker sigue haciendo un único barrido alfabético, pero deja las cajas en N bahías de staging (una por cliente) en lugar de directo al camión. Otro operario carga cada bahía al camión en orden de ruta.
2. **Carro de picking por cliente**: el picker coge 18 carros (uno por cliente), camina por el almacén 18 veces, deja cada carro en el camión en orden de ruta. Un paseo por cliente.
3. **Re-layout del almacén**: reorganizar el almacén para que los SKUs de los clientes con más frecuencia queden geográficamente cerca. Pickear "por cliente" pasa a ser un paseo corto.

### Por qué lo necesitamos

Cada una de esas tres opciones tiene costes / disrupción / plazos de implementación radicalmente distintos:
- **Opción 1** (zona de staging) necesita espacio en planta y un handover extra de personal. Factible en semanas.
- **Opción 2** (carro por cliente) no necesita infraestructura pero multiplica el tiempo del picker por ~5–10x. Probablemente inaceptable.
- **Opción 3** (re-layout) es un proyecto de meses. Mucho dolor, mucho payoff.

Toda nuestra recomendación arquitectónica depende de cuál considere el mentor que es realista. Si diseñamos para la opción 1 y nos dicen "no, la zona de staging está llena de retornables que no podemos mover", rediseñamos. Si diseñamos para la opción 3 y nos dicen "no podemos reestructurar el almacén en años", igual.

### Coste si no la tenemos

Tenemos que describir las tres opciones en el pitch como una matriz de decisión y dejar que DDI elija. Es defendible pero diluye nuestra recomendación — parecemos indecisos en lugar de comprometidos.

### Frase concreta para el mentor

> "Hoy el picker recorre el almacén alfabéticamente por `Ubicación` y carga todo en el camión en ese orden. Para cargar el camión por cliente en lugar de por referencia, necesitaríamos o bien una zona de staging entre picker y camión, o un picker haciendo un viaje por cliente (mucho más lento), o un rediseño del layout del almacén. ¿Cuál de estas tres es operativamente viable en Mollet?"

---

## 5. Mapeo entre camión físico y ruta

### Qué pedimos

Los CSVs que tenemos no incluyen una columna que diga *qué camión hizo qué transporte*. Los PDFs muestran un único pareo (NºCarga 11764300 fue el vehículo V235045 / matrícula 7524KXX, ruta DR0027). Necesitamos un maestro que nos dé:
- Vehículo (3P / 6P / 8P) por transporte (o por ruta).
- Y, dado que los conductores hacen hasta 9 transportes por día, si el mismo camión se reutiliza entre transportes consecutivos del mismo conductor.

### Por qué lo necesitamos

Para verificar que un transporte es factible tenemos que comparar su volumen / peso contra la capacidad del camión asignado. Si no sabemos qué camión es, o sobre-prometemos (carga > capacidad → inviable en la realidad, queda mal en el pitch) o subestimamos (lo metemos al camión grande "por si acaso", desperdiciando oportunidad).

El routing también depende: una furgoneta de 3 palets pasa por calles estrechas urbanas donde un camión de 8 palets no puede. Si no sabemos qué camión hace cada ruta, las distancias también están mal.

### Coste si no la tenemos

Asignamos camiones heurísticamente: volumen típico de la ruta en m³ → camión más pequeño que entra → listo. Defendible, pero si la heurística diverge de la asignación real en un caso concreto, parecemos despistados.

### Frase concreta para el mentor

> "¿Existe un maestro que vincule cada ruta (o cada transporte) al vehículo concreto que la hizo — incluyendo el tipo (furgoneta de 3 palets, camión de 6, camión de 8)? Y cuando un conductor hace varios transportes en un día, ¿cambia de camión entre ellos?"

---

## 6. Tiempos reales de la operación (o, idealmente, los timestamps en bruto de SAP)

### Qué pedimos

Para cuantificar el impacto esperado de la solución necesitamos números aproximados de:
- **Tiempo de picking**: cuánto se tarda en preparar un transporte en almacén (en minutos).
- **Tiempo de descarga por parada**: cuánto está el conductor en cada cliente (parada grande vs. parada pequeña).
- **Tiempo de viaje** dentro de una zona vs. entre zonas.
- **Hora de cierre**: a qué hora debe estar el camión de vuelta en base.

La alternativa mucho mejor: **los timestamps del ciclo de vida del transporte en SAP**. SAP guarda 6 timestamps por transporte — `Register`, `Load start`, `Load end`, `Dispatch`, `Transport start`, `Transport end`. Con esos para, digamos, 50–100 transportes históricos, calculamos lo de arriba empíricamente y no necesitamos preguntar a nadie por benchmarks.

### Por qué lo necesitamos

Nuestro pitch necesita un número. "Ahorramos un 12 % de tiempo de descarga" o "reducimos 3 km por ruta" suena concreto y creíble. "Ahorramos aproximadamente algunos minutos" suena amateur. El 20 % de la nota correspondiente al *impacto potencial* depende de esto.

### Coste si no la tenemos

Hacemos estimaciones desde industrias análogas (una entrega típica HORECA es 10 min por parada, etc.) y las ponemos con un "sujeto a validación con los tiempos reales de DDI". El pitch sigue siendo defendible, pero queda claro que es un modelo corrido sobre inputs asumidos en lugar de sobre vuestros datos.

### Frase concreta para el mentor

> "Para nuestras estimaciones de impacto nos vendría genial tener medias aproximadas: cuánto se tarda en pickear un transporte, cuál es el tiempo típico de descarga por parada, cuánto dura una ruta desde que sale de Mollet hasta que vuelve. Mejor aún: ¿sería posible obtener los timestamps SAP `Register / Load start / Load end / Dispatch / Transport start / Transport end` de algunos transportes históricos — digamos una muestra de 50–100 días? Con eso nosotros calculamos todo."

---

## 7. Reglas duras de compatibilidad de productos y seguridad de carga

### Qué pedimos

El conductor y el personal de almacén tienen un conjunto tácito de reglas sobre qué puede o no puede ir junto a o encima de qué — refinadas durante años de botellas rotas, cajas aplastadas y cargas inestables. Necesitamos verlas por escrito. Concretamente:
- ¿Se puede apilar vidrio frágil (botellas retornables) debajo de barriles (los barriles de 30 L pesan ~30 kg cada uno)? ¿O siempre vidrio arriba, barriles abajo?
- ¿Se requiere por normativa o política DDI separar físicamente productos de limpieza de comida y bebida?
- Latas a presión (cerveza en lata, refrescos) sobre o bajo vidrio retornable — ¿alguna regla?
- Los SKUs de cadena de frío (`Ubic. = CAMARA`, p.ej. `CACAOLAT MINIBRIK`) — ¿necesitan una nevera/aislante dentro del camión, o viajan ambient asumiendo que se rompe la cadena?
- Centro de gravedad: ¿hay una regla escrita (pesados delante, frágiles detrás, distribuir peso lateral) o es solo intuición del conductor?

### Por qué lo necesitamos

Sin estas reglas nuestros planes de carga van a parecer mecánicamente correctos pero operativamente amateur. Un cargador con experiencia mira nuestro visual y dice "ahí no puedes poner eso, se va a romper" — y todo el 30 % de la nota correspondiente a *aplicabilidad* se hunde. Con ellas, las codificamos como restricciones duras en el packer y nuestros outputs son visiblemente sensatos.

### Coste si no la tenemos

Codificamos las obvias (pesados al suelo, frágiles arriba, sin químicos cerca de comida) y dejamos el resto como "a confirmar". El mentor puede pillar en el pitch alguna regla que faltaba.

### Frase concreta para el mentor

> "¿Cuáles son las reglas duras de cómo deben (o no deben) ir cargadas las cosas juntas? En concreto: ¿se puede vidrio bajo barriles, productos de limpieza pueden compartir espacio con comida y bebida, los productos de cadena de frío se cargan de manera distinta dentro del camión, y existe alguna regla escrita sobre distribución de peso / centro de gravedad?"

---

## Cómo usar este documento

Llévatelo a la próxima sesión con mentores de Damm/DDI. Imprímelo o envíalo de antemano. Las siete preguntas en este orden maximizan el valor de desbloqueo: 1, 2 y 5 desbloquean el modelado; 3 y 4 desbloquean la elección de algoritmo; 6 y 7 desbloquean la credibilidad del pitch.

Si solo es posible una sesión con el mentor, el orden de prioridad es:

> **Q4 (flexibilidad de picking) > Q1 (dimensiones del camión) > Q2 (orden de visita / Prioridad Viaje) > Q6 (timestamps) > Q3 (equivalencia retornable) > Q5 (mapeo de vehículos) > Q7 (reglas de compatibilidad).**

Por qué Q4 primero: determina toda la arquitectura. Con esa respuesta podemos empezar a diseñar en serio mientras las otras se contestan en asíncrono.
