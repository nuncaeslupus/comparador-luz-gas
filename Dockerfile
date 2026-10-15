# Servidor MCP de comparador-luz-gas por stdio (sin el extra `facturas`: el QR se le
# pasa ya decodificado con `qr`).
#   docker build -t comparador-luz-gas .
#   docker run -i --rm comparador-luz-gas
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-compile . && rm -rf /src

RUN useradd --create-home --uid 1000 app
USER app
WORKDIR /home/app

ENTRYPOINT ["comparador-luz-gas"]
CMD ["mcp"]
