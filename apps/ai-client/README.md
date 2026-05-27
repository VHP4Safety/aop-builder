# ai-client

Vue frontend for AOP Builder. It uses the root `.env` file during local development.

```bash
cp ../../.env.example ../../.env
```

## Local Run

```bash
../../scripts/client-dev.sh
```

## Production Build

```bash
../../scripts/client-build.sh
```

The Docker image serves the built app with Nginx. Configure `VITE_API_URL` before building if the frontend should call an absolute backend URL instead of same-origin/proxied API paths.
