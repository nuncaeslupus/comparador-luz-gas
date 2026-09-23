"""Lectura del QR normativo que llevan las facturas eléctricas españolas.

Desde la Resolución de la CNMC de 24/06/2021 (modificada por BOE-A-2022-16989)
toda factura de electricidad debe imprimir un QR que apunta al comparador con
los datos del suministro ya desglosados::

    https://comparador.cnmc.gob.es/comparador/QRE?cp=28013&pP1=4.6&caP1=740...

Como el formato lo fija la CNMC y no la comercializadora, leer el QR sirve para
cualquier compañía: no hace falta un parser de texto por marca.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .cnmc import Consulta

HOST_QR = "comparador.cnmc.gob.es"
_RESOLUCION_PDF = 300
_LADOS = (0, 9000, 7000, 6000, 5300)
"""Píxeles del lado largo a los que reescalar la página; 0 es el tamaño original.

El QR ocupa ~3 px por módulo a 300 dpi, justo en el límite de los
decodificadores, así que lo que decide no es el dpi del escaneo sino el tamaño
al que se le presenta la página. Medido en `docs/qr-escaneado.md`.
"""


class SinQR(ValueError):
    """No se encontró un QR del comparador en el documento."""


@dataclass(frozen=True)
class Factura:
    """Datos de un suministro eléctrico tal y como los publica el QR."""

    cups: str
    codigo_postal: str
    potencia_p1: float
    potencia_p2: float
    consumo_anual: tuple[float, float, float]
    """Consumo de los últimos 12 meses en kWh: (punta, llano, valle)."""
    consumo_factura: tuple[float, float, float]
    """Consumo de este periodo de facturación en kWh: (punta, llano, valle)."""
    importe: float
    comercializadora: str
    inicio_anualidad: str
    inicio_factura: str
    fin_factura: str
    fecha_factura: str
    fin_contrato: str
    precio_potencia: tuple[float, float]
    """€/kW y año de P1 y P2."""
    precio_energia: tuple[float, float, float]
    """€/kWh de punta, llano y valle."""
    url_qr: str
    crudo: dict[str, str]
    """Todos los parámetros del QR, por si hace falta alguno que no mapeamos."""

    @property
    def consumo_anual_total(self) -> float:
        return round(sum(self.consumo_anual), 2)

    @property
    def potencia(self) -> float:
        """La que pide el comparador: la mayor de las dos contratadas."""
        return max(self.potencia_p1, self.potencia_p2)

    def consulta(self, **extra: Any) -> Consulta:
        """Consulta lista para `comparar()`, con el reparto real por franjas."""
        campos: dict[str, Any] = {
            "codigo_postal": self.codigo_postal,
            "consumo_anual_luz": self.consumo_anual_total,
            "potencia": self.potencia,
            "suministro": "luz",
            "franjas": self.consumo_anual,
        }
        return Consulta(**(campos | extra))


def _f(params: dict[str, list[str]], clave: str) -> float:
    try:
        return float(params.get(clave, ["0"])[0] or 0)
    except ValueError:
        return 0.0


def _s(params: dict[str, list[str]], clave: str) -> str:
    return params.get(clave, [""])[0]


def desde_qr(texto: str) -> Factura:
    """Convierte el contenido de un QR (la URL) en una `Factura`.

    Es el punto de entrada para quien ya haya decodificado el QR por su cuenta
    (una app móvil, por ejemplo): no necesita ni el PDF ni las dependencias de
    imagen.
    """
    texto = texto.strip()
    p = parse_qs(urlparse(texto).query, keep_blank_values=True)
    # Solo se han visto facturas de Iberdrola, así que no damos por hecho el
    # host: basta con que lleve los campos que define la resolución.
    if HOST_QR not in texto and not ("cp" in p and ("caP1" in p or "pP1" in p)):
        raise SinQR(f"El texto no es un QR del comparador de la CNMC: {texto[:80]!r}")
    if "cp" not in p:
        raise SinQR("El QR no lleva código postal; ¿es un QR de gas o de pago?")
    return Factura(
        cups=_s(p, "cups"),
        codigo_postal=_s(p, "cp"),
        potencia_p1=_f(p, "pP1"),
        potencia_p2=_f(p, "pP2"),
        consumo_anual=(_f(p, "caP1"), _f(p, "caP2"), _f(p, "caP3")),
        consumo_factura=(_f(p, "cfP1"), _f(p, "cfP2"), _f(p, "cfP3")),
        importe=_f(p, "imp"),
        comercializadora=_s(p, "com"),
        inicio_anualidad=_s(p, "iniA"),
        inicio_factura=_s(p, "iniF"),
        fin_factura=_s(p, "finF"),
        fecha_factura=_s(p, "fFact"),
        fin_contrato=_s(p, "finContrato"),
        precio_potencia=(_f(p, "prP1"), _f(p, "prP2")),
        precio_energia=(_f(p, "prE1"), _f(p, "prE2"), _f(p, "prE3")),
        url_qr=texto,
        crudo={k: v[0] for k, v in p.items()},
    )


def _es_qr(texto: str) -> bool:
    return HOST_QR in texto or "cp=" in texto


def _candidatos(img: Any, nativo: bool) -> Iterator[str]:
    """Lo que lean los decodificadores en esta imagen.

    A tamaño original solo se llama a zbar, que es quien lee el PDF nativo
    (22/22 facturas reales) y además es el rápido. OpenCV entra solo en las
    pasadas ampliadas, que es donde gana: no acertó ni un caso a escala 1 en
    ninguna de las medidas de `docs/qr-escaneado.md`.
    """
    import cv2
    from pyzbar.pyzbar import ZBarSymbol, decode  # type: ignore[import-untyped]

    # Solo QR: si no, zbar intenta además el código de barras de pago de la
    # factura y tarda varias veces más en cada página.
    for res in decode(img, symbols=[ZBarSymbol.QRCODE]):
        yield res.data.decode("utf-8", "replace")
    if nativo:
        return
    try:
        ok, textos, _, _ = cv2.QRCodeDetector().detectAndDecodeMulti(img)
    except cv2.error:  # pragma: no cover - OpenCV revienta con imágenes raras
        return
    if ok:
        yield from textos


def _escalar(img: Any, lado: int) -> Any | None:
    """La página a ese lado largo, o None si ya se probó a ese tamaño."""
    import cv2

    if not lado:
        return img
    f = lado / max(img.shape[:2])
    if abs(f - 1) < 0.1:
        return None
    interp = cv2.INTER_CUBIC if f > 1 else cv2.INTER_AREA
    return cv2.resize(img, None, fx=f, fy=f, interpolation=interp)


@contextmanager
def _paginas(ruta: Path, resolucion: int) -> Iterator[list[Path]]:
    """Las páginas del documento como ficheros de imagen."""
    if ruta.suffix.lower() != ".pdf":
        yield [ruta]
        return
    if not shutil.which("pdftoppm"):
        raise RuntimeError("Falta 'pdftoppm' (paquete poppler-utils) para leer PDFs.")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["pdftoppm", "-r", str(resolucion), "-png", str(ruta), f"{tmp}/pg"],
            check=True,
            capture_output=True,
        )
        yield sorted(Path(tmp).glob("pg-*.png"))


def leer_qr(ruta: Path | str) -> str:
    """Busca el QR del comparador en un PDF o en una imagen y devuelve su URL."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(ruta)
    try:
        import cv2
        import pyzbar.pyzbar  # type: ignore[import-untyped]  # noqa: F401
    except ImportError as e:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "Leer el QR necesita el extra 'facturas': pip install "
            "'comparador-luz-gas[facturas]' (y el sistema, libzbar: "
            "apt install libzbar0)."
        ) from e

    with _paginas(ruta, _RESOLUCION_PDF) as paginas:
        # Escala por fuera y página por dentro: la factura normal cae en la
        # primera pasada, que es la barata, y solo un escaneo malo paga el resto.
        for lado in _LADOS:
            for pagina in paginas:
                img = cv2.imread(str(pagina), cv2.IMREAD_GRAYSCALE)
                if img is None:
                    raise SinQR(f"No se pudo abrir la imagen {pagina}")
                if (b := _escalar(img, lado)) is None:
                    continue
                for texto in _candidatos(b, nativo=not lado):
                    if _es_qr(texto):
                        return texto
    raise SinQR(f"No se encontró el QR del comparador en {ruta}")


def desde_fichero(ruta: Path | str) -> Factura:
    """Lee el QR de un PDF/imagen de factura y devuelve sus datos."""
    return desde_qr(leer_qr(ruta))
