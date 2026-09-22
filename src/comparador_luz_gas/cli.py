"""CLI: perfil de consumo entra, JSON sale."""

from __future__ import annotations

import argparse
import json
import sys

from comparador_luz_gas.cnmc import Consulta, Resultado, comparar


def _tabla(r: Resultado, top: int) -> str:
    lineas = [
        f"{'1er año':>9} {'2º año':>9}  {'comercializadora':38} oferta",
        "-" * 100,
    ]
    lineas += [
        f"{o.importe_primer_anio:9.2f} {o.importe_segundo_anio:9.2f}  "
        f"{o.comercializadora[:38]:38} {o.oferta}"
        for o in r.ofertas[:top]
    ]
    lineas += ["", f"{len(r.ofertas)} ofertas de {len(r.comercializadoras)} comercializadoras."]
    alt = r.alternativa_por_separado
    if alt:
        lineas.append(
            f"Contratando por separado: {alt['importe_primer_anio']:.2f} el primer año "
            f"(luz {alt['luz']['comercializadora'] if alt['luz'] else '-'}, "
            f"gas {alt['gas']['comercializadora'] if alt['gas'] else '-'})."
        )
    if r.grandes_ausentes:
        lineas.append("No están en el comparador: " + ", ".join(r.grandes_ausentes) + ".")
    lineas.append(r.aviso_cobertura)
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="comparador-luz-gas",
        description="Consulta el comparador de la CNMC; ofertas ordenadas por precio.",
    )
    p.add_argument("--cp", required=True, help="código postal, p. ej. 08026")
    p.add_argument("--consumo", type=float, default=0, help="consumo anual de luz en kWh")
    p.add_argument("--consumo-gas", type=float, default=0, help="consumo anual de gas en kWh")
    p.add_argument("--potencia", type=float, default=3.45, help="potencia contratada en kW")
    p.add_argument("--suministro", choices=["luz", "gas", "ambas"], default="luz")
    p.add_argument(
        "--franjas",
        help="consumo punta,llano,valle en kWh; por defecto se reparte con el perfil 2.0TD",
    )
    p.add_argument("--sin-permanencia", action="store_true", help="excluir ofertas con permanencia")
    p.add_argument("--empresa", action="store_true", help="suministro que no es vivienda")
    p.add_argument("--top", type=int, default=10, help="filas a mostrar en modo texto")
    p.add_argument("--texto", action="store_true", help="tabla legible en vez de JSON")
    a = p.parse_args(argv)

    if a.suministro in ("luz", "ambas") and not a.consumo:
        p.error("--consumo es obligatorio para luz")
    if a.suministro in ("gas", "ambas") and not a.consumo_gas:
        p.error("--consumo-gas es obligatorio para gas")

    franjas = None
    if a.franjas:
        partes = [float(x) for x in a.franjas.split(",")]
        if len(partes) != 3:
            p.error("--franjas necesita tres valores: punta,llano,valle")
        franjas = (partes[0], partes[1], partes[2])

    r = comparar(
        Consulta(
            codigo_postal=a.cp,
            consumo_anual_luz=a.consumo,
            consumo_anual_gas=a.consumo_gas,
            potencia=a.potencia,
            suministro=a.suministro,
            franjas=franjas,
            vivienda=not a.empresa,
            permanencia=1 if a.sin_permanencia else 2,
        )
    )
    if a.texto:
        print(_tabla(r, a.top))
    else:
        json.dump(r.to_dict(), sys.stdout, ensure_ascii=False, indent=2)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
