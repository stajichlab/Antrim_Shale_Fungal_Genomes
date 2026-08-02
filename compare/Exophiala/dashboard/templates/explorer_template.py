"""Renders the self-contained explorer.html from a payload dict (see bin/make_dashboard.py).

Follows the same conventions as NovInvenio's view/Exophiala/*.html: one <script
type="application/json" id="payload"> blob, vanilla JS/SVG (no CDN, no charting library),
light/dark CSS variables toggled via [data-theme], CVD-safe categorical palette.
"""
import json

CSS = """
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface-1: #fcfcfb; --text-primary: #0b0b0b; --text-secondary: #52514e;
  --muted: #898781; --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10);
  --series-1: #2a78d6; --wash: rgba(42,120,214,0.10); --hover-wash: rgba(11,11,11,0.05);
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --page: #0d0d0d; --surface-1: #1a1a19; --text-primary: #ffffff; --text-secondary: #c3c2b7;
    --muted: #898781; --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
    --series-1: #3987e5; --wash: rgba(57,135,229,0.16); --hover-wash: rgba(255,255,255,0.06);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface-1: #1a1a19; --text-primary: #ffffff; --text-secondary: #c3c2b7;
  --muted: #898781; --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
  --series-1: #3987e5; --wash: rgba(57,135,229,0.16); --hover-wash: rgba(255,255,255,0.06);
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--text-primary);
  font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
.wrap { max-width: min(95vw, 1600px); margin: 0 auto; padding: 24px 20px 64px; }
header.top { display: flex; align-items: flex-start; gap: 16px; margin-bottom: 20px; }
header.top .titles { flex: 1; min-width: 0; }
h1 { margin: 0 0 4px; font-size: 22px; font-weight: 600; letter-spacing: -0.01em; }
.sub { margin: 0; color: var(--text-secondary); font-size: 13px; }
button, select, input[type="search"] {
  font: inherit; color: var(--text-primary); background: var(--surface-1);
  border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px;
}
button { cursor: pointer; }
button:hover { background: var(--hover-wash); }
button.active { background: var(--series-1); color: white; border-color: var(--series-1); }
nav.tabs { display: flex; gap: 6px; margin-bottom: 18px; flex-wrap: wrap; }
section.card {
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px;
  padding: 18px; margin-bottom: 16px;
}
.card-title { margin: 0 0 2px; font-size: 14px; font-weight: 600; }
.card-note { margin: 0 0 16px; color: var(--text-secondary); font-size: 12px; }
.caveat { color: var(--muted); font-size: 12px; padding: 8px 10px; background: var(--wash);
  border-radius: 6px; margin-top: 8px; }
.tab-panel { display: none; }
.tab-panel.active { display: block; }
table { border-collapse: collapse; width: 100%; font-size: 12px; }
th, td { text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--border); white-space: nowrap; }
th { color: var(--text-secondary); font-weight: 600; cursor: pointer; }
th.sort-asc::after { content: " \25B2"; }
th.sort-desc::after { content: " \25BC"; }
tr:hover td { background: var(--hover-wash); }
.controls { display: flex; gap: 10px; align-items: center; margin-bottom: 14px; flex-wrap: wrap; }
.tile-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }
.tile { border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; cursor: pointer; }
.tile:hover { background: var(--hover-wash); }
.tile.focus { outline: 2px solid var(--series-1); }
.tile .name { font-weight: 600; font-size: 13px; }
.tile .meta { color: var(--text-secondary); font-size: 11px; margin-top: 4px; }
svg text { fill: var(--text-secondary); font-size: 11px; }
svg .axis-line { stroke: var(--axis); stroke-width: 1; }
svg .grid-line { stroke: var(--grid); stroke-width: 1; }
svg circle.point { stroke: var(--surface-1); stroke-width: 1.2; cursor: pointer; }
svg circle.point.focus { stroke: var(--text-primary); stroke-width: 2.5; }
.legend { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 8px; font-size: 12px; }
.legend .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 900px) { .two-col { grid-template-columns: 1fr; } }
.link-btn { background: none; border: none; color: var(--series-1); cursor: pointer;
  font: inherit; padding: 0; text-decoration: underline; }
.modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  align-items: center; justify-content: center; z-index: 100; }
.modal-overlay.open { display: flex; }
.modal-box { background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px;
  padding: 18px; max-width: min(90vw, 480px); max-height: 80vh; overflow-y: auto; }
.modal-box h3 { margin: 0 0 4px; font-size: 15px; }
.modal-box .close-btn { float: right; }
tr.current-focus td { font-weight: 600; }
"""

JS = r"""
const PAYLOAD = JSON.parse(document.getElementById('payload').textContent);
const PALETTE = PAYLOAD.palette;
const SPECIES = PAYLOAD.species;
const N = SPECIES.locustag.length;
let FOCUS = null;

const genusColor = (() => {
  const uniq = [...new Set(SPECIES.GENUS)];
  const map = {};
  uniq.forEach((g, i) => { map[g] = PALETTE.categorical[i % PALETTE.categorical.length]; });
  return map;
})();

function speciesLabel(i) {
  return `${SPECIES.SPECIES[i]} (${SPECIES.STRAIN ? SPECIES.STRAIN[i] : ''}) [${SPECIES.locustag[i]}]`;
}

// Human-facing name for a locustag -- "Species name (STRAIN)". Falls back to the locustag
// itself if it can't be resolved (shouldn't happen, but a blank label is worse than a tag).
function speciesName(locustag) {
  const i = SPECIES.locustag.indexOf(locustag);
  if (i < 0) return locustag;
  const strain = SPECIES.STRAIN && SPECIES.STRAIN[i] ? ` (${SPECIES.STRAIN[i]})` : '';
  return `${SPECIES.SPECIES[i]}${strain}`;
}

// External database linkouts for domain-family names shown in the differential table.
// cazy/merops family names double as their own accession; pfam needs the separate
// (unversioned) accession attached server-side, since the displayed name is pfam_id.
function familyLink(kind, row) {
  const escaped = encodeURIComponent(row.family);
  if (kind === 'pfam' && row.pfam_accession) {
    return `<a href="https://www.ebi.ac.uk/interpro/entry/pfam/${row.pfam_accession}/" target="_blank" rel="noopener">${row.family}</a>`;
  }
  if (kind === 'cazy') {
    return `<a href="https://www.cazy.org/${escaped}.html" target="_blank" rel="noopener">${row.family}</a>`;
  }
  if (kind === 'merops') {
    return `<a href="https://www.ebi.ac.uk/merops/cgi-bin/famsum?family=${escaped}" target="_blank" rel="noopener">${row.family}</a>`;
  }
  return row.family;
}

// Shared by tile clicks (toggle on/off) and direct-selection controls (dropdown, ordination
// points, phylogeny tips) -- all funnel through here so every view of "current species" stays
// in sync.
function applyFocus(locustag) {
  FOCUS = locustag;
  document.querySelectorAll('[data-locustag]').forEach(el => {
    el.classList.toggle('focus', el.dataset.locustag === FOCUS);
  });
  if (FOCUS) {
    document.getElementById('composition-species-a').value = FOCUS;
    document.getElementById('species-detail-select').value = FOCUS;
  }
  renderSpeciesDetail();
}

// Tile/point clicks toggle off on a repeat click (back to the unfocused/GENUS-grouped view);
// the species-detail dropdown always sets a specific species instead (see applyFocus above).
function setFocus(locustag) {
  applyFocus(FOCUS === locustag ? null : locustag);
}

// ---------------------------------------------------------------- tabs
function showTab(name) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + name));
  document.querySelectorAll('nav.tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
}
document.querySelectorAll('nav.tabs button').forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));

// ---------------------------------------------------------------- theme toggle
const themeBtn = document.getElementById('theme-toggle');
themeBtn.addEventListener('click', () => {
  const cur = document.documentElement.getAttribute('data-theme');
  document.documentElement.setAttribute('data-theme', cur === 'dark' ? 'light' : 'dark');
});

// ---------------------------------------------------------------- Overview
function renderOverview() {
  const grid = document.getElementById('overview-tiles');
  grid.innerHTML = '';
  for (let i = 0; i < N; i++) {
    const lt = SPECIES.locustag[i];
    const div = document.createElement('div');
    div.className = 'tile';
    div.dataset.locustag = lt;
    const busco = SPECIES.busco_complete_pct && SPECIES.busco_complete_pct[i] != null
      ? `BUSCO C:${SPECIES.busco_complete_pct[i]}% D:${SPECIES.busco_duplicated_pct[i]}%` : 'BUSCO: n/a';
    div.innerHTML = `<div class="name">${SPECIES.SPECIES[i]}</div>
      <div class="meta">${SPECIES.STRAIN[i] || ''} &middot; ${lt}</div>
      <div class="meta">${(SPECIES.TOTAL_LENGTH[i]/1e6).toFixed(1)} Mb &middot; GC ${SPECIES.GC_PERCENT[i]}% &middot; ${SPECIES.gene_count[i]} genes</div>
      <div class="meta">${busco}</div>`;
    div.addEventListener('click', () => setFocus(lt));
    grid.appendChild(div);
  }
}

// ---------------------------------------------------------------- Ordination Explorer
function svgScatter(container, coords, axes, pctVar, colorFn, onClick) {
  const W = 640, H = 480, pad = 46;
  const xs = coords[axes[0]], ys = coords[axes[1]];
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const yMin = Math.min(...ys), yMax = Math.max(...ys);
  const xSpan = (xMax - xMin) || 1, ySpan = (yMax - yMin) || 1;
  const sx = v => pad + (v - xMin) / xSpan * (W - 2 * pad);
  const sy = v => H - pad - (v - yMin) / ySpan * (H - 2 * pad);

  let svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px">`;
  svg += `<line class="axis-line" x1="${pad}" y1="${H-pad}" x2="${W-pad}" y2="${H-pad}"/>`;
  svg += `<line class="axis-line" x1="${pad}" y1="${pad}" x2="${pad}" y2="${H-pad}"/>`;
  svg += `<text x="${W/2}" y="${H-8}" text-anchor="middle">${axes[0]} (${pctVar[0]?.toFixed(1) ?? '?'}%)</text>`;
  svg += `<text x="12" y="${H/2}" text-anchor="middle" transform="rotate(-90 12 ${H/2})">${axes[1]} (${pctVar[1]?.toFixed(1) ?? '?'}%)</text>`;
  for (let i = 0; i < N; i++) {
    const lt = SPECIES.locustag[i];
    const cls = 'point' + (lt === FOCUS ? ' focus' : '');
    svg += `<circle class="${cls}" data-locustag="${lt}" cx="${sx(xs[i])}" cy="${sy(ys[i])}" r="6" fill="${colorFn(i)}"><title>${speciesLabel(i)}</title></circle>`;
  }
  svg += `</svg>`;
  container.innerHTML = svg;
  container.querySelectorAll('circle.point').forEach(c => {
    c.addEventListener('click', () => onClick(c.dataset.locustag));
  });
}

function renderPermanova(container, stats) {
  if (!stats) { container.innerHTML = ''; return; }
  container.innerHTML = `<div class="caveat">
    PERMANOVA pseudo-F = ${stats.pseudo_f.toFixed(3)}, p = ${isNaN(stats.p_value) ? 'n/a' : stats.p_value.toFixed(3)}
    (${stats.n_permutations_run} of ${stats.n_unique_permutations} unique permutations run).
    Dispersion by group: ${Object.entries(stats.dispersion_by_group).map(([g,v]) => `${g}=${v.toFixed(3)}`).join(', ')}.
    <br>${stats.caveat}</div>`;
}

function renderOrdination() {
  const sel = document.getElementById('feature-set-select');
  const fsName = sel.value;
  const fs = PAYLOAD.feature_sets[fsName];
  document.getElementById('feature-set-description').textContent = fs.description || '';
  const container = document.getElementById('ordination-plot');
  svgScatter(container, fs.coords, fs.axes, fs.pct_variance, i => genusColor[SPECIES.GENUS[i]], setFocus);

  const legend = document.getElementById('ordination-legend');
  legend.innerHTML = Object.entries(genusColor).map(([g,c]) =>
    `<span><span class="swatch" style="background:${c}"></span>${g}</span>`).join('');

  const statsToShow = FOCUS ? fs.permanova_by_species[FOCUS] : fs.permanova_genus;
  renderPermanova(document.getElementById('ordination-stats'), statsToShow);
  document.getElementById('ordination-stats-label').textContent = FOCUS
    ? `${speciesName(FOCUS)} vs. rest` : 'grouped by GENUS';
}
document.getElementById('feature-set-select').addEventListener('change', renderOrdination);

// ---------------------------------------------------------------- Phylogeny (BUSCO/PHYling
// gene tree built from exactly these 11 genomes -- see lib/bfd_data.py load_tree/phylo_layout)
function renderPhyloTree() {
  const container = document.getElementById('phylo-tree');
  const phylo = PAYLOAD.phylogeny;
  if (!phylo) {
    container.innerHTML = '<p class="card-note">No phylogeny available for this build.</p>';
    return;
  }
  const nTips = phylo.tips.length;
  const rowH = 26, pad = 12, labelW = 140, treeW = 300;
  const W = pad*2 + treeW + labelW, H = pad*2 + rowH*nTips;
  const sx = x => pad + (x / (phylo.max_x || 1)) * treeW;
  const sy = y => pad + y * rowH + rowH/2;

  let svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px">`;
  phylo.segments.forEach(s => {
    svg += `<line class="axis-line" x1="${sx(s.x0).toFixed(1)}" y1="${sy(s.y0).toFixed(1)}" x2="${sx(s.x1).toFixed(1)}" y2="${sy(s.y1).toFixed(1)}"/>`;
  });
  phylo.tips.forEach(t => {
    const i = SPECIES.locustag.indexOf(t.locustag);
    const cls = 'point' + (t.locustag === FOCUS ? ' focus' : '');
    svg += `<circle class="${cls}" data-locustag="${t.locustag}" cx="${sx(t.x).toFixed(1)}" cy="${sy(t.y).toFixed(1)}" r="4.5" fill="${genusColor[SPECIES.GENUS[i]]}"><title>${speciesLabel(i)}</title></circle>`;
    svg += `<text x="${(sx(t.x)+8).toFixed(1)}" y="${(sy(t.y)+3.5).toFixed(1)}">${SPECIES.SPECIES[i]}</text>`;
  });
  svg += `</svg>`;
  container.innerHTML = svg;
  container.querySelectorAll('circle.point').forEach(c => {
    c.addEventListener('click', () => setFocus(c.dataset.locustag));
  });
}

// Click-to-sort for any <table> with a <thead>/<tbody>: click a <th> to sort ascending, click
// again for descending. Cells opt into numeric sorting via the header's data-sort-type="num"
// (default is string compare); a cell can override what gets compared via data-sort, since its
// rendered content may include markup (links, buttons) that textContent would garble.
function makeSortable(table) {
  const thead = table.querySelector('thead');
  const tbody = table.querySelector('tbody');
  if (!thead || !tbody) return;
  const ths = [...thead.querySelectorAll('th')];
  ths.forEach((th, colIndex) => {
    th.addEventListener('click', () => {
      const nextDir = th.classList.contains('sort-asc') ? 'desc' : 'asc';
      ths.forEach(t => t.classList.remove('sort-asc', 'sort-desc'));
      th.classList.add(nextDir === 'asc' ? 'sort-asc' : 'sort-desc');
      const isNum = th.dataset.sortType === 'num';
      const rows = [...tbody.querySelectorAll('tr')];
      rows.sort((a, b) => {
        const av = a.children[colIndex].dataset.sort ?? a.children[colIndex].textContent.trim();
        const bv = b.children[colIndex].dataset.sort ?? b.children[colIndex].textContent.trim();
        const cmp = isNum ? (parseFloat(av) - parseFloat(bv)) : String(av).localeCompare(String(bv));
        return nextDir === 'asc' ? cmp : -cmp;
      });
      rows.forEach(r => tbody.appendChild(r));
    });
  });
}

// ---------------------------------------------------------------- Composition
// Each series item is {label, values, counts?}. When counts (raw integers backing each
// fraction) are supplied -- e.g. localization's SignalP/IDP proportions -- the tooltip shows
// "N (X%)" instead of a bare fraction, since a percentage alone drops the sample size.
function barChart(container, categories, series, colors) {
  const W = 900, H = 220, pad = 40;
  const maxV = Math.max(...series.flatMap(s => s.values), 1e-9);
  const groupW = (W - 2*pad) / categories.length;
  let svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px">`;
  svg += `<line class="axis-line" x1="${pad}" y1="${H-pad}" x2="${W-pad}" y2="${H-pad}"/>`;
  categories.forEach((cat, ci) => {
    const bw = groupW / (series.length + 1);
    series.forEach((s, si) => {
      const v = s.values[ci];
      const h = (v / maxV) * (H - 2*pad);
      const x = pad + ci*groupW + si*bw;
      const valueText = s.counts ? `${s.counts[ci]} (${(v*100).toFixed(1)}%)` : v.toFixed(4);
      svg += `<rect x="${x.toFixed(1)}" y="${(H-pad-h).toFixed(1)}" width="${(bw*0.85).toFixed(1)}" height="${h.toFixed(1)}" fill="${colors[si]}"><title>${s.label}: ${cat} = ${valueText}</title></rect>`;
    });
    if (categories.length <= 25) {
      svg += `<text x="${(pad+ci*groupW+groupW/2).toFixed(1)}" y="${H-pad+14}" text-anchor="middle" font-size="9">${cat}</text>`;
    }
  });
  svg += `</svg>`;
  container.innerHTML = svg;
}

const REST_OF_ALL = '__rest__';

function speciesOptionsHtml() {
  return SPECIES.locustag.map(lt => `<option value="${lt}">${speciesName(lt)}</option>`).join('');
}

function populateCompositionSpeciesSelects() {
  const selA = document.getElementById('composition-species-a');
  const selB = document.getElementById('composition-species-b');
  const optionsHtml = speciesOptionsHtml();
  selA.innerHTML = optionsHtml;
  selB.innerHTML = `<option value="${REST_OF_ALL}">Mean of all other species</option>` + optionsHtml;
  selA.value = SPECIES.locustag[0];
  selB.value = REST_OF_ALL;
}

function populateSpeciesDetailSelect() {
  const sel = document.getElementById('species-detail-select');
  sel.innerHTML = speciesOptionsHtml();
  sel.value = FOCUS || SPECIES.locustag[0];
  sel.addEventListener('change', () => applyFocus(sel.value));
}

function compositionSeries(comp, lt) {
  if (lt === REST_OF_ALL) return null;  // caller falls back to meanOfRest
  return comp.values[lt];
}

// Raw counts only exist for a specific species (not a "mean of rest" series -- averaging raw
// integer counts across genomes of different sizes isn't a count anymore).
function compositionCounts(comp, lt) {
  return (lt !== REST_OF_ALL && comp.counts) ? comp.counts[lt] : undefined;
}

function meanOfRest(comp, excludeLt) {
  return comp.categories.map((_, ci) => {
    const vals = SPECIES.locustag.filter(lt => lt !== excludeLt).map(lt => comp.values[lt][ci]);
    return vals.reduce((a,b)=>a+b,0) / vals.length;
  });
}

function renderComposition() {
  const which = document.getElementById('composition-select').value;
  const comp = PAYLOAD.composition[which];
  const ltA = document.getElementById('composition-species-a').value;
  const ltB = document.getElementById('composition-species-b').value;

  const valuesA = compositionSeries(comp, ltA) || meanOfRest(comp, ltB === REST_OF_ALL ? null : ltB);
  const labelA = ltA === REST_OF_ALL ? 'Mean of all other species' : speciesName(ltA);
  const valuesB = compositionSeries(comp, ltB) || meanOfRest(comp, ltA);
  const labelB = ltB === REST_OF_ALL ? `Mean of all species except ${speciesName(ltA)}` : speciesName(ltB);

  const countsA = compositionCounts(comp, ltA);
  const countsB = compositionCounts(comp, ltB);
  barChart(document.getElementById('composition-plot'), comp.categories,
    [{label: labelA, values: valuesA, counts: countsA}, {label: labelB, values: valuesB, counts: countsB}],
    [PALETTE.blue, PALETTE.muted]);
  renderCompositionCountsTable(comp.categories, labelA, valuesA, countsA, labelB, valuesB, countsB);

  const diffFocus = ltA === REST_OF_ALL ? ltB : ltA;
  const diffSel = document.getElementById('differential-kind-select');
  renderDifferential(diffSel.value, diffFocus);
}
// Only shown for composition types that carry raw counts (currently just localization --
// SignalP/IDP/etc.) -- the hover tooltip on the bars has the same numbers, but a static table
// is more discoverable and matches the "total numbers + %" ask directly.
function renderCompositionCountsTable(categories, labelA, valuesA, countsA, labelB, valuesB, countsB) {
  const box = document.getElementById('composition-counts-table');
  if (!countsA || !countsB) { box.innerHTML = ''; return; }
  let html = `<table><thead><tr>
    <th data-sort-type="text">Category</th>
    <th data-sort-type="num">${labelA}</th>
    <th data-sort-type="num">${labelB}</th>
  </tr></thead><tbody>`;
  categories.forEach((cat, ci) => {
    const pctA = (valuesA[ci] * 100).toFixed(1), pctB = (valuesB[ci] * 100).toFixed(1);
    html += `<tr>
      <td data-sort="${cat}">${cat}</td>
      <td data-sort="${countsA[ci]}">${countsA[ci]} (${pctA}%)</td>
      <td data-sort="${countsB[ci]}">${countsB[ci]} (${pctB}%)</td>
    </tr>`;
  });
  html += `</tbody></table>`;
  box.innerHTML = html;
  box.querySelectorAll('table').forEach(makeSortable);
}
document.getElementById('composition-select').addEventListener('change', renderComposition);
document.getElementById('composition-species-a').addEventListener('change', renderComposition);
document.getElementById('composition-species-b').addEventListener('change', renderComposition);

function renderDifferential(kind, focusLt) {
  const box = document.getElementById('differential-table');
  const data = PAYLOAD.differential[kind] && PAYLOAD.differential[kind][focusLt];
  if (!data) { box.innerHTML = '<p class="card-note">No differential data for this selection.</p>'; return; }
  function section(title, rows, valueKey) {
    if (!rows.length) return `<h4>${title}</h4><p class="card-note">none</p>`;
    let html = `<h4>${title}</h4><table><thead><tr>
      <th data-sort-type="text">Family</th>
      <th data-sort-type="num">Value</th>
      <th data-sort-type="num">Species /1000 genes</th>
      <th data-sort-type="num">Rest mean /1000 genes</th>
      <th data-sort-type="text">Example proteins</th>
    </tr></thead><tbody>`;
    rows.forEach(r => {
      const familyCell = familyLink(kind, r) +
        ` <button class="link-btn" data-kind="${kind}" data-family="${r.family}" data-accession="${r.pfam_accession || ''}">counts</button>`;
      html += `<tr>
        <td data-sort="${r.family}">${familyCell}</td>
        <td data-sort="${r[valueKey]}">${r[valueKey].toFixed(3)}</td>
        <td data-sort="${r.species_value_per_1000}">${r.species_value_per_1000.toFixed(3)}</td>
        <td data-sort="${r.rest_mean_per_1000}">${r.rest_mean_per_1000.toFixed(3)}</td>
        <td data-sort="${r.example_proteins.join(', ')}">${r.example_proteins.join(', ')}</td>
      </tr>`;
    });
    return html + '</tbody></table>';
  }
  box.innerHTML = section(`Present only in ${speciesName(focusLt)}`, data.present_only, 'value_per_1000')
    + section(`Absent only in ${speciesName(focusLt)}`, data.absent_only, 'value_per_1000')
    + section(`Top fold-change vs. rest`, data.top_fold_change, 'log2_fold_change');
  box.querySelectorAll('.link-btn[data-family]').forEach(btn => {
    btn.addEventListener('click', () =>
      showDomainCounts(btn.dataset.kind, btn.dataset.family, btn.dataset.accession || undefined));
  });
  box.querySelectorAll('table').forEach(makeSortable);
}

// ---------------------------------------------------------------- Domain counts popup
function showDomainCounts(kind, family, pfamAccession) {
  const counts = PAYLOAD.domain_counts[kind] && PAYLOAD.domain_counts[kind][family];
  const body = document.getElementById('domain-counts-body');
  if (!counts) {
    body.innerHTML = `<h3>${family}</h3><p class="card-note">No per-species count data for this family.</p>`;
  } else {
    const rows = SPECIES.locustag
      .map(lt => ({lt, n: counts[lt] || 0}))
      .sort((a, b) => b.n - a.n);
    let html = `<h3>${familyLink(kind, {family, pfam_accession: pfamAccession})}</h3><p class="card-note">Raw protein counts per species (${kind}).</p>`;
    html += `<table><thead><tr><th data-sort-type="text">Species</th><th data-sort-type="num">Count</th></tr></thead><tbody>`;
    rows.forEach(r => {
      const cls = r.lt === FOCUS ? ' class="current-focus"' : '';
      html += `<tr${cls}><td data-sort="${speciesName(r.lt)}">${speciesName(r.lt)}</td><td data-sort="${r.n}">${r.n}</td></tr>`;
    });
    html += `</tbody></table>`;
    body.innerHTML = html;
    body.querySelectorAll('table').forEach(makeSortable);
  }
  document.getElementById('domain-counts-overlay').classList.add('open');
}
function closeDomainCounts() {
  document.getElementById('domain-counts-overlay').classList.remove('open');
}
document.getElementById('domain-counts-close').addEventListener('click', closeDomainCounts);
document.getElementById('domain-counts-overlay').addEventListener('click', e => {
  if (e.target.id === 'domain-counts-overlay') closeDomainCounts();
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDomainCounts(); });
function currentDiffFocus() {
  const ltA = document.getElementById('composition-species-a').value;
  const ltB = document.getElementById('composition-species-b').value;
  return ltA === REST_OF_ALL ? ltB : ltA;
}
document.getElementById('differential-kind-select').addEventListener('change', () => {
  renderDifferential(document.getElementById('differential-kind-select').value, currentDiffFocus());
});

// ---------------------------------------------------------------- Species Detail
function renderSpeciesDetail() {
  const box = document.getElementById('species-detail');
  if (!FOCUS) { box.innerHTML = '<p class="card-note">Select a species above to see its detail.</p>'; return; }
  const i = SPECIES.locustag.indexOf(FOCUS);
  let html = `<h3>${SPECIES.SPECIES[i]} ${SPECIES.STRAIN[i] || ''} (${FOCUS})</h3>`;
  html += `<table><tbody>`;
  for (const key of ['GENUS','FAMILY','ORDER','CLASS','TOTAL_LENGTH','GC_PERCENT','contig_count','N50_bp','gene_count','mean_protein_length']) {
    if (SPECIES[key]) html += `<tr><td>${key}</td><td>${SPECIES[key][i]}</td></tr>`;
  }
  html += `</tbody></table>`;
  html += `<p class="card-note">Ordination position and PERMANOVA (this species vs. rest) per feature set:</p><ul>`;
  for (const [name, fs] of Object.entries(PAYLOAD.feature_sets)) {
    const stats = fs.permanova_by_species[FOCUS];
    const coord0 = fs.coords[fs.axes[0]][i].toFixed(2);
    const coord1 = fs.coords[fs.axes[1]][i].toFixed(2);
    html += `<li><b>${name}</b>: (${fs.axes[0]}=${coord0}, ${fs.axes[1]}=${coord1}); pseudo-F=${stats.pseudo_f.toFixed(2)}, p=${isNaN(stats.p_value)?'n/a':stats.p_value.toFixed(3)}</li>`;
  }
  html += `</ul>`;
  // also refresh overview + ordination + composition to reflect focus highlight
  document.querySelectorAll('.tile').forEach(el => el.classList.toggle('focus', el.dataset.locustag === FOCUS));
  renderOrdination();
  renderComposition();
  renderPhyloTree();
  box.innerHTML = html;
}

// ---------------------------------------------------------------- init
renderOverview();
populateCompositionSpeciesSelects();
populateSpeciesDetailSelect();
applyFocus(SPECIES.locustag[0]);  // renders ordination/composition/phylo/detail together
showTab('overview');
"""


def build_html(payload: dict) -> str:
    payload_json = json.dumps(payload, separators=(",", ":"))
    feature_set_options = "".join(
        f'<option value="{name}">{name}</option>' for name in payload["feature_sets"]
    )
    composition_options = "".join(
        f'<option value="{name}">{name}</option>' for name in payload["composition"]
    )
    differential_options = "".join(
        f'<option value="{name}">{name}</option>' for name in payload["differential"]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BFD Explorer — Chaetothyriales comparative genomics</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div class="titles">
      <h1>BFD Comparative Explorer</h1>
      <p class="sub">{len(payload['species']['locustag'])} genomes &middot; generated {payload['generated_at']}</p>
    </div>
    <button id="theme-toggle" class="btn-ghost">Toggle theme</button>
  </header>

  <nav class="tabs">
    <button data-tab="overview" class="active">Overview</button>
    <button data-tab="ordination">Ordination Explorer</button>
    <button data-tab="composition">Composition</button>
  </nav>

  <section class="tab-panel active" id="tab-overview">
    <section class="card">
      <p class="card-title">Genome overview</p>
      <p class="card-note">Click a tile to focus a species -- its detail appears below and carries through to Ordination Explorer and Composition.</p>
      <div class="tile-grid" id="overview-tiles"></div>
    </section>
    <section class="card">
      <div class="controls">
        <p class="card-title" style="margin:0;flex:1;">Species detail</p>
        <label>Species: <select id="species-detail-select"></select></label>
      </div>
      <div id="species-detail"></div>
    </section>
  </section>

  <section class="tab-panel" id="tab-ordination">
    <section class="card">
      <div class="controls">
        <label>Feature set: <select id="feature-set-select">{feature_set_options}</select></label>
        <span id="ordination-stats-label" class="card-note"></span>
      </div>
      <p class="card-note" id="feature-set-description"></p>
      <div class="two-col">
        <div id="ordination-plot"></div>
        <div>
          <div class="legend" id="ordination-legend"></div>
          <div id="ordination-stats"></div>
        </div>
      </div>
    </section>
    <section class="card">
      <p class="card-title">Reference phylogeny</p>
      <p class="card-note">BUSCO/PHYling gene tree built from exactly these 11 genomes (FastTree, support values). Click a tip to focus that species.</p>
      <div id="phylo-tree"></div>
    </section>
  </section>

  <section class="tab-panel" id="tab-composition">
    <section class="card">
      <div class="controls">
        <label>Composition: <select id="composition-select">{composition_options}</select></label>
        <label>Species A: <select id="composition-species-a"></select></label>
        <label>Species B: <select id="composition-species-b"></select></label>
      </div>
      <div id="composition-plot"></div>
      <div id="composition-counts-table"></div>
    </section>
    <section class="card">
      <p class="card-title">Differential domain families</p>
      <div class="controls">
        <label>Domain type: <select id="differential-kind-select">{differential_options}</select></label>
      </div>
      <div id="differential-table"></div>
    </section>
  </section>

</div>

<div class="modal-overlay" id="domain-counts-overlay">
  <div class="modal-box">
    <button class="close-btn" id="domain-counts-close">Close</button>
    <div id="domain-counts-body"></div>
  </div>
</div>

<script type="application/json" id="payload">{payload_json}</script>
<script>{JS}</script>
</body>
</html>
"""
