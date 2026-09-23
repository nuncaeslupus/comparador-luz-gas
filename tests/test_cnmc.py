import json
from datetime import UTC, datetime
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


def test_modo_factura_manda_el_periodo_y_deja_el_anual_en_orig() -> None:
    # Valores de una captura del comparador en modo "mensual": el consumo pasa a
    # ser el del periodo y el anual se conserva en los campos "Orig".
    c = Consulta(
        codigo_postal="28013",
        consumo_anual_luz=2600,
        # Con los decimales que da el QR: en este modo la API los rechaza, así que
        # tienen que salir enteros y seguir sumando el total.
        consumo_factura=(47.57, 38.6, 59.57),
        inicio_factura="2026-08-23",
        fin_factura="2026-09-23",
    )
    p = _params(c)
    assert c.modo == "factura"
    assert p["factura"] == "true"
    assert (p["consumoAnualE"], p["consumoAnualEOrig"]) == ("146", "2600")
    franjas = [int(p[f"consumo{n}Franja"]) for n in ("Primera", "Segunda", "Tercera")]
    assert franjas == [48, 39, 59]
    assert sum(franjas) == int(p["consumoAnualE"])
    fechas = [
        datetime.fromtimestamp(int(p[k]) / 1000, UTC).date().isoformat()
        for k in ("dateInicio", "dateFin", "fFact")
    ]
    # fFact no se dio: cae en el fin del periodo, como hace el formulario.
    assert fechas == ["2026-08-23", "2026-09-23", "2026-09-23"]


def test_sin_modo_factura_no_se_cuelan_las_fechas() -> None:
    p = _params(Consulta(codigo_postal="28013", consumo_anual_luz=2600))
    assert p["factura"] == "false"
    assert "dateInicio" not in p and "fFact" not in p


def test_el_modo_factura_exige_fechas_y_gas_propio() -> None:
    with pytest.raises(ValueError, match="inicio_factura"):
        Consulta(codigo_postal="28013", consumo_factura=(64, 54, 103))
    with pytest.raises(ValueError, match="consumo_factura_gas"):
        Consulta(
            codigo_postal="28013",
            suministro="ambas",
            consumo_anual_gas=6000,
            consumo_factura=(64, 54, 103),
            inicio_factura="2026-08-23",
            fin_factura="2026-09-23",
        )
