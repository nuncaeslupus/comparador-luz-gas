"""Cliente de la API pública del comparador de la CNMC.

La API vive en https://comparador.cnmc.gob.es/api/publico y no pide
autenticación. Los nombres de parámetro son los que usa su propio frontend;
se conservan tal cual para que una captura del navegador siga siendo
comparable con lo que enviamos aquí.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Literal

BASE = "https://comparador.cnmc.gob.es/api/publico"

Suministro = Literal["luz", "gas", "ambas"]

_ENDPOINT: dict[Suministro, tuple[str, str, str]] = {
    # suministro -> (ruta, tipoSuministro, clave del resultado)
    "luz": ("ofertas/electricidad", "E", "resultadoComparador"),
    "gas": ("ofertas/gas", "G", "resultadoComparador"),
    "ambas": ("ofertas/conjuntas", "C", "resultadoComparadorConjuntas"),
}

# Reparto horario del perfil 2.0TD estándar (punta / llano / valle). Son las
# proporciones exactas que aplica el frontend de la CNMC: para 2600 kWh manda
# 745 / 639 / 1216. La API exige las tres franjas aunque solo conozcas el total.
PERFIL_2TD = (745 / 2600, 639 / 2600, 1216 / 2600)

# Comercializadoras con cuota relevante en España, para poder decir cuáles de
# ellas NO están en la respuesta. Se comprueba por subcadena en mayúsculas.
GRANDES = (
    "ENDESA",
    "IBERDROLA",
    "NATURGY",
    "REPSOL",
    "TOTALENERGIES",
    "PLENITUDE",
    "HOLALUZ",
    "EDP",
    "OCTOPUS",
    "GALP",
)

AVISO_COBERTURA = (
    "El comparador de la CNMC solo incluye ofertas que las comercializadoras le "
    "remiten y que sus técnicos validan una a una. No es un censo del mercado: "
    "varias comercializadoras grandes no publican aquí su oferta de mercado libre "
    "y aparecen, como mucho, bajo 'Comercializadora de referencia' (PVPC/TUR). "
    "Trata el resultado como 'la mejor oferta entre las verificadas por la CNMC', "
    "no como 'la mejor oferta que existe'."
)

# Campos que el backend exige presentes pero que solo se usan al comparar contra
# una factura escaneada por QR o con autoconsumo. A cero significa "no aplica".
_CAMPOS_A_CERO = (
    "consumoAnualEQr",
    "consumoPrimeraFranjaQr",
    "consumoSegundaFranjaQr",
    "consumoTerceraFranjaQr",
    "consumoCuartaFranjaQr",
    "consumoQuintaFranjaQr",
    "consumoSextaFranjaQr",
    "consumoAnualEPQr",
    "consumoPrimeraFranjaPQr",
    "consumoSegundaFranjaPQr",
    "consumoTerceraFranjaPQr",
    "consumoCuartaFranjaPQr",
    "consumoQuintaFranjaPQr",
    "consumoSextaFranjaPQr",
    "energiaAutoconsumo",
    "idAuditoriaQR",
    "importe",
    "mecanismoAjuste",
    "mecanismoAjusteIVA",
    "importeMecanismoAjustePunta",
    "importeMecanismoAjusteLlano",
    "importeMecanismoAjusteValle",
    "precioConsumoMecanismoAjusteTotal",
    "precioConsumoMecanismoAjustePunta",
    "precioConsumoMecanismoAjusteLlano",
    "precioConsumoMecanismoAjusteValle",
    "tc",
    "bs",
    "impSA",
    "impOtros",
    "exc",
    "reg",
    "impOtrosConIE",
    "impOtrosSinIE",
    "pmaxP1",
    "pmaxP2",
    "dtoBS",
    "finBS",
    "ajuste",
    "impPot",
    "impEner",
    "dto",
    "prP1",
    "prP2",
    "prE1",
    "prE2",
    "prE3",
    "cfP1flex",
    "cfP2flex",
    "cambio",
    "promo",
    "verde",
    "rev",
    "trampeo",
)


@dataclass(frozen=True)
class Consulta:
    """Perfil de consumo a comparar."""

    codigo_postal: str
    consumo_anual_luz: float = 0.0
    consumo_anual_gas: float = 0.0
    potencia: float = 3.45
    suministro: Suministro = "luz"
    # Consumo por franja; si se deja en None se reparte con PERFIL_2TD.
    franjas: tuple[float, float, float] | None = None
    vivienda: bool = True
    tarifa: int = 4  # peaje 2.0TD doméstico
    # Filtros del comparador: 2 = indiferente, 1 = solo las que NO lo tienen.
    # La API responde 400 ante cualquier otro valor.
    permanencia: int = 2
    servicios_adicionales: int = 2
    revision_precios: int = 2

    def reparto(self) -> tuple[float, float, float]:
        if self.franjas is not None:
            return self.franjas
        c = self.consumo_anual_luz
        p, ll = round(c * PERFIL_2TD[0]), round(c * PERFIL_2TD[1])
        return (p, ll, c - p - ll)  # el valle absorbe el redondeo


@dataclass(frozen=True)
class Oferta:
    comercializadora: str
    oferta: str
    importe_primer_anio: float
    importe_segundo_anio: float
    permanencia: bool
    servicios_adicionales: bool
    verde: bool
    validez: str | None
    precio_unico: bool
    id_oferta: int


@dataclass(frozen=True)
class Resultado:
    consulta: dict[str, Any]
    ofertas: list[Oferta]
    comercializadoras: list[str] = field(default_factory=list)
    grandes_ausentes: list[str] = field(default_factory=list)
    aviso_cobertura: str = AVISO_COBERTURA
    # Solo con suministro="ambas": la CNMC devuelve también la mejor oferta suelta
    # de luz y la de gas, que a menudo salen más baratas que el paquete dual.
    alternativa_por_separado: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "consulta": self.consulta,
            "cobertura": {
                "aviso": self.aviso_cobertura,
                "comercializadoras_en_resultado": len(self.comercializadoras),
                "comercializadoras": self.comercializadoras,
                "grandes_ausentes": self.grandes_ausentes,
            },
            "ofertas": [vars(o) for o in self.ofertas],
            "alternativa_por_separado": self.alternativa_por_separado,
        }


def _oferta(o: dict[str, Any]) -> Oferta:
    return Oferta(
        comercializadora=o["comercializadora"],
        oferta=o["oferta"],
        importe_primer_anio=o["importePrimerAnio"],
        importe_segundo_anio=o["importeSegundoAnio"],
        permanencia=bool(o.get("penalizacion")),
        servicios_adicionales=bool(o.get("serviciosAdicionales")),
        verde=bool(o.get("verde")),
        validez=o.get("validez"),
        precio_unico=o.get("tienePrecioUnico") == "S",
        id_oferta=o["id"],
    )


def _params(c: Consulta) -> dict[str, str]:
    _, tipo, _ = _ENDPOINT[c.suministro]
    f1, f2, f3 = c.reparto()
    p: dict[str, Any] = {
        "tipoSuministro": tipo,
        "codigoPostal": c.codigo_postal,
        "potencia": c.potencia,
        "consumoAnualE": c.consumo_anual_luz,
        "consumoAnualEOrig": c.consumo_anual_luz,
        "consumoPrimeraFranja": f1,
        "consumoSegundaFranja": f2,
        "consumoTerceraFranja": f3,
        "consumoAnualG": c.consumo_anual_gas,
        "consumoAnualGOrig": c.consumo_anual_gas,
        "tarifa": c.tarifa,
        "vivienda": "true" if c.vivienda else "false",
        "permanencia": c.permanencia,
        "serviciosAdicionales": c.servicios_adicionales,
        "revisionPrecios": c.revision_precios,
        "perfilConsumo": 13,
        "autoconsumo": "false",
        "factura": "false",
    }
    # El backend exige las seis franjas de potencia y consumo, y una batería de
    # campos que solo se usan al comparar contra una factura escaneada (QR).
    for n in ("Primera", "Segunda", "Tercera", "Cuarta", "Quinta", "Sexta"):
        p[f"potencia{n}Franja"] = c.potencia
        p.setdefault(f"consumo{n}Franja", 0)
    for n in ("Cuarta", "Quinta", "Sexta"):
        p[f"consumo{n}Franja"] = 0
    p["potenciaAutoconsumo"] = c.potencia
    for k in _CAMPOS_A_CERO:
        p[k] = 0
    p["cups"] = "0000"
    return {k: str(v) for k, v in p.items()}


def _fetch(c: Consulta, timeout: float) -> dict[str, Any]:
    ruta, _, _ = _ENDPOINT[c.suministro]
    url = f"{BASE}/{ruta}?" + urllib.parse.urlencode(_params(c))
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "comparador-luz-gas/0.1"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data: dict[str, Any] = json.load(r)
    return data


def parsear(payload: dict[str, Any], c: Consulta) -> Resultado:
    """Normaliza la respuesta cruda de la CNMC. Separado de la red para poder testearlo."""
    _, _, clave = _ENDPOINT[c.suministro]
    crudas = payload.get(clave) or []
    sueltas: dict[str, Any] | None = None
    if isinstance(crudas, dict):
        # "ofertas/conjuntas" devuelve un objeto: el paquete dual y, aparte, la
        # mejor oferta individual de cada suministro.
        sueltas = {
            k: _oferta(crudas[k])
            for k in ("electricidad", "gas")
            if isinstance(crudas.get(k), dict)
        }
        total = sum(o.importe_primer_anio for o in sueltas.values())
        sueltas = {
            "luz": vars(sueltas["electricidad"]) if "electricidad" in sueltas else None,
            "gas": vars(sueltas["gas"]) if "gas" in sueltas else None,
            "importe_primer_anio": round(total, 2),
        }
        crudas = crudas.get("ofertasConjuntas") or []
    ofertas = [_oferta(o) for o in crudas]
    ofertas.sort(key=lambda o: o.importe_primer_anio)
    nombres = sorted({o.comercializadora for o in ofertas})
    en_mayus = " | ".join(nombres).upper()
    ausentes = [g for g in GRANDES if g not in en_mayus]
    return Resultado(
        consulta={
            "codigo_postal": c.codigo_postal,
            "suministro": c.suministro,
            "consumo_anual_luz": c.consumo_anual_luz,
            "consumo_anual_gas": c.consumo_anual_gas,
            "potencia": c.potencia,
            "reparto_franjas": list(c.reparto()),
        },
        ofertas=ofertas,
        comercializadoras=nombres,
        grandes_ausentes=ausentes,
        alternativa_por_separado=sueltas,
    )


def comparar(c: Consulta, timeout: float = 90.0) -> Resultado:
    """Consulta la CNMC y devuelve el resultado normalizado y ordenado por precio."""
    return parsear(_fetch(c, timeout), c)
