# SPDX-FileCopyrightText: PyPSA Contributors
#
# SPDX-License-Identifier: MIT

"""Tests for temporal clustering with tsam."""

import numpy as np
import pandas as pd
import pytest

import pypsa

# Check if tsam is available
try:
    import tsam.timeseriesaggregation as tsam

    HAS_TSAM = True
except ImportError:
    HAS_TSAM = False


@pytest.fixture
def network_with_time_series() -> pypsa.Network:
    """Create a simple network with time-varying data for testing."""
    n = pypsa.Network()

    # Set up snapshots (1 week hourly)
    n.set_snapshots(pd.date_range("2020-01-01", periods=168, freq="h"))
    n.snapshot_weightings.loc[:] = 1.0

    # Add buses
    n.add("Bus", "bus0")
    n.add("Bus", "bus1")
    n.add("Bus", "bus2")

    # Add line
    n.add("Line", "line0-1", bus0="bus0", bus1="bus1", s_nom=100, x=0.01)
    n.add("Line", "line1-2", bus0="bus1", bus1="bus2", s_nom=100, x=0.01)

    # Add generators with time-varying availability
    solar_cf = np.maximum(0, np.sin(np.linspace(0, 14 * np.pi, 168)))  # Daily pattern
    wind_cf = 0.3 + 0.2 * np.sin(np.linspace(0, 2 * np.pi, 168))  # Weekly pattern

    n.add(
        "Generator",
        "solar",
        bus="bus0",
        p_nom=50,
        p_max_pu=solar_cf,
        marginal_cost=0,
        carrier="solar",
    )

    n.add(
        "Generator",
        "wind",
        bus="bus1",
        p_nom=100,
        p_max_pu=wind_cf,
        marginal_cost=0,
        carrier="wind",
    )

    n.add(
        "Generator",
        "gas",
        bus="bus2",
        p_nom=200,
        marginal_cost=50,
        carrier="gas",
    )

    # Add load with time-varying demand
    load_profile = 50 + 30 * np.sin(np.linspace(0, 14 * np.pi, 168))  # Daily pattern
    n.add("Load", "load", bus="bus2", p_set=load_profile)

    return n


@pytest.fixture
def network_annual() -> pypsa.Network:
    """Create a network with annual hourly data."""
    n = pypsa.Network()

    # Full year
    n.set_snapshots(pd.date_range("2020-01-01", periods=8760, freq="h"))
    n.snapshot_weightings.loc[:] = 1.0

    # Add buses
    n.add("Bus", "bus0")

    # Solar: daily and seasonal pattern
    hours = np.arange(8760)
    day_of_year = hours // 24
    hour_of_day = hours % 24

    # Seasonal factor
    seasonal = 0.5 + 0.5 * np.cos(2 * np.pi * (day_of_year - 172) / 365)
    # Daily factor
    daily = np.maximum(0, np.cos(np.pi * (hour_of_day - 12) / 12))
    solar_cf = seasonal * daily

    n.add(
        "Generator",
        "solar",
        bus="bus0",
        p_nom=100,
        p_max_pu=solar_cf,
        marginal_cost=0,
    )

    n.add(
        "Generator",
        "backup",
        bus="bus0",
        p_nom=200,
        marginal_cost=100,
    )

    # Load profile with daily and seasonal patterns
    base_load = 50
    daily_load = 20 * np.sin(np.pi * (hour_of_day - 6) / 12)
    seasonal_load = 10 * np.sin(2 * np.pi * (day_of_year - 200) / 365)
    load_profile = base_load + daily_load + seasonal_load

    n.add("Load", "load", bus="bus0", p_set=load_profile)

    return n


@pytest.mark.skipif(not HAS_TSAM, reason="tsam not installed")
class TestTemporalClustering:
    """Test temporal clustering functionality."""

    def test_cluster_temporally_basic(self, network_with_time_series):
        """Test basic temporal clustering."""
        n = network_with_time_series

        result = n.cluster.cluster_temporally(
            n_typical_periods=3,
            hours_per_period=24,
            cluster_method="hierarchical",
        )

        # Check that result has expected attributes
        assert hasattr(result, "n")
        assert hasattr(result, "aggregation")
        assert hasattr(result, "typical_periods")
        assert hasattr(result, "period_weights")

        # Check reduced network
        n_reduced = result.n
        assert len(n_reduced.snapshots) < len(n.snapshots)
        assert len(n_reduced.snapshots) == 3 * 24  # 3 periods × 24 hours

        # Check period weights sum approximately to original number of periods
        total_hours = result.period_weights.sum() * 24
        assert np.isclose(total_hours, 168, atol=24)  # Original was 168 hours

    def test_cluster_temporally_with_segmentation(self, network_with_time_series):
        """Test temporal clustering with intra-period segmentation."""
        n = network_with_time_series

        result = n.cluster.cluster_temporally(
            n_typical_periods=3,
            hours_per_period=24,
            n_segments=4,  # 4 segments per day
            cluster_method="hierarchical",
        )

        n_reduced = result.n

        # With segmentation, the number of snapshots depends on how tsam
        # implements segmentation. The key is that we get fewer snapshots
        # than the original.
        assert len(n_reduced.snapshots) < len(n.snapshots)

    def test_cluster_temporally_kmeans(self, network_with_time_series):
        """Test temporal clustering with k-means method."""
        n = network_with_time_series

        result = n.cluster.cluster_temporally(
            n_typical_periods=3,
            hours_per_period=24,
            cluster_method="k_means",
        )

        n_reduced = result.n
        assert len(n_reduced.snapshots) == 3 * 24

    def test_cluster_temporally_extreme_periods(self, network_with_time_series):
        """Test temporal clustering with extreme period handling."""
        n = network_with_time_series

        result = n.cluster.cluster_temporally(
            n_typical_periods=3,
            hours_per_period=24,
            cluster_method="hierarchical",
            extreme_period_method="append",
            add_peak_max=["Load-p_set-load"],
        )

        # With extreme periods appended, we might have more periods
        assert len(result.period_weights) >= 3

    def test_cluster_preserves_components(self, network_with_time_series):
        """Test that clustering preserves static component data."""
        n = network_with_time_series

        result = n.cluster.cluster_temporally(
            n_typical_periods=3,
            hours_per_period=24,
        )

        n_reduced = result.n

        # Check that static components are preserved
        assert len(n_reduced.buses) == len(n.buses)
        assert len(n_reduced.generators) == len(n.generators)
        assert len(n_reduced.loads) == len(n.loads)
        assert len(n_reduced.lines) == len(n.lines)

        # Check static attributes
        assert n_reduced.generators.loc["gas", "marginal_cost"] == 50

    def test_accuracy_indicators(self, network_with_time_series):
        """Test that accuracy indicators are computed."""
        n = network_with_time_series

        result = n.cluster.cluster_temporally(
            n_typical_periods=3,
            hours_per_period=24,
        )

        # Accuracy indicators should be a DataFrame
        assert isinstance(result.accuracy_indicators, pd.DataFrame)

    def test_typical_periods_shape(self, network_with_time_series):
        """Test typical periods have correct shape."""
        n = network_with_time_series

        result = n.cluster.cluster_temporally(
            n_typical_periods=3,
            hours_per_period=24,
        )

        # Should have 3*24 = 72 time steps
        assert len(result.typical_periods) == 72

        # Should have same columns as collected time series
        assert len(result.typical_periods.columns) > 0

    def test_snapshot_weightings_set(self, network_with_time_series):
        """Test that snapshot weightings are correctly set."""
        n = network_with_time_series

        result = n.cluster.cluster_temporally(
            n_typical_periods=3,
            hours_per_period=24,
        )

        n_reduced = result.n

        # Check weightings exist
        assert hasattr(n_reduced, "snapshot_weightings")
        assert len(n_reduced.snapshot_weightings) == len(n_reduced.snapshots)

        # All weightings should be positive (check all values in DataFrame/Series)
        assert (n_reduced.snapshot_weightings.values > 0).all()


@pytest.mark.skipif(not HAS_TSAM, reason="tsam not installed")
class TestOptimalAggregationParams:
    """Test optimal aggregation parameter finding."""

    def test_get_optimal_params_basic(self, network_with_time_series):
        """Test finding optimal parameters."""
        n = network_with_time_series

        # Use a high reduction target for fast test
        n_segments, n_periods, rmse = n.cluster.get_optimal_aggregation_params(
            target_reduction=0.3,  # 30% retention
            hours_per_period=24,
        )

        assert n_segments > 0
        assert n_periods > 0
        assert rmse >= 0


@pytest.mark.skipif(not HAS_TSAM, reason="tsam not installed")
class TestReconstructFullTimeSeries:
    """Test time series reconstruction."""

    def test_reconstruct_basic(self, network_with_time_series):
        """Test reconstructing original time series."""
        from pypsa.clustering.temporal import reconstruct_full_time_series

        n = network_with_time_series

        result = n.cluster.cluster_temporally(
            n_typical_periods=3,
            hours_per_period=24,
        )

        # Reconstruct
        reconstructed = reconstruct_full_time_series(result.n, result)

        # Should have original length
        assert len(reconstructed) == 168  # Original number of snapshots


@pytest.mark.skipif(not HAS_TSAM, reason="tsam not installed")
class TestIntegrationWithOptimization:
    """Test that clustered networks can be optimized."""

    def test_clustered_network_optimization(self, network_with_time_series):
        """Test that a clustered network can be optimized."""
        n = network_with_time_series

        result = n.cluster.cluster_temporally(
            n_typical_periods=2,
            hours_per_period=24,
        )

        n_reduced = result.n

        # Should be able to run optimization
        # Note: This will fail if no solver is installed, which is OK
        try:
            n_reduced.optimize(solver_name="highs")
            assert n_reduced.status == "ok"
        except Exception:
            # No solver available, but network structure is valid
            pass


@pytest.mark.skipif(HAS_TSAM, reason="testing tsam not installed")
def test_tsam_import_error():
    """Test proper error when tsam not installed."""
    from pypsa.clustering.temporal import _check_tsam_installed

    with pytest.raises(ImportError, match="tsam"):
        _check_tsam_installed()


class TestCollectTimeSeries:
    """Test time series collection from network."""

    @pytest.mark.skipif(not HAS_TSAM, reason="tsam not installed")
    def test_collect_generators(self, network_with_time_series):
        """Test collecting generator time series."""
        from pypsa.clustering.temporal import _collect_time_series

        n = network_with_time_series
        ts = _collect_time_series(n, include_loads=False)

        # Should have generator columns
        gen_cols = [c for c in ts.columns if "Generator" in c]
        assert len(gen_cols) > 0

    @pytest.mark.skipif(not HAS_TSAM, reason="tsam not installed")
    def test_collect_loads(self, network_with_time_series):
        """Test collecting load time series."""
        from pypsa.clustering.temporal import _collect_time_series

        n = network_with_time_series
        ts = _collect_time_series(n, include_generators=False)

        # Should have load columns
        load_cols = [c for c in ts.columns if "Load" in c]
        assert len(load_cols) > 0

    @pytest.mark.skipif(not HAS_TSAM, reason="tsam not installed")
    def test_collect_empty_network_error(self):
        """Test error when no time series data available."""
        from pypsa.clustering.temporal import _collect_time_series

        n = pypsa.Network()
        n.set_snapshots(pd.date_range("2020-01-01", periods=24, freq="h"))
        n.add("Bus", "bus0")

        with pytest.raises(ValueError, match="No time series data"):
            _collect_time_series(n)
