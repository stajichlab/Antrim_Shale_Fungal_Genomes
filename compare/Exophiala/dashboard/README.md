# BFD comparative-genomics dashboard

Self-contained, browsable comparative visualizations over `db/BFD.duckdb` (11 Chaetothyriales
genomes: 10 *Exophiala* spp. + *Cyphellophora europaea* outgroup), plus an optional local
natural-language chat layer over the same database.

See `/rhome/jstajich/.claude/plans/async-skipping-crescent.md` for the design rationale
(reviewed for statistical soundness and structure/strategy before implementation).

## Build the static dashboard

```
python3 bin/make_dashboard.py --db ../db/BFD.duckdb --out explorer.html
```

Two explicit steps under the hood (`--compute` writes `cache/payload.json`; `--render` builds
`explorer.html` from the cache) so re-theming the HTML doesn't re-run PERMANOVA. Open
`explorer.html` directly in a browser -- no server needed.

Tabs: **Overview** (per-genome stats + BUSCO), **Ordination Explorer** (PCoA/CA per feature set:
assembly stats, codon usage, amino-acid usage, Pfam/CAZy/MEROPS domain content, secretion/
localization profile -- each gene-count-normalized where relevant, with PERMANOVA + a stated
small-n/dispersion caveat), **Composition** (per-species codon/AA bars + a differential
domain-family list: present-only / absent-only / top fold-change, each linking to example
`protein_id`s), **Species Detail** (click any species to see its position across all feature
sets in one place -- includes an "*E. mansonii* vs rest" comparison since that's the same
machinery, just a different focus selection).

**Ordination Explorer** also shows a reference cladogram from
`results/phyling_pep/protein/buildtree/fungi_odb10/fasttree/protein-Emarsonii-taxa_11.fungi_odb10.fasttree.support.treefile`
-- a proper BUSCO/PHYling gene tree built from exactly these 11 genomes (unlike the
population-scale ASTRAL tree in `../../phylogeny/`, every tip here matches a species+strain
1:1). Species ordering across the whole dashboard (tiles, tables) follows the tree's tip order
when the tree loads successfully; it falls back to taxonomic order otherwise (see
`lib/bfd_data.load_tree`/`phylo_layout`).

Cross-links to the NovInvenio `view/Exophiala/*.html` reports are still deferred (fast-follow
-- see the plan doc, §4).

## Optional: NL chat layer

```bash
# Choose your LLM provider (Anthropic, OpenAI commercial, or any OpenAI-compatible endpoint):
export ANTHROPIC_API_KEY="sk-ant-..."     # Anthropic (default model: claude-sonnet-5)
# or
export OPENAI_API_KEY="sk-..."            # OpenAI commercial (default model: gpt-4o)
# or
export CUSTOM_LLM_BASE_URL="https://..."   # OpenAI-compatible (NRP.ai, Groq, Ollama, vLLM, etc.)
export CUSTOM_LLM_API_KEY="<token>"
export CUSTOM_LLM_MODEL="qwen3"           # e.g. qwen3 on NRP.ai

pip install --user fastapi uvicorn httpx   # httpx is required; duckdb is in the shared env
python3 chat/server.py --db ../db/BFD.duckdb
ssh -L 8811:localhost:8811 <this-host>    # from your laptop
# open http://localhost:8811/
```

The server detects which provider to use from the env vars above, in priority order:
Anthropic → OpenAI commercial → OpenAI-compatible (CUSTOM_LLM_*).

Read-only by construction: the LLM-generated SQL is checked (single SELECT/WITH, no DDL/DML,
`;`-free, LIMIT-capped) before it ever reaches a `duckdb.connect(..., read_only=True)`
connection, and the SQL used is always shown in the UI.

## Dependencies

Base conda `python3` on this host already has `duckdb`, `numpy`, `scipy`, `pandas`,
`scikit-learn`, `biopython` -- enough for the dashboard (`scikit-bio`/`prince` are not
installed; PCoA and correspondence analysis are implemented directly in `lib/ordination.py`
instead of pulling those in). The chat server additionally needs `fastapi`, `uvicorn`,
`anthropic` (not installed; see above).
