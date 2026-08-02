#!/usr/bin/bash -l
#SBATCH -p stajichlab -c 4 --mem 16gb --out logs/BFD.%A.log --time=720 -ansi-log false

# ─────────────────────────────────────────────────────────────────────────────
# BFD Pipeline — Functional annotation + genome stats for Exophiala genomes
#
# Key design decisions for this pre-annotated dataset:
#   • Files live in input/dna/*.scaffolds.fa  and  input/pep/*.proteins.fa
#     using the {Genus}_{species}_{strain} naming convention that the pipeline
#     constructs from samples.csv (SPECIES + STRAIN columns via makeSampleTag).
#     All 11 samples match perfectly after the Cyphellophora europaea fix.
#
#   • ASMID column is empty: ASM-dependent channels (CALC_ASM_STATS,
#     BUSCO_genome) will warn and skip — that is expected for this dataset.
#
#   • GFF3 / CDS / tRNA are not available: CALC_INTERGENIC, CALC_GENE_STATS,
#     codon_freq will warn and skip.  Only protein-dependent analyses run.
#
#   • INPUT_SETUP is disabled (--run_setup false) because
#     genome_annotation/predict_results/ does not exist — we bypass it and
#     point pep_dir / genome_dir directly at the existing files.
#
#   • All functional annotation runs (pfam, cazy, merops, signalp, tmhmm,
#     targetp, idp, wolfpsort, predgpi) are enabled.
#
#   • skip_merge=true: each tool writes its per-species result to
#     results/function/<tool>/ and does not attempt a cross-run merge table.
#     Change to --skip_merge false if you want merge tables built.
#
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

BFD_DIR=/bigdata/stajichlab/shared/projects/BFD/Fungi_BFD/nextflow
LOGDIR=logs/nextflow
mkdir -p "$LOGDIR"

module load nextflow

nextflow run "$BFD_DIR/main.nf" \
    -profile BFD \
    -c "$BFD_DIR/nextflow.config" \
    -w work/BFD \
    -params-file BFD_exophiala_params.yaml \
    -resume
