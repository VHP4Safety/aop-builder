# AOP Builder

AOP Builder is a monorepo for document-based adverse outcome pathway analysis. It provides a Vue frontend and a Docker Compose backend that can:

- upload and manage document collections
- preprocess and chunk documents
- score chunk relevance
- extract causal relationships with an OpenAI-compatible chat model
- enrich extracted entities against OLS4 and, optionally, an AOP-Wiki MCP service
- review raw and enriched graphs in the browser

## Repository Layout

- `apps/ai-client`: Vue 3 frontend served by Vite for development or Nginx for container builds
- `apps/ai-core`: FastAPI services, workers, and Compose files
- `scripts`: root-level helper scripts that keep commands consistent from the monorepo root
- `.env.example`: reproducible local configuration template with placeholder secrets only

## Prerequisites

Install:

- Docker Engine or Docker Desktop with Docker Compose v2
- Node.js 20+ and npm
- Git

Recommended:

- NVIDIA Container Toolkit if you want GPU-backed Ollama inference through Docker
- Python 3.11+ if you want to debug individual backend services outside Docker

The default local setup pulls `qwen3:14b` into an Ollama container. Use a smaller model such as `qwen3:8b` if local hardware is constrained.

## Reproduce Locally

1. Clone the repository.

```bash
git clone <repo-url>
cd aop-builder
```

2. Create a local environment file.

```bash
cp .env.example .env
```

3. Replace placeholder values in `.env`.

Use `.env.example` as the source of truth for available settings. At minimum, replace the local database password and JWT secret placeholders before starting the stack.

4. Install frontend dependencies.

```bash
cd apps/ai-client
npm install
cd ../..
```

5. Start the backend.

```bash
./scripts/core-up.sh
```

The first run can take time because the `llm_init` container pulls the configured Ollama model into the `ollama_data` volume.

6. Start the frontend.

```bash
./scripts/client-dev.sh
```

7. Open the Vite URL printed by the frontend, usually `http://localhost:5173`.

The default backend gateway is exposed on `http://localhost:8005`, matching the example environment and the Vite proxy in `apps/ai-client/vite.config.ts`.

## Optional AOP-Wiki MCP Enrichment

The repository does not build the AOP MCP image itself. To keep the stack reproducible from this repo alone, the `aop-mcp` service is disabled by default.

To enable it, make sure the MCP image referenced in `.env` exists locally or is pullable, set the MCP base URL in `.env`, then run:

```bash
COMPOSE_PROFILES=aop-mcp ./scripts/core-up.sh
```

Without that profile, enrichment still runs with OLS4 normalization and skips AOP-Wiki MCP lookups.

## Useful Commands

Start backend with local builds:

```bash
./scripts/core-up.sh
```

Stop backend:

```bash
./scripts/core-down.sh
```

Build frontend:

```bash
./scripts/client-build.sh
```

Run frontend dev server:

```bash
./scripts/client-dev.sh
```

Report stale sessions without changing data:

```bash
./scripts/cleanup-stale-sessions.sh --max-age-minutes 15
```

Cancel stale sessions after reviewing the dry-run output:

```bash
./scripts/cleanup-stale-sessions.sh --apply --max-age-minutes 15
```

## Deployment

Backend deployment uses `apps/ai-core/docker-compose-deploy.yml`, which references prebuilt GHCR images instead of building from local source.

1. Build and publish images through the root GitHub Actions workflow in `.github/workflows/docker.yml`, or publish equivalent images.
2. Copy `.env.example` to `.env` on the deployment host and replace all required placeholders.
3. Set the deploy image registry and tag in `.env` to match the published backend images.
4. Start the deploy stack:

```bash
./scripts/core-deploy.sh
```

The deploy compose file binds service ports to `127.0.0.1` by default. Put a reverse proxy in front of `public_gateway` if the API should be reachable from another host.

Notes:

- The frontend image is built by CI, but it is not currently included in `docker-compose-deploy.yml`. Deploy it separately or add it behind your reverse proxy.
- `aop-mcp` remains optional in deploy as well. Use `COMPOSE_PROFILES=aop-mcp ./scripts/core-deploy.sh` only when the MCP image is available.
- The workflow uses the built-in GitHub token with package write permissions; no personal access token is required for publishing to the same GitHub organization/user package namespace.

## Secret Handling

Tracked files should contain placeholders only. The root `.env` file is ignored by git and should never be committed.

Before publishing, run:

```bash
git status --short
rg -n --hidden -g '!.git/**' -g '!apps/ai-client/package-lock.json' \
  '(api[_-]?key|secret|password|token|bearer|BEGIN (RSA|OPENSSH|PRIVATE) KEY)' .
git grep -n -I -E \
  '(sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AIza[0-9A-Za-z_-]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|PRIVATE) KEY)' \
  $(git rev-list --all) -- .
```

This review found no high-confidence API keys, tokens, or private keys in the current tree or history. History does contain old demo placeholders such as `myuser`, `mypassword`, and `replace-with-openai-key`; those are not real secrets but they may still look noisy to automated scanners.

## Troubleshooting

### Missing `.env`

```bash
cp .env.example .env
```

Then replace the required placeholders documented in `.env.example`.

### Frontend Cannot Reach Backend

Check:

- backend containers are running with `cd apps/ai-core && docker compose --env-file ../../.env ps`
- the gateway port matches the Vite proxy
- browser requests are going to `/auth`, `/collections`, and `/sessions`

### Backend Service Restarts

Inspect logs:

```bash
cd apps/ai-core
docker compose --env-file ../../.env logs public_gateway
docker compose --env-file ../../.env logs cer_service
```

### Model Pull or CER Extraction Fails

Check:

- Docker has enough disk space for the selected Ollama model
- GPU support is available if `gpus: all` is required on your host
- the selected model tags are available to Ollama
- the CER API base URL points at the in-stack Ollama service for the default local path

### Port Conflicts

Common local ports:

- `5173`: Vite
- `8005`: public gateway
- `11434`: Ollama
- `5432`: Postgres
- `27017`: MongoDB
- `5672` and `15672`: RabbitMQ

Stop the conflicting process or adjust the mapped ports in `.env` and `apps/ai-core/docker-compose.yml`.
