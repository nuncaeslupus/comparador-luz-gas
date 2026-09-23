"""Lectura a largo plazo de un `Resultado`: qué sale a cuenta más allá del primer año.

El comparador ordena por `importe_primer_anio`, y ese puesto lo gana casi
siempre una oferta de bienvenida: un descuento que solo se cobra una vez. Aquí
se calcula el coste a varios años y se comparan las dos estrategias que tienen
sentido — quedarse con la misma oferta, o ir rotando ofertas de nuevo cliente.

Son cuentas sobre los números que ya da la CNMC. No hay modelo de precios ni
predicción: lo que el catálogo no trae, aquí no se inventa. En concreto **el
catálogo no lleva fechas**, así que no se puede decir en qué mes del año
conviene cambiar; lo único que fija un momento es tu propia permanencia.
"""

from __future__ import annotations

from typing import Any

from .cnmc import Oferta, Resultado

_SIN_DATOS = "Sin ofertas con coste a partir del segundo año: no hay nada que proyectar."


def coste(o: Oferta, anios: int) -> float:
    """Lo que cuesta esa oferta en `anios` años. El descuento de bienvenida va una sola vez."""
    return o.importe_primer_anio + (anios - 1) * o.importe_segundo_anio


def _rotacion(ofertas: list[Oferta], anios: int) -> list[Oferta]:
    """Las mejores ofertas de nuevo cliente, una por comercializadora y de barata a cara.

    Rotar consiste en ser cliente nuevo cada año, así que una comercializadora
    solo sirve una vez: la lista se acaba y con ella la estrategia.
    """
    mejor: dict[str, Oferta] = {}
    for o in ofertas:
        if o.solo_nuevos_clientes:
            m = mejor.get(o.comercializadora)
            if m is None or o.importe_primer_anio < m.importe_primer_anio:
                mejor[o.comercializadora] = o
    return sorted(mejor.values(), key=lambda o: o.importe_primer_anio)[:anios]


def _resumen(o: Oferta, anios: int) -> dict[str, Any]:
    return {
        "comercializadora": o.comercializadora,
        "oferta": o.oferta,
        "primer_anio": o.importe_primer_anio,
        "siguientes": o.importe_segundo_anio,
        "coste_total": round(coste(o, anios), 2),
        "permanencia": o.permanencia,
        "penalizacion_estimada": o.penalizacion_estimada,
        "solo_nuevos_clientes": o.solo_nuevos_clientes,
        "precio_unico": o.precio_unico,
    }


def _opcion(pool: list[Oferta], anios: int) -> dict[str, Any] | None:
    """La mejor de ese grupo y, si es de nuevo cliente, la mejor que no lo es.

    «Solo nuevos clientes» quiere decir que no la puedes contratar si ya eres
    cliente de esa comercializadora, así que quien vuelva a una que ya tuvo
    necesita la segunda.
    """
    if not pool:
        return None
    mejor = min(pool, key=lambda o: coste(o, anios))
    libres = [o for o in pool if not o.solo_nuevos_clientes]
    alt = min(libres, key=lambda o: coste(o, anios)) if libres else None
    return {
        "mejor": _resumen(mejor, anios),
        "sin_restriccion_de_nuevo_cliente": (
            _resumen(alt, anios) if alt is not None and alt is not mejor else None
        ),
    }


def interpretar(r: Resultado, anios: int = 3) -> dict[str, Any]:
    """Valoración textual y numérica del resultado, sin LLM y sin datos de fuera."""
    if r.modo == "factura":
        return {
            "nota": "En modo factura los importes son de un periodo, no de un año: "
            "la proyección a varios años no aplica. Repite la consulta en modo anual."
        }
    fijas = [o for o in r.ofertas if o.importe_segundo_anio > 0]
    if not fijas:
        return {"nota": _SIN_DATOS}

    largo = sorted(fijas, key=lambda o: coste(o, anios))
    quedarse = largo[0]
    primer = min(fijas, key=lambda o: o.importe_primer_anio)
    pvpc = next((o for o in r.ofertas if o.importe_segundo_anio <= 0), None)

    # La pregunta que decide la mitad del resultado: precio plano o por tramos.
    plana = _opcion([o for o in fijas if o.precio_unico], anios)
    horaria = _opcion([o for o in fijas if not o.precio_unico], anios)

    rota = _rotacion(fijas, anios)
    # Los años que la rotación no cubre se pagan a precio estable: quedarse es lo
    # que queda cuando ya has sido cliente nuevo de todas las que lo ofrecen.
    resto = anios - len(rota)
    coste_rotar = sum(o.importe_primer_anio for o in rota) + resto * quedarse.importe_segundo_anio

    avisos = []
    if quedarse.solo_nuevos_clientes:
        libre = next((o for o in largo if not o.solo_nuevos_clientes), None)
        avisos.append(
            f"La mejor a {anios} años es solo para nuevos clientes: no la puedes contratar si "
            f"ya eres cliente de {quedarse.comercializadora}."
            + (
                f" Sin esa restricción lo mejor es {libre.comercializadora} «{libre.oferta}», "
                f"{coste(libre, anios) - coste(quedarse, anios):.2f} € más a {anios} años."
                if libre
                else ""
            )
        )
    if primer.importe_primer_anio < quedarse.importe_primer_anio:
        avisos.append(
            f"La más barata a un año ({primer.comercializadora}, {primer.oferta}) cuesta "
            f"{primer.importe_primer_anio:.2f} € el primero y {primer.importe_segundo_anio:.2f} € "
            f"después: a {anios} años son {coste(primer, anios):.2f} €, "
            f"{coste(primer, anios) - coste(quedarse, anios):.2f} € más que quedarse con la mejor."
        )
    avisos.append(
        "Las ofertas con discriminación horaria están valoradas con TU reparto punta/llano/valle "
        "actual. Si piensas mover consumo al valle, vuelve a consultar con el reparto que "
        "esperas tener: es lo único que cambia su posición."
    )
    if quedarse.permanencia:
        avisos.append(
            f"La mejor a {anios} años tiene permanencia"
            + (
                f"; salirse antes cuesta unos {quedarse.penalizacion_estimada:.2f} €."
                if quedarse.penalizacion_estimada
                else "."
            )
        )
    if quedarse.servicios_adicionales:
        avisos.append(
            "La mejor a largo plazo incluye servicios adicionales; comprueba si los usas."
        )
    if pvpc:
        dif = pvpc.importe_primer_anio - quedarse.importe_segundo_anio
        avisos.append(
            f"El PVPC sale {abs(dif):.2f} € {'más caro' if dif > 0 else 'más barato'} al año que "
            f"la mejor fija ({pvpc.importe_primer_anio:.2f} € frente a "
            f"{quedarse.importe_segundo_anio:.2f} €), pero es variable: ese número es lo que "
            f"habría costado el último año, no lo que costará el siguiente."
        )
    con_perm = [o for o in fijas if o.permanencia]
    if con_perm:
        penas = [o.penalizacion_estimada for o in con_perm if o.penalizacion_estimada]
        avisos.append(
            f"{len(con_perm)} de {len(r.ofertas)} ofertas tienen permanencia"
            + (f" (penalización de {min(penas):.2f} a {max(penas):.2f} €)." if penas else ".")
        )
    avisos.append(
        "No se puede decir en qué mes conviene cambiar: el catálogo de la CNMC no lleva "
        "fechas de alta ni de caducidad de las ofertas, solo el tipo de cliente que admiten, "
        "y la CNMC no publica el histórico. El momento lo marca tu permanencia, no el mercado."
    )

    return {
        "horizonte_anios": anios,
        "pregunta": _pregunta(plana, horaria),
        "opciones": {"todas_las_horas_igual": plana, "con_discriminacion_horaria": horaria},
        "mejor_a_largo_plazo": _resumen(quedarse, anios),
        "ranking_a_largo_plazo": [_resumen(o, anios) for o in largo[:5]],
        "rotar_nuevo_cliente": {
            "coste_total": round(coste_rotar, 2),
            "ahorro_frente_a_quedarse": round(coste(quedarse, anios) - coste_rotar, 2),
            "anios_cubiertos": len(rota),
            "cambios": [{"comercializadora": o.comercializadora, "oferta": o.oferta} for o in rota],
        },
        "avisos": avisos,
        "resumen": (
            f"A {anios} años, lo más barato es {quedarse.comercializadora} «{quedarse.oferta}»: "
            f"{coste(quedarse, anios):.2f} € ({quedarse.importe_segundo_anio:.2f} €/año en "
            f"régimen). {_pregunta(plana, horaria)}"
        ),
    }


def _pregunta(plana: dict[str, Any] | None, horaria: dict[str, Any] | None) -> str:
    """Lo que hay que preguntarle al usuario, ya con la diferencia calculada."""
    if not (plana and horaria):
        return "Solo hay ofertas de un tipo: no hay nada que elegir entre precio plano y tramos."
    a, b = plana["mejor"], horaria["mejor"]
    dif = b["coste_total"] - a["coste_total"]
    gana, pierde = (a, b) if dif > 0 else (b, a)
    tipo = "el precio igual a todas horas" if dif > 0 else "la discriminación horaria"
    return (
        f"¿Prefieres pagar lo mismo a cualquier hora o puedes concentrar el consumo en las horas "
        f"baratas? Con tu reparto actual gana {tipo} por {abs(dif):.2f} €: "
        f"{gana['comercializadora']} «{gana['oferta']}» {gana['coste_total']:.2f} € frente a "
        f"{pierde['comercializadora']} «{pierde['oferta']}» {pierde['coste_total']:.2f} €."
    )
