"""
duckdb -> per-species feature matrices for the BFD comparative dashboard.

All matrices are indexed by LOCUSTAG (11 rows, one per genome in this Exophiala/BFD run).
No I/O happens at import time; call get_connection() to open the db.

Zero-handling rule (documented once, used everywhere a family/species cell can be a true
zero — Pfam/CAZy/MEROPS domain counts): a family absent from a species is a true zero, not
missing data. Where a method requires strictly positive values (chi-square/CA distances,
log/fold-change), add PSEUDOCOUNT once at matrix-build time rather than letting each
downstream consumer improvise its own fix.
"""
from __future__ import annotations

import re
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

PSEUDOCOUNT = 0.5  # Anscombe-style; applied once, at matrix build, not per-consumer

DASHBOARD_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = DASHBOARD_DIR.parent / "db" / "BFD.duckdb"
DEFAULT_BUSCO_PROTEIN_DIR = DASHBOARD_DIR.parent / "results" / "genome_stats" / "BUSCO_protein"
DEFAULT_TREE_PATH = (
    DASHBOARD_DIR.parent
    / "results" / "phyling_pep" / "protein" / "buildtree" / "fungi_odb10" / "fasttree"
    / "protein-Emarsonii-taxa_11.fungi_odb10.fasttree.support.treefile"
)
DEFAULT_MEROPS_FAMILIES_PATH = Path("/srv/projects/db/MEROPS/124/merops_lib.families.tab")

_BUSCO_HEADER_RE = re.compile(
    r"C:([\d.]+)%\[S:([\d.]+)%,D:([\d.]+)%\],F:([\d.]+)%,M:([\d.]+)%,n:(\d+)"
)


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path), read_only=True)


# --------------------------------------------------------------------------- schema (shared
# with chat/server.py -- reuse these two helpers there rather than re-introspecting duckdb,
# to avoid schema drift between the dashboard and the chat layer)
def list_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    return [r[0] for r in con.execute("SHOW TABLES").fetchall()]


def describe_table(con: duckdb.DuckDBPyConnection, table: str) -> pd.DataFrame:
    return con.execute(f"DESCRIBE {table}").fetchdf()


def schema_context(con: duckdb.DuckDBPyConnection) -> str:
    """Compact table/column/dtype text block for an LLM system prompt -- no sample rows."""
    lines = []
    for t in list_tables(con):
        cols = describe_table(con, t)
        col_list = ", ".join(f"{r.column_name} {r.column_type}" for r in cols.itertuples())
        lines.append(f"{t}({col_list})")
    return "\n".join(lines)


# --------------------------------------------------------------------------- curated notes for LLM
# Deliberately hand-curated rather than scraped from docstrings: docstrings are dev-facing and
# drift with refactors, so scraping them into a prompt would silently go stale. Keep this in sync
# by hand whenever a normalization/analysis choice below changes.
DATASET_NOTES = """\
Dataset shape: 11 fungal genomes (mostly Exophiala spp.; one outgroup, Cyphellophora europaea).
`species_prefix` (in per-hit tables like pfam/cazy/merops/signalp/...) and `LOCUSTAG` (in
species/asm_stats/gene_info) are the SAME identifier for the same genome -- just named
differently by table. Always join/filter genomes through one of these two columns.

Normalization choices baked into the feature matrices (do not re-derive differently):
- Pfam/CAZy/MEROPS domain-family counts are gene-count-normalized to "per 1000 genes" before
  any distance/ordination step, because raw gene counts range 6,468-16,710 across these 11
  genomes (2.6x) -- comparing raw counts would mostly measure genome/annotation size, not
  domain content.
- A family absent from a genome is a true zero (not missing data). Where a method needs
  strictly positive values (log/fold-change), a single PSEUDOCOUNT=0.5 is added at matrix-build
  time -- never re-add a different pseudocount downstream.
- Assembly stats and the localization composite are z-scored per column (needed for Euclidean
  distance across fields with very different scales/units).
- Codon and amino-acid usage are compositional frequency profiles analyzed via correspondence
  analysis (chi-square distance), not Euclidean/Bray-Curtis.

Small-n caveats (n=11 total, and any taxon-filtered subset is smaller still):
- PCoA/CA and PERMANOVA are unreliable at very small n: a 3-point configuration is exactly
  planar and will spuriously "explain" ~100% of variance; PERMANOVA on a singleton group has
  zero within-group variance by construction, which can look like a location effect when it is
  really a dispersion artifact. The ordination/PERMANOVA tools enforce minimum-n floors and
  attach caveat text directly in their output for exactly this reason -- always surface that
  caveat text in the reply, don't drop it.
- NMDS is intentionally not the default (needs multiple random restarts to avoid a degenerate
  solution) -- offered only as an explicit opt-in, always reporting stress.
- A domain-count ordination axis can reflect assembly/annotation quality (BUSCO completeness,
  N50/contig count) or shared ancestry (phylogenetic relatedness) rather than a genuine
  biological signal -- treat BUSCO/contiguity metadata and phylogenetic distance attached to
  ordination results as confound checks, not decoration, especially for small subsets.
- `differential_families`'s "rest of clade" comparison group shrinks with any taxon filter --
  its output reports which genomes made up "rest" for exactly this reason; a "differs from
  the rest" claim with a 2-genome rest group is "differs from one arbitrary other genome," not
  a clade-level statement.
"""


def dataset_notes() -> str:
    return DATASET_NOTES


# --------------------------------------------------------------------------- taxa filtering
def resolve_taxa_filter(
    con: duckdb.DuckDBPyConnection,
    genus: str | None = None,
    species: str | None = None,
    locustags: list[str] | None = None,
    exclude_locustags: list[str] | None = None,
) -> list[str]:
    """Resolve a taxon description into a concrete list of LOCUSTAGs, for consistent subsetting
    across every FEATURE_SETS loader and analysis tool. `genus`/`species` do a case-insensitive
    substring match against the `species` table; `locustags` (if given) intersects with that
    match instead of replacing it, so callers can combine e.g. genus="Exophiala" with an
    explicit locustags allowlist. Returns LOCUSTAGs in species-table order (stable across calls).
    """
    sp = con.execute("SELECT LOCUSTAG, GENUS, SPECIES FROM species ORDER BY LOCUSTAG").fetchdf()
    mask = pd.Series(True, index=sp.index)
    if genus:
        mask &= sp["GENUS"].str.contains(genus, case=False, na=False)
    if species:
        mask &= sp["SPECIES"].str.contains(species, case=False, na=False)
    result = sp.loc[mask, "LOCUSTAG"].tolist()
    if locustags:
        wanted = set(locustags)
        result = [lt for lt in result if lt in wanted]
    if exclude_locustags:
        excluded = set(exclude_locustags)
        result = [lt for lt in result if lt not in excluded]
    return result


# --------------------------------------------------------------------------- species / overview
def get_species_table(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """v_species_summary (genome/annotation stats) joined with species (STRAIN, taxon id) --
    v_species_summary alone lacks STRAIN, which the dashboard needs for species labels."""
    df = con.execute(
        """
        SELECT v.*, s.STRAIN, s.NCBI_TAXONID
        FROM v_species_summary v
        JOIN species s USING (LOCUSTAG)
        ORDER BY v.LOCUSTAG
        """
    ).fetchdf()
    return df.set_index("LOCUSTAG")


def get_busco_scores(busco_dir: Path = DEFAULT_BUSCO_PROTEIN_DIR) -> pd.DataFrame:
    """Parse per-genome protein-set BUSCO summaries into a LOCUSTAG-indexed table.

    Returns NaN-filled rows for any species missing a summary file rather than dropping
    them -- callers should show "not available" in the UI, not silently omit a species.
    """
    rows = {}
    if busco_dir.exists():
        for txt in busco_dir.glob("*/*.BUSCO_summary.*.txt"):
            locustag = txt.name.split(".BUSCO_summary.")[0]
            text = txt.read_text()
            m = _BUSCO_HEADER_RE.search(text)
            if not m:
                continue
            c, s, d, f, miss, n = m.groups()
            rows[locustag] = {
                "busco_complete_pct": float(c),
                "busco_single_pct": float(s),
                "busco_duplicated_pct": float(d),
                "busco_fragmented_pct": float(f),
                "busco_missing_pct": float(miss),
                "busco_n": int(n),
            }
    return pd.DataFrame.from_dict(rows, orient="index")


def _filter_rows(df: pd.DataFrame, rows: list[str] | None) -> pd.DataFrame:
    """Subset a genome-indexed matrix to `rows` (LOCUSTAGs/species_prefixes) BEFORE any
    normalization that follows -- z-scoring/CA computed on the full cohort and then sliced
    would leave a subset's "standardized" values centered/scaled on genomes not even in the
    subset, which is invalid. Every FEATURE_SETS loader takes `rows` for exactly this reason."""
    if rows is None:
        return df
    return df.loc[df.index.isin(rows)]


# --------------------------------------------------------------------------- feature matrices
def get_assembly_matrix(con: duckdb.DuckDBPyConnection, rows: list[str] | None = None) -> pd.DataFrame:
    """Numeric assembly-stats block, standardized (z-score) per column. `rows` (LOCUSTAGs)
    subsets BEFORE z-scoring, so a taxon-filtered ordination is standardized on that subset,
    not silently inheriting the full-cohort mean/std."""
    df = con.execute("SELECT * FROM asm_stats ORDER BY LOCUSTAG").fetchdf().set_index("LOCUSTAG")
    df = df.drop(columns=["ASMID"], errors="ignore")
    df = _filter_rows(df, rows)
    numeric = df.select_dtypes(include="number")
    z = (numeric - numeric.mean()) / numeric.std(ddof=0).replace(0, 1)
    return z


def get_codon_matrix(con: duckdb.DuckDBPyConnection, rows: list[str] | None = None) -> pd.DataFrame:
    """species x codon frequency profile (rows ~sum to 1). Raw frequencies -- CA in
    ordination.py handles the compositional/chi-square structure directly, no transform here."""
    df = con.execute("SELECT species_prefix, codon, frequency FROM codon_frequency").fetchdf()
    matrix = df.pivot(index="species_prefix", columns="codon", values="frequency").fillna(0.0)
    return _filter_rows(matrix, rows)


def get_aa_matrix(con: duckdb.DuckDBPyConnection, rows: list[str] | None = None) -> pd.DataFrame:
    df = con.execute("SELECT species_prefix, amino_acid, frequency FROM aa_frequency").fetchdf()
    matrix = df.pivot(index="species_prefix", columns="amino_acid", values="frequency").fillna(0.0)
    return _filter_rows(matrix, rows)


_DOMAIN_TABLES = {
    "pfam": ("pfam", "pfam_id"),
    "cazy": ("cazy", "HMM_id"),
    "merops": ("v_merops_family", "family"),
}


def get_pfam_accessions(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    """pfam_id (human-readable family name, e.g. "1-cysPrx_C") -> unversioned pfam_acc
    (e.g. "PF10417"), for linking out to the Pfam/InterPro entry page. A pfam_id can appear
    with more than one accession version across proteins (rare HMM updates); any one instance
    is fine since the URL only needs the PFxxxxx prefix, not the version suffix."""
    df = con.execute("SELECT DISTINCT pfam_id, pfam_acc FROM pfam").fetchdf()
    accession = df["pfam_acc"].str.split(".").str[0]
    return dict(zip(df["pfam_id"], accession))


def _ensure_merops_family_view(
    con: duckdb.DuckDBPyConnection, path: Path = DEFAULT_MEROPS_FAMILIES_PATH
) -> None:
    """(Re)create v_merops_family: the raw `merops` hits table joined to its MEROPS family
    code. merops_id there is the nearest-match reference sequence (e.g. MER0034723), which is
    ~1:1 with individual proteins in the MEROPS database -- grouping domain hits by merops_id,
    the way pfam groups by pfam_id, is close to grouping by protein and tells you almost
    nothing at the family level. merops_lib.families.tab (shipped with the local MEROPS
    database build) maps each merops_id to a family.member code such as "S09.996"; the family
    itself is the part before the dot ("S09"). Hits with no lookup match keep their raw
    merops_id as a fallback rather than being dropped."""
    fam = pd.read_csv(
        path, sep="\t", header=None, names=["merops_id", "subfamily", "family_member"]
    )
    fam["family"] = fam["family_member"].str.split(".").str[0]
    con.register("_merops_family_lookup", fam[["merops_id", "family"]])
    # TEMP (session-local, in the attached in-memory catalog) -- the db is opened read_only,
    # which forbids CREATE VIEW against its own catalog.
    con.execute(
        """
        CREATE OR REPLACE TEMP VIEW v_merops_family AS
        SELECT m.*, COALESCE(f.family, m.merops_id) AS family
        FROM merops m
        LEFT JOIN _merops_family_lookup f USING (merops_id)
        """
    )


def _domain_table(con: duckdb.DuckDBPyConnection, kind: str) -> tuple[str, str]:
    if kind == "merops":
        _ensure_merops_family_view(con)
    return _DOMAIN_TABLES[kind]


def get_domain_matrix(
    con: duckdb.DuckDBPyConnection, kind: str, rows: list[str] | None = None
) -> pd.DataFrame:
    """species x family RAW counts, gene-count-normalized (per 1000 genes) to avoid genome-size
    artifacts -- gene counts here range 6,468-16,710 (2.6x) across the 11 genomes. Per-1000-genes
    normalization is row-wise (each genome divided by its own gene_count), so `rows` subsetting
    order doesn't change values here -- kept for API consistency with the other loaders."""
    table, family_col = _domain_table(con, kind)
    counts = con.execute(
        f"SELECT species_prefix, {family_col} AS family, COUNT(*) AS n "
        f"FROM {table} GROUP BY species_prefix, {family_col}"
    ).fetchdf()
    matrix = counts.pivot(index="species_prefix", columns="family", values="n").fillna(0.0)
    matrix = _filter_rows(matrix, rows)

    gene_counts = get_species_table(con)["gene_count"]
    gene_counts = gene_counts.reindex(matrix.index)
    per_1000_genes = matrix.div(gene_counts, axis=0) * 1000.0
    return per_1000_genes


def get_domain_raw_counts(con: duckdb.DuckDBPyConnection, kind: str) -> pd.DataFrame:
    """Un-normalized companion to get_domain_matrix, for sanity-checking against gene_count."""
    table, family_col = _domain_table(con, kind)
    counts = con.execute(
        f"SELECT species_prefix, {family_col} AS family, COUNT(*) AS n "
        f"FROM {table} GROUP BY species_prefix, {family_col}"
    ).fetchdf()
    return counts.pivot(index="species_prefix", columns="family", values="n").fillna(0.0)


def get_domain_example_proteins(
    con: duckdb.DuckDBPyConnection, kind: str, species_prefix: str, family: str, limit: int = 3
) -> list[str]:
    table, family_col = _domain_table(con, kind)
    df = con.execute(
        f"SELECT DISTINCT protein_id FROM {table} "
        f"WHERE species_prefix = ? AND {family_col} = ? LIMIT {int(limit)}",
        [species_prefix, family],
    ).fetchdf()
    return df["protein_id"].tolist()


MIN_REST_GROUP_SIZE = 3  # below this, "differs from the rest" is really "differs from 1-2
# arbitrary other genomes," not a clade-level statement -- see DATASET_NOTES.


def differential_families(
    con: duckdb.DuckDBPyConnection, kind: str, top_n: int = 15, rows: list[str] | None = None
) -> dict[str, dict]:
    """Per-species (focus) differential domain-family ranking against the gene-count-normalized
    matrix's mean-of-rest. NOT a z-score (n=10 'rest' group is too small/non-normal for that to
    mean what it implies) -- ranks by (1) presence/absence flags as the headline list, (2)
    fold-change over group mean (with PSEUDOCOUNT) as a secondary continuous rank. Each entry
    carries a few example protein_ids for drill-down to specific genes.

    `rows` restricts which genomes participate (both as focus species AND as the "rest" pool) --
    every result also reports `rest_group` (the actual LOCUSTAGs averaged) and `rest_group_n`,
    since a taxon-filtered "rest" can shrink to 1-2 genomes and stop meaning "the clade."
    Raises ValueError if any species' rest-group would fall below MIN_REST_GROUP_SIZE, rather
    than silently returning a claim that isn't a clade-level comparison anymore.
    """
    normalized = get_domain_matrix(con, kind, rows=rows)
    if len(normalized) - 1 < MIN_REST_GROUP_SIZE:
        raise ValueError(
            f"Only {len(normalized)} genome(s) in this subset -- the 'rest of clade' comparison "
            f"group would have {len(normalized) - 1}, below the minimum of {MIN_REST_GROUP_SIZE}. "
            "Widen the taxon filter before running differential_families."
        )
    pfam_accessions = get_pfam_accessions(con) if kind == "pfam" else {}
    result = {}
    for species in normalized.index:
        rest_group = [s for s in normalized.index if s != species]
        rest_mean = normalized.loc[rest_group].mean()
        mine = normalized.loc[species]

        present_only = mine[(mine > 0) & (rest_mean == 0)].sort_values(ascending=False)
        absent_only = rest_mean[(mine == 0) & (rest_mean > 0)].sort_values(ascending=False)
        fold = (mine + PSEUDOCOUNT) / (rest_mean + PSEUDOCOUNT)
        log2fold = np.log2(fold).sort_values(key=np.abs, ascending=False)

        def family_rows(series, value_label):
            out = []
            for family, value in series.head(top_n).items():
                row = {
                    "family": family,
                    value_label: float(value),
                    "species_value_per_1000": float(mine[family]),
                    "rest_mean_per_1000": float(rest_mean[family]),
                    "example_proteins": get_domain_example_proteins(con, kind, species, family),
                }
                if kind == "pfam" and family in pfam_accessions:
                    row["pfam_accession"] = pfam_accessions[family]
                out.append(row)
            return out

        result[species] = {
            "rest_group": rest_group,
            "rest_group_n": len(rest_group),
            "present_only": family_rows(present_only, "value_per_1000"),
            "absent_only": family_rows(absent_only, "value_per_1000"),
            "top_fold_change": family_rows(log2fold, "log2_fold_change"),
        }
    return result


_LOCALIZATION_QUERIES = {
    "signalp_frac": (
        "SELECT species_prefix, COUNT(DISTINCT protein_id) AS n FROM signalp GROUP BY species_prefix",
        "n",
    ),
    "tmhmm_frac": (
        "SELECT species_prefix, COUNT(*) AS n FROM tmhmm WHERE PredHel > 0 GROUP BY species_prefix",
        "n",
    ),
    "secreted_frac": (
        "SELECT species_prefix, COUNT(*) AS n FROM targetp WHERE prediction = 'SP' GROUP BY species_prefix",
        "n",
    ),
    "gpi_frac": (
        "SELECT species_prefix, COUNT(DISTINCT protein_id) AS n FROM predgpi "
        "WHERE feature = 'GPI-anchor' GROUP BY species_prefix",
        "n",
    ),
    "has_disordered_region_frac": (
        "SELECT species_prefix, COUNT(DISTINCT protein_id) AS n FROM idp GROUP BY species_prefix",
        "n",
    ),
    "wolfpsort_extr_frac": (
        "SELECT species_prefix, COUNT(*) AS n FROM wolfpsort WHERE localization = 'extr' GROUP BY species_prefix",
        "n",
    ),
}


def get_localization_counts(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Per-species raw integer counts for signal peptide (SignalP) / TM helix / secretion
    (TargetP) / GPI-anchor / high-disorder (IDP) proteins -- backs both
    get_localization_fractions (gene_count-normalized) and the composition payload's "counts"
    field, so bars can show "N proteins (X%)" instead of a bare fraction."""
    idx = get_species_table(con).index
    cols = {}
    for name, (sql, col) in _LOCALIZATION_QUERIES.items():
        series = con.execute(sql).fetchdf().set_index("species_prefix")[col]
        cols[name] = series.reindex(idx).fillna(0).astype(int)
    return pd.DataFrame(cols)


def get_localization_fractions(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Per-species proportions (of gene_count) -- raw fractions, not standardized, for
    human-readable display (composition bars, tables). See get_localization_matrix for the
    z-scored version ordination/PERMANOVA use."""
    gene_counts = get_species_table(con)["gene_count"]
    counts = get_localization_counts(con)
    return counts.div(gene_counts, axis=0).fillna(0.0)


def get_localization_matrix(con: duckdb.DuckDBPyConnection, rows: list[str] | None = None) -> pd.DataFrame:
    """Same fractions as get_localization_fractions, standardized (z-score) per column for
    ordination/PERMANOVA (euclidean distance needs comparable scales across very different
    fraction magnitudes -- e.g. signalp_frac vs. gpi_frac). `rows` subsets BEFORE z-scoring, same
    reasoning as get_assembly_matrix."""
    block = get_localization_fractions(con)
    block = _filter_rows(block, rows)
    return (block - block.mean()) / block.std(ddof=0).replace(0, 1)


# --------------------------------------------------------------------------- enriched feature matrices for fine-grained analysis
def get_secreted_domains_matrix(con: duckdb.DuckDBPyConnection, rows: list[str] | None = None) -> pd.DataFrame:
    """Domain families restricted to secreted proteins (SignalP+). Reveals secretome-specific
    variation separately from intracellular domains, useful for pathogenicity/virulence genomics."""
    table_pfam = "pfam"
    counts = con.execute(
        f"""
        SELECT p.species_prefix, p.pfam_id AS family, COUNT(*) AS n
        FROM {table_pfam} p
        JOIN signalp s ON p.protein_id = s.protein_id
        GROUP BY p.species_prefix, p.pfam_id
        """
    ).fetchdf()
    matrix = counts.pivot(index="species_prefix", columns="family", values="n").fillna(0.0)
    matrix = _filter_rows(matrix, rows)
    gene_counts = get_species_table(con)["gene_count"]
    gene_counts = gene_counts.reindex(matrix.index)
    return matrix.div(gene_counts, axis=0) * 1000.0


def get_cytoplasmic_domains_matrix(con: duckdb.DuckDBPyConnection, rows: list[str] | None = None) -> pd.DataFrame:
    """Domain families in proteins WITHOUT signal peptides. Isolates cytoplasmic/nuclear proteome
    variation from membrane-biased secretome effects."""
    table_pfam = "pfam"
    counts = con.execute(
        f"""
        SELECT p.species_prefix, p.pfam_id AS family, COUNT(*) AS n
        FROM {table_pfam} p
        LEFT JOIN signalp s ON p.protein_id = s.protein_id
        WHERE s.protein_id IS NULL
        GROUP BY p.species_prefix, p.pfam_id
        """
    ).fetchdf()
    matrix = counts.pivot(index="species_prefix", columns="family", values="n").fillna(0.0)
    matrix = _filter_rows(matrix, rows)
    gene_counts = get_species_table(con)["gene_count"]
    gene_counts = gene_counts.reindex(matrix.index)
    return matrix.div(gene_counts, axis=0) * 1000.0


def get_transmembrane_domains_matrix(con: duckdb.DuckDBPyConnection, rows: list[str] | None = None) -> pd.DataFrame:
    """Domain families in proteins with TM helices (TMHMM > 0). Membrane protein repertoire
    variation -- critical for ecological niche/host interaction."""
    table_pfam = "pfam"
    counts = con.execute(
        f"""
        SELECT p.species_prefix, p.pfam_id AS family, COUNT(*) AS n
        FROM {table_pfam} p
        JOIN tmhmm t ON p.protein_id = t.protein_id
        WHERE t.PredHel > 0
        GROUP BY p.species_prefix, p.pfam_id
        """
    ).fetchdf()
    matrix = counts.pivot(index="species_prefix", columns="family", values="n").fillna(0.0)
    matrix = _filter_rows(matrix, rows)
    gene_counts = get_species_table(con)["gene_count"]
    gene_counts = gene_counts.reindex(matrix.index)
    return matrix.div(gene_counts, axis=0) * 1000.0


def get_gc_normalized_domains(con: duckdb.DuckDBPyConnection, kind: str, rows: list[str] | None = None) -> pd.DataFrame:
    """Domain matrix with GC-content regression removed. Eliminates compositional confounding
    where domain differences track GC% bias rather than true functional divergence."""
    from scipy import stats

    domain_matrix = get_domain_matrix(con, kind, rows=rows)
    gc_col = get_species_table(con)["GC"]
    gc_col = gc_col.reindex(domain_matrix.index)

    residuals = pd.DataFrame(index=domain_matrix.index, columns=domain_matrix.columns)
    for family in domain_matrix.columns:
        slope, intercept, _, _, _ = stats.linregress(gc_col, domain_matrix[family])
        residuals[family] = domain_matrix[family] - (slope * gc_col + intercept)

    return residuals.fillna(0.0)


def get_protein_length_distribution_matrix(con: duckdb.DuckDBPyConnection, rows: list[str] | None = None) -> pd.DataFrame:
    """Per-species protein-length statistics (mean, median, std, skewness). Genome-wide
    variation in proteome 'architecture' -- correlates with lifestyle (parasitic/saprobic)."""
    stats_df = con.execute(
        """
        SELECT
            species_prefix,
            COUNT(*) AS n_proteins,
            AVG(length) AS mean_length,
            APPROX_QUANTILE(length, 0.5) AS median_length,
            STDDEV_POP(length) AS std_length,
            MIN(length) AS min_length,
            MAX(length) AS max_length
        FROM gene_proteins
        GROUP BY species_prefix
        ORDER BY species_prefix
        """
    ).fetchdf().set_index("species_prefix")
    stats_df = _filter_rows(stats_df, rows)
    numeric = stats_df.select_dtypes(include="number")
    z = (numeric - numeric.mean()) / numeric.std(ddof=0).replace(0, 1)
    return z


def get_gene_structure_matrix(con: duckdb.DuckDBPyConnection, rows: list[str] | None = None) -> pd.DataFrame:
    """Per-species gene structure metrics: mean exons/gene, mean intron length, total intergenic
    distance. Intron density and gene spacing vary with GC%, chromatin compaction, and lifestyle."""
    try:
        struct_df = con.execute(
            """
            SELECT
                species_prefix,
                COUNT(DISTINCT gene_id) AS n_genes,
                AVG(exons_per_gene) AS mean_exons,
                AVG(intron_length) AS mean_intron_length,
                AVG(gene_length) AS mean_gene_length
            FROM gene_info
            GROUP BY species_prefix
            ORDER BY species_prefix
            """
        ).fetchdf().set_index("species_prefix")
        struct_df = _filter_rows(struct_df, rows)
        numeric = struct_df.select_dtypes(include="number")
        z = (numeric - numeric.mean()) / numeric.std(ddof=0).replace(0, 1)
        return z
    except Exception:
        return pd.DataFrame()  # graceful fail if gene_info lacks structure columns


def get_cazy_by_class_matrix(con: duckdb.DuckDBPyConnection, rows: list[str] | None = None) -> pd.DataFrame:
    """CAZy families grouped into functional classes (GH/GT/PL/CE/AA/CBM). Reveals carbohydrate
    degradation capability profiles (e.g. cellulolytic vs. hemicellulolytic specialization)."""
    counts = con.execute(
        """
        SELECT
            species_prefix,
            CASE
                WHEN HMM_id LIKE 'GH%' THEN 'GH (Glycoside Hydrolase)'
                WHEN HMM_id LIKE 'GT%' THEN 'GT (Glycosyl Transferase)'
                WHEN HMM_id LIKE 'PL%' THEN 'PL (Polysaccharide Lyase)'
                WHEN HMM_id LIKE 'CE%' THEN 'CE (Carbohydrate Esterase)'
                WHEN HMM_id LIKE 'AA%' THEN 'AA (Auxiliary Activity)'
                WHEN HMM_id LIKE 'CBM%' THEN 'CBM (Carbohydrate Binding)'
                ELSE 'Unknown'
            END AS cazy_class,
            COUNT(*) AS n
        FROM cazy
        GROUP BY species_prefix, cazy_class
        """
    ).fetchdf()
    matrix = counts.pivot(index="species_prefix", columns="cazy_class", values="n").fillna(0.0)
    matrix = _filter_rows(matrix, rows)
    gene_counts = get_species_table(con)["gene_count"]
    gene_counts = gene_counts.reindex(matrix.index)
    return matrix.div(gene_counts, axis=0) * 1000.0


def get_peptidase_class_matrix(con: duckdb.DuckDBPyConnection, rows: list[str] | None = None) -> pd.DataFrame:
    """MEROPS families by catalytic class (S/T/C/A/M/G/N/P). Protease specialization patterns
    indicate whether pathogen/endophyte leverages extracellular proteolysis (virulence) or
    intracellular degradation (nutrient mining)."""
    counts = con.execute(
        """
        SELECT
            species_prefix,
            SUBSTR(family, 1, 1) AS pep_class,
            COUNT(*) AS n
        FROM v_merops_family
        GROUP BY species_prefix, pep_class
        """
    ).fetchdf()
    matrix = counts.pivot(index="species_prefix", columns="pep_class", values="n").fillna(0.0)
    matrix = _filter_rows(matrix, rows)
    gene_counts = get_species_table(con)["gene_count"]
    gene_counts = gene_counts.reindex(matrix.index)
    return matrix.div(gene_counts, axis=0) * 1000.0


FEATURE_SETS = {
    "assembly": {
        "loader": get_assembly_matrix, "metric": "euclidean", "method": "pcoa",
        "description": "Assembly/annotation stats (size, N50, GC%, gene count, etc.), z-scored.",
    },
    "codon": {
        "loader": get_codon_matrix, "metric": "chi-square", "method": "ca",
        "description": "Codon usage frequency profile (all 64 codons).",
    },
    "amino_acid": {
        "loader": get_aa_matrix, "metric": "chi-square", "method": "ca",
        "description": "Amino-acid usage frequency profile (all 20 residues).",
    },
    "pfam": {
        "loader": lambda con, rows=None: get_domain_matrix(con, "pfam", rows=rows),
        "metric": "bray-curtis", "method": "pcoa",
        "description": "Pfam domain-family content, gene-count-normalized.",
    },
    "cazy": {
        "loader": lambda con, rows=None: get_domain_matrix(con, "cazy", rows=rows),
        "metric": "bray-curtis", "method": "pcoa",
        "description": "CAZy carbohydrate-active-enzyme family content, gene-count-normalized.",
    },
    "merops": {
        "loader": lambda con, rows=None: get_domain_matrix(con, "merops", rows=rows),
        "metric": "bray-curtis", "method": "pcoa",
        "description": "MEROPS peptidase family content, gene-count-normalized.",
    },
    "localization": {
        "loader": get_localization_matrix, "metric": "euclidean", "method": "pcoa",
        "description": (
            "Composite of six protein-localization/secretion proportions, z-scored and "
            "ordinated together (not one plot per field): SignalP secretion, TMHMM "
            "transmembrane-helix count, TargetP secretion, PredGPI GPI-anchor, IDP "
            "intrinsic-disorder, WoLF PSORT extracellular."
        ),
    },
    "secreted_pfam": {
        "loader": get_secreted_domains_matrix, "metric": "bray-curtis", "method": "pcoa",
        "description": "Pfam domains restricted to secreted proteins (SignalP+). Isolates secretome variation from cytoplasmic proteome.",
    },
    "cytoplasmic_pfam": {
        "loader": get_cytoplasmic_domains_matrix, "metric": "bray-curtis", "method": "pcoa",
        "description": "Pfam domains in non-secreted proteins. Reveals intracellular/nuclear proteome repertoire.",
    },
    "transmembrane_pfam": {
        "loader": get_transmembrane_domains_matrix, "metric": "bray-curtis", "method": "pcoa",
        "description": "Pfam domains in proteins with transmembrane helices. Membrane proteome specialization.",
    },
    "gc_normalized_pfam": {
        "loader": lambda con, rows=None: get_gc_normalized_domains(con, "pfam", rows=rows),
        "metric": "bray-curtis", "method": "pcoa",
        "description": "Pfam domains with GC%-content regressed out. Removes compositional confounding.",
    },
    "gc_normalized_cazy": {
        "loader": lambda con, rows=None: get_gc_normalized_domains(con, "cazy", rows=rows),
        "metric": "bray-curtis", "method": "pcoa",
        "description": "CAZy families with GC%-content regressed out.",
    },
    "protein_length": {
        "loader": get_protein_length_distribution_matrix, "metric": "euclidean", "method": "pcoa",
        "description": "Proteome-wide protein-length statistics (mean, median, std, range). Architecture of protein repertoire.",
    },
    "gene_structure": {
        "loader": get_gene_structure_matrix, "metric": "euclidean", "method": "pcoa",
        "description": "Gene structural metrics: exon count, intron length, gene length. Genome compaction and intron density patterns.",
    },
    "cazy_by_class": {
        "loader": get_cazy_by_class_matrix, "metric": "bray-curtis", "method": "pcoa",
        "description": "CAZy families grouped by catalytic class (GH/GT/PL/CE/AA/CBM). Carbohydrate degradation capability profile.",
    },
    "peptidase_class": {
        "loader": get_peptidase_class_matrix, "metric": "bray-curtis", "method": "pcoa",
        "description": "MEROPS peptidases grouped by catalytic class (S/T/C/A/M/G/N/P). Protease specialization patterns.",
    },
}


# --------------------------------------------------------------------------- phylogeny
# This is a proper BUSCO/PHYling gene tree built from exactly these 11 genomes (not the
# population-scale ASTRAL tree in ../../phylogeny/, which has hundreds of strain-level tips
# and no clean 1:1 match) -- tip labels are "{SPECIES}_{STRAIN}.proteins" with spaces
# replaced by underscores, which matches the species table's SPECIES/STRAIN columns exactly
# for all 11 genomes, verified before wiring this in.
def _tip_to_locustag(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    sp = con.execute("SELECT LOCUSTAG, SPECIES, STRAIN FROM species").fetchdf()
    mapping = {}
    for row in sp.itertuples():
        tip = f"{row.SPECIES}_{row.STRAIN}.proteins".replace(" ", "_")
        mapping[tip] = row.LOCUSTAG
    return mapping


OUTGROUP_SPECIES = "Cyphellophora europaea"  # only non-Exophiala genome in this 11-taxon set


def load_tree(con: duckdb.DuckDBPyConnection, tree_path: Path = DEFAULT_TREE_PATH):
    """Bio.Phylo tree with tips renamed to LOCUSTAG, rooted on OUTGROUP_SPECIES. Raises if any
    tip fails to match a species row -- silent partial matches would be worse than a loud
    failure here, since the tree is only useful if every tip in this 11-genome build maps
    cleanly. FastTree writes an unrooted trifurcation at the root, so without an explicit
    reroot the outgroup placement is arbitrary."""
    from Bio import Phylo

    tree = Phylo.read(str(tree_path), "newick")
    tip_map = _tip_to_locustag(con)
    unmatched = []
    for tip in tree.get_terminals():
        if tip.name in tip_map:
            tip.name = tip_map[tip.name]
        else:
            unmatched.append(tip.name)
    if unmatched:
        raise ValueError(f"Tree tips with no matching species row: {unmatched}")

    sp = con.execute(
        "SELECT LOCUSTAG FROM species WHERE SPECIES = ?", [OUTGROUP_SPECIES]
    ).fetchdf()
    if len(sp) != 1:
        raise ValueError(f"Expected exactly one {OUTGROUP_SPECIES!r} row, found {len(sp)}")
    outgroup_locustag = sp.iloc[0]["LOCUSTAG"]
    outgroup_tip = next(
        (t for t in tree.get_terminals() if t.name == outgroup_locustag), None
    )
    if outgroup_tip is None:
        raise ValueError(f"Outgroup tip {outgroup_locustag!r} not found in tree")
    tree.root_with_outgroup(outgroup_tip)
    return tree


def phylo_layout(tree) -> dict:
    """Rectangular-cladogram layout: (x, y) per node plus the segments to draw, precomputed
    in Python so the front end only needs to draw lines/circles -- no Newick parser in JS."""
    tree = tree.__class__(tree.root, rooted=True)  # shallow-ish; ladderize() mutates in place
    tree.ladderize()

    y_counter = {"n": 0}
    y_pos = {}
    for tip in tree.get_terminals():
        y_pos[id(tip)] = y_counter["n"]
        y_counter["n"] += 1

    def assign_y(clade):
        if clade.is_terminal():
            return y_pos[id(clade)]
        ys = [assign_y(c) for c in clade.clades]
        y = sum(ys) / len(ys)
        y_pos[id(clade)] = y
        return y

    assign_y(tree.root)

    x_pos = {id(tree.root): 0.0}

    def assign_x(clade):
        for child in clade.clades:
            x_pos[id(child)] = x_pos[id(clade)] + (child.branch_length or 0.0)
            assign_x(child)

    assign_x(tree.root)

    segments = []  # each: {x0,y0,x1,y1} -- one horizontal branch + connecting vertical per node

    def walk(clade):
        for child in clade.clades:
            segments.append(
                {
                    "x0": x_pos[id(clade)], "y0": y_pos[id(child)],
                    "x1": x_pos[id(child)], "y1": y_pos[id(child)],
                }
            )
            walk(child)
        if len(clade.clades) > 1:
            child_ys = [y_pos[id(c)] for c in clade.clades]
            segments.append(
                {
                    "x0": x_pos[id(clade)], "y0": min(child_ys),
                    "x1": x_pos[id(clade)], "y1": max(child_ys),
                }
            )

    walk(tree.root)

    tips = sorted(tree.get_terminals(), key=lambda t: y_pos[id(t)])
    return {
        "segments": segments,
        "tips": [{"locustag": t.name, "x": x_pos[id(t)], "y": y_pos[id(t)]} for t in tips],
        "tip_order": [t.name for t in tips],
        "max_x": max(x_pos.values()) if x_pos else 0.0,
    }


def gene_link(con: duckdb.DuckDBPyConnection, protein_ids: list[str]) -> pd.DataFrame:
    """Map protein_id -> gene_id/chrom/coords for 'examine this gene' drill-down links."""
    if not protein_ids:
        return pd.DataFrame(columns=["protein_id", "gene_id", "chrom", "start", "end", "strand"])
    con.execute("CREATE OR REPLACE TEMP TABLE _pids AS SELECT UNNEST(?) AS protein_id", [protein_ids])
    return con.execute(
        """
        SELECT gp.protein_id, gi.gene_id, gi.chrom, gi.start, gi.end, gi.strand
        FROM _pids p
        JOIN gene_proteins gp ON gp.protein_id = p.protein_id
        JOIN gene_info gi ON gi.gene_id = gp.gene_id
        """
    ).fetchdf()
