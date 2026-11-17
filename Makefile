PYTHON ?= python
RUFF = $(PYTHON) -m ruff

.PHONY: format lint arch docs test test-portable check frontend-build
format:
	$(RUFF) format src tests tools deployment/windows scene.py serve.py
	npm run format --prefix frontend
lint:
	$(RUFF) check src tests tools deployment/windows scene.py serve.py
	npm run lint --prefix frontend
arch:
	$(PYTHON) tools/check_architecture.py

docs:
	$(PYTHON) tools/render_workflow_doc.py --check

test:
	$(PYTHON) -m pytest -q
	npm test --prefix frontend
test-portable:
	$(PYTHON) -m pytest tests/portable -q
check: lint arch docs
	$(RUFF) format --check src tests tools deployment/windows scene.py serve.py
	npm run typecheck --prefix frontend
	npm run format:check --prefix frontend
	$(MAKE) test
frontend-build:
	npm run build --prefix frontend
