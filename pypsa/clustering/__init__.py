# SPDX-FileCopyrightText: PyPSA Contributors
#
# SPDX-License-Identifier: MIT

"""Clustering functionality for PyPSA networks."""

from functools import wraps
from typing import TYPE_CHECKING, Any

import pandas as pd

from pypsa.clustering import spatial, temporal
from pypsa.common import _scenarios_not_implemented

if TYPE_CHECKING:
    from pypsa import Network
    from pypsa.clustering.spatial import Clustering


class ClusteringAccessor:
    """Clustering accessor for clustering a network spatially and temporally.

    <!-- md:guide clustering.ipynb -->
    """

    def __init__(self, n: "Network") -> None:
        """Initialize the ClusteringAccessor."""
        self.n = n

    @_scenarios_not_implemented
    @wraps(spatial.busmap_by_hac)
    def busmap_by_hac(self, *args: Any, **kwargs: Any) -> pd.Series:
        """Wrap [`pypsa.clustering.spatial.busmap_by_hac`][]."""
        return spatial.busmap_by_hac(self.n, *args, **kwargs)

    @_scenarios_not_implemented
    @wraps(spatial.busmap_by_kmeans)
    def busmap_by_kmeans(self, *args: Any, **kwargs: Any) -> pd.Series:
        """Wrap [`pypsa.clustering.spatial.busmap_by_kmeans`][]."""
        return spatial.busmap_by_kmeans(self.n, *args, **kwargs)

    @_scenarios_not_implemented
    @wraps(spatial.busmap_by_greedy_modularity)
    def busmap_by_greedy_modularity(self, *args: Any, **kwargs: Any) -> pd.Series:
        """Wrap [`pypsa.clustering.spatial.busmap_by_greedy_modularity`][]."""
        return spatial.busmap_by_greedy_modularity(self.n, *args, **kwargs)

    @_scenarios_not_implemented
    @wraps(spatial.hac_clustering)
    def cluster_spatially_by_hac(self, *args: Any, **kwargs: Any) -> "Clustering":
        """Wrap [`pypsa.clustering.spatial.hac_clustering`][]."""
        return spatial.hac_clustering(self.n, *args, **kwargs).n

    @_scenarios_not_implemented
    @wraps(spatial.kmeans_clustering)
    def cluster_spatially_by_kmeans(self, *args: Any, **kwargs: Any) -> "Clustering":
        """Wrap [`pypsa.clustering.spatial.kmeans_clustering`][]."""
        return spatial.kmeans_clustering(self.n, *args, **kwargs).n

    @_scenarios_not_implemented
    @wraps(spatial.greedy_modularity_clustering)
    def cluster_spatially_by_greedy_modularity(
        self, *args: Any, **kwargs: Any
    ) -> "Clustering":
        """Wrap [`pypsa.clustering.spatial.greedy_modularity_clustering`][]."""
        return spatial.greedy_modularity_clustering(self.n, *args, **kwargs).n

    @_scenarios_not_implemented
    def cluster_by_busmap(self, *args: Any, **kwargs: Any) -> "Clustering":
        """Cluster the network spatially by busmap.

        This function calls [`pypsa.clustering.ClusteringAccessor.get_clustering_from_busmap`][] internally.
        For more information, see the documentation of that function.

        Returns
        -------
        n : pypsa.Network

        """
        return spatial.get_clustering_from_busmap(self.n, *args, **kwargs).n

    @_scenarios_not_implemented
    @wraps(spatial.get_clustering_from_busmap)
    def get_clustering_from_busmap(self, *args: Any, **kwargs: Any) -> "Clustering":
        """Wrap [`get_clustering_from_busmap`][pypsa.clustering.ClusteringAccessor.get_clustering_from_busmap]."""
        return spatial.get_clustering_from_busmap(self.n, *args, **kwargs)

    # Temporal clustering methods

    @wraps(temporal.cluster_temporally)
    def cluster_temporally(
        self, *args: Any, **kwargs: Any
    ) -> "temporal.TemporalClustering":
        """Cluster network snapshots to typical periods using tsam.

        This function reduces the temporal complexity of a PyPSA network by
        aggregating similar time periods into representative typical periods.
        
        Supports stochastic networks and multi-investment periods.

        Wraps [`pypsa.clustering.temporal.cluster_temporally`][].

        Returns
        -------
        TemporalClustering
            Container with the clustered network and aggregation details.
            Access the reduced network via `result.n`.

        Examples
        --------
        >>> result = n.clustering.cluster_temporally(
        ...     n_typical_periods=12,
        ...     hours_per_period=24,
        ...     cluster_method="hierarchical"
        ... )
        >>> n_reduced = result.n

        See Also
        --------
        pypsa.clustering.temporal.cluster_temporally : Full documentation
        """
        return temporal.cluster_temporally(self.n, *args, **kwargs)

    @wraps(temporal.get_optimal_aggregation_params)
    def get_optimal_aggregation_params(
        self, *args: Any, **kwargs: Any
    ) -> tuple[int, int, float]:
        """Find optimal number of periods and segments for temporal clustering.

        Uses tsam's HyperTunedAggregations to find the Pareto-optimal combination.

        Wraps [`pypsa.clustering.temporal.get_optimal_aggregation_params`][].

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
        >>> result = n.clustering.cluster_temporally(
        ...     n_typical_periods=periods,
        ...     n_segments=segments
        ... )
        """
        return temporal.get_optimal_aggregation_params(self.n, *args, **kwargs)


__all__ = ["ClusteringAccessor", "spatial", "temporal"]
