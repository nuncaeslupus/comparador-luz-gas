# Leer el QR de un escaneo: qué funciona y qué no

Medido, no estimado: 22 facturas reales de una comercializadora en PDF nativo, y
una de ellas degradada a propósito a cinco resoluciones × cuatro deterioros.

## Por qué cuesta tanto

El QR de la factura es pequeño y muy denso: unos **240 px de ancho a 300 dpi para
~80 módulos**, es decir **~3 px por módulo**. El mínimo teórico son 2 y los
decodificadores piden 3-4 para ir sobrados. Está justo en el límite, y de ahí que
los resultados parezcan caprichosos: pequeñas diferencias de tamaño deciden entre
leerlo y no leerlo.

Consecuencia práctica: **lo que manda no es el dpi del escaneo sino el tamaño al
que se le presenta la página al decodificador.** Por eso `leer_qr()` reescala a
lados fijos (`_LADOS`) en vez de subir la resolución del renderizado.

## Qué lee `leer_qr()` hoy

| | limpio | JPEG q40 | girado 7° | desenfoque |
|---|---|---|---|---|
| 150 dpi | ✗ | ✗ | ✗ | ✗ |
| 200 dpi | ✓ | ✓ | ✓ | ✗ |
| 300 dpi | ✓ | ✓ | ✓ | ✗ |
| 400 dpi | ✓ | ✓ | ✓ | ✓ |
| 600 dpi | ✓ | ✗ | ✓ | ✓ |

13/20. Y **22/22 en las facturas reales en PDF** (~7 s cada una), que es el caso
que importa.

Recomendación para quien escanee: **300-400 dpi, en gris, sin JPEG agresivo y sin
desenfoque**. 400 dpi es el único punto que aguanta las cuatro degradaciones.

## Los dos decodificadores se necesitan

Cada uno por su cuenta, sin escalera:

| | zbar | OpenCV |
|---|---|---|
| Matriz de degradaciones (30 casos) | 4 | **9** |
| 400 dpi (6 casos) | 0 | **4** |
| Facturas reales, PDF nativo (22) | **22** | 16 |

Ninguno domina al otro: **zbar lee el PDF nativo perfecto y se queda ciego por
encima de 300 dpi; OpenCV falla 6 de las 22 facturas reales pero rescata los
escaneos a 400 dpi.** Además OpenCV no acertó **ni un solo caso a escala 1**, así
que la pasada a tamaño original llama solo a zbar —que es la rápida y la que
resuelve la factura normal— y OpenCV entra únicamente en las ampliadas.

## Qué lado largo salva cada caso

| Resolución | Lado largo nativo | Lados que leen el QR |
|---|---|---|
| 150 dpi | 1754 px | **ninguno** |
| 200 dpi | 2339 px | 9000 |
| 300 dpi | 3508 px | nativo, 7000-12000 |
| 400 dpi | 4678 px | 9000-12000 |
| 600 dpi | 7016 px | 6000 (y solo ese, si está limpio) |

De ahí `_LADOS = (0, 9000, 7000, 6000, 5300)`: 0 es el tamaño original y el resto
cubre la tabla. El orden está puesto para que el caso frecuente salga pronto.

## Dónde está el suelo

- **150 dpi: irrecuperable.** No lo salva ninguna escala, filtro, desenfoque ni
  troceado. La información ya no está en la imagen.
- **300 dpi: el mínimo práctico.** 200 dpi funciona limpio, pero se cae con
  cualquier desenfoque.
- **600 dpi no es mejor que 400.** A tamaño nativo falla; hay que reducir a 6000 px,
  y con JPEG encima ya no hay manera.
- **El desenfoque es lo que más mata** por debajo de 400 dpi: a 3 px por módulo no
  queda margen para que los módulos se mezclen entre sí.

## Lo que se probó y no sirvió

- **Binarizar** (umbral fijo a 128): ningún caso nuevo.
- **Trocear la página** con solapamiento del 50 % y zoom 1-3×: cero mejora. El
  problema no es que el QR se pierda en la página, es que le faltan píxeles.
- **Normalizar el lado largo a 2200-4400 px**: 0/30. Reducir es lo contrario de lo
  que hace falta, salvo en el caso concreto de 600 dpi.
- **Renderizar el PDF a 600 dpi en vez de 300**: empeora.

## La salida de emergencia

Si el escaneo no da, `desde_qr()` acepta la cadena ya decodificada. Una foto del QR
hecha con el móvil —que enfoca solo el código y le dedica todos sus píxeles— se lee
sin problema, y la aplicación puede mandarnos el texto y saltarse todo esto.
