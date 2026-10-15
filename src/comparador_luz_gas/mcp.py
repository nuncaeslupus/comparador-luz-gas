"""Servidor MCP: `comparador-luz-gas mcp` sirve el comparador como herramientas, por stdio.

El transporte es JSON-RPC 2.0 delimitado por saltos de línea en stdin/stdout, que es todo
lo que necesita un servidor MCP que solo ofrece herramientas; así el paquete sigue sin
dependencias. Las respuestas son el mismo JSON que da el CLI.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from importlib.metadata import PackageNotFoundError, version
from typing import IO, Any, cast

from comparador_luz_gas.analisis import interpretar
from comparador_luz_gas.cnmc import Consulta, Suministro, comparar
from comparador_luz_gas.factura import desde_fichero, desde_qr

# Revisiones del protocolo que habla; a un cliente que pida otra se le ofrece la más nueva.
PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")

_QR = {
    "type": "string",
    "description": "contenido del QR de la factura de luz, ya decodificado: la URL de "
    "comparador.cnmc.gob.es que lleva impresa, p. ej. "
    "`https://comparador.cnmc.gob.es/comparador/QRE?cp=28013&pP1=4.6&caP1=740...`",
}

# Ninguna herramienta escribe nada: repetir una llamada con los mismos
# argumentos devuelve lo mismo y no cambia nada.
_SOLO_LECTURA: dict[str, Any] = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
}

# Una sola forma de error para las tres herramientas.
_ERROR = (
    "Si falla, devuelve un error con texto JSON "
    '`{"ok": false, "error": "ArgumentoInvalido", "message": "..."}`'
)

_DATOS_FACTURA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "codigo_postal": {"type": "string"},
        "potencia_p1": {"type": "number"},
        "potencia_p2": {"type": "number"},
        "consumo_anual": {"type": "array", "items": {"type": "number"}},
        "consumo_factura": {"type": "array", "items": {"type": "number"}},
        "importe": {"type": "number"},
    },
    "required": ["codigo_postal", "consumo_anual"],
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "comparar_ofertas",
        "description": "Consulta el comparador oficial de la CNMC y devuelve las ofertas de luz "
        "y/o gas, de la más barata a la más cara, con un análisis a varios años (rotar de "
        "oferta, permanencias, fijo vs. tramos). Luz: `qr`, o `cp` + `consumo`; gas: "
        "`suministro` gas, `cp` + `consumo_gas`; ambas: lo de luz más `consumo_gas`. `cp`, "
        "`consumo` o `potencia` explícitos prevalecen sobre el `qr`; sin `qr`, 3,45 kW y "
        "reparto 2.0TD. Con el texto del QR no hace falta `leer_factura_qr`. Una petición "
        "HTTPS sin caché (segundos; límite 90 s); las ofertas cambian con el mercado. Euros, "
        "sin desglose de impuestos. "
        + _ERROR
        + " (`ArgumentoInvalido` si falta `cp` o consumo; otro si falla la red).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cp": {"type": "string", "description": "código postal, p. ej. 28013"},
                "consumo": {"type": "number", "description": "consumo anual de luz en kWh"},
                "consumo_gas": {"type": "number", "description": "consumo anual de gas en kWh"},
                "potencia": {
                    "type": "number",
                    "description": "potencia contratada en kW (por defecto 3.45)",
                },
                "suministro": {
                    "type": "string",
                    "enum": ["luz", "gas", "ambas"],
                    "description": "qué comparar (por defecto luz); ambas añade las ofertas "
                    "conjuntas y la alternativa de contratar por separado",
                },
                "franjas": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "consumo anual punta, llano y valle en kWh; por defecto "
                    "se reparte con el perfil 2.0TD",
                },
                "qr": _QR,
                "mensual": {
                    "type": "boolean",
                    "description": "con qr, coste de ese periodo de facturación en vez del anual",
                },
                "sin_permanencia": {
                    "type": "boolean",
                    "description": "excluir ofertas con permanencia",
                },
                "empresa": {"type": "boolean", "description": "suministro que no es vivienda"},
                "anios": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "horizonte del análisis a largo plazo (por defecto 3)",
                },
                "max_ofertas": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "ofertas a devolver, las más baratas (por defecto 20)",
                },
            },
            "additionalProperties": False,
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "consulta": {"type": "object"},
                "ofertas": {"type": "array", "items": {"type": "object"}},
                "analisis": {"type": "object"},
            },
            "required": ["consulta", "ofertas", "analisis"],
        },
        "annotations": _SOLO_LECTURA | {"openWorldHint": True},
    },
    {
        "name": "leer_factura_qr",
        "description": "Interpreta el texto ya decodificado del QR de una factura de luz y "
        "devuelve sus datos. `qr` es la URL de comparador.cnmc.gob.es impresa en la factura; "
        "de su query se leen `cp` (código postal, obligatorio), `pP1`/`pP2` (potencias, kW), "
        "`caP1`-`caP3` (consumo anual punta/llano/valle, kWh), `cfP1`-`cfP3` (consumo del "
        "periodo facturado) e `imp` (importe, euros); un campo numérico ausente o ilegible "
        "vale 0. Úsala para ver los datos; para comparar, pasa el QR a `comparar_ofertas`; "
        "con el archivo, `leer_factura_archivo`. Local e instantánea: sin red ni disco. "
        + _ERROR
        + ": `SinQR` si no es un QR del comparador o falta `cp` (p. ej. QR de gas o de pago).",
        "inputSchema": {
            "type": "object",
            "properties": {"qr": _QR},
            "required": ["qr"],
            "additionalProperties": False,
        },
        "outputSchema": _DATOS_FACTURA,
        "annotations": _SOLO_LECTURA | {"openWorldHint": False},
    },
    {
        "name": "leer_factura_archivo",
        "description": "Busca el QR del comparador en una factura de luz del disco del "
        "servidor y devuelve los mismos datos que `leer_factura_qr`. `ruta`: si termina en "
        "`.pdf` (sin distinguir mayúsculas) se rasteriza con pdftoppm y se recorren las "
        "páginas hasta dar con el QR, y se usa el primero; con cualquier otra extensión se "
        "abre como imagen (PNG, JPG...). Úsala cuando tengas el archivo y no el texto del "
        "QR. Necesita el extra `facturas`. Sin red; segundos por PDF, más con un escaneo "
        "malo. "
        + _ERROR
        + ": `FileNotFoundError`, `RuntimeError` (falta el extra o pdftoppm) o `SinQR`.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ruta": {
                    "type": "string",
                    "description": "ruta al PDF o imagen de la factura en el disco del "
                    "servidor; mejor absoluta (una relativa se resuelve desde el "
                    "directorio de trabajo del proceso MCP), p. ej. "
                    "`/home/ana/facturas/2025-03.pdf`",
                }
            },
            "required": ["ruta"],
            "additionalProperties": False,
        },
        "outputSchema": _DATOS_FACTURA,
        "annotations": _SOLO_LECTURA | {"openWorldHint": False},
    },
]


class ArgumentoInvalido(ValueError):
    """Argumentos que no permiten hacer la consulta; se devuelven como error de la herramienta."""


def _comparar_ofertas(a: dict[str, Any]) -> dict[str, Any]:
    factura = desde_qr(a["qr"]) if a.get("qr") else None
    cp = a.get("cp") or (factura.codigo_postal if factura else None)
    consumo = a.get("consumo")
    consumo_luz = (
        consumo if consumo is not None else (factura.consumo_anual_total if factura else 0)
    )
    consumo_gas = a.get("consumo_gas") or 0
    potencia = a.get("potencia") or (factura.potencia if factura else 3.45)
    suministro = a.get("suministro") or "luz"
    if suministro not in ("luz", "gas", "ambas"):
        raise ArgumentoInvalido("suministro es luz, gas o ambas")

    if not cp:
        raise ArgumentoInvalido("hace falta cp (o qr, que ya lo trae)")
    if suministro in ("luz", "ambas") and not consumo_luz:
        raise ArgumentoInvalido("consumo es obligatorio para luz")
    if suministro in ("gas", "ambas") and not consumo_gas:
        raise ArgumentoInvalido("consumo_gas es obligatorio para gas")
    if a.get("mensual") and not factura:
        raise ArgumentoInvalido("mensual necesita qr: el periodo y sus fechas los da el QR")

    franjas = a.get("franjas")
    if franjas is not None:
        if len(franjas) != 3:
            raise ArgumentoInvalido("franjas necesita tres valores: punta, llano, valle")
        franjas = (float(franjas[0]), float(franjas[1]), float(franjas[2]))
    elif factura and consumo is None:
        # Reparto real de la factura; si han forzado otro consumo, ya no cuadra.
        franjas = factura.consumo_anual

    r = comparar(
        Consulta(
            codigo_postal=str(cp),
            consumo_anual_luz=float(consumo_luz),
            consumo_anual_gas=float(consumo_gas),
            potencia=float(potencia),
            suministro=cast(Suministro, suministro),
            franjas=franjas,
            vivienda=not a.get("empresa"),
            permanencia=1 if a.get("sin_permanencia") else 2,
            **(factura.periodo if a.get("mensual") and factura else {}),
        )
    )
    salida = r.to_dict()
    salida["analisis"] = interpretar(r, int(a.get("anios") or 3))
    ofertas = salida.get("ofertas", [])
    tope = int(a.get("max_ofertas") or 20)
    if len(ofertas) > tope:
        salida["ofertas"] = ofertas[:tope]
        salida["ofertas_omitidas"] = len(ofertas) - tope
    if factura:
        salida["factura"] = dataclasses.asdict(factura)
    return salida


def llamar(nombre: str, argumentos: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta una herramienta; `handle` convierte sus excepciones en un error de la herramienta."""
    if nombre == "comparar_ofertas":
        return _comparar_ofertas(argumentos)
    if nombre == "leer_factura_qr":
        return dataclasses.asdict(desde_qr(str(argumentos["qr"])))
    if nombre == "leer_factura_archivo":
        return dataclasses.asdict(desde_fichero(str(argumentos["ruta"])))
    raise KeyError(nombre)


def _version() -> str:
    try:
        return version("comparador-luz-gas")
    except PackageNotFoundError:  # pragma: no cover - solo sin instalar
        return "0"


def handle(message: Any) -> dict[str, Any] | None:
    """Responde a un mensaje JSON-RPC; None si es una notificación."""
    if not isinstance(message, dict) or not isinstance(message.get("method"), str):
        return _error(None, -32600, "invalid request")
    if "id" not in message:
        return None
    msg_id, method = message["id"], message["method"]
    params = message.get("params")
    params = params if isinstance(params, dict) else {}
    if method == "initialize":
        pedida = params.get("protocolVersion")
        result: dict[str, Any] = {
            "protocolVersion": pedida if pedida in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "comparador-luz-gas", "version": _version()},
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        nombre, argumentos = params.get("name"), params.get("arguments") or {}
        if nombre not in {t["name"] for t in TOOLS} or not isinstance(argumentos, dict):
            return _error(msg_id, -32602, f"unknown tool or invalid arguments: {nombre}")
        try:
            datos = llamar(str(nombre), argumentos)
        except Exception as e:  # el modelo debe ver el fallo para corregir la llamada
            fallo = {"ok": False, "error": type(e).__name__, "message": str(e)}
            texto = json.dumps(fallo, ensure_ascii=False)
            result = {"content": [{"type": "text", "text": texto}], "isError": True}
        else:
            texto = json.dumps(datos, ensure_ascii=False)
            result = {
                "content": [{"type": "text", "text": texto}],
                "structuredContent": datos,
                "isError": False,
            }
    else:
        return _error(msg_id, -32601, f"method not found: {method}")
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def serve(stdin: IO[bytes] | None = None, stdout: IO[bytes] | None = None) -> int:
    """Sirve hasta que se cierre stdin. Bytes de entrada y salida: UTF-8 en cualquier sistema."""
    stdin = sys.stdin.buffer if stdin is None else stdin
    stdout = sys.stdout.buffer if stdout is None else stdout
    for line in stdin:
        if not line.strip():
            continue
        try:
            reply = handle(json.loads(line))
        except ValueError:
            reply = _error(None, -32700, "parse error")
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False).encode() + b"\n")
            stdout.flush()
    return 0
