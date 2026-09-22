# comparador-luz-gas

Consulta el [comparador de ofertas de energía de la CNMC](https://comparador.cnmc.gob.es/)
y devuelve las ofertas ordenadas por precio, en JSON pensado para que lo consuma un LLM.

```bash
uv run comparador-luz-gas --cp 28013 --consumo 2600 --texto
uv run comparador-luz-gas --cp 28013 --consumo 2600 --consumo-gas 6000 --suministro ambas
uv run comparador-luz-gas --factura factura.pdf --texto   # saca los datos del QR
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

Trae código postal, potencias contratadas, **consumo anual real por periodo**
(punta/llano/valle), consumo del periodo facturado, precios e importe. Es decir,
exactamente lo que el comparador necesita — y el formato lo fija la CNMC, no la
comercializadora, así que **no hace falta un parser por compañía**.

Tres puntos de entrada:

```python
from comparador_luz_gas import comparar, desde_fichero, desde_qr

f = desde_fichero("factura.pdf")  # PDF o imagen: localiza y decodifica el QR
f = desde_qr(texto_del_qr)  # si la app ya lo ha escaneado (sin dependencias)
r = comparar(f.consulta())  # ofertas ordenadas por precio
```

`desde_qr()` es solo `urllib.parse`: una app que escanee el QR con la cámara puede
mandarnos la cadena y saltarse por completo el extra de imagen. Desde el CLI,
`--qr '<cadena>'`; con `--solo-datos` se imprimen los datos leídos sin consultar nada.

Leer el QR de un fichero necesita el extra y `libzbar`:

```bash
uv sync --extra facturas   # pyzbar + opencv-python-headless
sudo apt install libzbar0 poppler-utils
```

### ¿Y una factura escaneada?

Depende de a cuánto se escanee. **300 dpi es el mínimo práctico**: el QR mide unos
3 px por módulo a esa resolución, justo en el límite de los decodificadores. A 150
dpi no hay nada que hacer. Los números medidos, y por qué se prueban dos
decodificadores a varias escalas, están en [docs/qr-escaneado.md](docs/qr-escaneado.md).

## Qué cubre el comparador, y qué no

La CNMC solo publica ofertas que las comercializadoras le remiten y que sus técnicos
validan una a una. **No es un censo del mercado.** Comprobado contra la API en vivo el
2026-09-23, sobre 20 códigos postales:

- Presentes: Naturgy, Repsol, Galp, Octopus, Fenie, Nexus, Lumisa y ~45 más.
- **Iberdrola Clientes**: una sola oferta, solo gas (`Plan Gas Hogar RL2 online`).
- **Endesa Energía**: ninguna oferta, ni luz ni gas.
- TotalEnergies, Plenitude, Holaluz, EDP: ninguna.

Endesa e Iberdrola aparecen solo como `Comercializadora de referencia`, que es el
PVPC/TUR regulado de sus filiales obligadas por ley (Energía XXI, Curenergía).

Por eso cada respuesta lleva un bloque `cobertura` con las comercializadoras grandes
ausentes. La respuesta correcta a "¿cuál es la mejor tarifa?" es *la mejor entre las
verificadas por la CNMC*, no *la mejor que existe*.

## Desarrollo

```bash
make sync && make lint && make test
make test-live       # consulta la API real
make test-facturas   # lee el QR de los PDFs de data/facturas/, si los hay
```

Las capturas HAR (`data/har/`) y las facturas (`data/facturas/`) están en `.gitignore`:
pueden contener CUPS, dirección y consumos reales. Los tests versionados usan un QR
inventado.
