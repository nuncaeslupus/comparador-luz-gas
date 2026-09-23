from comparador_luz_gas.analisis import coste, interpretar
from comparador_luz_gas.cnmc import Consulta, Oferta, Resultado


def _o(com: str, primer: float, segundo: float, **kw: object) -> Oferta:
    campos: dict[str, object] = {
        "comercializadora": com,
        "oferta": f"tarifa de {com}",
        "importe_primer_anio": primer,
        "importe_segundo_anio": segundo,
        "permanencia": False,
        "servicios_adicionales": False,
        "verde": False,
        "validez": None,
        "precio_unico": True,
        "id_oferta": 1,
    }
    return Oferta(**(campos | kw))  # type: ignore[arg-type]


def _resultado(*ofertas: Oferta) -> Resultado:
    return Resultado(consulta={}, ofertas=list(ofertas))


def test_el_descuento_de_bienvenida_no_gana_a_largo_plazo() -> None:
    barata_un_anio = _o("Gancho", 100, 300, solo_nuevos_clientes=True)
    r = _resultado(barata_un_anio, _o("Sosa", 200, 200))
    a = interpretar(r, anios=3)

    assert coste(barata_un_anio, 3) == 700
    assert a["mejor_a_largo_plazo"]["comercializadora"] == "Sosa"
    assert "Gancho" in a["avisos"][0]


def test_la_rotacion_gasta_una_comercializadora_por_anio() -> None:
    # Dos ofertas de la misma comercializadora no dan dos años de cliente nuevo.
    r = _resultado(
        _o("A", 100, 500, solo_nuevos_clientes=True),
        _o("A", 110, 500, solo_nuevos_clientes=True),
        _o("B", 120, 500, solo_nuevos_clientes=True),
        _o("Sosa", 300, 300),
    )
    rot = interpretar(r, anios=3)["rotar_nuevo_cliente"]

    assert [c["comercializadora"] for c in rot["cambios"]] == ["A", "B"]
    assert rot["anios_cubiertos"] == 2
    # El tercer año ya no queda nadie a quien estrenar: se paga a precio estable.
    assert rot["coste_total"] == 100 + 120 + 300
    assert rot["ahorro_frente_a_quedarse"] == 900 - 520


def test_el_pvpc_no_entra_en_la_proyeccion() -> None:
    # La CNMC le pone importe del segundo año a cero; proyectarlo daría 0 €.
    a = interpretar(_resultado(_o("PVPC", 50, 0), _o("Sosa", 200, 200)), anios=3)

    assert a["mejor_a_largo_plazo"]["comercializadora"] == "Sosa"
    assert "más barato" in a["avisos"][0]


def test_en_modo_factura_no_se_proyecta_nada() -> None:
    c = Consulta(
        codigo_postal="28013",
        consumo_anual_luz=2200,
        consumo_factura=(48.0, 39.0, 59.0),
        inicio_factura="2026-08-23",
        fin_factura="2026-09-23",
    )
    a = interpretar(Resultado(consulta={}, ofertas=[_o("Sosa", 200, 200)], modo=c.modo))

    assert "no aplica" in a["nota"]
    assert "mejor_a_largo_plazo" not in a
