# comparador-luz-gas

El [comparador de ofertas de energía de la CNMC](https://comparador.cnmc.gob.es/) es
la única comparativa oficial de tarifas de luz y gas en España, pero solo se puede
usar rellenando su formulario web. Por debajo hay una API pública sin autenticación
que, para una consulta doméstica normal, pide **83 parámetros**.

Esto es un proxy con una API clara por delante: tres datos entran, JSON ordenado por
precio sale. Pensado para que lo llame un LLM o un script, sin pasar por la web.

```python
from comparador_luz_gas import Consulta, comparar

r = comparar(Consulta(codigo_postal="28013", consumo_anual_luz=2600, potencia=3.45))
r.ofertas[0]  # Oferta(comercializadora='CIDE HCENERGÍA S.A.U', importe_primer_anio=590.19, ...)
```

```bash
uv run comparador-luz-gas --cp 28013 --consumo 2600 --texto
```

Además hace dos cosas que la web no: lee el **QR de la factura** para no tener que
teclear nada, y dice en cada respuesta **qué comercializadoras grandes faltan**, que
es la trampa principal de este comparador.

## Instalación

```bash
uv sync                                  # solo la consulta
uv sync --extra facturas                 # + leer el QR de un PDF o imagen
sudo apt install libzbar0 poppler-utils  # lo que necesita ese extra
```

## La API

### `Consulta` — lo que preguntas

| campo | por defecto | qué es |
|---|---|---|
| `codigo_postal` | — | obligatorio, p. ej. `"28013"` |
| `consumo_anual_luz` | `0` | kWh/año |
| `consumo_anual_gas` | `0` | kWh/año |
| `potencia` | `3.45` | kW contratados |
| `suministro` | `"luz"` | `"luz"`, `"gas"` o `"ambas"` |
| `franjas` | `None` | `(punta, llano, valle)`; si falta, se reparte con el perfil 2.0TD |
| `vivienda` | `True` | `False` si el suministro no es doméstico |
| `permanencia` | `2` | `1` = solo ofertas sin permanencia |
| `servicios_adicionales` | `2` | `1` = solo ofertas sin servicios contratados aparte |

`comparar(consulta, timeout=90)` devuelve un `Resultado`. Es una sola petición HTTP:
tarda entre 3 y 8 segundos, que es lo que tarda la CNMC.

### `Resultado` — lo que devuelve

`r.ofertas` viene ordenado de más barato a más caro. `r.to_dict()` es lo que imprime
el CLI en JSON:

```jsonc
{
  "modo": "anual",
  "importes": "importe_primer_anio / importe_segundo_anio son el coste estimado de 12 meses.",
  "consulta": { "codigo_postal": "28013", "consumo_anual_luz": 2600.0, "reparto_franjas": [745, 639, 1216] },
  "cobertura": {
    "aviso": "El comparador de la CNMC solo incluye ofertas que...",
    "comercializadoras_en_resultado": 28,
    "comercializadoras": ["ADX RENOVABLES, S.L.", "..."],
    "grandes_ausentes": ["ENDESA", "IBERDROLA", "TOTALENERGIES", "..."]
  },
  "ofertas": [
    {
      "comercializadora": "CIDE HCENERGÍA S.A.U",
      "oferta": "Plan Estrella Dúo",
      "importe_primer_anio": 590.19,   // con el descuento de bienvenida
      "importe_segundo_anio": 640.9,   // ya sin él
      "permanencia": false,
      "servicios_adicionales": false,
      "verde": false,
      "validez": "Oferta válida solo para nuevos clientes",
      "precio_unico": true,
      "id_oferta": 7137
    }
  ],
  "alternativa_por_separado": null     // con suministro="ambas": luz + gas sueltos
}
```

Los importes **no llevan desglose de impuestos**: la CNMC no lo publica en esta
respuesta. Antes de cambiarte, confirma con la comercializadora si son con IVA.

### CLI

```bash
comparador-luz-gas --cp 28013 --consumo 2600                      # JSON
comparador-luz-gas --cp 28013 --consumo 2600 --texto --top 5      # tabla legible
comparador-luz-gas --cp 28013 --consumo 2600 --sin-permanencia
comparador-luz-gas --cp 28013 --consumo 2600 --consumo-gas 6000 --suministro ambas
comparador-luz-gas --factura factura.pdf --texto                  # datos del QR
comparador-luz-gas --factura factura.pdf --mensual --texto        # coste de esa factura
comparador-luz-gas --qr 'https://comparador.cnmc.gob.es/comparador/QRE?cp=...'
comparador-luz-gas --factura factura.pdf --solo-datos             # lee el QR y nada más
```

## Leer la factura: el QR, no el texto

Desde la Resolución de la CNMC de 24/06/2021 (modificada por
[BOE-A-2022-16989](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2022-16989)) **toda
factura de electricidad lleva un QR** que apunta al comparador con el suministro ya
desglosado:

```
https://comparador.cnmc.gob.es/comparador/QRE?cp=28013&pP1=4.6&pP2=4.6
   &caP1=740&caP2=660&caP3=757&cups=ES0000000000000000XX&imp=72.50&prE1=0.2288...
```

Código postal, potencias, consumo anual por franja, consumo y fechas del periodo
facturado, precios e importe: justo lo que pide el comparador. Como **el formato lo
fija la CNMC y no la comercializadora**, sirve para cualquier compañía — no hace
falta un parser por marca.

```python
from comparador_luz_gas import comparar, desde_fichero, desde_qr

f = desde_fichero("factura.pdf")  # PDF o imagen: localiza y decodifica el QR (~5 s)
f = desde_qr(texto_del_qr)  # si la app ya lo escaneó: solo urllib.parse
r = comparar(f.consulta())
```

`desde_qr()` no tiene dependencias, así que una app que escanee el QR con la cámara
puede mandar la cadena y saltarse el extra de imagen por completo.

**Si la factura está escaneada**, depende de a cuánto: el QR mide unos 3 px por módulo
a 300 dpi, justo en el límite de los decodificadores. 400 dpi aguanta JPEG, giro y
desenfoque; 300 dpi va bien salvo desenfoque; 200 dpi solo si está limpio; 150 dpi es
imposible. Los números y el porqué, en [docs/qr-escaneado.md](docs/qr-escaneado.md).

### Dos modos: anual y factura

Por defecto la CNMC estima el **coste de doce meses** a partir del consumo anual del
QR. Con `--mensual` (`f.consulta(mensual=True)`) calcula lo que habría costado **ese
periodo de facturación concreto**, con sus fechas y su consumo reales, así que sale
en la misma escala que el importe impreso en la factura:

```
Periodo 2026-07-14→2026-08-16: 146 kWh, pagaste 72.50 €.

  periodo  sin dto.  comercializadora                       oferta
    40.03     51.03  CIDE HCENERGÍA S.A.U                   Plan Estrella Dúo
    47.20     47.20  TRACTAMENT I SELECCIÓ DE RESIDUS, S.A. TARIFA FIJA CLÁSICA - 2.0TD
```

Dos avisos al leerlo:

- El importe de la factura incluye cosas que el comparador no cuenta: servicios
  adicionales, alquiler de equipos, bono social. El QR los desglosa (`impSA`,
  `finBS`); réstalos antes de comparar.
- La segunda columna es el mismo periodo **sin descuento de bienvenida**, no un
  segundo año. En el PVPC sale 0 porque no hay promoción que quitar.

En JSON, `"modo"` e `"importes"` dicen cuál de los dos es, para que un LLM no lea un
mes como si fuera un año.

## Valoración a largo plazo, sin LLM

`interpretar(resultado, anios=3)` (clave `"analisis"` del JSON de la CLI) es aritmética
sobre lo que ya devuelve la CNMC, pensada para que un LLM o una persona no lea mal el
ranking. El comparador ordena por `importe_primer_anio` y ese puesto lo gana casi
siempre una oferta de bienvenida, que **solo se cobra una vez**:

```python
from comparador_luz_gas import comparar, Consulta, interpretar

a = interpretar(comparar(Consulta(codigo_postal="28013", consumo_anual_luz=2200)), anios=3)
print(a["resumen"])
for aviso in a["avisos"]:
    print("-", aviso)
```

Devuelve el coste a N años de cada oferta (`primer_anio + (N-1) × siguientes`) y, sobre
todo, **separa las dos decisiones que el ranking mezcla**:

- `opciones.todas_las_horas_igual` vs `opciones.con_discriminacion_horaria`, con la
  diferencia ya calculada en `pregunta` — es lo que hay que preguntarle al usuario antes
  de recomendarle nada, porque una oferta por tramos solo compensa si va a mover consumo.
- Dentro de cada una, `sin_restriccion_de_nuevo_cliente`: la mejor que también puede
  contratar quien ya es cliente de esa comercializadora.

Más avisos derivados de los datos: permanencia y su penalización estimada, servicios
adicionales, y el PVPC frente a la mejor fija.

Un detalle que conviene no perder de vista: **las ofertas por tramos se valoran con tu
reparto punta/llano/valle actual**. Para saber si te compensaría mover consumo, repite la
consulta con el reparto que esperas tener (`--franjas`). En un caso real, mover 150 kWh al
año de punta a valle movía la mejor horaria de 660 € a 639 €: 8 € por debajo de la mejor
plana, después de reorganizar un año entero de lavadoras.

Lo que **no** hace, porque los datos no dan para ello: decir en qué mes del año conviene
cambiar. El catálogo no lleva fechas de alta ni de caducidad de las ofertas, solo el tipo
de cliente que admiten, y la CNMC no publica el histórico del comparador — hay una
[solicitud abierta en datos.gob.es](https://datos.gob.es/es/solicitud-de-datos/historico-de-ofertas-del-comparador-de-ofertas-de-la-cnmc)
desde septiembre de 2025, respondida con que esos datos no están en el catálogo de datos
abiertos. El momento lo marca tu permanencia, no el mercado.

### Consumo: la ventana importa

El QR trae los **12 meses rodantes**, que arrastran lo que consumías hace un año. Con
varias facturas a mano, `anualizar()` extrapola una ventana más corta y más parecida a hoy:

```python
from comparador_luz_gas import anualizar, desde_fichero

ultimas = [desde_fichero(p) for p in sorted(Path("facturas").glob("*.pdf"))[-6:]]
total, franjas = anualizar(ultimas)
```

Cambia el importe estimado, no tanto el ranking: la CNMC solo usa tus kWh y les aplica su
propio catálogo, así que lo que te haya subido tu comercializadora no entra en el cálculo.

## Método y limitaciones

Todo lo que devuelve este proyecto sale de la API oficial de la CNMC
(comparador.cnmc.gob.es): no hay estimación de precios propia, solo cuentas sobre lo
que ella responde. Es, con diferencia, la fuente más transparente que hay — pero eso
no la hace completa.

### No es un censo del mercado

La CNMC solo publica ofertas que las comercializadoras le remiten y que sus técnicos
validan una a una. Comprobado contra la API en vivo el 2026-09-23, sobre 20 códigos
postales:

- Presentes: Naturgy, Repsol, Galp, Octopus, Fenie, Nexus, Lumisa y ~45 más.
- **Iberdrola Clientes**: una sola oferta, solo gas (`Plan Gas Hogar RL2 online`).
- **Endesa Energía**: ninguna oferta, ni luz ni gas.
- TotalEnergies, Plenitude, Holaluz, EDP: ninguna.

Endesa e Iberdrola aparecen solo como `Comercializadora de referencia`, que es el
PVPC/TUR regulado de sus filiales obligadas por ley (Energía XXI, Curenergía).

Por eso cada respuesta lleva el bloque `cobertura`. La respuesta correcta a "¿cuál es
la mejor tarifa?" es *la mejor entre las verificadas por la CNMC*, no *la mejor que
existe*.

### Otras limitaciones

- **Sin desglose de impuestos**: los importes no llevan IVA desglosado; confírmalo con
  la comercializadora antes de cambiarte.
- **Sin histórico**: el catálogo no lleva fechas de alta ni caducidad de las ofertas,
  así que no se puede decir en qué mes conviene cambiar (más detalle en
  [Valoración a largo plazo](#valoración-a-largo-plazo-sin-llm)).
- **Las ofertas por tramos se valoran con TU reparto punta/llano/valle**, sacado del
  QR o de `anualizar()`. En Península, Illes Balears y Canarias, ese reparto asume los
  tramos 2.0TD que fija la Circular 3/2020, aplicables desde el 1/06/2021 (punta 10-14h
  y 18-22h, llano el resto del día laborable, valle 0-8h y festivos). Ceuta y Melilla
  usan horarios distintos. **Si vienes de una tarifa de discriminación horaria
  anterior** (p. ej. una "tarifa 8 horas" donde el valle lo elegías tú o lo fijaba la
  comercializadora, no el tramo 0-8h regulado), el reparto histórico de esas facturas
  no representa cómo caería ese consumo en los tramos *actuales* — la comparación de
  ofertas horarias hereda esa incertidumbre. Usa solo facturas posteriores al 1/06/2021
  si puedes.
- **El comparador aplica su catálogo de hoy a tus kWh**: una subida de precio de tu
  comercializadora actual no distorsiona la estimación, pero un cambio en tu propio
  consumo sí.

## Desarrollo

```bash
make sync && make lint && make test
make test-live       # consulta la API real
make test-facturas   # lee el QR de los PDFs de data/facturas/, si los hay
```

Las capturas HAR (`data/har/`) y las facturas (`data/facturas/`) están en
`.gitignore`: llevan CUPS, dirección y consumos reales. Los tests versionados usan un
QR inventado.
