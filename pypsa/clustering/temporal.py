# SPDX-FileCopyrightText: PyPSA Contributors
#
# SPDX-License-Identifier: MIT

"""Functions for temporal clustering of networks using tsam.

This module provides time series aggregation capabilities for PyPSA networks
using the tsam (time series aggregation module) library. It enables reduction
of computational complexity by clustering time periods into representative
typical periods.

References
----------
.. [1] Kotzur, L., Markewitz, P., Robinius, M., & Stolten, D. (2018).
       Impact of different time series aggregation methods on optimal energy
       system design. Renewable Energy, 117, 474-487.

.. [2] Hoffmann, M., Kotzur, L., Stolten, D., & Robinius, M. (2020).
       A review on time series aggregation methods for energy system models.
       Energies, 13(3), 641.

.. [3] Hoffmann, M., Kotzur, L., & Stolten, D. (2022).
       The Pareto-Optimal Temporal Aggregation of Energy System Models.
       Applied Energy, 315, 118857.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from pypsa import Network

logger = logging.getLogger(__name__)

# Check if tsam is available
try:
    import tsam.timeseriesaggregation as tsam

    HAS_TSAM = True
except ImportError:
    HAS_TSAM = False
    tsam = None  # type: ignore


ClusterMethod = Literal[
    "averaging", "k_means", "k_medoids", "k_maxoids", "hierarchical", "adjacent_periods"
]

RepresentationMethod = Literal[
    "meanRepresentation",
    "medoidRepresentation",
    "minmaxmeanRepresentation",
    "durationRepresentation",
    "distributionRepresentation",
    "distributionAndMinMaxRepresentation",
]

ExtremePeriodMethod = Literal["None", "append", "new_cluster_center", "replace_cluster_center"]


@dataclass
class TemporalClustering:
    """Result container for temporal clustering.

    Attributes
    ----------
    n : Network
        The temporally clustered network with reduced snapshots.
    aggregation : tsam.TimeSeriesAggregation
        The tsam aggregation object containing clustering details.
    typical_periods : pd.DataFrame
        The typical periods data.
    period_weights : pd.Series
        Weights for each typical period (number of occurrences).
    snapshot_map : pd.DataFrame
        Mapping from original snapshots to clustered snapshots.
    accuracy_indicators : pd.DataFrame
        Quality metrics for the aggregation.
    """

    n: "Network"
    aggregation: Any  # tsam.TimeSeriesAggregation
    typical_periods: pd.DataFrame
    period_weights: pd.Series
    snapshot_map: pd.DataFrame = field(default_factory=pd.DataFrame)
    accuracy_indicators: pd.DataFrame = field(default_factory=pd.DataFrame)


def _check_tsam_installed() -> None:
    """Check if tsam is installed and raise error if not."""
    if not HAS_TSAM:
        raise ImportError(
            "The 'tsam' package is required for temporal clustering. "
            "Install it with: pip install tsam"
        )


def _collect_time_series(
    n: "Network",
    include_generators: bool = True,
    include_loads: bool = True,
    include_storage_units: bool = True,
    include_stores: bool = True,
    include_links: bool = True,
    custom_columns: dict[str, pd.Series] | None = None,
) -> pd.DataFrame:
    """Collect all relevant time series from the network.

    Parameters
    ----------
    n : Network
        The PyPSA network.
    include_generators : bool, default True
        Include generator time series (p_max_pu, marginal_cost).
    include_loads : bool, default True
        Include load time series (p_set).
    include_storage_units : bool, default True
        Include storage unit time series.
    include_stores : bool, default True
        Include store time series.
    include_links : bool, default True
        Include link time series (efficiency, p_max_pu).
    custom_columns : dict, optional
        Additional custom time series to include.

    Returns
    -------
    pd.DataFrame
        Combined time series with datetime index.
    """
    dfs = []

    if include_generators:
        # Generator availability profiles
        if not n.generators_t.p_max_pu.empty:
            gen_pu = n.generators_t.p_max_pu.copy()
            gen_pu.columns = [f"Generator-p_max_pu-{c}" for c in gen_pu.columns]
            dfs.append(gen_pu)

        # Generator marginal costs (if time-varying)
        if not n.generators_t.marginal_cost.empty:
            gen_mc = n.generators_t.marginal_cost.copy()
            gen_mc.columns = [f"Generator-marginal_cost-{c}" for c in gen_mc.columns]
            dfs.append(gen_mc)

    if include_loads:
        # Load profiles
        if not n.loads_t.p_set.empty:
            load_p = n.loads_t.p_set.copy()
            load_p.columns = [f"Load-p_set-{c}" for c in load_p.columns]
            dfs.append(load_p)

    if include_storage_units:
        # Storage unit inflow
        if not n.storage_units_t.inflow.empty:
            su_inflow = n.storage_units_t.inflow.copy()
            su_inflow.columns = [f"StorageUnit-inflow-{c}" for c in su_inflow.columns]
            dfs.append(su_inflow)

    if include_stores:
        # Store inflow
        if not n.stores_t.e_set.empty:
            st_e = n.stores_t.e_set.copy()
            st_e.columns = [f"Store-e_set-{c}" for c in st_e.columns]
            dfs.append(st_e)

    if include_links:
        # Link efficiency profiles
        if not n.links_t.efficiency.empty:
            link_eff = n.links_t.efficiency.copy()
            link_eff.columns = [f"Link-efficiency-{c}" for c in link_eff.columns]
            dfs.append(link_eff)

        # Link availability profiles
        if not n.links_t.p_max_pu.empty:
            link_pu = n.links_t.p_max_pu.copy()
            link_pu.columns = [f"Link-p_max_pu-{c}" for c in link_pu.columns]
            dfs.append(link_pu)

    # Add custom columns
    if custom_columns:
        for name, series in custom_columns.items():
            if isinstance(series, pd.Series):
                dfs.append(series.to_frame(name))
            elif isinstance(series, pd.DataFrame):
                series.columns = [f"{name}-{c}" for c in series.columns]
                dfs.append(series)

    if not dfs:
        raise ValueError(
            "No time series data found in the network. "
            "Ensure the network has time-varying data before clustering."
        )

    # Combine all time series
    combined = pd.concat(dfs, axis=1)

    # Ensure datetime index
    if not isinstance(combined.index, pd.DatetimeIndex):
        logger.warning(
            "Snapshot index is not DatetimeIndex. "
            "Creating synthetic datetime index for tsam."
        )
        combined.index = pd.date_range(
            start="2020-01-01", periods=len(combined), freq="h"
        )

    return combined


def _apply_typical_periods_to_network(
    n: "Network",
    aggregation: Any,  # tsam.TimeSeriesAggregation
    typical_periods: pd.DataFrame,
) -> "Network":
    """Apply the typical periods to create a new reduced network.

    Parameters
    ----------
    n : Network
        Original network.
    aggregation : tsam.TimeSeriesAggregation
        The tsam aggregation object.
    typical_periods : pd.DataFrame
        The typical periods.

    Returns
    -------
    Network
        New network with reduced snapshots.
    """
    import pypsa

    # Get clustering information
    period_weights = pd.Series(aggregation.clusterPeriodNoOccur)

    # Create new network
    n_clustered = n.copy()

    # Create new snapshot index
    n_periods = len(period_weights)
    hours_per_period = aggregation.hoursPerPeriod

    if aggregation.segmentation:
        # With segmentation: variable number of time steps per period
        new_snapshots = []
        snapshot_weightings = []

        for period_idx in range(n_periods):
            segment_durations = aggregation.segmentDurationDict.get(period_idx, {})
            n_segments = len(segment_durations) if segment_durations else hours_per_period

            for seg_idx in range(n_segments):
                # Create snapshot label
                snapshot_label = f"period_{period_idx}_seg_{seg_idx}"
                new_snapshots.append(snapshot_label)

                # Calculate weighting: period occurrences * segment duration
                period_occur = period_weights.get(period_idx, 1)
                seg_duration = segment_durations.get(seg_idx, 1)
                snapshot_weightings.append(period_occur * seg_duration)

        new_index = pd.Index(new_snapshots, name="snapshot")
        weightings = pd.Series(snapshot_weightings, index=new_index)
    else:
        # Without segmentation: regular structure
        new_snapshots = []
        snapshot_weightings = []

        for period_idx in range(n_periods):
            for hour in range(hours_per_period):
                snapshot_label = f"period_{period_idx}_hour_{hour}"
                new_snapshots.append(snapshot_label)
                snapshot_weightings.append(period_weights.get(period_idx, 1))

        new_index = pd.Index(new_snapshots, name="snapshot")
        weightings = pd.Series(snapshot_weightings, index=new_index)

    # Set new snapshots
    n_clustered.set_snapshots(new_index)
    n_clustered.snapshot_weightings = weightings

    # Apply typical periods to time-varying data
    _apply_time_series_to_network(n_clustered, typical_periods, aggregation)

    logger.info(
        f"Created clustered network with {len(new_index)} snapshots "
        f"(reduced from {len(n.snapshots)})"
    )

    return n_clustered


def _apply_time_series_to_network(
    n: "Network",
    typical_periods: pd.DataFrame,
    aggregation: Any,
) -> None:
    """Apply the typical period time series to network components.

    Parameters
    ----------
    n : Network
        The network to update (modified in-place).
    typical_periods : pd.DataFrame
        The typical periods data.
    aggregation : tsam.TimeSeriesAggregation
        The aggregation object.
    """
    # Map column names back to component attributes
    for col in typical_periods.columns:
        parts = col.split("-", 2)
        if len(parts) != 3:
            continue

        component, attr, name = parts

        # Get the component's dynamic attribute DataFrame
        try:
            component_t = getattr(n, f"{component.lower()}s_t")
            if hasattr(component_t, attr):
                df = getattr(component_t, attr)
                if name in df.columns or df.empty:
                    # Assign the typical period values
                    values = typical_periods[col].values
                    if len(values) == len(n.snapshots):
                        df[name] = values
        except (AttributeError, KeyError):
            logger.debug(f"Could not apply {col} to network")
            continue


def cluster_temporally(
    n: "Network",
    n_typical_periods: int = 10,
    hours_per_period: int = 24,
    n_segments: int | None = None,
    cluster_method: ClusterMethod = "hierarchical",
    representation_method: RepresentationMethod | None = None,
    extreme_period_method: ExtremePeriodMethod = "None",
    rescale_cluster_periods: bool = True,
    weight_dict: dict[str, float] | None = None,
    add_peak_min: list[str] | None = None,
    add_peak_max: list[str] | None = None,
    include_generators: bool = True,
    include_loads: bool = True,
    include_storage_units: bool = True,
    include_stores: bool = True,
    include_links: bool = True,
    custom_time_series: dict[str, pd.Series] | None = None,
    solver: str = "highs",
) -> TemporalClustering:
    """Cluster network snapshots to typical periods using tsam.

    This function reduces the temporal complexity of a PyPSA network by
    aggregating similar time periods into representative typical periods.
    This is particularly useful for long-term energy system optimization
    where full hourly resolution is computationally prohibitive.

    Parameters
    ----------
    n : Network
        The PyPSA network to cluster.
    n_typical_periods : int, default 10
        Number of typical periods to create. More periods increase accuracy
        but also computational cost.
    hours_per_period : int, default 24
        Length of each period in hours. Common values are 24 (daily),
        168 (weekly), or 8760 (yearly).
    n_segments : int, optional
        Number of segments within each period. If None, no segmentation
        is applied. Segmentation further reduces complexity by merging
        similar consecutive hours within periods.
    cluster_method : str, default "hierarchical"
        Clustering algorithm. Options:
        - "averaging": Simple averaging
        - "k_means": K-means clustering
        - "k_medoids": K-medoids clustering (exact, uses solver)
        - "k_maxoids": K-maxoids clustering
        - "hierarchical": Hierarchical agglomerative clustering
        - "adjacent_periods": Cluster only adjacent periods
    representation_method : str, optional
        How to represent each cluster. If None, uses default for cluster_method.
        Options: "meanRepresentation", "medoidRepresentation",
        "minmaxmeanRepresentation", "durationRepresentation",
        "distributionRepresentation", "distributionAndMinMaxRepresentation"
    extreme_period_method : str, default "None"
        How to handle extreme periods (peak demand, etc.).
        Options: "None", "append", "new_cluster_center", "replace_cluster_center"
    rescale_cluster_periods : bool, default True
        Whether to rescale periods to preserve mean values.
    weight_dict : dict, optional
        Weights for different time series during clustering.
        Keys are column names, values are weights.
    add_peak_min : list, optional
        Time series columns for which to add the period with minimum peak.
    add_peak_max : list, optional
        Time series columns for which to add the period with maximum peak.
    include_generators : bool, default True
        Include generator time series in clustering.
    include_loads : bool, default True
        Include load time series in clustering.
    include_storage_units : bool, default True
        Include storage unit time series in clustering.
    include_stores : bool, default True
        Include store time series in clustering.
    include_links : bool, default True
        Include link time series in clustering.
    custom_time_series : dict, optional
        Additional custom time series to include.
    solver : str, default "highs"
        Solver for k_medoids clustering.

    Returns
    -------
    TemporalClustering
        Container with the clustered network and aggregation details.

    Examples
    --------
    Basic usage with 12 typical days:

    >>> result = n.clustering.cluster_temporally(
    ...     n_typical_periods=12,
    ...     hours_per_period=24,
    ...     cluster_method="hierarchical"
    ... )
    >>> n_reduced = result.n
    >>> print(f"Reduced from {len(n.snapshots)} to {len(n_reduced.snapshots)} snapshots")

    With segmentation for further reduction:

    >>> result = n.clustering.cluster_temporally(
    ...     n_typical_periods=8,
    ...     hours_per_period=24,
    ...     n_segments=6,  # 6 segments per day
    ...     cluster_method="k_means"
    ... )

    Preserving extreme periods:

    >>> result = n.clustering.cluster_temporally(
    ...     n_typical_periods=10,
    ...     hours_per_period=24,
    ...     extreme_period_method="append",
    ...     add_peak_max=["Load-p_set-load1"]  # Ensure peak load is captured
    ... )

    See Also
    --------
    pypsa.clustering.temporal.get_optimal_aggregation_params : Find optimal parameters
    tsam.TimeSeriesAggregation : Underlying tsam class

    References
    ----------
    .. [1] Kotzur et al. (2018). Impact of different time series aggregation
           methods on optimal energy system design. Renewable Energy.
    """
    _check_tsam_installed()

    logger.info(
        f"Starting temporal clustering: {n_typical_periods} periods, "
        f"{hours_per_period} hours/period, method={cluster_method}"
    )

    # Collect time series from network
    time_series = _collect_time_series(
        n,
        include_generators=include_generators,
        include_loads=include_loads,
        include_storage_units=include_storage_units,
        include_stores=include_stores,
        include_links=include_links,
        custom_columns=custom_time_series,
    )

    logger.info(f"Collected {len(time_series.columns)} time series for clustering")

    # Prepare tsam parameters
    tsam_kwargs: dict[str, Any] = {
        "noTypicalPeriods": n_typical_periods,
        "hoursPerPeriod": hours_per_period,
        "clusterMethod": cluster_method,
        "rescaleClusterPeriods": rescale_cluster_periods,
        "extremePeriodMethod": extreme_period_method,
        "solver": solver,
    }

    if n_segments is not None:
        tsam_kwargs["segmentation"] = True
        tsam_kwargs["noSegments"] = n_segments
    else:
        tsam_kwargs["segmentation"] = False

    if representation_method is not None:
        tsam_kwargs["representationMethod"] = representation_method

    if weight_dict is not None:
        tsam_kwargs["weightDict"] = weight_dict

    if add_peak_min is not None:
        tsam_kwargs["addPeakMin"] = add_peak_min

    if add_peak_max is not None:
        tsam_kwargs["addPeakMax"] = add_peak_max

    # Create aggregation object
    aggregation = tsam.TimeSeriesAggregation(time_series, **tsam_kwargs)

    # Run clustering
    typical_periods = aggregation.createTypicalPeriods()

    logger.info(
        f"Created {len(aggregation.clusterPeriodNoOccur)} typical periods "
        f"with {len(typical_periods)} time steps total"
    )

    # Get accuracy indicators
    try:
        accuracy = aggregation.accuracyIndicators()
    except Exception as e:
        logger.warning(f"Could not compute accuracy indicators: {e}")
        accuracy = pd.DataFrame()

    # Get index matching for snapshot mapping
    try:
        snapshot_map = aggregation.indexMatching()
    except Exception as e:
        logger.warning(f"Could not compute snapshot mapping: {e}")
        snapshot_map = pd.DataFrame()

    # Create period weights
    period_weights = pd.Series(
        aggregation.clusterPeriodNoOccur,
        name="occurrences"
    )

    # Apply to network
    n_clustered = _apply_typical_periods_to_network(n, aggregation, typical_periods)

    return TemporalClustering(
        n=n_clustered,
        aggregation=aggregation,
        typical_periods=typical_periods,
        period_weights=period_weights,
        snapshot_map=snapshot_map,
        accuracy_indicators=accuracy,
    )


def get_optimal_aggregation_params(
    n: "Network",
    target_reduction: float = 0.05,
    hours_per_period: int = 24,
    cluster_method: ClusterMethod = "hierarchical",
    include_generators: bool = True,
    include_loads: bool = True,
    include_storage_units: bool = True,
    include_stores: bool = True,
    include_links: bool = True,
) -> tuple[int, int, float]:
    """Find optimal number of periods and segments for a target data reduction.

    Uses tsam's HyperTunedAggregations to find the Pareto-optimal combination
    of typical periods and segments that minimizes RMSE for a given data
    reduction target.

    Parameters
    ----------
    n : Network
        The PyPSA network.
    target_reduction : float, default 0.05
        Target fraction of original data to retain (0.05 = 5% = 95% reduction).
    hours_per_period : int, default 24
        Length of each period in hours.
    cluster_method : str, default "hierarchical"
        Clustering method to use.
    include_generators : bool, default True
        Include generator time series.
    include_loads : bool, default True
        Include load time series.
    include_storage_units : bool, default True
        Include storage unit time series.
    include_stores : bool, default True
        Include store time series.
    include_links : bool, default True
        Include link time series.

    Returns
    -------
    n_segments : int
        Optimal number of segments.
    n_periods : int
        Optimal number of typical periods.
    rmse : float
        Root mean square error of the aggregation.

    Examples
    --------
    >>> segments, periods, rmse = n.clustering.get_optimal_aggregation_params(
    ...     target_reduction=0.05  # Reduce to 5% of original data
    ... )
    >>> print(f"Optimal: {periods} periods with {segments} segments, RMSE={rmse:.4f}")
    >>> result = n.clustering.cluster_temporally(
    ...     n_typical_periods=periods,
    ...     n_segments=segments
    ... )

    References
    ----------
    .. [1] Hoffmann et al. (2022). The Pareto-Optimal Temporal Aggregation
           of Energy System Models. Applied Energy.
    """
    _check_tsam_installed()
    from tsam import hyperparametertuning as tune

    logger.info(f"Finding optimal aggregation params for {target_reduction:.1%} data retention")

    # Collect time series
    time_series = _collect_time_series(
        n,
        include_generators=include_generators,
        include_loads=include_loads,
        include_storage_units=include_storage_units,
        include_stores=include_stores,
        include_links=include_links,
    )

    # Create base aggregation
    base_aggregation = tsam.TimeSeriesAggregation(
        time_series,
        hoursPerPeriod=hours_per_period,
        clusterMethod=cluster_method,
        rescaleClusterPeriods=True,
        segmentation=True,
    )

    # Use hypertuning
    tuner = tune.HyperTunedAggregations(base_aggregation)

    n_segments, n_periods, rmse = tuner.identifyOptimalSegmentPeriodCombination(
        dataReduction=target_reduction
    )

    logger.info(
        f"Optimal parameters: {n_periods} periods, {n_segments} segments, "
        f"RMSE={rmse:.6f}"
    )

    return int(n_segments), int(n_periods), float(rmse)


def reconstruct_full_time_series(
    n_clustered: "Network",
    clustering_result: TemporalClustering,
) -> pd.DataFrame:
    """Reconstruct the full time series from clustered results.

    This is useful for post-processing optimization results back to
    the original temporal resolution.

    Parameters
    ----------
    n_clustered : Network
        The clustered network with optimization results.
    clustering_result : TemporalClustering
        The clustering result containing the aggregation object.

    Returns
    -------
    pd.DataFrame
        Reconstructed time series at original resolution.

    Examples
    --------
    >>> # After optimization
    >>> result = n.clustering.cluster_temporally(n_typical_periods=12)
    >>> n_reduced = result.n
    >>> n_reduced.optimize()  # Optimize reduced network
    >>> # Reconstruct results
    >>> full_results = reconstruct_full_time_series(n_reduced, result)
    """
    aggregation = clustering_result.aggregation

    # Use tsam's prediction to reconstruct
    predicted = aggregation.predictOriginalData()

    return predicted
