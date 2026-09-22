.PHONY: sync lint format test test-live test-facturas clean update-skills

sync:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src tests

format:
	uv run ruff format .
	uv run ruff check --fix .

test:
	uv run pytest -q -m "not live and not facturas" $(filter-out $@,$(MAKECMDGOALS))

test-live:
	uv run pytest -q -m live

# Facturas reales, no versionadas: se salta solo si data/facturas/ está vacío.
test-facturas:
	uv run pytest -q -m facturas

clean:
	rm -rf dist build .pytest_cache .mypy_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

update-skills:
	git subtree pull --prefix .claude/skills https://github.com/nuncaeslupus/my-skills.git main --squash

%:
	@:
