# BFD chat server — setup and connection guide

Optional natural-language query layer over `db/BFD.duckdb`. Not part of the static dashboard
build (`explorer.html`) — it's a small local FastAPI service you start on demand, ask questions
against, and stop when you're done. Nothing here needs to run continuously.

## What it does

You type a question in plain English (e.g. "which species has the most CAZy families?"). The
server sends your question, plus the database's table/column schema, to an LLM and asks
for a single read-only SQL query back. The LLM provider is pluggable (see §1 below).

Before running the query, the server checks the SQL is a single `SELECT`/`WITH` statement
with no `;`, no `DROP`/`DELETE`/`INSERT`/`ATTACH`/etc, and adds a `LIMIT` if one is missing
— then runs it against a **read-only** DuckDB connection as a second line of defense.
The SQL used is always shown in the UI so you can verify it, not just trust it.

It never modifies `BFD.duckdb`, and it never sends the database's contents to the LLM —
only the schema (table/column names and types) and your question.

## 1. Choose your LLM provider

The server detects which provider to use from environment variables, in this priority order:

| Provider | Env vars to set | Default model |
|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-5` |
| OpenAI commercial | `OPENAI_API_KEY` | `gpt-4o` |
| OpenAI-compatible | `CUSTOM_LLM_BASE_URL` + `CUSTOM_LLM_API_KEY` + `CUSTOM_LLM_MODEL` | — |

### NRP.ai (recommended for this HPC environment)

The HPC cluster runs NRP.ai pods with qwen3 and other models behind an OpenAI-compatible
endpoint. Set:

```bash
export CUSTOM_LLM_BASE_URL="https://ellm.nrp-nautilus.io/v1"
export CUSTOM_LLM_API_KEY="$OPENAI_API_KEY"   # same token you use elsewhere on NRP.ai
export CUSTOM_LLM_MODEL="qwen3"
```

Available models on NRP.ai (from `~/.config/opencode/opencode.jsonc`):
`qwen3`, `qwen3-small`, `gpt-oss`, `gemma`, `gemma-small`, `kimi`, `glm-5`, `minimax-m2`, `olmo`.
Set `CUSTOM_LLM_MODEL` to whichever you want for SQL generation.

### Anthropic

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export ANTHROPIC_MODEL="claude-sonnet-5"
```

### OpenAI commercial

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o"
```

## 2. Install dependencies

On the HPCC host, in the `compare/Exophiala/` directory:

```bash
pip install --user fastapi uvicorn httpx
```

`duckdb` is already in the base Python environment. `httpx` is the only additional
dependency (used for the OpenAI-compatible client). No Anthropic SDK needed unless you
specifically want Anthropic as your provider.

## 3. Start the server

From `compare/Exophiala/`:

```bash
python3 dashboard/chat/server.py --db db/BFD.duckdb
```

You should see uvicorn log a line like:

```
Uvicorn running on http://127.0.0.1:8811 (Press CTRL+C to quit)
```

Leave this running in its own terminal (or a `tmux`/`screen` session if you're on a login
node and want it to survive a disconnect). `Ctrl+C` stops it.

If you see `EnvironmentError: No LLM credentials found`, double-check the env vars from §1
are set in the same shell you launched `server.py` from.

Optional flags:

- `--port 8811` — change the port if 8811 is already in use.
- `--host 127.0.0.1` — the default; do not change this to `0.0.0.0` on a shared HPC node.

## 5. Connect from your laptop

In a **new terminal on your laptop** (not on the cluster), open an SSH tunnel that forwards a
local port to the server's port on the cluster:

```bash
ssh -L 8811:localhost:8811 <your-username>@<hpcc-login-host>
```

Replace `<your-username>@<hpcc-login-host>` with however you normally SSH into this cluster
(the same hostname you'd use for a regular login). Leave this SSH session open — it's the
tunnel; closing it disconnects the browser from the server.

If you started the server on a different port (`--port 8822`), forward that port instead:
`ssh -L 8822:localhost:8822 ...`, and use the matching port in your browser.

If you started the server on a compute/interactive node rather than the login node (common if
you requested an interactive SLURM allocation), you may need a two-hop tunnel instead, since the
compute node usually isn't reachable directly:

```bash
ssh -L 8811:localhost:8811 <username>@<login-host> \
    ssh -L 8811:localhost:8811 -N <compute-node-hostname>
```

Ask whoever manages the cluster's SSH config if the two-hop form doesn't connect — node names
and jump-host setups vary by site.

## 6. Open it in a browser

With the tunnel open, go to:

```
http://localhost:8811/
```

You'll see a single text box. Type a question and press "Ask" (or Enter). Example questions to
try first:

- "which species has the most CAZy families?"
- "compare GC percent across genus"
- "list Pfam domains that only appear in Exophiala mansonii"
- "how many genes does each species have, sorted descending?"

Each answer shows the generated SQL above the result table — read it before trusting the
numbers, especially for anything that will go into a figure or a claim.

## 7. Stopping / cleaning up

- Close the browser tab any time.
- `Ctrl+C` the `server.py` process on the cluster when you're done (or exit the tmux/screen
  session running it).
- Close the SSH tunnel terminal on your laptop (or just let it end when you disconnect).

Nothing here needs to be left running between sessions — start it fresh each time you want to
use the chat interface.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'httpx'`** — step 2 wasn't run in the same
  Python environment you're launching `server.py` with. Run `pip install --user fastapi
  uvicorn httpx` in that environment.
- **`EnvironmentError: No LLM credentials found`** — none of `ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, or `CUSTOM_LLM_BASE_URL` is set in the shell you launched
  `server.py` from. Re-export the env vars there (env vars don't carry over into a new
  terminal/tmux pane automatically).
- **Browser can't connect / times out** — the SSH tunnel isn't open, or the port doesn't
  match between `--port` and the `-L` forward. Confirm the server is still running and
  the tunnel terminal is still open.
- **"Refused: query must be a single SELECT/WITH statement"** or similar — this is the
  read-only guard working as intended; it means the generated SQL wasn't a plain read query.
  Rephrase the question more directly (e.g. avoid words like "delete" or "update" even in a
  hypothetical sense — the model sometimes echoes them into the SQL it drafts).
