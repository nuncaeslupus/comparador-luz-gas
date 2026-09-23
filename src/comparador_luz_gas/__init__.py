"""Consulta el comparador de ofertas de energía de la CNMC."""

from comparador_luz_gas.analisis import coste, interpretar
from comparador_luz_gas.cnmc import Consulta, Oferta, Resultado, comparar
from comparador_luz_gas.factura import (
    Factura,
    SinQR,
    anualizar,
    desde_fichero,
    desde_qr,
    leer_qr,
)

__all__ = [
    "Consulta",
    "Factura",
    "Oferta",
    "Resultado",
    "SinQR",
    "anualizar",
    "comparar",
    "coste",
    "desde_fichero",
    "desde_qr",
    "interpretar",
    "leer_qr",
]
