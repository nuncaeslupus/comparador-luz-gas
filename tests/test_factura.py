"""El QR normativo de la factura, de URL a Consulta."""

from pathlib import Path

import pytest

from comparador_luz_gas.factura import SinQR, desde_fichero, desde_qr

# Inventado: mismos campos que uno real, con CUPS y CP de ejemplo. Las facturas
# de verdad viven en data/facturas/, que está en .gitignore.
QR = (
    "https://comparador.cnmc.gob.es/comparador/QRE?cp=28001&pP1=4.6&pP2=4.6"
    "&caP1=740&caP2=660&caP3=757&iniA=2025-08-16&tc=G0&finPen=0000-00-00"
    "&finContrato=2031-02-16&tf=N&imp=72.5&cfP1=47.57&cfP2=38.6&cfP3=59.57"
    "&iniF=2026-07-14&finF=2026-08-16&impSA=7.65&impOtrosConIE=0"
    "&impOtrosSinIE=0.88&exc=0&com=R2-515&cups=ES0000000000000000XX"
    "&pmaxP1=5.09&pmaxP2=4.51&fFact=2026-08-24&dtoBS=0&finBS=0.81&ajuste=0"
    "&impPot=24.16&impEner=23.92&dto=0&prP1=41.03768&prP2=17.0455"
    "&prE1=0.228857&prE2=0.084707&prE3=0&cfP1Flex=80&cfP2Flex=65"
    "&cambio=&promo=&verde=1&rev=0"
)

FACTURAS = sorted(Path("data/facturas").glob("*.pdf"))


def test_el_qr_trae_todo_lo_que_pide_el_comparador() -> None:
    f = desde_qr(QR)
    assert f.codigo_postal == "28001"
    assert f.potencia == 4.6
    assert f.consumo_anual == (740, 660, 757)
    assert f.consumo_anual_total == 2157
    assert f.cups == "ES0000000000000000XX"
    assert f.importe == 72.5


def test_la_consulta_usa_el_reparto_real_en_vez_del_perfil_estimado() -> None:
    c = desde_qr(QR).consulta()
    assert c.codigo_postal == "28001"
    assert c.reparto() == (740, 660, 757)
    assert sum(c.reparto()) == c.consumo_anual_luz


def test_la_consulta_admite_ajustes() -> None:
    c = desde_qr(QR).consulta(permanencia=1)
    assert c.permanencia == 1
    assert c.potencia == 4.6


def test_los_campos_ausentes_no_revientan() -> None:
    f = desde_qr("https://comparador.cnmc.gob.es/comparador/QRE?cp=28013")
    assert f.consumo_anual == (0, 0, 0)
    assert f.cups == ""


def test_un_texto_que_no_es_del_comparador_se_rechaza() -> None:
    with pytest.raises(SinQR):
        desde_qr("https://ejemplo.test/otra-cosa?cp=28001")


@pytest.mark.facturas
@pytest.mark.skipif(not FACTURAS, reason="no hay facturas reales en data/facturas/")
def test_se_lee_el_qr_de_las_facturas_reales() -> None:
    for pdf in FACTURAS:
        f = desde_fichero(pdf)
        assert f.codigo_postal.isdigit(), pdf.name
        assert f.consumo_anual_total > 0, pdf.name


def test_un_qr_con_los_campos_de_la_resolucion_vale_aunque_cambie_el_host() -> None:
    # Solo tenemos facturas de una comercializadora; si otra sirve el QR desde
    # su propio dominio, los campos siguen siendo los que fija la CNMC.
    otro = QR.replace("https://comparador.cnmc.gob.es/comparador", "https://otra.example/qr")
    assert desde_qr(otro).consumo_anual == (740, 660, 757)


def test_escalar_lleva_la_pagina_al_lado_pedido_y_no_repite_el_nativo() -> None:
    import numpy as np

    from comparador_luz_gas.factura import _escalar

    pagina = np.zeros((3508, 2480), dtype="uint8")
    assert _escalar(pagina, 0) is pagina
    assert _escalar(pagina, 3600) is None, "un 3 % de diferencia no merece otra pasada"
    ampliada = _escalar(pagina, 7000)
    assert ampliada is not None
    assert max(ampliada.shape) == 7000
