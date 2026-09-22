.PHONY: sync lint format test test-live clean update-skills

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
	uv run pytest -q -m "not live" $(filter-out $@,$(MAKECMDGOALS))

test-live:
	uv run pytest -q -m live

clean:
	rm -rf dist build .pytest_cache .mypy_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

update-skills:
	git subtree pull --prefix .claude/skills https://github.com/nuncaeslupus/my-skills.git main --squash

%:
	@:
