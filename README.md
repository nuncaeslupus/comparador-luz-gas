# comparador-luz-gas

Consulta el [comparador de ofertas de energía de la CNMC](https://comparador.cnmc.gob.es/)
y devuelve las ofertas ordenadas por precio, en JSON pensado para que lo consuma un LLM.

```bash
uv run comparador-luz-gas --cp 08026 --consumo 2600 --texto
uv run comparador-luz-gas --cp 08026 --consumo 2600 --consumo-gas 6000 --suministro ambas
```

## Qué cubre el comparador, y qué no

La CNMC solo publica ofertas que las comercializadoras le remiten y que sus técnicos
validan una a una. **No es un censo del mercado.** Comprobado contra la API en vivo el
2026-09-23, sobre 20 códigos postales:

- Presentes: Naturgy, Repsol, Galp, Octopus, Fenie, Nexus, Lumisa y ~45 más.
- **Iberdrola Clientes**: una sola oferta, solo gas (`Plan Gas Hogar RL2 online`).
- **Endesa Energía**: ninguna oferta, ni luz ni gas.
- TotalEnergies, Plenitude, Holaluz, EDP: ninguna.

Endesa e Iberdrola aparecen solo como `Comercializadora de referencia`, que es el
PVPC/TUR regulado de sus filiales obligadas por ley (Energía XXI, Curenergía).

Por eso cada respuesta lleva un bloque `cobertura` con las comercializadoras grandes
ausentes. La respuesta correcta a "¿cuál es la mejor tarifa?" es *la mejor entre las
verificadas por la CNMC*, no *la mejor que existe*.

## Desarrollo

```bash
make sync && make lint && make test
make test-live   # consulta la API real
```

Las capturas HAR (`data/har/`) y las facturas (`data/facturas/`) están en `.gitignore`:
pueden contener CUPS, dirección y consumos reales.
