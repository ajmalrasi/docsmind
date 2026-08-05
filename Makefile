# DocsMind — local development + DigitalOcean execution
#
# The git repo lives on the development machine. Remote workloads run on a
# DigitalOcean Droplet; GPU-dependent targets require a GPU Droplet. `make sync`
# mirrors the working tree to that Droplet, and the digitalocean-* targets run
# commands there over SSH.

DIGITALOCEAN_HOST ?=
DIGITALOCEAN_DIR  ?= /home/docsmind/app
PY          ?= python3
VENV        ?= .venv
WHATSAPP_ZIP ?=
AWS_PROFILE ?= ml-prep-deploy
AWS_REGION ?= us-east-1

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
ingest: ## Build the configured vector index
	$(VENV)/bin/python -m scripts.ingest

.PHONY: wikipedia-corpus
wikipedia-corpus: ## Fetch the curated Volkswagen Wikipedia snapshot
	$(VENV)/bin/python -m scripts.fetch_wikipedia $(ARGS)

.PHONY: prepare-whatsapp
prepare-whatsapp: ## Anonymize a WhatsApp export (WHATSAPP_ZIP=/path/chat.zip)
	@test -n "$(WHATSAPP_ZIP)" || (echo "Set WHATSAPP_ZIP=/path/to/chat.zip" && exit 1)
	$(VENV)/bin/python -m scripts.prepare_whatsapp \
		--input "$(WHATSAPP_ZIP)" \
		--output data/private/whatsapp/vagbay.whatsapp.jsonl \
		--chat VAGBAY

.PHONY: serve
serve: ## Run the FastAPI server on :8000
	$(VENV)/bin/uvicorn docsmind.serving.app:app --host 0.0.0.0 --port 8000

.PHONY: demo
demo: ## Ingest if needed, then run a sample query with citations
	$(VENV)/bin/python -m scripts.demo

.PHONY: vllm-smoke
vllm-smoke: ## Test the configured authenticated vLLM endpoint (no corpus needed)
	$(VENV)/bin/python -m scripts.vllm_smoke $(ARGS)

.PHONY: vllm-demo
vllm-demo: ## Run the full RAG pipeline with vLLM primary + cloud fallback
	DOCSMIND_LLM_PROVIDER=router $(VENV)/bin/python -m scripts.demo $(ARGS)

.PHONY: vllm-benchmark
vllm-benchmark: ## Measure vLLM TTFT, latency, and throughput (corpus-independent)
	$(VENV)/bin/python -m scripts.vllm_benchmark $(ARGS)

.PHONY: test
test: ## Run the offline test suite
	$(VENV)/bin/pytest

.PHONY: benchmark
benchmark: ## Benchmark FAISS index types (recall@k vs latency vs memory)
	$(VENV)/bin/python -m scripts.benchmark

.PHONY: eval
eval: ## Retrieval eval: dense vs hybrid (add ARGS=--rerank for the cross-encoder)
	$(VENV)/bin/python -m scripts.retrieval_eval $(ARGS)

.PHONY: notebook
notebook: ## Open the visual pipeline walkthrough in JupyterLab
	$(VENV)/bin/jupyter lab notebooks/docsmind_pipeline_walkthrough.ipynb

# ---------- AWS embedding service ----------

.PHONY: aws-embedding-deploy
aws-embedding-deploy: ## Deploy the CPU BGE-M3 ECS/EC2 development service
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) bash scripts/aws_embedding_service.sh deploy

.PHONY: aws-embedding-status
aws-embedding-status: ## Show CloudFormation and ECS embedding-service status
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) bash scripts/aws_embedding_service.sh status

.PHONY: aws-embedding-start
aws-embedding-start: ## Start one CPU embedding EC2 instance and ECS task
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) bash scripts/aws_embedding_service.sh start

.PHONY: aws-embedding-stop
aws-embedding-stop: ## Stop the ECS task and scale embedding EC2 capacity to zero
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) bash scripts/aws_embedding_service.sh stop

.PHONY: aws-embedding-tunnel
aws-embedding-tunnel: ## Tunnel localhost:8080 to private TEI through SSM
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) bash scripts/aws_embedding_service.sh tunnel

.PHONY: aws-embedding-logs
aws-embedding-logs: ## Follow TEI container logs in CloudWatch
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) bash scripts/aws_embedding_service.sh logs

.PHONY: aws-embedding-benchmark
aws-embedding-benchmark: ## Benchmark TEI through the localhost SSM tunnel
	$(VENV)/bin/python -m scripts.embedding_benchmark $(ARGS)

.PHONY: wikipedia-embedding-eval
wikipedia-embedding-eval: ## Compare bge-small and BGE-M3 persisted Wikipedia indexes
	$(VENV)/bin/python -m scripts.wikipedia_embedding_eval $(ARGS)

# ---------- DigitalOcean (remote) ----------

.PHONY: check-digitalocean
check-digitalocean:
	@test -n "$(DIGITALOCEAN_HOST)" || \
		(echo "Set DIGITALOCEAN_HOST=user@droplet-ip" && exit 1)

.PHONY: sync
sync: check-digitalocean ## Sync the working tree to DigitalOcean
	rsync -az --delete \
		--exclude '.git' --exclude '.venv' --exclude '__pycache__' \
		--exclude 'data/index' --exclude '*.egg-info' \
		./ $(DIGITALOCEAN_HOST):$(DIGITALOCEAN_DIR)/

.PHONY: digitalocean-install
digitalocean-install: sync ## Install the package on DigitalOcean
	ssh $(DIGITALOCEAN_HOST) "cd $(DIGITALOCEAN_DIR) && python3 -m venv .venv && .venv/bin/pip install -U pip && .venv/bin/pip install -e '.[dev]'"

.PHONY: digitalocean-ingest
digitalocean-ingest: sync ## Build the index on DigitalOcean
	ssh $(DIGITALOCEAN_HOST) "cd $(DIGITALOCEAN_DIR) && .venv/bin/python -m scripts.ingest"

.PHONY: digitalocean-opensearch-smoke
digitalocean-opensearch-smoke: sync ## Run the OpenSearch smoke check from DigitalOcean
	ssh $(DIGITALOCEAN_HOST) "cd $(DIGITALOCEAN_DIR) && .venv/bin/python -m scripts.opensearch_smoke $(ARGS)"

.PHONY: digitalocean-demo
digitalocean-demo: sync ## Run the demo on DigitalOcean
	ssh $(DIGITALOCEAN_HOST) "cd $(DIGITALOCEAN_DIR) && .venv/bin/python -m scripts.demo"

.PHONY: digitalocean-test
digitalocean-test: sync ## Run tests on DigitalOcean
	ssh $(DIGITALOCEAN_HOST) "cd $(DIGITALOCEAN_DIR) && .venv/bin/pytest"

.PHONY: digitalocean-serve
digitalocean-serve: sync ## Serve from the DigitalOcean Droplet on :8000
	ssh $(DIGITALOCEAN_HOST) "cd $(DIGITALOCEAN_DIR) && .venv/bin/uvicorn docsmind.serving.app:app --host 0.0.0.0 --port 8000"

.PHONY: digitalocean-eval
digitalocean-eval: sync ## Run reranker evaluation on a DigitalOcean GPU Droplet
	ssh $(DIGITALOCEAN_HOST) "cd $(DIGITALOCEAN_DIR) && .venv/bin/python -m scripts.retrieval_eval --rerank"
