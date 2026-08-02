# Chatbot Deployment Plan: BFD Natural-Language DB Explorer

## Implementation Status

| Phase | Status | Files |
|---|---|---|
| Phase 1: LLM abstraction | ✅ DONE | `lib/llm_clients.py`, `chat/server.py` |
| Phase 2: Dockerize | ✅ DONE | `Dockerfile`, `.dockerignore`, `k8s/build.sh` |
| Phase 3: K8s deployment | ✅ DONE | `k8s/deployment.yaml` (all-in-one) |
| Phase 4: Frontend polish | ⬜ TODO | `chat/static/chat.html` |

---

## Quick-Start: What Was Built

### Backend: LLM pluggable (`lib/llm_clients.py`)

Three providers, picked by env var at runtime:

| Provider | Env vars | Default model |
|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-5` |
| OpenAI commercial | `OPENAI_API_KEY` | `gpt-4o` |
| NRP.ai / OpenAI-compatible | `CUSTOM_LLM_BASE_URL` + `CUSTOM_LLM_API_KEY` + `CUSTOM_LLM_MODEL` | `qwen3` |

**NRP.ai config** (confirmed from `~/.config/opencode/opencode.jsonc`):
```
CUSTOM_LLM_BASE_URL=https://ellm.nrp-nautilus.io/v1
CUSTOM_LLM_API_KEY=$OPENAI_API_KEY
CUSTOM_LLM_MODEL=qwen3
```

Available NRP.ai models: `qwen3`, `qwen3-small`, `gpt-oss`, `gemma`, `gemma-small`, `kimi`, `glm-5`, `minimax-m2`, `olmo`.

### Docker (`Dockerfile`)

```bash
# Build from the Exophiala/ project root:
./dashboard/k8s/build.sh

# Or manually:
docker build -t bfd-chat:latest -f dashboard/Dockerfile .

# Run locally:
docker run --rm -p 8811:8000 \
  -v $(pwd)/db/BFD.duckdb:/data/BFD.duckdb:ro \
  -e BFD_DUCKDB_PATH=/data/BFD.duckdb \
  -e CUSTOM_LLM_BASE_URL="https://ellm.nrp-nautilus.io/v1" \
  -e CUSTOM_LLM_MODEL="qwen3" \
  -e OPENAI_API_KEY \
  bfd-chat:latest
# open http://localhost:8811/
```

Key design choices:
- Lazy app construction: `chat/server.py` uses module-level `__getattr__` so the DB is not opened and LLM client is not initialized until uvicorn first touches `app`. This means the image can be built without the .duckdb file present.
- Non-root user (`appuser`, uid 1000) matching K8s `runAsNonRoot` security context.
- `HEALTHCHECK` hitting `/health` for both `docker run` and K8s liveness probes.

### Kubernetes (`k8s/deployment.yaml`)

All-in-one YAML: Secret + Deployment + Service + optional PVC + optional Ingress.

Steps to deploy:
1. Push image to a registry accessible from NRP.ai (see `k8s/build.sh --push`).
2. Create the PVC for `BFD.duckdb` (uncomment the PVC section in the manifest or create via the NRP.ai UI).
3. Set your LLM credentials in the Secret section (uncomment the right provider block).
4. Replace `<your-registry>/bfd-chat:latest` with your actual image path.
5. `kubectl apply -f k8s/deployment.yaml`
6. Watch: `kubectl rollout status deployment/bfd-chat`

---

## File Map

```
compare/Exophiala/dashboard/
├── Dockerfile               # Phase 2: container image definition
├── .dockerignore            # Phase 2: exclude build artifacts
├── lib/
│   ├── llm_clients.py       # Phase 1: LLM abstraction (NEW)
│   ├── bfd_data.py          # existing: DB schema introspection
│   └── ordination.py        # existing: PCoA/CA (static dashboard)
├── chat/
│   ├── server.py            # Phase 1: refactored to use llm_clients
│   └── static/chat.html     # existing: minimal chat UI
├── k8s/
│   ├── deployment.yaml      # Phase 3: Secret + Deployment + Service + optional PVC/Ingress (all-in-one)
│   └── build.sh             # Phase 2: docker build/push helper script
└── explorer.html            # existing: static dashboard (separate)
```

---

## Checklist (updated)

- [x] Add `lib/llm_clients.py` (LLM abstraction: Anthropic, OpenAI, NRP.ai/OpenAI-compatible)
- [x] Refactor `chat/server.py` to use `make_llm_client()` instead of hardcoded Anthropic
- [x] Add `/health` endpoint to `make_app()`
- [x] Lazy app construction via `__getattr__` (no DB open at import time)
- [x] Write `Dockerfile` and `.dockerignore`
- [x] Write `k8s/build.sh` helper script
- [x] Write `k8s/deployment.yaml` (Secret + Deployment + Service + optional PVC + optional Ingress)
- [ ] Build Docker image (needs Docker runtime — run on NRP.ai pod or local machine)
- [ ] Push image to NRP.ai / container registry
- [ ] Provision PVC for `BFD.duckdb` on the NRP.ai cluster
- [ ] Set `CUSTOM_LLM_API_KEY` secret with your NRP.ai token
- [ ] Replace `<your-registry>/bfd-chat:latest` in the Deployment manifest
- [ ] `kubectl apply -f k8s/deployment.yaml`
- [ ] Smoke-test `/health`, `/ask` endpoints, and SQL correctness end-to-end
