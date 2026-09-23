# Session Handover

**2026-09-23.** Rama `main` al día (`01c3d8a`), CI en verde, nada sin subir.

## Lo que se hizo

Lectura de facturas por el **QR normativo de la CNMC** (Resolución 24/06/2021, mod.
BOE-A-2022-16989) en `src/comparador_luz_gas/factura.py`. El QR trae el suministro
desglosado —CP, potencias, consumo anual por punta/llano/valle, CUPS, importe,
precios— y **el formato lo fija la CNMC, no la comercializadora**, así que sustituye
al parser por compañía que había en el backlog. También da el reparto real por
franjas, que hasta ahora se estimaba con `PERFIL_2TD`.

Tres entradas: `desde_qr()` (solo `urllib.parse`, para una app que ya haya escaneado),
`desde_fichero()` y `f.consulta()`. En CLI: `--factura`, `--qr`, `--solo-datos`.

**Verificado**: 22/22 facturas reales, QR en la página 3, ~7 s cada una
(`make test-facturas`, que se salta solo si `data/facturas/` está vacío).

## Decisiones que conviene no deshacer

- **Se usan dos decodificadores**, zbar y OpenCV. Ninguno domina: zbar lee 22/22 en
  PDF nativo y se queda ciego por encima de 300 dpi; OpenCV falla 6 de esas 22 pero
  rescata los escaneos a 400 dpi. zbar va en la pasada a tamaño original, OpenCV solo
  en las ampliadas (no acertó ni un caso a escala 1).
- **`_LADOS = (0, 9000, 7000, 6000, 5300)`** no es arbitrario: cada peldaño salva un
  rango de dpi concreto y el de 6000 es el único que lee los 600 dpi. Los números y
  lo que se probó sin éxito están en `docs/qr-escaneado.md`. No tocar a ojo.
- **El bucle es escala por fuera, página por dentro**, para que la factura normal
  salga en la primera pasada barata.

## Estado de la cola

- `t-11b25b34` (issue #1) sigue abierta, `requires: [access:human]`. Queda: el QR de
  la **factura de gas** (¿existe un equivalente al `QRE`?) y validar el de luz con
  **otra comercializadora** — basta una factura de Endesa, Naturgy o Repsol.
- Tres tareas en `_history/`, cerradas por merge.

## Privacidad

`data/facturas/` y `data/har/` están en `.gitignore` (comprobado). Los ejemplos del
README y del código usan CP 28013 y un CUPS inventado: el repo es público y llevaban
los reales.
