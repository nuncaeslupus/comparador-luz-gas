import json
from pathlib import Path

import pytest

from comparador_luz_gas.cnmc import Consulta, _params, comparar, parsear

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "ofertas_luz_28001.json").read_text(encoding="utf-8")
)


def test_reparto_suma_el_consumo_anual() -> None:
    # El redondeo no puede inventar ni perder kWh: la CNMC compara franja a franja.
    for consumo in (2600, 2500, 999, 1, 12345):
        c = Consulta(codigo_postal="28001", consumo_anual_luz=consumo)
        assert sum(c.reparto()) == consumo


def test_reparto_reproduce_el_del_frontend() -> None:
    # Valores observados en una captura del comparador real para 2600 kWh.
    assert Consulta(codigo_postal="28013", consumo_anual_luz=2600).reparto() == (745, 639, 1216)


def test_franjas_explicitas_ganan_al_perfil() -> None:
    c = Consulta(codigo_postal="28013", consumo_anual_luz=2600, franjas=(1000, 800, 800))
    assert c.reparto() == (1000, 800, 800)


def test_params_lleva_lo_que_la_api_exige() -> None:
    p = _params(Consulta(codigo_postal="28013", consumo_anual_luz=2600, potencia=3.5))
    assert p["tipoSuministro"] == "E"
    assert p["codigoPostal"] == "28013"
    assert p["cups"] == "0000"
    # Seis franjas de potencia, aunque 2.0TD solo use dos.
    for n in ("Primera", "Segunda", "Tercera", "Cuarta", "Quinta", "Sexta"):
        assert p[f"potencia{n}Franja"] == "3.5"
    assert all(isinstance(v, str) for v in p.values())


def test_parsear_ordena_por_precio_y_normaliza() -> None:
    c = Consulta(codigo_postal="28001", consumo_anual_luz=2500)
    r = parsear(FIXTURE, c)
    assert len(r.ofertas) == 12
    importes = [o.importe_primer_anio for o in r.ofertas]
    assert importes == sorted(importes)
    assert all(o.comercializadora and o.oferta for o in r.ofertas)
    assert r.comercializadoras == sorted(set(r.comercializadoras))


def test_grandes_ausentes_detecta_a_endesa() -> None:
    # El caso que motiva el aviso de cobertura: Endesa no remite ofertas a la CNMC.
    r = parsear(FIXTURE, Consulta(codigo_postal="28001", consumo_anual_luz=2500))
    assert "ENDESA" in r.grandes_ausentes
    assert "cobertura" in r.to_dict()


def test_respuesta_vacia_no_revienta() -> None:
    r = parsear({"resultadoComparador": None}, Consulta(codigo_postal="99999"))
    assert r.ofertas == []
    assert {"ENDESA", "IBERDROLA"} <= set(r.grandes_ausentes)


@pytest.mark.live
def test_live_luz() -> None:
    r = comparar(Consulta(codigo_postal="28001", consumo_anual_luz=2500))
    assert len(r.ofertas) > 20
    assert r.ofertas[0].importe_primer_anio > 0


CONJUNTAS = json.loads(
    (Path(__file__).parent / "fixtures" / "ofertas_conjuntas_28001.json").read_text(
        encoding="utf-8"
    )
)


def test_conjuntas_separa_el_paquete_dual_de_las_ofertas_sueltas() -> None:
    # "ofertas/conjuntas" no devuelve una lista sino un objeto: los paquetes de
    # luz+gas y, aparte, la mejor oferta suelta de cada suministro.
    c = Consulta(
        codigo_postal="28001", consumo_anual_luz=2500, consumo_anual_gas=6000, suministro="ambas"
    )
    r = parsear(CONJUNTAS, c)
    assert len(r.ofertas) == 4
    alt = r.alternativa_por_separado
    assert alt is not None
    assert alt["luz"] is not None and alt["gas"] is not None
    esperado = alt["luz"]["importe_primer_anio"] + alt["gas"]["importe_primer_anio"]
    assert alt["importe_primer_anio"] == pytest.approx(esperado, abs=0.01)


def test_las_consultas_de_un_solo_suministro_no_traen_alternativa() -> None:
    r = parsear(FIXTURE, Consulta(codigo_postal="28001", consumo_anual_luz=2500))
    assert r.alternativa_por_separado is None
