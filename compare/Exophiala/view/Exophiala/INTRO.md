# Genome & Domain Comparison: *Exophiala*

I've been building tools to look at genome and domain data at a high level.

The units of comparison here are all at the gene / protein level, so if there are allele or transcription-factor (TF) binding site differences that change regulation, this of course isn't picking that up.

## Two sets of questions

### 1. Overall composition — do any factors separate the taxa?

**Exploration dashboard:** <https://cluster.hpcc.ucr.edu/~jstajich/projects/SSF/Exophiala/dashboard/explorer.html>

This dashboard has several interactive panels with precomputed data around the ordination of total content across different classes, plus some more specific content comparisons and enrichment identification. One thing that popped out is an excess of [EthD domains (Pfam PF07110)](https://www.ebi.ac.uk/interpro/entry/pfam/PF07110/) involved in degrading the hydrocarbon ethyl *tert*-butyl ether. I still want to confirm all the numbers, but right now the analysis says 20 copies in *E. mansonii* and only a few in the related *E. mesophila* and the other species.

The tool that displays things was put together with help from AI. The database backing it was also constructed using some AI-generated prompts, but it relies on standard tools for the sequence alignments and calls.

There's more to look through, but this was a starting place to examine.

### 2. Are there novel genes that define this lineage (or group of lineages)?

The question is whether, when we start to compare *E. mansonii* (the first genome from this species) to its relatives, there are novel genes that define this lineage. I built another tool — which I'm calling **NovInvenio** for now — that tries to pick out novelty. I've been training and parameterizing it on things like the *Hex* genes in *Neurospora* that are unique to filamentous fungi, to see what molecular synapomorphies are identifiable.

It has an ingroup and outgroup designation, and we look for genes that fall into the category of being unique to an ingroup. I have some "NEAR" ingroups which are compared but aren't part of the novelty assessment, to cut down on the number of pairwise searches — similarly some "BROAD" outgroups that can be used to examine uniqueness further but aren't part of the novelty assessment tool. All of this is a work in progress, but I'm building it up as Nextflow workflows so it's easy to change datasets and try a different set.

- **[NovInvenio report](https://cluster.hpcc.ucr.edu/~jstajich/projects/SSF/Exophiala/view/Exophiala/report.html)**
- **[Novelties page](https://cluster.hpcc.ucr.edu/~jstajich/projects/SSF/Exophiala/view/Exophiala/novelties.html)** — has a heatmap by default of the presence/absence table. You can sort things with the dropdown and restrict to see only the novelty in one of the ingroups. You can also search for known Pfam domains to see what genes match, and sort by chromosome position so you can see it walking from one end to another (one might expect the telomeric region to have more novelty in some species, for example). The TBLASTN tickbox is a further check for annotation uncertainty: if we couldn't find the protein in the other species but can find it by TBLASTN, maybe it's a cryptic gene that wasn't predicted. The e-value cutoffs are probably important to adjust here to make this more useful; right now it's just an on/off tickbox. If you click on a gene name on the left, it brings up a panel with the protein sequence so you can run a BLAST or follow linkouts to the Pfam domains.

## Other pages (still need work)

These show genes found in everyone. I did not integrate the Pfam domains yet (right now I only compute Pfam on the genes that fall in the novelty class, for speed, since I'm iterating a bit), but you can get a sense of what the patterns are for genes found in all species if we decorate this more.

- **[Core genes](https://cluster.hpcc.ucr.edu/~jstajich/projects/SSF/Exophiala/view/Exophiala/core.html)**

Then there's the loss page, which shows genes we infer to be lost in the ingroup. These might reflect another type of adaptation where the ingroup has lost a collection of genes.

- **[Gene losses](https://cluster.hpcc.ucr.edu/~jstajich/projects/SSF/Exophiala/view/Exophiala/losses.html)**
