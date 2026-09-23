# Session Handover

**2026-09-23 (tarde).** `main` en `368e519`, CI en verde. PR abierto:
[#9 docs: aclarar método y limitaciones](https://github.com/nuncaeslupus/comparador-luz-gas/pull/9)
(rama `docs/metodo-y-limitaciones`, `d536d89`), sin mergear todavía.

## Lo que se hizo

Sobre el análisis de facturas de la sesión anterior, esta sesión añadió una **capa de
interpretación a largo plazo** en `src/comparador_luz_gas/analisis.py`:

- `coste(oferta, anios)`: primer año + (N-1) × segundo año — el descuento de
  bienvenida se cobra una sola vez, así que el ranking por `importe_primer_anio` de la
  CNMC no es el ranking a largo plazo.
- `interpretar(resultado, anios=3)` separa dos decisiones que el ranking mezcla:
  precio plano vs. discriminación horaria (`opciones.todas_las_horas_igual` /
  `con_discriminacion_horaria`, con la diferencia ya calculada en `pregunta`), y dentro
  de cada una, la mejor oferta sin restricción de nuevo cliente si la mejor a secas
  exige serlo. Avisa de permanencia+penalización, servicios adicionales, PVPC vs. mejor
  fija, y siempre cierra con que **el catálogo no lleva fechas**, así que no se puede
  decir en qué mes conviene cambiar (confirmado por email de la CNMC vía una
  [solicitud en datos.gob.es](https://datos.gob.es/es/solicitud-de-datos/historico-de-ofertas-del-comparador-de-ofertas-de-la-cnmc)).
- Dos campos nuevos leídos de la respuesta cruda de la CNMC que antes se descartaban:
  `validez` → `Oferta.solo_nuevos_clientes` (41/80 "cualquier consumidor", 14/80 "solo
  nuevos clientes") e `importeEstimadoPenalizacion` → `Oferta.penalizacion_estimada`.
- `factura.anualizar(facturas)`: extrapola a 12 meses una ventana corta de facturas
  reales en vez de usar los 12 meses rodantes del QR (que arrastran consumo de hace un
  año). Útil cuando el consumo del usuario está cambiando.
- CLI: flag `--anios` (por defecto 3); la clave `"analisis"` del JSON y el resumen en
  modo `--texto` salen de `interpretar()`.
- README: sección "Valoración a largo plazo, sin LLM", y "Método y limitaciones"
  (sustituye a "Qué cubre el comparador, y qué no" ampliándola): dejar explícito que
  todo sale de la API de la CNMC sin estimación propia, impuestos sin desglosar, sin
  histórico, y — a raíz de una pregunta del usuario sobre su antigua "tarifa 8 horas"
  — que el reparto punta/llano/valle usado para valorar ofertas horarias asume los
  tramos regulados desde la Resolución de 24/06/2021 (valle 0-8h fijo); facturas de
  tarifas de discriminación horaria anteriores, donde el valle lo elegía el cliente o
  la comercializadora, no representan bien cómo caería ese consumo en los tramos de
  hoy.
- Corregido de paso: el README decía "CNMV" (regulador bursátil) en vez de CNMC.

**Aplicado al caso real del usuario** (no versionado, CP real usado en memoria, nunca
escrito a fichero): con su consumo real, PVPC gana por 15-19 €/año a la mejor fija
(TRACTAMENT, sin permanencia ni restricción de nuevo cliente, pero horaria). Recomendado
TRACTAMENT como opción sin riesgo de variabilidad, con el aviso de que su gap con PVPC es
pequeño y de que la comparación horaria depende de su reparto real, que en su caso viene
de facturas ya bajo los tramos regulados de 2021 (no de la tarifa 8 horas antigua).

## Decisiones que conviene no deshacer

- **`_rotacion()` da 1 oferta de nuevo cliente por comercializadora, no repetible.**
  Rotar exige ser cliente nuevo cada vez, así que una comercializadora solo cuenta una
  vez en el horizonte de años. (Corregí en la propia sesión una primera estimación que
  multiplicaba la misma oferta ×3, imposible.)
- **`_pregunta()` (plana vs. horaria) se calcula siempre con el reparto de la consulta
  actual**, nunca con un perfil genérico — si el usuario piensa mover consumo, tiene
  que repetir la consulta con `--franjas`, no fiarse del resultado guardado.
- **Modo factura no proyecta a varios años** (`interpretar()` devuelve solo `"nota"`):
  los importes de ese modo son de un periodo, no de un año.
- Ver también las decisiones de la sesión del QR en el historial de este mismo fichero
  (git log), sobre los dos decodificadores y los `_LADOS` de reintento — siguen vigentes,
  no se tocaron esta sesión.

## Estado de la cola

- `t-11b25b34` (issue #1) sigue abierta, `requires: [access:human]`. Queda: el QR de la
  **factura de gas** (¿existe un equivalente al `QRE`?) y validar el de luz con **otra
  comercializadora** (basta una factura de Endesa, Naturgy o Repsol).
- Pendiente de confirmar con la comercializadora, no del código: si `importe_primer_anio`
  lleva IVA. La respuesta cruda no trae ningún campo de impuestos.
- Ofrecido y no aceptado: un cron que capture el catálogo de la CNMC mensualmente, para
  que la pregunta "¿en qué mes conviene cambiar?" tenga respuesta dentro de ~12 meses.
- PR #9 sin mergear — solo README, sin cambios de código ni de tests.

## Privacidad

`data/facturas/` y `data/har/` siguen en `.gitignore`. El CP real del usuario (para las
consultas de recomendación de esta sesión) se usó solo en comandos sueltos, nunca escrito
a un fichero del repo — comprobado con `grep` antes de cada commit. Los ejemplos del
README y del código siguen usando CP 28013 y un CUPS inventado.
