# Leer el QR de un escaneo: qué funciona y qué no

Medido sobre 22 facturas reales de una comercializadora (PDF nativo) y sobre una
de ellas degradada a propósito. Todo lo de aquí está comprobado, no estimado.

## Por qué cuesta tanto

El QR de la factura es pequeño y muy denso: unos **240 px de ancho a 300 dpi para
~80 módulos**, es decir **~3 px por módulo**. El mínimo teórico son 2 y los
decodificadores piden 3-4 para ir sobrados. Está justo en el límite, y de ahí que
los resultados parezcan caprichosos: pequeñas diferencias de tamaño o de filtro
deciden entre leerlo y no leerlo.

Consecuencia práctica: **lo que manda no es el dpi del escaneo, sino el tamaño al
que se le presenta la página al decodificador.** Por eso el código reescala.

## Escalas que funcionan (OpenCV, página limpia)

| Resolución | Lado largo | Factores que leen el QR |
|---|---|---|
| 150 dpi | 1754 px | **ninguno** |
| 200 dpi | 2339 px | 4× |
| 300 dpi | 3508 px | 2×, 2.5×, 3×, 4× |
| 400 dpi | 4678 px | 2×, 2.5× |
| 600 dpi | 7016 px | 0.75× |

Todos los aciertos caen entre **5300 y 9400 px de lado largo**, de ahí los valores
de `_LADOS` en `factura.py`.

## Los dos decodificadores se necesitan

Misma página, cinco resoluciones × seis degradaciones (limpio, JPEG q40, ruido 2 %,
giro 1.5°, giro 7°, desenfoque), a tamaño nativo:

| | zbar | OpenCV |
|---|---|---|
| Matriz de degradaciones (30 casos) | 4 | **9** |
| 400 dpi (6 casos) | 0 | **4** |
| Facturas reales, PDF nativo (22) | **22** | 16 |

Ninguno domina al otro: **zbar lee el PDF nativo perfecto y se queda ciego por
encima de 300 dpi; OpenCV falla 6 de las 22 facturas reales pero rescata los
escaneos a 400 dpi.** Por eso se prueban los dos.

## Dónde está el suelo

- **150 dpi: irrecuperable.** No lo salva ninguna escala, filtro, desenfoque ni
  troceado. La información ya no está en la imagen.
- **200 dpi: al límite.** Solo a 4× y con la página limpia.
- **300 dpi: el mínimo práctico.** Aguanta JPEG y giros de hasta 7°.
- **600 dpi: no es mejor que 300.** A tamaño nativo falla; hay que reducir.

Recomendación para quien escanee: **300 dpi, en gris, sin JPEG agresivo.** Más
resolución no ayuda; menos, no hay manera.

## Lo que se probó y no sirvió

- **Binarizar** (umbral fijo a 128): ningún caso nuevo.
- **Trocear la página** con solapamiento del 50 % y zoom 1-3×: cero mejora. El
  problema no es que el QR se pierda en la página, es que le faltan píxeles.
- **Normalizar el lado largo a 2200-4400 px**: 0/30. Reducir es exactamente lo
  contrario de lo que hace falta.
- **Subir el dpi del renderizado a 600**: empeora.

## La salida de emergencia

Si el escaneo no da, `desde_qr()` acepta la cadena ya decodificada. Una foto del
QR hecha con el móvil —que enfoca solo el código y le dedica todos sus píxeles— se
lee sin problema, y la app puede mandarnos el texto.
