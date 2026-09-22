"""Lectura del QR normativo que llevan las facturas eléctricas españolas.

Desde la Resolución de la CNMC de 24/06/2021 (modificada por BOE-A-2022-16989)
toda factura de electricidad debe imprimir un QR que apunta al comparador con
los datos del suministro ya desglosados::

    https://comparador.cnmc.gob.es/comparador/QRE?cp=08026&pP1=4.6&caP1=740...

Como el formato lo fija la CNMC y no la comercializadora, leer el QR sirve para
cualquier compañía: no hace falta un parser de texto por marca.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .cnmc import Consulta

HOST_QR = "comparador.cnmc.gob.es"
_RESOLUCION_PDF = 300
_LADOS = (2500, 3500, 1700, 5000)
"""Píxeles del lado largo a los que reescalar antes de reintentar.

zbar no falla por falta de calidad sino porque el módulo del QR le queda
demasiado grande o demasiado pequeño: una página a 600 dpi se lee peor que
la misma a 300. Por eso se barren tamaños en vez de subir la resolución.
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
    if HOST_QR not in texto:
        raise SinQR(f"El texto no es un QR del comparador de la CNMC: {texto[:80]!r}")
    p = parse_qs(urlparse(texto).query, keep_blank_values=True)
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


def _decodificar(imagen: Any) -> str | None:
    from pyzbar.pyzbar import ZBarSymbol, decode  # type: ignore[import-untyped]

    # Solo QR: si no, zbar intenta además el código de barras de pago de la
    # factura y tarda varias veces más en cada página.
    for res in decode(imagen, symbols=[ZBarSymbol.QRCODE]):
        texto: str = res.data.decode("utf-8", "replace")
        if HOST_QR in texto:
            return texto
    return None


def _variantes(imagen: Any) -> Iterator[Any]:
    """La imagen tal cual, a varios tamaños y binarizada; se para en la primera."""
    from PIL import Image

    gris = imagen.convert("L")
    yield gris
    lado = max(gris.size)
    for objetivo in _LADOS:
        if abs(objetivo - lado) > lado * 0.15:
            f = objetivo / lado
            nuevo = (max(1, round(gris.width * f)), max(1, round(gris.height * f)))
            yield gris.resize(nuevo, Image.Resampling.LANCZOS)
    yield gris.point(lambda v: 255 if v > 128 else 0)


def _paginas(ruta: Path, resolucion: int) -> Iterator[Any]:
    from PIL import Image

    if ruta.suffix.lower() != ".pdf":
        yield Image.open(ruta)
        return
    if not shutil.which("pdftoppm"):
        raise RuntimeError("Falta 'pdftoppm' (paquete poppler-utils) para leer PDFs.")
    with tempfile.TemporaryDirectory() as tmp:
        # ponytail: renderiza el PDF entero de una vez; si algún día pesan de
        # verdad, pasar a -f/-l página a página y parar en el primer QR.
        subprocess.run(
            ["pdftoppm", "-r", str(resolucion), "-png", str(ruta), f"{tmp}/pg"],
            check=True,
            capture_output=True,
        )
        for png in sorted(Path(tmp).glob("pg-*.png")):
            yield Image.open(png)


def leer_qr(ruta: Path | str) -> str:
    """Busca el QR del comparador en un PDF o en una imagen y devuelve su URL."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(ruta)
    try:
        import pyzbar.pyzbar  # type: ignore[import-untyped]  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as e:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "Leer el QR necesita el extra 'facturas': pip install "
            "'comparador-luz-gas[facturas]' (y el sistema, libzbar: "
            "apt install libzbar0)."
        ) from e

    for pagina in _paginas(ruta, _RESOLUCION_PDF):
        for variante in _variantes(pagina):
            if texto := _decodificar(variante):
                return texto
    raise SinQR(f"No se encontró el QR del comparador en {ruta}")


def desde_fichero(ruta: Path | str) -> Factura:
    """Lee el QR de un PDF/imagen de factura y devuelve sus datos."""
    return desde_qr(leer_qr(ruta))
