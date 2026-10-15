import io
import json
import tomllib
from pathlib import Path
from typing import Any

import pytest

from comparador_luz_gas import mcp
from comparador_luz_gas.cnmc import Consulta, Resultado, parsear

from .test_cnmc import FIXTURE
from .test_factura import QR


@pytest.fixture
def sin_red(monkeypatch: pytest.MonkeyPatch) -> list[Consulta]:
    consultas: list[Consulta] = []

    def fake(c: Consulta, timeout: float = 90.0) -> Resultado:
        consultas.append(c)
        return parsear(FIXTURE, c)

    monkeypatch.setattr(mcp, "comparar", fake)
    return consultas


def _sesion(*mensajes: dict[str, Any]) -> list[dict[str, Any]]:
    entrada = io.BytesIO(b"".join(json.dumps(m).encode() + b"\n" for m in mensajes))
    salida = io.BytesIO()
    assert mcp.serve(entrada, salida) == 0
    return [json.loads(linea) for linea in salida.getvalue().splitlines()]


def _llamar(nombre: str, **argumentos: Any) -> dict[str, Any]:
    (r,) = _sesion(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": nombre, "arguments": argumentos},
        }
    )
    resultado: dict[str, Any] = r["result"]
    return resultado


def test_handshake_y_lista_de_herramientas() -> None:
    init, lista = _sesion(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "x"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )
    assert init["result"]["protocolVersion"] == mcp.PROTOCOL_VERSIONS[0]
    assert init["result"]["serverInfo"]["name"] == "comparador-luz-gas"
    nombres = {t["name"] for t in lista["result"]["tools"]}
    assert nombres == {"comparar_ofertas", "leer_factura_qr", "leer_factura"}


def test_comparar_devuelve_el_json_del_cli(sin_red: list[Consulta]) -> None:
    r = _llamar("comparar_ofertas", cp="28001", consumo=2500, max_ofertas=5)
    assert not r["isError"]
    salida = json.loads(r["content"][0]["text"])
    assert salida["consulta"]["codigo_postal"] == "28001"
    assert len(salida["ofertas"]) == 5
    assert salida["ofertas_omitidas"] == 7
    assert "analisis" in salida


def test_comparar_desde_el_qr(sin_red: list[Consulta]) -> None:
    r = _llamar("comparar_ofertas", qr=QR)
    assert not r["isError"]
    assert sin_red[0].codigo_postal == "28001"
    assert sin_red[0].franjas is not None
    assert "factura" in json.loads(r["content"][0]["text"])


def test_argumentos_insuficientes_son_error_de_la_herramienta(sin_red: list[Consulta]) -> None:
    r = _llamar("comparar_ofertas", cp="28001")
    assert r["isError"]
    assert "consumo" in r["content"][0]["text"]
    assert not sin_red


def test_leer_factura_qr() -> None:
    r = _llamar("leer_factura_qr", qr=QR)
    assert json.loads(r["content"][0]["text"])["codigo_postal"] == "28001"


def test_herramienta_desconocida_y_json_roto() -> None:
    (desconocida,) = _sesion(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "nada"}}
    )
    assert desconocida["error"]["code"] == -32602
    salida = io.BytesIO()
    mcp.serve(io.BytesIO(b"{no es json\n"), salida)
    assert json.loads(salida.getvalue())["error"]["code"] == -32700


def test_server_json_va_con_la_version_del_paquete() -> None:
    """El registro de MCP publica `server.json` tal cual: su versión debe ser la de PyPI."""
    raiz = Path(__file__).parent.parent
    version = tomllib.loads((raiz / "pyproject.toml").read_text())["project"]["version"]
    server = json.loads((raiz / "server.json").read_text())
    assert server["version"] == version
    assert {p["version"] for p in server["packages"]} == {version}
    assert f"mcp-name: {server['name']}" in (raiz / "README.md").read_text()
