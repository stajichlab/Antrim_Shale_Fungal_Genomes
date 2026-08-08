#!/usr/bin/env python3
"""
Quick examples: comparing ordination methods and filtering strategies.

Usage:
    cd ../.. (to dashboard parent)
    python dashboard/examples/compare_ordinations.py
"""
import sys
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DASHBOARD_DIR / "lib"))

import bfd_data as bd
import ordination as ordi
import pandas as pd
import numpy as np


def example_1_nmds_vs_pcoa():
    """Ordination comparison: NMDS stress vs PCoA variance explained."""
    print("\n" + "="*60)
    print("Example 1: NMDS vs PCoA on Pfam domain matrix")
    print("="*60)

    con = bd.get_connection()
    matrix = bd.get_domain_matrix(con, "pfam")
    dist = ordi.distance_matrix(matrix, "bray-curtis")

    pcoa = ordi.pcoa(dist)
    print(f"PCoA: PC1={pcoa.pct_variance[0]:.1f}%, PC2={pcoa.pct_variance[1]:.1f}%")
    print(f"      (high % normal at n=11; not interpretable alone)")

    nmds = ordi.nmds(dist)
    print(f"NMDS: stress={nmds.extra['stress']:.3f} (< 0.2 = reliable)")
    if nmds.extra.get("unreliable"):
        print("      ⚠️  High stress: NMDS result is unstable")

    tsne = ordi.tsne(dist)
    print(f"t-SNE: perplexity={tsne.extra['perplexity']:.1f} (auto-tuned for n=11)")
    print(f"       {tsne.extra['caveat']}")


def example_2_compartment_specific():
    """Secretome vs cytoplasmic domain analysis."""
    print("\n" + "="*60)
    print("Example 2: Secreted vs Cytoplasmic domain repertoires")
    print("="*60)

    con = bd.get_connection()
    secreted = bd.get_secreted_domains_matrix(con)
    cytoplasmic = bd.get_cytoplasmic_domains_matrix(con)

    print(f"Total Pfam families in secretome: {secreted.shape[1]}")
    print(f"Total Pfam families in cytoplasm: {cytoplasmic.shape[1]}")

    # Compute distances
    dist_sec = ordi.distance_matrix(secreted, "bray-curtis")
    dist_cyt = ordi.distance_matrix(cytoplasmic, "bray-curtis")

    # Compare pairwise distances: E. mansonii vs others
    species_order = secreted.index.tolist()
    try:
        emansonii_idx = species_order.index("Emarsonii")  # or whatever LOCUSTAG is
    except ValueError:
        emansonii_idx = 0  # fallback

    print(f"\nMean distance, E. mansonii to others:")
    print(f"  Secretome:   {dist_sec.iloc[emansonii_idx, :].mean():.3f}")
    print(f"  Cytoplasm:   {dist_cyt.iloc[emansonii_idx, :].mean():.3f}")
    if dist_sec.iloc[emansonii_idx, :].mean() > dist_cyt.iloc[emansonii_idx, :].mean():
        print(f"  → E. mansonii secretome is MORE divergent (likely functional)")
    else:
        print(f"  → E. mansonii secretome is LESS divergent (less functional niche differentiation)")


def example_3_gc_confounding():
    """Check whether domain differences are GC-driven."""
    print("\n" + "="*60)
    print("Example 3: GC% confounding in Pfam ordination")
    print("="*60)

    con = bd.get_connection()

    # Raw vs GC-normalized
    raw_pfam = bd.get_domain_matrix(con, "pfam")
    gc_norm_pfam = bd.get_gc_normalized_domains(con, "pfam")

    # Compute PCoA on both
    dist_raw = ordi.distance_matrix(raw_pfam, "bray-curtis")
    dist_norm = ordi.distance_matrix(gc_norm_pfam, "bray-curtis")

    pcoa_raw = ordi.pcoa(dist_raw)
    pcoa_norm = ordi.pcoa(dist_norm)

    print(f"Raw Pfam:")
    print(f"  PC1: {pcoa_raw.pct_variance[0]:.1f}%")
    print(f"Pfam (GC-normalized):")
    print(f"  PC1: {pcoa_norm.pct_variance[0]:.1f}%")

    # Correlate raw ordination with GC%
    species = bd.get_species_table(con).reindex(raw_pfam.index)
    gc_values = species["GC"]
    pc1_raw = pcoa_raw.coords.iloc[:, 0].values
    corr_gc_pc1 = np.corrcoef(gc_values.dropna(), pc1_raw[:len(gc_values.dropna())])[0, 1]

    print(f"\nCorrelation: GC% vs raw-Pfam PC1 = {corr_gc_pc1:.3f}")
    if abs(corr_gc_pc1) > 0.6:
        print("  ⚠️  Strong GC confounding! Use gc_normalized_pfam instead.")
    elif abs(corr_gc_pc1) > 0.3:
        print("  ⚠️  Moderate GC confounding; compare both ordinations.")
    else:
        print("  ✓  Weak GC confounding; pfam signal appears real.")


def example_4_focus_exophiala_only():
    """Subset to Exophiala spp. only (remove outgroup)."""
    print("\n" + "="*60)
    print("Example 4: Within-Exophiala variation (excluding outgroup)")
    print("="*60)

    con = bd.get_connection()

    # Get just Exophiala genomes
    exo_genomes = bd.resolve_taxa_filter(con, genus="Exophiala")
    print(f"Exophiala genomes: {exo_genomes}")
    print(f"(vs 11 total including Cyphellophora europaea)")

    # Recompute on this subset
    matrix = bd.get_pfam_matrix(con, rows=exo_genomes)
    dist = ordi.distance_matrix(matrix, "bray-curtis")
    ordination = ordi.pcoa(dist)

    print(f"\nPCoA (Exophiala only):")
    print(f"  PC1: {ordination.pct_variance[0]:.1f}%")
    print(f"  PC2: {ordination.pct_variance[1]:.1f}%")
    print(f"  (Compare to full-cohort ordination; outgroup usually dominates PC1)")


def example_5_permanova_framing():
    """Understand PERMANOVA caveats at small n."""
    print("\n" + "="*60)
    print("Example 5: PERMANOVA interpretation at n=11")
    print("="*60)

    con = bd.get_connection()
    species = bd.get_species_table(con)
    matrix = bd.get_domain_matrix(con, "pfam")
    dist = ordi.distance_matrix(matrix, "bray-curtis")

    # Test by genus
    genus = species["GENUS"]
    result = ordi.permanova(dist, genus)

    print(f"PERMANOVA (by genus):")
    print(f"  F-statistic: {result.pseudo_f:.3f}")
    print(f"  p-value: {result.p_value:.3f}")
    print(f"  Unique permutations possible: {result.n_unique_permutations}")
    print(f"  Permutations used: {result.n_permutations_run}")
    print(f"  Dispersion ratio: {result.dispersion_ratio:.2f}")
    print(f"\nCaveat: {result.caveat}")

    if result.dispersion_ratio > 5:
        print("  → Large dispersion_ratio: effect is mostly due to outgroup being far away")
    elif result.p_value > 0.05:
        print("  → p > 0.05: no strong genus-level clustering")
    else:
        print("  → p < 0.05 + reasonable dispersion: some genus-level signal (verify with domain inspection)")


if __name__ == "__main__":
    example_1_nmds_vs_pcoa()
    example_2_compartment_specific()
    example_3_gc_confounding()
    example_4_focus_exophiala_only()
    example_5_permanova_framing()
    print("\n" + "="*60)
    print("Done! See ANALYSIS_GUIDE.md for interpretation details.")
    print("="*60)
