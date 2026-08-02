"""
Ordination + group-separation stats over the feature matrices from bfd_data.py.

No scikit-bio/prince in this environment's Python (checked: base conda python3 has
duckdb/numpy/scipy/scikit-learn but not skbio/prince) -- PCoA is implemented directly via
classical (Gower) MDS, and correspondence analysis via a hand-rolled SVD on the chi-square-
standardized matrix (the standard CA algorithm, e.g. Greenacre 2007). Both are ~20 lines of
linear algebra; no need for the extra dependency at this scale (11 samples).

With only 11 samples, PCoA (not NMDS) is the default for every feature set, including
Bray-Curtis domain matrices -- NMDS needs multiple random restarts to avoid an unstable/
degenerate solution (sklearn.manifold.MDS has no built-in restart logic, unlike R's
vegan::metaMDS), so it is offered only as an explicit opt-in via nmds(), and always reports
its stress with a "stress > 0.2 = unreliable" flag.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations as _itertools_permutations
from math import comb, factorial

import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist, squareform


# --------------------------------------------------------------------------- distances
def distance_matrix(matrix: pd.DataFrame, metric: str) -> pd.DataFrame:
    """metric: 'euclidean' or 'bray-curtis' (scipy's 'braycurtis')."""
    scipy_metric = "braycurtis" if metric == "bray-curtis" else metric
    d = squareform(pdist(matrix.values, metric=scipy_metric))
    return pd.DataFrame(d, index=matrix.index, columns=matrix.index)


# --------------------------------------------------------------------------- PCoA (classical MDS)
@dataclass
class Ordination:
    coords: pd.DataFrame          # samples x axes
    eigenvalues: np.ndarray
    pct_variance: np.ndarray      # per axis, of positive eigenvalues
    method: str
    extra: dict


def pcoa(dist_df: pd.DataFrame, n_axes: int = 2) -> Ordination:
    """Classical (Gower/Torgerson) MDS: double-center the squared distance matrix and
    eigendecompose. Equivalent to skbio.stats.ordination.pcoa for a valid distance matrix."""
    d = dist_df.values.astype(float)
    n = d.shape[0]
    d2 = d ** 2
    J = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * J @ d2 @ J
    eigvals, eigvecs = np.linalg.eigh(B)
    order = np.argsort(eigvals)[::-1]
    eigvals, eigvecs = eigvals[order], eigvecs[:, order]

    pos = eigvals > 1e-10
    total_pos = eigvals[pos].sum() if pos.any() else 1.0
    pct_variance = np.where(pos, eigvals, 0.0) / total_pos * 100.0

    k = min(n_axes, pos.sum()) if pos.any() else 0
    coords = eigvecs[:, :k] * np.sqrt(np.clip(eigvals[:k], 0, None))
    coords_df = pd.DataFrame(
        coords, index=dist_df.index, columns=[f"PCo{i+1}" for i in range(k)]
    )
    return Ordination(coords_df, eigvals, pct_variance, "pcoa", {})


def correspondence_analysis(count_matrix: pd.DataFrame, n_axes: int = 2) -> Ordination:
    """Standard CA via SVD of the chi-square-standardized matrix (Greenacre's algorithm).
    Used for codon/amino-acid usage profiles -- the established method in comparative codon-
    usage genomics, and it handles rows that are compositional profiles (frequencies) directly,
    with no zero-count pseudocount hackery needed for this data (every codon/AA appears at
    nonzero frequency in every species here)."""
    # Drop all-zero columns (e.g. an 'X'/ambiguous-residue column with no observed frequency
    # in any species) -- a zero column mass makes the chi-square standardization divide by
    # zero and CA meaningless for that column anyway.
    count_matrix = count_matrix.loc[:, count_matrix.sum(axis=0) > 0]
    X = count_matrix.values.astype(float)
    grand_total = X.sum()
    P = X / grand_total
    row_mass = P.sum(axis=1, keepdims=True)
    col_mass = P.sum(axis=0, keepdims=True)
    expected = row_mass @ col_mass
    S = (P - expected) / np.sqrt(expected)

    U, sigma, Vt = np.linalg.svd(S, full_matrices=False)
    eigvals = sigma ** 2
    total = eigvals.sum() if eigvals.sum() > 0 else 1.0
    pct_variance = eigvals / total * 100.0

    Dr_inv_sqrt = 1.0 / np.sqrt(row_mass)
    k = min(n_axes, len(sigma))
    row_coords = Dr_inv_sqrt * U[:, :k] * sigma[:k]
    coords_df = pd.DataFrame(
        row_coords, index=count_matrix.index, columns=[f"CA{i+1}" for i in range(k)]
    )
    return Ordination(coords_df, eigvals, pct_variance, "ca", {})


def nmds(dist_df: pd.DataFrame, n_axes: int = 2, n_restarts: int = 20, seed: int = 0) -> Ordination:
    """Opt-in only (see module docstring). Runs n_restarts random initializations of
    non-metric MDS and keeps the lowest-stress solution; always reports stress so the caller
    can flag stress > 0.2 as unreliable, which is common at n=11."""
    from sklearn.manifold import MDS

    rng = np.random.default_rng(seed)
    best = None
    for i in range(n_restarts):
        model = MDS(
            n_components=n_axes,
            metric=False,
            dissimilarity="precomputed",
            random_state=int(rng.integers(0, 2**31 - 1)),
            normalized_stress=True,
            n_init=1,
        )
        coords = model.fit_transform(dist_df.values)
        if best is None or model.stress_ < best[1]:
            best = (coords, model.stress_)
    coords, stress = best
    coords_df = pd.DataFrame(
        coords, index=dist_df.index, columns=[f"NMDS{i+1}" for i in range(n_axes)]
    )
    return Ordination(coords_df, np.array([]), np.array([]), "nmds", {"stress": float(stress), "unreliable": stress > 0.2})


# --------------------------------------------------------------------------- PERMANOVA + dispersion
@dataclass
class GroupSeparationTest:
    pseudo_f: float
    p_value: float
    n_permutations_run: int
    n_unique_permutations: int
    group_sizes: dict
    dispersion_by_group: dict
    dispersion_ratio: float
    caveat: str


def _unique_permutation_count(group_sizes: list[int]) -> int:
    n = sum(group_sizes)
    denom = 1
    for g in group_sizes:
        denom *= factorial(g)
    return factorial(n) // denom


def _pseudo_f(dist: np.ndarray, labels: np.ndarray) -> float:
    n = dist.shape[0]
    groups = np.unique(labels)
    ss_total = (dist ** 2).sum() / (2 * n)
    ss_within = 0.0
    for g in groups:
        idx = np.where(labels == g)[0]
        if len(idx) <= 1:
            continue
        sub = dist[np.ix_(idx, idx)]
        ss_within += (sub ** 2).sum() / (2 * len(idx))
    ss_among = ss_total - ss_within
    df_among = len(groups) - 1
    df_within = n - len(groups)
    if df_within <= 0 or ss_within == 0:
        return np.inf
    return (ss_among / df_among) / (ss_within / df_within)


def permanova(dist_df: pd.DataFrame, groups: pd.Series, n_permutations: int = 999, seed: int = 0) -> GroupSeparationTest:
    """PERMANOVA with an honest small-n framing: reports how many *unique* label permutations
    actually exist (often far below n_permutations for small/singleton groups, so "999
    permutations" can overstate precision), plus a simple dispersion check (mean
    distance-to-group-centroid, via the PCoA embedding) since a singleton group has zero
    within-group variance by construction and can make PERMANOVA "detect" a dispersion
    artifact rather than a true location difference."""
    dist = dist_df.values
    labels = groups.reindex(dist_df.index).values
    group_sizes = groups.value_counts().to_dict()

    observed_f = _pseudo_f(dist, labels)
    n_unique = _unique_permutation_count(list(group_sizes.values()))
    n_perm_run = min(n_permutations, max(n_unique - 1, 0))

    rng = np.random.default_rng(seed)
    if n_perm_run == 0 or not np.isfinite(observed_f):
        p_value = float("nan")
    else:
        count_ge = 0
        for _ in range(n_perm_run):
            perm_labels = rng.permutation(labels)
            f = _pseudo_f(dist, perm_labels)
            if np.isfinite(f) and f >= observed_f:
                count_ge += 1
        p_value = (count_ge + 1) / (n_perm_run + 1)

    ordination = pcoa(dist_df, n_axes=min(4, dist.shape[0] - 1))
    coords = ordination.coords.values
    dispersion = {}
    for g in np.unique(labels):
        idx = np.where(labels == g)[0]
        if len(idx) == 0:
            continue
        centroid = coords[idx].mean(axis=0)
        dispersion[str(g)] = float(np.mean(np.linalg.norm(coords[idx] - centroid, axis=1)))
    nonzero = [v for v in dispersion.values() if v > 0]
    ratio = (max(dispersion.values()) / min(nonzero)) if nonzero and min(nonzero) > 0 else float("inf")

    caveat = (
        f"n={dist.shape[0]} across {len(group_sizes)} groups: only {n_unique:,} unique label "
        f"permutations exist ({n_perm_run} used, not the full {n_permutations} requested); "
        "treat this as a screening signal, not a confirmatory test."
    )
    if any(v == 1 for v in group_sizes.values()):
        caveat += (
            " At least one group is a singleton (zero within-group variance by construction) -- "
            "an apparent PERMANOVA effect may reflect dispersion, not location; compare the "
            "dispersion_by_group values before concluding the groups differ in composition."
        )

    return GroupSeparationTest(
        pseudo_f=float(observed_f),
        p_value=float(p_value),
        n_permutations_run=n_perm_run,
        n_unique_permutations=n_unique,
        group_sizes=group_sizes,
        dispersion_by_group=dispersion,
        dispersion_ratio=float(ratio),
        caveat=caveat,
    )
