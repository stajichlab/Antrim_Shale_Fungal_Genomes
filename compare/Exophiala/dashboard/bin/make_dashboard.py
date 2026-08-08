#!/usr/bin/env python3
"""
Build the BFD comparative-genomics explorer dashboard.

Two explicit steps (compute is not free -- PERMANOVA runs per feature set per focus species):

    make_dashboard.py --compute   # duckdb -> dashboard/cache/payload.json
    make_dashboard.py --render    # dashboard/cache/payload.json -> dashboard/explorer.html

Running with neither flag does both, for convenience on a first build.
"""
import argparse
import dataclasses
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DASHBOARD_DIR / "lib"))
sys.path.insert(0, str(DASHBOARD_DIR / "templates"))

import bfd_data as bd  # noqa: E402
import ordination as ordi  # noqa: E402
import figures as fig  # noqa: E402

DOMAIN_KINDS = ["pfam", "cazy", "merops"]
DIFF_TOP_N = 15


def build_payload(db_path: Path, busco_dir: Path, tree_path: Path, alt_ordinations: bool = False) -> dict:
    con = bd.get_connection(db_path)
    species_df = bd.get_species_table(con)
    busco_df = bd.get_busco_scores(busco_dir)
    species_df = species_df.join(busco_df)

    phylo_payload = None
    try:
        tree = bd.load_tree(con, tree_path)
        phylo_payload = bd.phylo_layout(tree)
        sp_order = phylo_payload["tip_order"]
        print(f"  phylogeny: loaded, using tree tip order for species ordering", file=sys.stderr)
    except (FileNotFoundError, ValueError) as e:
        print(f"  phylogeny: unavailable ({e}); falling back to taxonomic order", file=sys.stderr)
        sp_order = species_df.index.tolist()

    species_df = species_df.reindex(sp_order)
    species_block = {"locustag": sp_order}
    for col in species_df.columns:
        values = species_df[col]
        if values.dtype.kind in "fc":
            species_block[col] = [None if pd_isna(v) else float(v) for v in values]
        elif values.dtype.kind in "iu":
            species_block[col] = [None if pd_isna(v) else int(v) for v in values]
        else:
            species_block[col] = [None if pd_isna(v) else str(v) for v in values]

    genus = species_df["GENUS"]

    feature_sets_payload = {}
    differential_payload = {}
    composition_payload = {}
    domain_counts_payload = {}

    for name, cfg in bd.FEATURE_SETS.items():
        print(f"  feature set: {name}", file=sys.stderr)
        matrix = cfg["loader"](con).reindex(sp_order).fillna(0.0)

        if cfg["method"] == "ca":
            ordination = ordi.correspondence_analysis(matrix)
            dist_for_stats = ordi.distance_matrix(matrix, "euclidean")
        else:
            dist_for_stats = ordi.distance_matrix(matrix, cfg["metric"])
            ordination = ordi.pcoa(dist_for_stats)

        permanova_genus = dataclasses.asdict(ordi.permanova(dist_for_stats, genus))

        permanova_by_species = {}
        for focus in sp_order:
            grouping = genus.index.to_series().apply(lambda x: "focus" if x == focus else "rest")
            permanova_by_species[focus] = dataclasses.asdict(
                ordi.permanova(dist_for_stats, grouping)
            )

        coords = ordination.coords.reindex(sp_order)
        ordinations = {
            cfg["method"]: {
                "pct_variance": [float(x) for x in ordination.pct_variance[:4]],
                "axes": list(coords.columns),
                "coords": {c: [float(v) for v in coords[c]] for c in coords.columns},
                "extra": ordination.extra,
            }
        }

        if alt_ordinations and cfg["method"] != "ca":
            for alt_method, alt_fn in [("nmds", ordi.nmds), ("tsne", ordi.tsne)]:
                try:
                    alt_ord = alt_fn(dist_for_stats)
                    alt_coords = alt_ord.coords.reindex(sp_order)
                    ordinations[alt_method] = {
                        "pct_variance": [float(x) for x in alt_ord.pct_variance[:4]],
                        "axes": list(alt_coords.columns),
                        "coords": {c: [float(v) for v in alt_coords[c]] for c in alt_coords.columns},
                        "extra": alt_ord.extra,
                    }
                except Exception as e:
                    print(f"    {alt_method} failed: {e}", file=sys.stderr)

            try:
                umap_ord = ordi.umap_ordination(dist_for_stats)
                umap_coords = umap_ord.coords.reindex(sp_order)
                ordinations["umap"] = {
                    "pct_variance": [float(x) for x in umap_ord.pct_variance[:4]],
                    "axes": list(umap_coords.columns),
                    "coords": {c: [float(v) for v in umap_coords[c]] for c in umap_coords.columns},
                    "extra": umap_ord.extra,
                }
            except ImportError:
                print(f"    umap: not installed (optional; pip install umap-learn)", file=sys.stderr)
            except Exception as e:
                print(f"    umap failed: {e}", file=sys.stderr)

        feature_sets_payload[name] = {
            "description": cfg.get("description", ""),
            "metric": cfg["metric"],
            "primary_method": cfg["method"],
            "ordinations": ordinations,
            "permanova_genus": permanova_genus,
            "permanova_by_species": permanova_by_species,
        }

        if name in DOMAIN_KINDS:
            differential_payload[name] = bd.differential_families(con, name, top_n=DIFF_TOP_N)

            # Raw per-species counts for exactly the families that surface in the differential
            # table (present-only/absent-only/top-fold-change, across all focus species) -- not
            # every family in the domain library, which would be thousands of mostly-irrelevant
            # columns. This backs the "counts across all species" popup for a clicked family.
            referenced = {
                row["family"]
                for per_focus in differential_payload[name].values()
                for section in ("present_only", "absent_only", "top_fold_change")
                for row in per_focus[section]
            }
            raw_counts = bd.get_domain_raw_counts(con, name).reindex(sp_order).fillna(0.0)
            domain_counts_payload[name] = {
                family: {
                    locustag: int(raw_counts.loc[locustag, family]) if family in raw_counts.columns else 0
                    for locustag in sp_order
                }
                for family in sorted(referenced)
            }

        if name in ("codon", "amino_acid"):
            raw = cfg["loader"](con).reindex(sp_order).fillna(0.0)
            composition_payload[name] = {
                "categories": list(raw.columns),
                "values": {locustag: [float(v) for v in raw.loc[locustag]] for locustag in sp_order},
            }

        if name == "localization":
            # Composition wants the human-readable fractions (SignalP secretion, IDP disorder,
            # etc.), not the z-scored version get_localization_matrix feeds to PCoA/PERMANOVA --
            # plus the raw counts behind each fraction, so bars/tooltips can show "412 (6.2%)"
            # instead of a bare proportion.
            frac = bd.get_localization_fractions(con).reindex(sp_order).fillna(0.0)
            counts = bd.get_localization_counts(con).reindex(sp_order).fillna(0)
            composition_payload[name] = {
                "categories": list(frac.columns),
                "values": {locustag: [float(v) for v in frac.loc[locustag]] for locustag in sp_order},
                "counts": {locustag: [int(v) for v in counts.loc[locustag]] for locustag in sp_order},
            }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db_path": str(db_path),
        "palette": fig.PALETTE_JSON,
        "species": species_block,
        "feature_sets": feature_sets_payload,
        "differential": differential_payload,
        "composition": composition_payload,
        "domain_counts": domain_counts_payload,
        "phylogeny": phylo_payload,
    }


def pd_isna(v) -> bool:
    try:
        import math

        return v is None or (isinstance(v, float) and math.isnan(v))
    except Exception:
        return v is None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=bd.DEFAULT_DB_PATH)
    ap.add_argument("--busco-dir", type=Path, default=bd.DEFAULT_BUSCO_PROTEIN_DIR)
    ap.add_argument("--tree", type=Path, default=bd.DEFAULT_TREE_PATH)
    ap.add_argument("--cache", type=Path, default=DASHBOARD_DIR / "cache" / "payload.json")
    ap.add_argument("--out", type=Path, default=DASHBOARD_DIR / "explorer.html")
    ap.add_argument("--compute", action="store_true")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--alt-ordinations", action="store_true", help="Include NMDS, t-SNE, UMAP alongside default ordination")
    args = ap.parse_args()

    do_compute = args.compute or not (args.compute or args.render)
    do_render = args.render or not (args.compute or args.render)

    if do_compute:
        print(f"Computing payload from {args.db} ...", file=sys.stderr)
        payload = build_payload(args.db, args.busco_dir, args.tree, alt_ordinations=args.alt_ordinations)
        args.cache.parent.mkdir(parents=True, exist_ok=True)
        args.cache.write_text(json.dumps(payload))
        print(f"Wrote {args.cache} ({args.cache.stat().st_size:,} bytes)", file=sys.stderr)

    if do_render:
        payload = json.loads(args.cache.read_text())
        import explorer_template

        html = explorer_template.build_html(payload)
        args.out.write_text(html)
        print(f"Wrote {args.out} ({args.out.stat().st_size:,} bytes)", file=sys.stderr)


if __name__ == "__main__":
    main()
