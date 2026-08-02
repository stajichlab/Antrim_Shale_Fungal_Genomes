#!/usr/bin/env python3
"""
Optional local NL -> DuckDB SQL chat service over the BFD database.

Not part of the static dashboard build -- start on demand:

    export ANTHROPIC_API_KEY=...
    python dashboard/chat/server.py --db ../../db/BFD.duckdb
    # then, from your laptop:
    ssh -L 8811:localhost:8811 <cluster-host>
    # open http://localhost:8811/ in a browser

Requires `fastapi`, `uvicorn`, `anthropic` -- not in the base pixi env used for the rest of
this dashboard (checked: only duckdb/scipy/numpy/pandas/scikit-learn are available). Install
with `pip install --user fastapi uvicorn anthropic` (or add to the pixi env) before running
this. No public exposure: bind to localhost only and access via SSH port-forward.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DASHBOARD_DIR / "lib"))   # bfd_data lives here as a top-level module
sys.path.insert(0, str(DASHBOARD_DIR))           # llm_clients lives under lib/ as a subpackage

import bfd_data as bd  # noqa: E402

try:
    import duckdb
    import uvicorn
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
except ImportError as e:
    sys.exit(
        f"Missing dependency ({e}). Install with:\n"
        "  pip install --user fastapi uvicorn httpx duckdb\n"
        "(duckdb is in the shared pixi env; httpx is the only extra needed.)"
    )
MAX_ROWS = 500

# Read-only guard: reject anything that isn't a single SELECT/WITH statement. This is
# defense-in-depth #1; the duckdb connection is also opened read_only=True (defense #2), so
# even a slipped-through mutation fails at the database layer.
_FORBIDDEN = re.compile(
    r"\b(ATTACH|DETACH|COPY|PRAGMA|INSTALL|LOAD|CREATE|INSERT|UPDATE|DELETE|DROP|ALTER|GRANT|CALL|EXPORT|IMPORT)\b",
    re.IGNORECASE,
)


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    sql: str
    columns: list[str]
    rows: list[list]
    truncated: bool


def build_system_prompt(schema_text: str) -> str:
    return f"""You translate natural-language questions into a single read-only DuckDB SQL
query over the following schema (table(column type, ...)):

{schema_text}

Rules:
- Output ONLY the SQL query, no prose, no markdown code fences.
- A single SELECT or WITH...SELECT statement. No semicolons, no multiple statements.
- Never use ATTACH/COPY/PRAGMA/INSTALL/CREATE/INSERT/UPDATE/DELETE/DROP/ALTER.
- Always include a LIMIT clause (<= {MAX_ROWS}) unless the question clearly wants an
  aggregate scalar (e.g. COUNT(*)).
- species_prefix / LOCUSTAG columns identify a genome; join through `species` for taxonomy
  (GENUS, SPECIES, STRAIN) or `v_species_summary` for precomputed per-genome summary stats.
"""


def validate_sql(sql: str) -> str:
    sql = sql.strip().strip(";").strip()
    if not re.match(r"^\s*(SELECT|WITH)\b", sql, re.IGNORECASE):
        raise HTTPException(400, "Refused: query must be a single SELECT/WITH statement.")
    if ";" in sql:
        raise HTTPException(400, "Refused: multi-statement queries are not allowed.")
    if _FORBIDDEN.search(sql):
        raise HTTPException(400, "Refused: query contains a disallowed keyword.")
    if not re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
        sql = f"{sql}\nLIMIT {MAX_ROWS}"
    return sql


def make_app(db_path: Path) -> "FastAPI":
    con = bd.get_connection(db_path)  # read_only=True -- second line of defense
    schema_text = bd.schema_context(con)  # reused from bfd_data.py; keeps dashboard/chat in sync
    system_prompt = build_system_prompt(schema_text)
    from lib.llm_clients import make_llm_client  # noqa: E402
    llm = make_llm_client()

    app = FastAPI(title="BFD chat")

    @app.get("/health")
    def health():
        """Kubernetes readiness/liveness probe."""
        return {"status": "ok"}

    @app.post("/ask", response_model=AskResponse)
    def ask(req: AskRequest) -> AskResponse:
        raw_sql = llm.complete(system_prompt, req.question, max_tokens=500).strip()
        sql = validate_sql(raw_sql)

        try:
            result = con.execute(sql)
        except duckdb.Error as e:
            raise HTTPException(400, f"DuckDB rejected the generated query: {e}\nSQL was:\n{sql}")

        columns = [d[0] for d in result.description]
        rows = result.fetchmany(MAX_ROWS + 1)
        truncated = len(rows) > MAX_ROWS
        rows = rows[:MAX_ROWS]
        return AskResponse(sql=sql, columns=columns, rows=[list(r) for r in rows], truncated=truncated)

    static_dir = Path(__file__).resolve().parent / "static"

    @app.get("/")
    def index():
        return FileResponse(static_dir / "chat.html")

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    return app


# --- Lazy app (defers DB open + LLM init until uvicorn first touches `app`) ---
_lazy_app: "FastAPI | None" = None


def _get_app() -> "FastAPI":
    global _lazy_app
    if _lazy_app is None:
        db_path = os.environ.get("BFD_DUCKDB_PATH", "/data/BFD.duckdb")
        _lazy_app = make_app(Path(db_path))
    return _lazy_app


# Module-level __getattr__ makes `from chat.server import app` and
# `uvicorn chat.server:app` both work without triggering DB open at import time.
def __getattr__(name: str):
    if name == "app":
        return _get_app()
    raise AttributeError(name)


def main():
    """CLI entry point (used when running `python chat/server.py` directly)."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=bd.DEFAULT_DB_PATH)
    ap.add_argument("--host", default="127.0.0.1", help="bind address; keep localhost-only, access via SSH tunnel")
    ap.add_argument("--port", type=int, default=8811)
    args = ap.parse_args()
    the_app = make_app(args.db)
    uvicorn.run(the_app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
