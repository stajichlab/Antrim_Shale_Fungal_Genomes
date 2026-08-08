# Quick Reference: Dashboard Analysis Cheat Sheet

## Choose Your Feature Set

### "Which domains/functions does E. mansonii have?"
→ **pfam** (primary; most families) or **cazy** (if carbs relevant) or **merops** (if proteases relevant)

### "Are differences in virulence/adhesion factors?"
→ **secreted_pfam** (SignalP+ proteins only)

### "Are differences in metabolic/regulatory genes?"
→ **cytoplasmic_pfam** (SignalP- proteins only)

### "Are differences in membrane biology?"
→ **transmembrane_pfam** (TMHMM+ proteins only)

### "Is the signal GC%-driven artifact or real biology?"
→ Compare **pfam** vs **gc_normalized_pfam**. If very similar → signal is real.

### "Does E. mansonii have a different protease arsenal?"
→ **peptidase_class** (quick classification) then **merops** (fine-grain families)

### "Does E. mansonii specialize in plant-biomass or other carbs?"
→ **cazy_by_class** (quick: GH/GT/PL/CE/AA/CBM) then **cazy** (fine-grain families)

---

## Ordination Methods: Which to Use?

### PCoA (default, always run)
- **Good for**: Seeing overall structure, baseline comparison
- **Bad for**: Outliers can dominate axis; variance % inflated at n=11
- **Read**: Axis positions + PERMANOVA p-value + dispersion_ratio

### NMDS (alternative, opt-in with `--alt-ordinations`)
- **Good for**: Rank-order preservation; less outlier-sensitive than PCoA
- **Check**: Stress < 0.2 = reliable; > 0.2 = unstable
- **Use if**: PCoA axis is dominated by single outlier

### t-SNE (alternative, opt-in)
- **Good for**: Local clustering (which samples are neighbors?)
- **Bad for**: Reproducibility, global structure, quantitative interpretation
- **Use if**: Quickly asking "is there clustering?" Yes/no only
- **Never read**: t-SNE coordinates directly

### UMAP (alternative, opt-in; requires `pip install umap-learn`)
- **Good for**: Balancing local + global structure; slightly more stable than t-SNE at small n
- **Bad for**: Still stochastic; don't read coordinates directly
- **Use if**: t-SNE looks weird; want to check robustness

---

## Interpreting PERMANOVA Results

| Result | Interpretation |
|--------|---|
| p < 0.05, dispersion_ratio < 3 | Possible real grouping; check differential families |
| p < 0.05, dispersion_ratio > 5 | Mostly dispersion (outlier far away); not biological grouping |
| p > 0.05 | No strong clustering; focus on exploratory observation |
| Group size = 1 | Zero within-group variance by construction; ignore this result |

**At n=11, p-values are screening signals, not confirmatory. Always verify with differential families.**

---

## Red Flags: When to Be Suspicious

🚩 **PCoA axis 1 explains > 90%**
- Expected at n=11; doesn't mean real signal
- Check: Is axis 1 correlated with BUSCO % or N50? (assembly artifact)

🚩 **PERMANOVA dispersion_ratio > 5**
- Effect is mostly that one species is far away
- Not evidence of real clade-level differences

🚩 **E. mansonii differs only in raw pfam, not in secreted_pfam or gc_normalized_pfam**
- Signal is GC-driven or assembly-quality artifact
- Probably not biological

🚩 **GC-normalized and raw ordinations look very different**
- Large GC confounding
- Biological signal is smaller than compositional noise

🚩 **t-SNE shows tight clustering; PCoA doesn't**
- t-SNE is overstating local structure
- Trust PCoA + PERMANOVA instead

---

## Workflow: "Does E. mansonii Have a Unique X?"

### Step 1: Choose feature set
| Question | Feature Set |
|----------|------------|
| Unique proteins? | pfam |
| Unique secretome? | secreted_pfam |
| Unique metabolism? | cytoplasmic_pfam |
| Unique carbs? | cazy |
| Unique proteases? | merops |

### Step 2: Check ordination
- View **PCoA** (primary)
- Check: Does E. mansonii cluster alone or with others?
- Read: PERMANOVA p-value + dispersion_ratio

### Step 3: Check confounds
- Hover over points in explorer.html
- Note: BUSCO %, N50, phylogenetic distance
- Ask: Does E. mansonii's position correlate with these? (yes → confound; no → real)

### Step 4: Check for GC artifact
- Switch to **gc_normalized_[feature_set]** if available
- Compare ordination positions
- Ask: Does E. mansonii stay distinct? (yes → real; no → GC-driven)

### Step 5: Examine differential families
- Click E. mansonii in explorer.html
- Scroll to "Top 15 families" section
- Read: "present only in E. mansonii", "absent in E. mansonii", "top fold-change"
- Example proteins: Click to see gene names

### Step 6: Verify it's not assembly artifact
- Check E. mansonii's BUSCO % and N50
- If BUSCO < 80% or N50 is very low: might be assembly-quality artifact, not biology

---

## Common Questions

**Q: Why does PCoA show 95% variance explained?**
A: Normal at n=11. Axis 1 probably just separates the outgroup from Exophiala. Check PERMANOVA p-value instead.

**Q: Can I compare p-values across feature sets?**
A: No. Each feature set has different n_unique_permutations. Use as screening signals only; don't rank them.

**Q: t-SNE shows E. mansonii separate; PCoA doesn't. Which is right?**
A: Trust PCoA. t-SNE overstates local structure at n=11. Run `--alt-ordinations` to see both, but believe PCoA + PERMANOVA.

**Q: How do I subset to Exophiala only?**
A: Edit `examples/compare_ordinations.py`, example_4. Or in Python:
```python
exo = bd.resolve_taxa_filter(con, genus="Exophiala")
matrix = bd.get_pfam_matrix(con, rows=exo)
```

**Q: Can I combine feature sets?**
A: Not in this dashboard. But in Python you can concatenate matrices and recompute ordinations. See examples/.

**Q: What if E. mansonii doesn't cluster uniquely in any feature set?**
A: Possible interpretations:
- E. mansonii is phylogenetically "average" relative to Exophiala
- E. mansonii's adaptations are subtle (differ in degree, not presence/absence)
- Differences exist but are masked by assembly/annotation noise (check BUSCO %, differential families on small subsets)

---

## Command Cheat Sheet

### Build dashboard (PCoA only, ~15–30 sec)
```bash
cd compare/Exophiala/dashboard
./bin/make_dashboard.py --compute
./bin/make_dashboard.py --render
```

### Build with alternatives (NMDS/t-SNE/UMAP, ~45–90 sec)
```bash
./bin/make_dashboard.py --alt-ordinations --compute
./bin/make_dashboard.py --render
```

### Just re-render (use cached payload)
```bash
./bin/make_dashboard.py --render
```

### Programmatic: Check one feature set
```python
import sys; sys.path.insert(0, "dashboard/lib")
import bfd_data as bd, ordination as ordi

con = bd.get_connection()
matrix = bd.get_pfam_matrix(con)  # or any other get_*_matrix()
dist = ordi.distance_matrix(matrix, "bray-curtis")  # or euclidean
ord = ordi.pcoa(dist)  # or ordi.nmds(dist), ordi.tsne(dist), ordi.umap_ordination(dist)
print(ord.coords)  # sample coordinates
```

---

## Feature Set Quick Stats

| Feature | Samples | Matrix Size | Metric | Method |
|---------|---------|------------|--------|--------|
| assembly | 11 | 11 × 8 | Euclidean | PCoA |
| codon | 11 | 11 × 64 | chi-square | CA |
| amino_acid | 11 | 11 × 20 | chi-square | CA |
| pfam | 11 | 11 × ~3500 | Bray-Curtis | PCoA |
| cazy | 11 | 11 × ~200 | Bray-Curtis | PCoA |
| merops | 11 | 11 × ~80 | Bray-Curtis | PCoA |
| localization | 11 | 11 × 6 | Euclidean | PCoA |
| secreted_pfam | 11 | 11 × ~1200 | Bray-Curtis | PCoA |
| cytoplasmic_pfam | 11 | 11 × ~3200 | Bray-Curtis | PCoA |
| transmembrane_pfam | 11 | 11 × ~500 | Bray-Curtis | PCoA |
| gc_normalized_pfam | 11 | 11 × ~3500 | Bray-Curtis | PCoA |
| gc_normalized_cazy | 11 | 11 × ~200 | Bray-Curtis | PCoA |
| protein_length | 11 | 11 × 6 | Euclidean | PCoA |
| gene_structure | 11 | 11 × 4 | Euclidean | PCoA |
| cazy_by_class | 11 | 11 × 6 | Bray-Curtis | PCoA |
| peptidase_class | 11 | 11 × 8 | Bray-Curtis | PCoA |

---

## One-Minute Primer: What Each Method Does

**PCoA**: Linear projection. Preserves distances. Best for seeing overall structure.
**NMDS**: Nonlinear; preserves rank-order distances. Good for outlier robustness.
**t-SNE**: Emphasizes local clustering. Stochastic. Use for exploratory "is there clustering?" only.
**UMAP**: Balances local + global. Slightly more stable than t-SNE.

**CA**: For compositional data (codons, AAs). Chi-square distance. Eigenvalue interpretation ≠ variance.
**Bray-Curtis**: For species-abundance data (domains). Accounts for relative frequencies. Good for comparative genomics.
**Euclidean**: For continuous measurements (assembly stats, protein properties). Requires standardization (z-score).

---

## Remember

1. **n=11 is tiny** → high variance explained is expected, not meaningful
2. **PERMANOVA p < 0.05 is a screening signal** → verify with differential families
3. **Dispersion ratio matters** → if > 5, effect is mostly dispersion, not clustering
4. **GC% is a hidden confounder** → check gc_normalized versions
5. **t-SNE/UMAP are exploratory** → don't read coordinates; use PCoA + PERMANOVA for conclusions
6. **Assembly quality confounds domains** → check BUSCO %, N50 as metadata
7. **Always compare compartments** (secreted vs cytoplasm) if looking for functional niche

---

See **ANALYSIS_GUIDE.md** for depth.
See **examples/compare_ordinations.py** for working code.
See **ENHANCEMENTS.md** for what's new.
