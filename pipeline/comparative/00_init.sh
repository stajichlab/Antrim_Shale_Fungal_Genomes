#!/usr/bin/env bash
#SBATCH -p short --out logs/comparative_init.log

mkdir -p Comparative
pushd Comparative
ln -s ../Comparative_pipeline/lib
ln -s ../Comparative_pipeline/pipeline .
ln -s ../Comparative_pipeline
cp lib/config.txt .
perl -i -p -e 's/PROJECT=(\S+)/PROJECT=AfumRef/' config.txt
perl -i -p -e 's/OUTGROUP=(\S+)/OUTGROUP=W72310/' config.txt
mkdir -p pep cds input

for f in $(ls ../annotation/*/annotate_results/*.proteins.fa)
do
 b=$(basename $f .proteins.fa)
 if [ ! -f  pep/$b.aa.fasta ]; then
  perl -p -e 's/>([^_]+)_/>$1|$1_/' $f > pep/$b.aa.fasta
  rsync -aL $f input
 fi
done
bash Comparative_pipeline/pipeline/00_init.sh
count=$(ls pep/*.aa.fasta | wc -l | awk '{print $1}')

#sbatch -a 1-${count} pipeline/01_domains_MEROPS.sh
sbatch -a 1-${count} pipeline/01_domains_pfam.sh
#sbatch -a 1-${count} pipeline/01_domains_CAZY.sh

sbatch pipeline/03_OrthoFinder.sh
