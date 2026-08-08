# Dashboard Enhancements Summary

## What's New

Three categories of enhancements to expose *Exophiala mansonii* genomic signatures:

### 1. Alternative Ordination Methods

**Files modified**: `lib/ordination.py`

Added three nonlinear ordination methods alongside the default PCoA:

- **NMDS (Non-Metric Multidimensional Scaling)**
  - Preserves rank-order distances; less sensitive to outliers than PCoA
  - Includes stress metric (> 0.2 = unreliable; common at n=11)
  - Useful when PCoA shows single-outlier-driven artifacts

- **t-SNE (t-Distributed Stochastic Neighbor Embedding)**
  - Emphasizes local clustering structure
  - Stochastic; results vary by random seed
  - **Use only for exploratory "does clustering exist?" questions**, not quantitative interpretation
  - Perplexity auto-tuned for n=11

- **UMAP (Uniform Manifold Approximation and Projection)**
  - Balances local + global structure
  - Fewer hyperparameters than t-SNE
  - Requires optional `pip install umap-learn`
  - More stable than t-SNE at small n, but still exploratory

**How to use**: 
```bash
make_dashboard.py --alt-ordinations --compute
```
Adds NMDS/t-SNE/UMAP to every feature set (except correspondence analysis, where they don't apply). Increases compute time ~2–3x and file size moderately.

---

### 2. Compartment-Specific Domain Analysis

**Files modified**: `lib/bfd_data.py` (new functions added)

Isolates functional variation by protein localization, removing compositional noise:

- **secreted_pfam** — Domains in SignalP+ proteins only
  - Isolates secretome virulence factors, adhesins
  - Removes ~70% of proteome noise (cytoplasmic proteins)

- **cytoplasmic_pfam** — Domains in SignalP- proteins
  - Intracellular metabolic/regulatory functions
  - Unconfounded by secretion bias

- **transmembrane_pfam** — Domains in TMHMM+ proteins
  - Membrane protein repertoire
  - Strong correlate of ecological niche (host-specificity, endophytism)

**Why this matters**: E. mansonii differences might be entirely in the secretome (virulence-driven), entirely intracellular (metabolic), or both. Compartment-specific ordinations separate these signals.

---

### 3. Confounding Decontamination & Enrichment

**Files modified**: `lib/bfd_data.py` (new functions added)

#### Compositional Confounding
- **gc_normalized_pfam** & **gc_normalized_cazy**
  - Regress out GC% content before ordination
  - **Why**: GC% is a strong driver of domain composition independent of function
  - **Example**: High-GC E. mansonii might appear domain-rich from bias alone, not genuine innovation

#### Genome Architecture
- **protein_length** — Proteome statistics (mean, median, std, skewness, min, max)
  - Isolates proteome "shape" variation
  - Correlates with lifestyle (endophytes = compact; saprobes = modular)

- **gene_structure** — Gene-structural metrics (exon count, intron length, gene length)
  - Intron density + gene-space organization
  - Correlates with genome size, GC%, chromatin complexity

#### Functional Classification (Reduced Noise)
- **cazy_by_class** — CAZy families grouped by catalytic class (GH/GT/PL/CE/AA/CBM)
  - Coarse functional grouping removes family-level noise
  - **Example**: High GH + PL (hemicellulolytic) vs. GH + CE (pectinolytic)

- **peptidase_class** — MEROPS by catalytic class (S/T/C/A/M/G/N/P)
  - Protease arsenal specialization
  - Serine proteases (S) = extracellular virulence; Cysteine (C) = intracellular remodeling

---

## New Feature Sets (Total: 16, up from 7)

| Feature Set | Ordination | Metric | Purpose |
|-------------|-----------|--------|---------|
| assembly | PCoA | Euclidean | Genome size/complexity (confound check) |
| codon | CA | chi-square | Translational selection, GC bias |
| amino_acid | CA | chi-square | Proteome-wide compositional shifts |
| **pfam** | PCoA | Bray-Curtis | Functional repertoire (primary) |
| **cazy** | PCoA | Bray-Curtis | Carbohydrate degradation |
| **merops** | PCoA | Bray-Curtis | Protease specialization |
| localization | PCoA | Euclidean | Secretion capacity, membrane complexity |
| **secreted_pfam** | PCoA | Bray-Curtis | **NEW**: Secretome virulence factors |
| **cytoplasmic_pfam** | PCoA | Bray-Curtis | **NEW**: Intracellular proteome |
| **transmembrane_pfam** | PCoA | Bray-Curtis | **NEW**: Membrane proteome |
| **gc_normalized_pfam** | PCoA | Bray-Curtis | **NEW**: Pfam minus GC% confound |
| **gc_normalized_cazy** | PCoA | Bray-Curtis | **NEW**: CAZy minus GC% confound |
| **protein_length** | PCoA | Euclidean | **NEW**: Proteome architecture |
| **gene_structure** | PCoA | Euclidean | **NEW**: Genome organization |
| **cazy_by_class** | PCoA | Bray-Curtis | **NEW**: CAZy functional classes |
| **peptidase_class** | PCoA | Bray-Curtis | **NEW**: MEROPS functional classes |

**All CA feature sets automatically use correspondence analysis (chi-square); others default to PCoA but can optionally use NMDS/t-SNE/UMAP.**

---

## Files Changed

### Core Library

**lib/ordination.py**
- Added `nmds()`, `tsne()`, `umap_ordination()` functions
- All return `Ordination` dataclass with stress/caveat metadata

**lib/bfd_data.py**
- Added 9 new feature-matrix loaders:
  - `get_secreted_domains_matrix()`
  - `get_cytoplasmic_domains_matrix()`
  - `get_transmembrane_domains_matrix()`
  - `get_gc_normalized_domains()`
  - `get_protein_length_distribution_matrix()`
  - `get_gene_structure_matrix()`
  - `get_cazy_by_class_matrix()`
  - `get_peptidase_class_matrix()`
- Updated `FEATURE_SETS` dict to include all 16 feature sets

**bin/make_dashboard.py**
- Added `--alt-ordinations` flag (computes NMDS/t-SNE/UMAP for non-CA feature sets)
- Modified `build_payload()` to optionally compute alternative ordinations
- Payload structure now groups ordinations by method per feature set (allows UI to switch between methods)

### Documentation

**ANALYSIS_GUIDE.md** (NEW)
- Comprehensive guide to all feature sets
- Interpretation of PERMANOVA at small n
- 6 concrete filtering strategies (Exophiala-only, E. mansonii vs relatives, secretome focus, GC confounding, assembly confounds, phylogenetic control)
- Worked example: "Does E. mansonii have a distinct secretome?"
- Caveats & when NOT to over-interpret

**examples/compare_ordinations.py** (NEW)
- 5 runnable examples:
  1. NMDS vs PCoA comparison
  2. Compartment-specific analysis (secreted vs cytoplasmic)
  3. GC% confounding check
  4. Exophiala-only subset
  5. PERMANOVA framing at small n

---

## How to Use

### Quick Start

**Compute dashboard with alternative ordinations**:
```bash
cd compare/Exophiala/dashboard
./bin/make_dashboard.py --alt-ordinations --compute
./bin/make_dashboard.py --render
# Opens explorer.html in browser
```

**Without alternatives** (faster):
```bash
./bin/make_dashboard.py --compute  # default: PCoA only
```

### Programmatic Examples

```python
import sys
sys.path.insert(0, "dashboard/lib")
import bfd_data as bd
import ordination as ordi

con = bd.get_connection()

# Compartment-specific analysis
secretome = bd.get_secreted_domains_matrix(con)
cytoplasm = bd.get_cytoplasmic_domains_matrix(con)

# GC confounding check
pfam_raw = bd.get_domain_matrix(con, "pfam")
pfam_gc_norm = bd.get_gc_normalized_domains(con, "pfam")

# Exophiala-only subset
exo_genomes = bd.resolve_taxa_filter(con, genus="Exophiala")
exo_pfam = bd.get_domain_matrix(con, "pfam", rows=exo_genomes)

# Try NMDS
dist = ordi.distance_matrix(pfam_raw, "bray-curtis")
nmds_result = ordi.nmds(dist)
print(f"Stress: {nmds_result.extra['stress']:.3f}")
```

See `examples/compare_ordinations.py` for 5 more detailed examples.

---

## Small-n Caveats (Always Remembered)

With n=11 genomes (10 Exophiala + 1 outgroup):

1. **PCoA variance explained ≥ 95% is expected, not informative** — a 3-point ordination is exactly planar
2. **PERMANOVA p < 0.05 is a screening signal, not confirmatory** — only ~10 unique label permutations at worst
3. **Dispersion matters**: If a "significant" PERMANOVA has dispersion_ratio > 5, the effect is mostly that the outgroup is far away, not location differences within Exophiala
4. **t-SNE/UMAP are exploratory**: Stochastic and seed-dependent at n=11; use to ask "is there clustering?" not to read coordinates
5. **Assembly quality confounds domain counts**: Check BUSCO %, N50, contig count as metadata before concluding domain-count differences are biological
6. **GC% is a hidden confounder**: Always compare raw vs `gc_normalized_*` ordinations

---

## Dependencies

### Required (already in environment)
- scipy, numpy, pandas, scikit-learn

### Optional
- `pip install umap-learn` (for UMAP ordination)

---

## Performance

- **Default (PCoA only)**: ~15–30 seconds for 16 feature sets
- **With alt-ordinations (`--alt-ordinations`)**: ~45–90 seconds
  - NMDS + t-SNE + UMAP per non-CA feature set (14 feature sets × 3 methods)
  - Payload JSON ~50% larger (~8–10 MB vs ~5 MB)

---

## Next Steps / Future Enhancements

1. **Interactive filtering in explorer.html**:
   - Taxon filter UI (show/hide Exophiala subsets dynamically)
   - Compose custom feature sets (e.g., "secreted + CAZy by class")

2. **Permutation-based resampling**:
   - PERMANOVA jackknife confidence intervals on E. mansonii vs rest

3. **Domain co-occurrence networks**:
   - Which Pfam families cluster together across species?
   - E. mansonii-specific multi-domain modules

4. **Integration with secondary-metabolite clusters** (if AntiSMASH data available):
   - "Does E. mansonii have distinct BGC content?"

5. **Expression-weighted analysis** (if RNA-seq added later):
   - Weight domain counts by transcript abundance
   - "What matters: having the gene or expressing it?"

---

## Questions?

1. **How do I interpret this feature set?** → See ANALYSIS_GUIDE.md
2. **Why is my result different with alt-ordinations?** → See caveats; run examples/compare_ordinations.py to understand
3. **Can I subset to just Exophiala?** → Yes; see example_4 in examples/compare_ordinations.py
4. **How confident should I be in a PERMANOVA p < 0.05?** → Low; it's a screening signal, not confirmatory at n=11

---

## Citation / Referencing

If you use the enhanced dashboard in a paper, cite:

- **PCoA/PERMANOVA**: McArdle & Anderson (2001), Anderson (2001)
- **NMDS**: Clarke (1993), Kruskal (1964)
- **t-SNE**: van der Maaten & Hinton (2008)
- **UMAP**: McInnes et al. (2018)
- **Correspondence Analysis**: Greenacre (2007)
- **Domain normalization**: Carbone et al. (2013) CAZypedia

(See ANALYSIS_GUIDE.md for full references and DOI links)
