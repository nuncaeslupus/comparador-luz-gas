"""Compone la imagen de cabecera del README: 83 parámetros entran, 3 datos bastan.

No es código del paquete. Escribe docs/hero.svg y lo rasteriza a docs/hero.png con
un Chromium headless (el README enseña el PNG: GitHub muestra los SVG con `<img>`,
sin cargar fuentes). Necesita las fuentes Inter y DejaVu Sans Mono, y Pillow para
recortar la captura.

La lámina es de la misma familia que las de los otros repos (marco de plano, marcas
de zona, cajetín). Las comercializadoras y los importes son de ejemplo: el resultado
real cambia con la CNMC, así que en la imagen no va ningún nombre ni precio real.

Uso, desde la raíz del repo:

    make hero
    CHROMIUM=/ruta/a/chrome make hero
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
OUT_SVG = ROOT / "docs" / "hero.svg"
OUT_PNG = ROOT / "docs" / "hero.png"
LOGO_SVG = ROOT / "docs" / "logo.svg"

#: El tamaño de la vista previa social de GitHub; el README la escala a su columna.
W, H = 1280, 640

GROUND = "#0f1d27"
GRID = "#16293a"
INK = "#eef2f5"
DIM = "#8ea3b4"
FRAME = "#4d6577"
PANEL = "#152836"
AMBER = "#f2b632"  # luz
BLUE = "#5aa9e6"  # gas
SANS = "Inter, 'DejaVu Sans', sans-serif"
DISPLAY = "'Inter Display', Inter, sans-serif"
MONO = "'DejaVu Sans Mono', monospace"


def text(
    x: float,
    y: float,
    s: str,
    *,
    size: float,
    fill: str = INK,
    family: str = SANS,
    weight: int = 400,
    anchor: str = "start",
    spacing: float = 0,
    italic: bool = False,
) -> str:
    style = ' font-style="italic"' if italic else ""
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" '
        f'letter-spacing="{spacing}"{style} xml:space="preserve">{escape(s)}</text>'
    )


def sheet() -> list[str]:
    """Grid, border with zone marks, registration marks — the family's drafting sheet."""
    out = [f'<rect width="{W}" height="{H}" fill="{GROUND}"/>']
    for x in range(0, W, 20):
        width = 0.9 if x % 100 == 0 else 0.4
        out.append(
            f'<line x1="{x}" y1="0" x2="{x}" y2="{H}" stroke="{GRID}" stroke-width="{width}"/>'
        )
    for y in range(0, H, 20):
        width = 0.9 if y % 100 == 0 else 0.4
        out.append(
            f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{GRID}" stroke-width="{width}"/>'
        )
    out.append(
        f'<rect x="16" y="16" width="{W - 32}" height="{H - 32}" fill="none" stroke="{GRID}"/>'
    )
    out.append(
        f'<rect x="30" y="30" width="{W - 60}" height="{H - 60}" fill="none" '
        f'stroke="{FRAME}" stroke-width="1.5"/>'
    )
    zw = (W - 60) / 8
    for i in range(8):
        x = 30 + zw * i
        if i:
            out.append(f'<line x1="{x}" y1="16" x2="{x}" y2="30" stroke="{FRAME}"/>')
            out.append(f'<line x1="{x}" y1="{H - 30}" x2="{x}" y2="{H - 16}" stroke="{FRAME}"/>')
        for y in (27, H - 19):
            out.append(
                text(x + zw / 2, y, str(8 - i), size=9, fill=DIM, family=MONO, anchor="middle")
            )
    zh = (H - 60) / 4
    for i in range(4):
        y = 30 + zh * i
        if i:
            out.append(f'<line x1="16" y1="{y}" x2="30" y2="{y}" stroke="{FRAME}"/>')
            out.append(f'<line x1="{W - 30}" y1="{y}" x2="{W - 16}" y2="{y}" stroke="{FRAME}"/>')
        for x in (23, W - 23):
            out.append(
                text(x, y + zh / 2 + 3, "ABCD"[i], size=9, fill=DIM, family=MONO, anchor="middle")
            )
    for cx, cy in ((48, 48), (48, H - 48)):
        out += [
            f'<circle cx="{cx}" cy="{cy}" r="7" fill="none" stroke="{AMBER}"/>',
            f'<line x1="{cx - 11}" y1="{cy}" x2="{cx + 11}" y2="{cy}" stroke="{AMBER}"/>',
            f'<line x1="{cx}" y1="{cy - 11}" x2="{cx}" y2="{cy + 11}" stroke="{AMBER}"/>',
        ]
    return out


#: Logo tile (side, left, top) and the x where the wordmark starts after it.
LOGO_SIZE, LOGO_X, LOGO_Y = 84, 64, 54
TEXT_X = LOGO_X + LOGO_SIZE + 22


def logo() -> list[str]:
    """docs/logo.svg nested inline, so the hero stays generated from repo source."""
    inner = LOGO_SVG.read_text()
    inner = inner[inner.index("<svg") :].strip()
    inner = inner.replace(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">', "", 1
    ).removesuffix("</svg>")
    return [
        f'<svg x="{LOGO_X}" y="{LOGO_Y}" width="{LOGO_SIZE}" height="{LOGO_SIZE}" '
        f'viewBox="0 0 64 64">{inner}</svg>',
        f'<rect x="{LOGO_X}" y="{LOGO_Y}" width="{LOGO_SIZE}" height="{LOGO_SIZE}" '
        f'rx="{LOGO_SIZE * 14 / 64}" fill="none" stroke="{FRAME}" stroke-width="1.2"/>',
    ]


def wordmark() -> list[str]:
    return [
        f'<text x="{TEXT_X}" y="122" font-family="{DISPLAY}" font-size="70" font-weight="800" '
        f'letter-spacing="-2"><tspan fill="{INK}">comparador-</tspan>'
        f'<tspan fill="{AMBER}">luz</tspan><tspan fill="{INK}">-</tspan>'
        f'<tspan fill="{BLUE}">gas</tspan></text>',
        text(
            TEXT_X + 4,
            164,
            "El comparador oficial de la CNMC, sin el formulario.",
            size=25,
            fill="#c9d4dd",
        ),
        text(
            TEXT_X + 4,
            192,
            "Tres datos entran, JSON ordenado por precio sale. Para scripts y LLMs.",
            size=15,
            fill=DIM,
        ),
    ]


def title_block() -> list[str]:
    x, y, w, h = 842, 62, 376, 64
    half = w / 2 - 20
    cells = [(0.0, "FUENTE", "API pública de la CNMC"), (half, "SALIDA", "JSON · CLI · Python")]
    out = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{GROUND}" stroke="{FRAME}" '
        f'stroke-width="1.2"/>',
        f'<line x1="{x}" y1="{y + h / 2 + 4}" x2="{x + w}" y2="{y + h / 2 + 4}" stroke="{FRAME}"/>',
        f'<line x1="{x + half}" y1="{y + h / 2 + 4}" x2="{x + half}" y2="{y + h}" '
        f'stroke="{FRAME}"/>',
        text(x + 10, y + 14, "PROYECTO", size=8, fill=DIM, family=MONO, spacing=1.5),
        text(x + 10, y + 30, "comparador-luz-gas", size=14, weight=700, family=MONO),
    ]
    for cx, label, value in cells:
        out.append(text(x + cx + 10, y + 47, label, size=8, fill=DIM, family=MONO, spacing=1.5))
        out.append(
            text(x + cx + 10, y + 61, value, size=11, family=MONO, fill=AMBER if cx else INK)
        )
    return out


def caption(x: float, y: float, s: str, colour: str = AMBER) -> str:
    return text(x, y, s, size=10, fill=colour, family=MONO, spacing=2)


def arrow(x1: float, x2: float, y: float) -> list[str]:
    return [
        f'<line x1="{x1}" y1="{y}" x2="{x2 - 6}" y2="{y}" stroke="{AMBER}" '
        f'stroke-width="1.6" stroke-dasharray="5 3"/>',
        f'<path d="M{x2 - 9},{y - 6} L{x2},{y} L{x2 - 9},{y + 6}" fill="none" '
        f'stroke="{AMBER}" stroke-width="1.6"/>',
    ]


def form() -> list[str]:
    """The 83 parameters the CNMC endpoint asks for, as a wall of empty form fields."""
    x, y, cols, fw, fh, gx, gy = 64, 270, 7, 30, 11, 5, 8.6
    out = [caption(x, y - 14, "ANTES · 83 PARÁMETROS", DIM)]
    for i in range(83):
        cx = x + (i % cols) * (fw + gx)
        cy = y + (i // cols) * (fh + gy)
        width = fw if (i * 7) % 5 else fw * 0.6
        out.append(
            f'<rect x="{cx}" y="{cy}" width="{width}" height="{fh}" rx="2" fill="{PANEL}" '
            f'stroke="{FRAME}" stroke-width="0.7"/>'
        )
    return out


def qr(x: float, y: float, size: float) -> list[str]:
    """A QR-like glyph: three finder squares and a fixed scatter of modules."""
    n, out = 17, []
    m = size / n
    out.append(f'<rect x="{x}" y="{y}" width="{size}" height="{size}" fill="{INK}" rx="2"/>')
    for fx, fy in ((0, 0), (n - 5, 0), (0, n - 5)):
        out += [
            f'<rect x="{x + (fx + 0.5) * m}" y="{y + (fy + 0.5) * m}" width="{4 * m}" '
            f'height="{4 * m}" fill="none" stroke="{GROUND}" stroke-width="{m}"/>',
            f'<rect x="{x + (fx + 1.75) * m}" y="{y + (fy + 1.75) * m}" width="{1.5 * m}" '
            f'height="{1.5 * m}" fill="{GROUND}"/>',
        ]
    for i in range(n):
        for j in range(n):
            finder = (i < 6 and j < 6) or (i > n - 7 and j < 6) or (i < 6 and j > n - 7)
            if not finder and (i * 31 + j * 17 + i * j) % 3 == 0:
                out.append(
                    f'<rect x="{x + i * m}" y="{y + j * m}" width="{m}" height="{m}" '
                    f'fill="{GROUND}"/>'
                )
    return out


INPUTS = [("código postal", "28013"), ("consumo luz", "2600 kWh/año"), ("potencia", "3,45 kW")]


def inputs() -> list[str]:
    x, y, w = 380, 270, 270
    out = [caption(x, y - 14, "AHORA · 3 DATOS")]
    for i, (label, value) in enumerate(INPUTS):
        cy = y + i * 50
        out += [
            text(x, cy + 10, label, size=11, fill=DIM),
            f'<rect x="{x}" y="{cy + 16}" width="{w}" height="26" rx="4" fill="{PANEL}" '
            f'stroke="{AMBER}" stroke-width="1.2"/>',
            text(x + 10, cy + 34, value, size=13, family=MONO),
        ]
    qy = y + 160
    out += qr(x, qy, 62)
    out += [
        text(x + 76, qy + 26, "o el QR de tu factura,", size=13, fill=INK),
        text(x + 76, qy + 45, "sin teclear nada", size=13, fill=DIM),
    ]
    return out


#: Example offers: placeholder suppliers and illustrative yearly costs, cheapest first.
OFFERS = [("Comercializadora A", 590), ("Comercializadora B", 612), ("Comercializadora C", 637)]
OFFERS += [("Comercializadora D", 664), ("Comercializadora E", 701)]


def offers() -> list[str]:
    x, y, w = 740, 270, 478
    out = [caption(x, y - 14, "OFERTAS · DE MÁS BARATA A MÁS CARA")]
    lo, hi = OFFERS[0][1], OFFERS[-1][1]
    for i, (name, euros) in enumerate(OFFERS):
        cy = y + i * 34
        bar = 90 + (euros - lo) / (hi - lo) * 110
        colour = AMBER if i == 0 else "#2b4457"
        out += [
            text(x, cy + 17, f"{i + 1}", size=12, fill=DIM, family=MONO),
            text(x + 22, cy + 17, name, size=13, fill=INK if i == 0 else "#c9d4dd"),
            f'<rect x="{x + 182}" y="{cy + 4}" width="{bar}" height="18" rx="3" fill="{colour}"/>',
            text(
                x + w,
                cy + 17,
                f"{euros} €/año",
                size=12.5,
                family=MONO,
                anchor="end",
                fill=INK if i == 0 else DIM,
            ),
        ]
    wy = y + 182
    out += [
        f'<rect x="{x}" y="{wy}" width="{w}" height="46" rx="5" fill="none" stroke="{AMBER}" '
        f'stroke-width="1.2" stroke-dasharray="4 3"/>',
        text(x + 14, wy + 19, "grandes_ausentes", size=12, weight=700, family=MONO, fill=AMBER),
        text(
            x + 14,
            wy + 36,
            "cada respuesta dice qué comercializadoras grandes faltan",
            size=12,
            fill="#c9d4dd",
        ),
    ]
    return out


def strip() -> list[str]:
    x, y = 64, 548
    items = [
        ("sin autenticación", "la misma API pública que usa la web"),
        ("luz, gas o ambas", "con o sin permanencia"),
        ("una petición", "lo que tarde la CNMC, nada más"),
    ]
    out, w, gap = [], 372, 13
    for i, (name, sub) in enumerate(items):
        cx = x + i * (w + gap)
        out += [
            f'<rect x="{cx}" y="{y}" width="{w}" height="40" rx="4" fill="{PANEL}" '
            f'stroke="{FRAME}" stroke-width="0.8"/>',
            f'<rect x="{cx}" y="{y}" width="4" height="40" rx="2" fill="{BLUE}"/>',
            text(cx + 16, y + 25, name, size=12.5, weight=700, family=MONO, fill=BLUE),
            text(cx + 16 + len(name) * 7.6 + 10, y + 25, sub, size=12, fill="#c9d4dd"),
        ]
    return out


def svg() -> str:
    parts = sheet() + logo() + wordmark() + title_block() + form() + inputs() + offers() + strip()
    parts += arrow(320, 368, 345) + arrow(670, 728, 345)
    body = "\n  ".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">\n  {body}\n</svg>\n'
    )


def chromium() -> str:
    for candidate in (
        os.environ.get("CHROMIUM"),
        "/opt/pw-browsers/chromium",
        shutil.which("chromium"),
        shutil.which("google-chrome"),
    ):
        if candidate and Path(candidate).exists():
            return candidate
    sys.exit("hero: no Chromium found; set CHROMIUM=/path/to/chrome")


def main() -> None:
    OUT_SVG.write_text(svg())
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "hero.html"
        page.write_text(f'<html><body style="margin:0;overflow:hidden">{svg()}</body></html>')
        subprocess.run(
            [
                chromium(),
                "--headless=new",
                "--no-sandbox",
                "--hide-scrollbars",
                "--force-device-scale-factor=2",
                f"--window-size={W},{H + 200}",
                f"--screenshot={OUT_PNG}",
                page.as_uri(),
            ],
            check=True,
            capture_output=True,
        )
    # Headless Chromium's viewport is shorter than its window: shoot tall, then crop.
    from PIL import Image  # type: ignore[import-not-found, unused-ignore]

    with Image.open(OUT_PNG) as shot:
        shot.crop((0, 0, W * 2, H * 2)).save(OUT_PNG, optimize=True)
    print(f"wrote {OUT_SVG.relative_to(ROOT)} and {OUT_PNG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
