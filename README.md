# comparador-luz-gas

<!-- mcp-name: io.github.nuncaeslupus/comparador-luz-gas -->

[![PyPI](https://img.shields.io/pypi/v/comparador-luz-gas)](https://pypi.org/project/comparador-luz-gas/)
[![CI](https://github.com/nuncaeslupus/comparador-luz-gas/actions/workflows/ci.yml/badge.svg)](https://github.com/nuncaeslupus/comparador-luz-gas/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![comparador-luz-gas MCP server – quality and maintenance score on Glama](https://glama.ai/mcp/servers/nuncaeslupus/comparador-luz-gas/badges/score.svg)](https://glama.ai/mcp/servers/nuncaeslupus/comparador-luz-gas)
<!-- claude-arsenal:attribution: added by claude-arsenal's /init. Delete this block to drop it (it is not put back), or set `attribution = false` in the arsenal config.toml. -->
[![Built with claude-arsenal](https://img.shields.io/badge/built%20with-claude--arsenal-d97756)](https://github.com/nuncaeslupus/claude-arsenal)
<!-- /claude-arsenal:attribution -->

<p align="center">
  <img src="https://raw.githubusercontent.com/nuncaeslupus/comparador-luz-gas/main/docs/hero.png" width="100%" alt="comparador-luz-gas: los 83 parámetros del formulario de la CNMC se quedan en tres datos, código postal, consumo y potencia, o el QR de la factura, y salen las ofertas ordenadas de más barata a más cara, con el aviso de qué comercializadoras grandes faltan">
</p>

**El comparador oficial de tarifas de luz y gas de la CNMC, como librería, CLI y servidor MCP.**

El [comparador de la CNMC](https://comparador.cnmc.gob.es/) es la única comparativa
oficial de ofertas de energía en España, pero solo se usa a través de un formulario web;
su API pública pide 83 parámetros por consulta. Este proyecto la reduce a tres datos
(código postal, consumo, potencia) o al QR de la factura, y devuelve las ofertas en JSON
ordenadas por precio, con un análisis a varios años y el aviso de qué comercializadoras
grandes no están en el comparador.

## Inicio rápido

```bash
uvx comparador-luz-gas --cp 28013 --consumo 2600 --texto --top 5
```

O instalado: `pip install comparador-luz-gas`. Para leer el QR de un PDF o una imagen,
`pip install "comparador-luz-gas[facturas]"` y `sudo apt install libzbar0 poppler-utils`.

## Ejemplo

Salida real (consulta del 2026-10-20; los precios cambian con el mercado):

```text
$ comparador-luz-gas --cp 28013 --consumo 2600 --texto --top 5
  1er año    2º año  comercializadora                       oferta
----------------------------------------------------------------------------------------------------
   653.02      0.00  Comercializadora de referencia         PVPC Histórico 19/10/2025 - 19/10/2026
   655.15    655.15  ENERGIA NUFRI SL                       ENERGIA NUFRI - CON HORARIOS
   657.85    721.45  niba                                   niba Zen
   661.53    661.53  ENERGIA NUFRI SL                       ENERGIA NUFRI - UNIVERSAL CON HORARIOS
   662.80    713.51  CIDE HCENERGÍA S.A.U                   Plan Estrella Dúo

70 ofertas de 28 comercializadoras.
No están en el comparador: ENDESA, IBERDROLA, TOTALENERGIES, HOLALUZ, EDP, GALP.
[...]

A 3 años, lo más barato es ENERGIA NUFRI SL «ENERGIA NUFRI - CON HORARIOS»: 1965.45 €
(655.15 €/año en régimen). ¿Prefieres pagar lo mismo a cualquier hora o puedes concentrar
el consumo en las horas baratas? Con tu reparto actual gana la discriminación horaria por
41.79 €: [...]
- La mejor a 3 años es solo para nuevos clientes: [...]
- El PVPC sale 2.13 € más barato al año que la mejor fija (653.02 € frente a 655.15 €),
  pero es variable: [...]
- 13 de 70 ofertas tienen permanencia (penalización de 16.87 a 37.42 €).
```

Sin `--texto` imprime JSON con las claves `modo`, `importes`, `consulta`, `cobertura`,
`ofertas`, `alternativa_por_separado` y `analisis`. Cada oferta:

```json
{"comercializadora": "Comercializadora de referencia", "oferta": "PVPC Histórico 19/10/2025 - 19/10/2026",
 "importe_primer_anio": 653.02, "importe_segundo_anio": 0.0, "permanencia": false,
 "servicios_adicionales": false, "verde": false, "validez": "Válida para consumidores con derecho a PVPC",
 "precio_unico": false, "id_oferta": 180, "penalizacion_estimada": 0, "solo_nuevos_clientes": false}
```

Desde Python:

```python
from comparador_luz_gas import Consulta, comparar, desde_fichero, interpretar

r = comparar(Consulta(codigo_postal="28013", consumo_anual_luz=2600, potencia=3.45))
r.ofertas[0]  # la más barata el primer año
r.to_dict()  # lo mismo que imprime el CLI
interpretar(r, anios=3)["resumen"]  # valoración a 3 años

r = comparar(desde_fichero("factura.pdf").consulta())  # todo desde el QR de la factura
```

## Uso con agentes de IA

### Servidor MCP

`comparador-luz-gas mcp` sirve el comparador por stdio, sin dependencias extra. Está en
el [registro oficial de MCP](https://registry.modelcontextprotocol.io) como
`io.github.nuncaeslupus/comparador-luz-gas`.

```json
{
  "mcpServers": {
    "comparador-luz-gas": { "command": "uvx", "args": ["comparador-luz-gas", "mcp"] }
  }
}
```

Para leer facturas del disco:
`"args": ["--from", "comparador-luz-gas[facturas]", "comparador-luz-gas", "mcp"]`.
También hay `Dockerfile` (`docker run -i --rm comparador-luz-gas`).

| herramienta | qué hace |
|---|---|
| `comparar_ofertas` | ofertas + análisis a largo plazo, como el JSON del CLI. Basta `qr`, o `cp` + `consumo` (luz); para gas, `suministro: "gas"` con `cp` + `consumo_gas`; para ambas, `suministro: "ambas"` con `cp`, `consumo` y `consumo_gas`; `max_ofertas` (20 por defecto) recorta la lista |
| `leer_factura_qr` | los datos del QR de una factura, sin consultar la CNMC |
| `leer_factura_archivo` | lee el QR de un PDF o imagen del disco (necesita el extra `facturas`) |

Los errores vuelven como `{"ok": false, "error": "ArgumentoInvalido", "message": "..."}`.

### Desde el CLI

Un agente sin MCP puede llamar al CLI: por defecto escribe JSON en stdout. `modo` e
`importes` dicen si los importes son anuales o de un periodo de factura, para que no se
confunda un mes con un año. Un argumento inválido sale con código 2 y el mensaje en
stderr.

## Cómo funciona

- **Una petición a la API oficial** de la CNMC (3-8 s, límite 90 s). No hay precios
  propios ni caché: solo cuentas sobre lo que responde la CNMC.
- **Lee el QR de la factura.** Desde la Resolución de la CNMC de 24/06/2021
  ([BOE-A-2022-16989](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2022-16989)) toda
  factura de luz lleva un QR con código postal, potencias, consumo anual por franja,
  periodo e importe. El formato lo fija la CNMC, así que vale para cualquier
  comercializadora. `desde_qr()` no tiene dependencias: una app que ya escaneó el QR le
  pasa la cadena.
- **Dos modos.** Por defecto, coste estimado de 12 meses. Con `--mensual`
  (`f.consulta(mensual=True)`), el coste del periodo concreto de la factura, comparable
  con el importe impreso.
- **Análisis a largo plazo** (`interpretar()`, clave `analisis`): coste a N años
  (`primer_anio + (N-1) × siguientes`), porque el primer puesto suele ganarlo un
  descuento de bienvenida que se cobra una vez. Separa precio único frente a
  discriminación horaria, señala las ofertas solo para nuevos clientes, la permanencia y
  su penalización, y el PVPC frente a la mejor fija.
- **Cobertura.** Cada respuesta lista las comercializadoras presentes y las grandes que
  faltan (`cobertura.grandes_ausentes`).
- **Anualizar.** `anualizar(facturas)` extrapola el consumo de varias facturas recientes
  en vez de usar los 12 meses rodantes del QR.

## CLI

```bash
comparador-luz-gas --cp 28013 --consumo 2600                      # JSON
comparador-luz-gas --cp 28013 --consumo 2600 --texto --top 5      # tabla
comparador-luz-gas --cp 28013 --consumo 2600 --sin-permanencia
comparador-luz-gas --cp 28013 --consumo 2600 --consumo-gas 6000 --suministro ambas
comparador-luz-gas --cp 28013 --consumo 2600 --franjas 600,700,1300 --anios 5
comparador-luz-gas --factura factura.pdf --texto                  # compara con los datos del QR
comparador-luz-gas --factura factura.pdf --mensual --texto        # coste de ese periodo
comparador-luz-gas --qr 'https://comparador.cnmc.gob.es/comparador/QRE?cp=...'
comparador-luz-gas --factura factura.pdf --solo-datos             # solo lee el QR
```

Otras opciones: `--potencia` (kW, 3,45 por defecto), `--empresa` (suministro que no es
vivienda). `comparador-luz-gas --help` las lista todas.

Campos de `Consulta`: `codigo_postal` (obligatorio), `consumo_anual_luz`,
`consumo_anual_gas`, `potencia` (3.45), `suministro` (`"luz"`, `"gas"`, `"ambas"`),
`franjas` (`(punta, llano, valle)`; si falta, perfil 2.0TD), `vivienda` (`True`),
`permanencia` y `servicios_adicionales` (`2`; `1` = solo ofertas sin ellos).

## Limitaciones

- **No es un censo del mercado.** La CNMC solo publica ofertas que las comercializadoras
  le remiten y valida. Comprobado el 2026-09-23 sobre 20 códigos postales: Endesa,
  TotalEnergies, Plenitude, Holaluz y EDP no tienen ofertas; Iberdrola, una de gas.
  Endesa e Iberdrola solo aparecen como `Comercializadora de referencia` (PVPC/TUR). El
  resultado es *la mejor entre las verificadas por la CNMC*.
- **Sin desglose de impuestos.** Confirma con la comercializadora si el importe lleva IVA.
- **La factura incluye cosas que el comparador no cuenta**: servicios adicionales,
  alquiler de equipos, bono social. El QR los desglosa (`impSA`, `finBS`); réstalos antes
  de comparar.
- **Las ofertas por tramos se valoran con tu reparto punta/llano/valle actual**, con los
  tramos 2.0TD de la Circular 3/2020 (vigentes desde el 1/06/2021; Ceuta y Melilla usan
  otros). Si piensas mover consumo, repite con `--franjas`. Si vienes de una tarifa de
  discriminación horaria anterior, usa solo facturas posteriores a esa fecha.
- **Sin histórico.** El catálogo no lleva fechas de alta ni caducidad, y la CNMC no
  publica el histórico, así que no se puede decir en qué mes conviene cambiar.
- **QR escaneado:** 400 dpi aguanta JPEG, giro y desenfoque; 300 dpi va bien salvo
  desenfoque; 200 dpi solo si está limpio; 150 dpi no se lee.

## Documentación

- [docs/qr-escaneado.md](docs/qr-escaneado.md): lectura del QR en facturas escaneadas,
  con las cifras por resolución.

## Desarrollo

```bash
make sync && make lint && make test
make test-live       # consulta la API real
make test-facturas   # lee el QR de los PDFs de data/facturas/, si los hay
```

`data/har/` y `data/facturas/` están en `.gitignore` (llevan CUPS, dirección y consumos
reales); los tests versionados usan un QR inventado.

## Proyectos relacionados

- [claude-arsenal](https://github.com/nuncaeslupus/claude-arsenal) — flujo de Claude Code guiado por especificaciones y cola de tareas con puertas de aceptación.
- [drawspec](https://github.com/nuncaeslupus/drawspec) — especificación declarativa de diagramas a SVG/PNG/texto limpio, escribible por LLMs; incluye servidor MCP.
- [doc-control](https://github.com/nuncaeslupus/doc-control) — permite a agentes de IA editar documentos Word como cambios controlados.
- [literary-critic](https://github.com/nuncaeslupus/literary-critic) — análisis de manuscritos con LLM al modo de un editor profesional.
- [integral-job-search](https://github.com/nuncaeslupus/integral-job-search) — búsqueda de empleo centrada en el candidato, dentro de Claude Code.

## Licencia

[MIT](LICENSE)
