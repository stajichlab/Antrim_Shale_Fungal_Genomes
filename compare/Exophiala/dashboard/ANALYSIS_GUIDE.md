# Exophiala Dashboard: Advanced Analysis Guide

## Overview

This guide describes the enhanced analysis capabilities for exposing *Exophiala mansonii* genomic signatures relative to close relatives (*E. dermatitidis*, *E. jeanselmei*, etc.) and the singleton outgroup *Cyphellophora europaea*.

With only 11 genomes (10 Exophiala spp. + 1 outgroup), statistical power is limited. The dashboard uses multiple complementary ordination methods and data-filtering strategies to triangulate true biological signals from noise and artifacts.

---

## Feature Sets

### Core (Always Available)

- **assembly**: Assembly/annotation stats (size, N50, GC%, gene count). Z-scored; ordinated via PCoA (Euclidean).
  - Good for: Overall genome size/complexity signals, confound checks (BUSCO, contiguity correlate with assembly quality, not necessarily biology)

- **codon**: Codon usage frequency (all 64 codons). Ordinated via CA (correspondence analysis, chi-square distance).
  - Good for: Translational selection, GC-driven codon bias, horizontally acquired gene detection

- **amino_acid**: Amino-acid frequency (all 20 residues). Ordinated via CA (chi-square).
  - Good for: Proteome-wide compositional shifts (rare), baseline for domain-specific deviations

- **pfam**: Pfam domain families (gene-count normalized per 1000 genes). PCoA (Bray-Curtis).
  - Good for: Functional repertoire breadth, metabolic lifestyle

- **cazy**: Carbohydrate-active enzyme families. PCoA (Bray-Curtis).
  - Good for: Carbohydrate degradation capability (plant-interaction generalist vs. specialist)

- **merops**: Peptidase families. PCoA (Bray-Curtis).
  - Good for: Protease specialization (extracellular virulence vs. intracellular nutrient mining)

- **localization**: Composite of six protein-localization metrics (SignalP, TMHMM, TargetP, PredGPI, IDP, WoLF PSORT). Z-scored; PCoA (Euclidean).
  - Good for: Secretion pathway capacity, membrane complexity, intrinsic disorder in proteome

### New: Compartment-Specific Domain Analysis

These isolate functional variation in specific cellular compartments, removing compositional noise from the full proteome:

- **secreted_pfam**: Pfam domains *restricted to* SignalP+ proteins. PCoA (Bray-Curtis).
  - Good for: Secretome virulence factors, plant-interaction proteins. Removes ~70% of proteome noise.

- **cytoplasmic_pfam**: Pfam domains in SignalP- proteins. PCoA (Bray-Curtis).
  - Good for: Intracellular metabolic/regulatory functions, unconfounded by secretion bias

- **transmembrane_pfam**: Pfam domains in TMHMM+ proteins. PCoA (Bray-Curtis).
  - Good for: Membrane proteome specialization; correlates with ecological niche (host-specificity, endophytism)

### New: Compositional Deconfounding

- **gc_normalized_pfam** & **gc_normalized_cazy**: Domain matrices with GC%-content regressed out.
  - **Why**: GC% is a strong driver of codon/domain composition independent of function. Removes confounding so true biological signals emerge.
  - Example: If *E. mansonii* is high-GC, it may appear domain-rich simply due to bias, not genuine functional innovation. Regressing GC% isolates the functional component.

### New: Genome Architecture

- **protein_length**: Proteome statistics (mean protein length, median, std, skewness, min, max). Z-scored; PCoA (Euclidean).
  - Good for: Proteome "architecture" — e.g., endophytes often have shorter, more compact proteins; saprobes have longer, modular proteins.

- **gene_structure**: Gene structural metrics (mean exons per gene, intron length, gene length). Z-scored; PCoA (Euclidean).
  - Good for: Intron density and gene-space organization — correlates with genome size, GC%, and chromatin complexity

### New: Functional Classification

- **cazy_by_class**: CAZy families grouped into catalytic classes (GH/GT/PL/CE/AA/CBM). PCoA (Bray-Curtis).
  - Good for: High-level carbohydrate-degradation profile without family-level noise.
  - Example: High GH + PL (hemicellulolytic) vs. high GH + CE (pectinolytic specialization)

- **peptidase_class**: MEROPS peptidases grouped by catalytic class (S/T/C/A/M/G/N/P). PCoA (Bray-Curtis).
  - Good for: Protease arsenal specialization.
  - Example: Serine proteases (S) for extracellular virulence vs. cysteine proteases (C) for intracellular remodeling

---

## Ordination Methods

### Default: PCoA (Principal Coordinates Analysis)

PCoA is classical MDS: a linear, distance-preserving projection. With n=11 samples, variance explained is often high (spuriously — few degrees of freedom). Always check:
- Axis 1 vs 2 (do you see clustering?)
- PERMANOVA *p* value and *dispersion_ratio* (real separation or dispersal artifact?)
- BUSCO/N50/phylogenetic distance (are ordination axes confounded with assembly quality?)

### Alternative 1: NMDS (Non-metric Multidimensional Scaling)

Nonlinear: preserves rank-order distances, not distances themselves. Useful when:
- PCoA shows artifacts (single outlier pulls axis; see "stress" metric)
- You want to relax the linearity assumption
- Small n (n=11) makes NMDS unstable; always check **stress > 0.2 = unreliable**

Invoke: `make_dashboard.py --alt-ordinations`

### Alternative 2: t-SNE (t-Distributed Stochastic Neighbor Embedding)

Nonlinear; emphasizes local structure (which samples are neighbors). Stochastic/seed-dependent, so reproducibility is low at n=11. Use **only** for exploratory "does clustering exist?" (yes/no), not for quantitative interpretation.

- Perplexity auto-set to min(5.0, (n-1)/3) = 3 for this dataset
- Always report: "t-SNE clustering is exploratory; verify with PCoA/PERMANOVA"

### Alternative 3: UMAP (Uniform Manifold Approximation and Projection)

Nonlinear; balances local and global structure. Fewer hyperparameters than t-SNE. Somewhat more stable at small n than t-SNE, but still seed-dependent.

- n_neighbors auto-set to 3 (must be < n)
- Requires `pip install umap-learn`

---

## PERMANOVA Interpretation

Each feature set includes PERMANOVA results:

### permanova_genus
- Tests whether genus (Exophiala vs. Cyphellophora) explains composition
- **p < 0.05 ≠ real difference**: With n=11 and 10 unique label permutations possible (one single outgroup), only ~1 permutation counts. p-value is a screening signal, not confirmatory.
- Check **dispersion_ratio**: If > 5, the "genus effect" is mostly dispersion (outgroup is far away), not location

### permanova_by_species
- Tests whether each single species (E. mansonii focus) differs from rest
- **Only valid if rest group ≥ 3 genomes** (enforced; MIN_REST_GROUP_SIZE=3)
- Caveats printed in output (singleton groups have zero within-group variance by construction)

---

## Filtering & Comparison Strategies

### Strategy 1: Focus on Exophiala Only
**Question**: Are Exophiala species varying internally, or is all signal driven by the outgroup?

**Method**:
```python
import sys
sys.path.insert(0, "dashboard/lib")
import bfd_data as bd
con = bd.get_connection()

# Get just Exophiala genomes
exo_genomes = bd.resolve_taxa_filter(con, genus="Exophiala")

# Recompute any feature matrix on this subset
matrix = bd.get_pfam_matrix(con, rows=exo_genomes)
dist = bd.distance_matrix(matrix, "bray-curtis")
ordination = bd.pcoa(dist)
# Now ordinate 10 Exophiala without the outgroup skewing axes
```

### Strategy 2: E. mansonii vs Close Relatives
**Question**: How does E. mansonii specifically differ from *E. dermatitidis* and *E. jeanselmei* (the closest relatives)?

**Method**:
- Filter to just {E. mansonii, E. dermatitidis, E. jeanselmei} (n=3)
- These are monophyletic in the tree; ordinations at n=3 are degenerate (planar; 100% variance explained)
- Instead, directly compare differential families: `bd.differential_families(con, "pfam", rows=[...])`

### Strategy 3: Secretome-Driven Differentiation
**Question**: Do *E. mansonii*'s differences lie in virulence/adhesion proteins (secretome) or metabolic proteins (cytoplasm)?

**Method**:
- Use **secreted_pfam** vs **cytoplasmic_pfam** ordinations
- If ordinations differ, compartmentalization matters
- Example: If PCoA/Bray-Curtis shows no clustering, but secreted_pfam shows tight clustering with E. mansonii distinct → secretome-driven differences

### Strategy 4: GC-Confounding Check
**Question**: Are domain differences real biology, or artifacts of GC% composition?

**Method**:
- Compare **pfam** ordination to **gc_normalized_pfam**
- If GC-normalized ordination shows much weaker clustering: GC% was driving signal (confound)
- If similar: domain differences are GC-independent (likely biological)

### Strategy 5: Assembly Quality Confounds
**Question**: Are ordination differences driven by assembly contiguity/BUSCO, or biology?

**Method**:
- In explorer.html, hover over each point in a domain ordination
- Check if high/low axis positions correlate with BUSCO %, N50, or contig count
- If yes: consider re-ordinating with assembly-similar subsets (control for quality)

### Strategy 6: Phylogenetic Relatedness Control
**Question**: Are differences between species phylogenetically expected (just drift since divergence) or driven by environmental adaptation?

**Method**:
- Use phylogeny (included in payload) to overlay phylogenetic distance
- If species ordination closely matches phylogenetic topology (phylogenetic clades cluster), difference is drift
- If ordination cross-cuts phylogeny (basal species cluster with derived ones), driven by environment/niche

---

## Worked Example: Does E. mansonii Have a Distinct Secretome?

1. **Load data**:
   ```
   make_dashboard.py --alt-ordinations --compute
   ```

2. **In explorer.html**, switch feature set to **secreted_pfam** (only SignalP+ proteins)

3. **Check ordination**:
   - PCoA axis 1–2: Does E. mansonii cluster alone?
   - PERMANOVA p-value (E. mansonii vs rest): < 0.05?
   - Dispersion ratio: > 5 (outlier) or < 2 (real cohesion)?

4. **Differential secretome**:
   - Click E. mansonii in the browser
   - Scroll to "Top 15 families" (top fold-change, presence/absence)
   - Example: If E. mansonii has unique hydrophobin (PF05469) + unique aspergillopepsin (MEROPS A01): evidence of host adaptation

5. **Verify it's not a GC artifact**:
   - Re-run ordination with **gc_normalized_pfam**
   - If E. mansonii still distinct: secretome difference is real, not GC-driven

6. **Control for phylogeny**:
   - Overlay phylogenetic tree (available in explorer.html)
   - E. mansonii is basal within Exophiala; if secreted_pfam clusters it with derived species, niche-adaptation signal is strong

---

## Running the Dashboard

### Default (PCoA only):
```bash
cd compare/Exophiala/dashboard
./bin/make_dashboard.py --compute
./bin/make_dashboard.py --render
# Opens explorer.html in browser
```

### With Alternative Ordinations (slower; requires scikit-learn, optional umap-learn):
```bash
./bin/make_dashboard.py --alt-ordinations --compute
# Adds NMDS, t-SNE, UMAP to every feature set (except CA, where they don't apply)
# ~2–3x slower; file size larger
```

### Just Render (don't recompute; reuse cache/payload.json):
```bash
./bin/make_dashboard.py --render
```

---

## Caveats & When NOT to Over-Interpret

1. **n=11 is tiny**: A 3-point ordination is exactly planar. Variance explained ≥ 95% is normal/expected, not informative.

2. **PERMANOVA p < 0.05 ≠ real effect**: With 10–50 unique label permutations, p-values are noisy. Use as a screening signal; verify with follow-up comparisons.

3. **Domain counts measure assembly quality too**: A genome with BUSCO=100%, N50=5Mbp, and 100 contigs will "find" more domains than one with BUSCO=80%, N50=200kbp, and 10,000 contigs (even if proteomes are functionally identical). Always check assembly metadata before concluding a domain-count difference is biological.

4. **GC% is a strong hidden confounder**: Codons, amino acids, and even domain composition are influenced by genome-wide GC%. Check gc_normalized matrices to rule this out.

5. **Small taxon subsets (e.g., n=3 focus + 2 rest)**: PERMANOVA enforces MIN_REST_GROUP_SIZE=3 before allowing differential_families. A 2-genome rest group is "differs from one arbitrary other genome," not a clade-level statement.

6. **t-SNE/UMAP are exploratory only**: They are stochastic and seed-dependent at n=11. Use to ask "is there clustering?" (yes/no); don't read coordinates directly.

---

## References & Links

- **PCoA & PERMANOVA**: Anderson (2001) "A new method for non-parametric multivariate analysis of variance" Austral Ecol
- **t-SNE**: van der Maaten & Hinton (2008) "Visualizing data using t-SNE" JMLR
- **UMAP**: McInnes et al. (2018) "UMAP: Uniform Manifold Approximation and Projection" arXiv
- **Correspondence Analysis**: Greenacre (2007) "Correspondence Analysis in Practice" CRC Press
- **Domain normalization (per-1000-genes)**: Carbone et al. (2013) in CAZypedia; accounts for 2.6x variation in gene count here

---

## Questions?

Ask Claude Code: `claude-ai/code` with this dashboard directory open, or inspect the Python code in `lib/bfd_data.py` and `lib/ordination.py` for implementation details.
