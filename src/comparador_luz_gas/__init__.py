"""Consulta el comparador de ofertas de energía de la CNMC."""

from comparador_luz_gas.cnmc import Consulta, Oferta, Resultado, comparar
from comparador_luz_gas.factura import Factura, SinQR, desde_fichero, desde_qr, leer_qr

__all__ = [
    "Consulta",
    "Factura",
    "Oferta",
    "Resultado",
    "SinQR",
    "comparar",
    "desde_fichero",
    "desde_qr",
    "leer_qr",
]
