PYTHON ?= python
RUFF = $(PYTHON) -m ruff

.PHONY: format lint test check frontend-build
format:
	$(RUFF) format src tests tools deployment scene.py serve.py
	npm run format --prefix frontend
lint:
	$(RUFF) check src tests tools deployment scene.py serve.py
	npm run lint --prefix frontend
test:
	$(PYTHON) -m pytest -q
	npm test --prefix frontend
check: lint
	$(RUFF) format --check src tests tools deployment scene.py serve.py
	npm run typecheck --prefix frontend
	npm run format:check --prefix frontend
	$(MAKE) test
frontend-build:
	npm run build --prefix frontend
