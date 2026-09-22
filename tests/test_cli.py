import json

import pytest

from comparador_luz_gas import cli
from comparador_luz_gas.cnmc import Consulta, Resultado, parsear

from .test_cnmc import FIXTURE


@pytest.fixture
def sin_red(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(c: Consulta, timeout: float = 90.0) -> Resultado:
        return parsear(FIXTURE, c)

    monkeypatch.setattr(cli, "comparar", fake)


def test_json_por_defecto(sin_red: None, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--cp", "28001", "--consumo", "2500"]) == 0
    salida = json.loads(capsys.readouterr().out)
    assert salida["consulta"]["codigo_postal"] == "28001"
    assert salida["cobertura"]["grandes_ausentes"]
    assert len(salida["ofertas"]) == 12


def test_texto_avisa_de_la_cobertura(sin_red: None, capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["--cp", "28001", "--consumo", "2500", "--texto", "--top", "3"])
    out = capsys.readouterr().out
    assert "No están en el comparador" in out
    assert "no como 'la mejor oferta que existe'" in out


def test_luz_sin_consumo_es_error(sin_red: None) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--cp", "28001"])


def test_gas_exige_consumo_de_gas(sin_red: None) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--cp", "28001", "--suministro", "gas"])
