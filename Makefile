# DocsMind — local dev + remote (beast) execution
#
# The git repo lives here (Mac); heavy work runs on `beast` (RTX 3070 Ti, Ollama,
# Docker). `make sync` mirrors the working tree to beast; the beast-* targets run
# commands there over SSH.

BEAST       ?= ajmalrasi@192.168.3.226
BEAST_DIR   ?= ~/projects/docsmind
PY          ?= python
VENV        ?= .venv

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ---------- local ----------

.PHONY: install
install: ## Create a venv and install the package (dev extras)
	$(PY) -m venv $(VENV)
	$(VENV)/bin/pip install -U pip
	$(VENV)/bin/pip install -e ".[dev]"

.PHONY: ingest
ingest: ## Build the FAISS index from data/sample_docs
	$(VENV)/bin/python -m scripts.ingest

.PHONY: serve
serve: ## Run the FastAPI server on :8000
	$(VENV)/bin/uvicorn docsmind.serving.app:app --host 0.0.0.0 --port 8000

.PHONY: demo
demo: ## Ingest if needed, then run a sample query with citations
	$(VENV)/bin/python -m scripts.demo

.PHONY: test
test: ## Run the offline test suite
	$(VENV)/bin/pytest

.PHONY: benchmark
benchmark: ## Benchmark FAISS index types (recall@k vs latency vs memory)
	$(VENV)/bin/python -m scripts.benchmark

.PHONY: eval
eval: ## Retrieval eval: dense vs hybrid (add ARGS=--rerank for the cross-encoder)
	$(VENV)/bin/python -m scripts.retrieval_eval $(ARGS)

# ---------- beast (remote) ----------

.PHONY: sync
sync: ## rsync the working tree to beast (excludes venv, index, .git)
	rsync -az --delete \
		--exclude '.git' --exclude '.venv' --exclude '__pycache__' \
		--exclude 'data/index' --exclude '*.egg-info' \
		./ $(BEAST):$(BEAST_DIR)/

.PHONY: beast-install
beast-install: sync ## Install the package on beast
	ssh $(BEAST) "cd $(BEAST_DIR) && python3 -m venv .venv && .venv/bin/pip install -U pip && .venv/bin/pip install -e '.[dev]'"

.PHONY: beast-ingest
beast-ingest: sync ## Build the index on beast
	ssh $(BEAST) "cd $(BEAST_DIR) && .venv/bin/python -m scripts.ingest"

.PHONY: beast-demo
beast-demo: sync ## Run the demo on beast (uses its GPU for embeddings)
	ssh $(BEAST) "cd $(BEAST_DIR) && .venv/bin/python -m scripts.demo"

.PHONY: beast-test
beast-test: sync ## Run tests on beast
	ssh $(BEAST) "cd $(BEAST_DIR) && .venv/bin/pytest"

.PHONY: beast-serve
beast-serve: sync ## Serve from beast on :8000 (reachable on the LAN)
	ssh $(BEAST) "cd $(BEAST_DIR) && .venv/bin/uvicorn docsmind.serving.app:app --host 0.0.0.0 --port 8000"

.PHONY: beast-eval
beast-eval: sync ## Run the retrieval eval on beast with the reranker (GPU)
	ssh $(BEAST) "cd $(BEAST_DIR) && .venv/bin/python -m scripts.retrieval_eval --rerank"
