# ai-core

Backend services for AOP Builder. Run them from the repository root so Compose receives the shared `.env` file.

## Local Run

```bash
cp ../../.env.example ../../.env
../../scripts/core-up.sh
```

## Deployment

Use the root deployment entrypoint:

```bash
../../scripts/core-deploy.sh
```

That command uses `docker-compose-deploy.yml` and prebuilt GHCR images. See the root README for required environment values and optional AOP MCP configuration.
