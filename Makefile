ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
BACKEND_VENV := $(ROOT)backend/.venv/bin/python

.PHONY: test test-backend test-frontend test-cov test-cov-backend test-cov-frontend check

## test: 前后端全量回归(AI coding 收工前必跑)
test: test-backend test-frontend

test-backend:
	@if [ -x "$(BACKEND_VENV)" ]; then \
		cd $(ROOT)backend && .venv/bin/python -m pytest tests/; \
	else \
		echo "backend/.venv 不存在,请先: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt"; \
		exit 1; \
	fi

test-frontend:
	cd $(ROOT)frontend && pnpm test

test-cov: test-cov-backend test-cov-frontend

test-cov-backend:
	cd $(ROOT)backend && .venv/bin/python -m pytest tests/ --cov=astock --cov-report=term-missing

test-cov-frontend:
	cd $(ROOT)frontend && pnpm test:cov

## check: 测试 + 前端类型检查
check: test
	cd $(ROOT)frontend && pnpm run type:check
