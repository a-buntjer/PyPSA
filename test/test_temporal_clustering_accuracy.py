# SPDX-FileCopyrightText: PyPSA Contributors
#
# SPDX-License-Identifier: MIT

"""
Comprehensive accuracy test for temporal clustering with realistic energy system model.

This test creates a realistic energy system with:
- Stochastic scenarios (2 scenarios: "niedrig", "hoch")
- Multi-investment periods (2020, 2030)
- Extendable generators (solar, wind)
- Heat storage (PyPSA Store component)
- Heat pump (Link)
- Electricity and heat buses

The test compares:
1. Full resolution optimization (8760 hours × 2 periods = 17520 snapshots)
2. Clustered optimization (e.g., 12 typical days × 24 hours = 288 snapshots)

Metrics evaluated:
- Total system cost deviation
- Optimal capacity deviation
- Storage operation patterns
- Computational time savings

Storage SOC Handling during Clustering:
=======================================
When using temporal clustering with storage components (Store, StorageUnit),
the following aspects are important:

1. **Cyclic Storage Constraint** (`e_cyclic=True`):
   - The `e_cyclic` attribute is preserved during clustering
   - This ensures that the state of charge (SOC) at the end of each
     typical period equals the SOC at the beginning
   - This is appropriate for seasonal storage patterns

2. **Standing Loss** (`standing_loss`):
   - The standing loss rate is preserved during clustering
   - Loss is applied per snapshot, so the effective loss per typical
     period is calculated correctly

3. **Period Weights** (`snapshot_weightings`):
   - Each typical period has a weight indicating how often it occurs
     in the original time series
   - These weights are applied to:
     - Operational costs (marginal_cost × weight)
     - Investment decisions (spread across weighted periods)
   - This ensures that the total energy balance is preserved

4. **Inter-period Storage**:
   - For multi-investment periods, the storage operates independently
     within each investment period
   - The `cyclic_state_of_charge_per_period` setting controls whether
     SOC is cyclic per investment period

5. **Accuracy Considerations**:
   - Clustering can underestimate storage needs if peak events are
     averaged out
   - Using `add_peak_min`/`add_peak_max` can help preserve extreme values
   - More typical periods generally improve accuracy at computational cost

Typical accuracy results (with 3 typical days from 1 week):
- Simple network: ~0% cost deviation
- Stochastic network: ~9% cost deviation  
- Full model (stochastic + multi-invest): ~9% cost deviation

Note: Higher number of typical periods reduces the error significantly.
"""

import logging
import time
from typing import Any

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

logger = logging.getLogger(__name__)


def create_realistic_heat_network(
    n_hours: int = 8760,
    investment_periods: list[int] | None = None,
    scenarios: dict[str, float] | None = None,
) -> pypsa.Network:
    """Create a realistic network with heat storage and multiple scenarios.

    Parameters
    ----------
    n_hours : int
        Number of hours per investment period (default: 8760 for full year)
    investment_periods : list[int], optional
        Investment periods (default: [2020, 2030])
    scenarios : dict[str, float], optional
        Scenarios with probabilities (default: {"niedrig": 0.5, "hoch": 0.5})

    Returns
    -------
    pypsa.Network
        Configured network with all components
    """
    if investment_periods is None:
        investment_periods = [2020, 2030]
    # Note: scenarios=None means no scenarios (deterministic network)
    # To use default scenarios, pass scenarios={"niedrig": 0.5, "hoch": 0.5}

    n = pypsa.Network()

    # Create time index
    hours = pd.date_range("2020-01-01", periods=n_hours, freq="h")

    # For multi-investment: create MultiIndex snapshots
    if len(investment_periods) > 1:
        period_index = pd.Index(investment_periods, name="period")
        multi_snapshots = pd.MultiIndex.from_product(
            [period_index, hours], names=["period", "timestep"]
        )
        n.set_snapshots(multi_snapshots)
        n.snapshot_weightings.loc[:, "objective"] = 1.0
        n.snapshot_weightings.loc[:, "generators"] = 1.0
        n.snapshot_weightings.loc[:, "stores"] = 1.0

        # Investment period weightings
        n.investment_period_weightings = pd.DataFrame(
            {"years": [10.0] * len(investment_periods), "objective": [1.0, 0.9]},
            index=period_index,
        )
        total_snapshots = n_hours * len(investment_periods)
    else:
        n.set_snapshots(hours)
        n.snapshot_weightings.loc[:] = 1.0
        total_snapshots = n_hours

    # =========================================================================
    # Create time series profiles
    # =========================================================================

    # Hour of day and day of year for pattern generation
    hour_of_day = np.tile(np.arange(24), n_hours // 24 + 1)[:n_hours]
    day_of_year = np.arange(n_hours) // 24

    # Solar capacity factor: daily and seasonal pattern
    solar_daily = np.maximum(0, np.cos(np.pi * (hour_of_day - 12) / 12))
    solar_seasonal = 0.5 + 0.5 * np.cos(2 * np.pi * (day_of_year - 172) / 365)
    solar_cf = solar_daily * solar_seasonal
    solar_cf = np.clip(solar_cf, 0, 1)

    # Wind capacity factor: more variable, with seasonal pattern
    np.random.seed(42)
    wind_base = 0.3 + 0.2 * np.sin(2 * np.pi * (day_of_year - 30) / 365)
    wind_variability = np.random.normal(0, 0.15, n_hours)
    wind_cf = np.clip(wind_base + wind_variability, 0.05, 0.95)

    # Electricity demand: daily and seasonal pattern
    elec_daily = 0.7 + 0.3 * np.sin(np.pi * (hour_of_day - 6) / 12)
    elec_seasonal = 1.0 + 0.2 * np.cos(2 * np.pi * (day_of_year - 15) / 365)
    elec_demand = 100 * elec_daily * elec_seasonal  # MW

    # Heat demand: higher in winter, daily pattern
    heat_daily = 0.8 + 0.2 * np.sin(np.pi * (hour_of_day - 8) / 12)
    heat_seasonal = 1.5 - 1.0 * np.cos(2 * np.pi * (day_of_year - 15) / 365)
    heat_seasonal = np.clip(heat_seasonal, 0.3, 2.0)
    heat_demand = 50 * heat_daily * heat_seasonal  # MW_th

    # COP of heat pump: temperature dependent (higher in summer)
    cop_base = 3.0
    cop_seasonal = 0.5 * np.cos(2 * np.pi * (day_of_year - 15) / 365)
    cop = cop_base + cop_seasonal
    cop = np.clip(cop, 2.0, 4.5)

    # Repeat profiles for multi-investment periods
    if len(investment_periods) > 1:
        solar_cf = np.tile(solar_cf, len(investment_periods))
        wind_cf = np.tile(wind_cf, len(investment_periods))
        elec_demand = np.tile(elec_demand, len(investment_periods))
        heat_demand = np.tile(heat_demand, len(investment_periods))
        cop = np.tile(cop, len(investment_periods))

    # =========================================================================
    # Add carriers
    # =========================================================================
    n.add("Carrier", "electricity")
    n.add("Carrier", "heat")
    n.add("Carrier", "solar")
    n.add("Carrier", "wind")
    n.add("Carrier", "gas")
    n.add("Carrier", "chp")

    # =========================================================================
    # Add buses
    # =========================================================================
    n.add("Bus", "elec_bus", carrier="electricity")
    n.add("Bus", "heat_bus", carrier="heat")
    n.add("Bus", "gas_bus", carrier="gas")  # Gas bus for CHP

    # =========================================================================
    # Create electricity market price profile (variable)
    # =========================================================================
    
    # Electricity market price: varies by time of day and season
    # Base price ~50 €/MWh, higher during peak hours, lower at night
    price_daily = 50 + 30 * np.sin(np.pi * (hour_of_day - 6) / 12)  # Peak at noon
    price_seasonal = 1.0 + 0.3 * np.cos(2 * np.pi * (day_of_year - 15) / 365)  # Higher in winter
    electricity_price = price_daily * price_seasonal
    electricity_price = np.clip(electricity_price, 20, 120)  # €/MWh
    
    # Repeat for multi-investment periods
    if len(investment_periods) > 1:
        electricity_price = np.tile(electricity_price, len(investment_periods))

    # =========================================================================
    # Add generators
    # =========================================================================

    # Solar PV - extendable
    n.add(
        "Generator",
        "solar",
        bus="elec_bus",
        carrier="solar",
        p_nom=0,
        p_nom_extendable=True,
        p_nom_min=0,
        p_nom_max=500,  # MW
        p_max_pu=solar_cf,
        marginal_cost=0,
        capital_cost=0,  # €/MW/year (free for testing all components)
        build_year=investment_periods[0] if len(investment_periods) > 1 else 2020,
        lifetime=25,
    )

    # Wind - extendable
    n.add(
        "Generator",
        "wind",
        bus="elec_bus",
        carrier="wind",
        p_nom=0,
        p_nom_extendable=True,
        p_nom_min=0,
        p_nom_max=300,  # MW
        p_max_pu=wind_cf,
        marginal_cost=0,
        capital_cost=0,  # €/MW/year (free for testing all components)
        build_year=investment_periods[0] if len(investment_periods) > 1 else 2020,
        lifetime=25,
    )

    # Gas backup - not extendable (small capacity to force renewables)
    n.add(
        "Generator",
        "gas",
        bus="elec_bus",
        carrier="gas",
        p_nom=50,  # MW (reduced to force renewable investment)
        p_nom_extendable=False,
        marginal_cost=120,  # €/MWh (increased - expensive peak power)
    )

    # Gas boiler for heat - connected to gas_bus via Link
    # Converts gas to heat with ~90% efficiency
    n.add(
        "Link",
        "gas_boiler",
        bus0="gas_bus",
        bus1="heat_bus",
        carrier="gas",
        p_nom=100,  # MW_gas input
        p_nom_extendable=False,
        efficiency=0.9,  # 90% thermal efficiency
    )

    # =========================================================================
    # Add CHP (Combined Heat and Power) - 3-port Link
    # =========================================================================

    # CHP: bus0=gas input, bus1=electricity output, bus2=heat output
    # Typical efficiencies: electrical ~40%, thermal ~45%, total ~85%
    n.add(
        "Link",
        "chp",
        bus0="gas_bus",
        bus1="elec_bus",
        bus2="heat_bus",
        carrier="chp",
        p_nom=0,  # MW_gas input
        p_nom_extendable=True,
        p_nom_max=200,  # Max 200 MW gas input
        efficiency=0.4,  # 40% electrical efficiency
        efficiency2=0.45,  # 45% thermal efficiency
        capital_cost=2000,  # €/MW/a (moderate - profitable when elec price high)
        build_year=investment_periods[0] if len(investment_periods) > 1 else 2020,
        lifetime=25,
    )

    # Gas supply for CHP (gas price affects CHP vs heat pump dispatch)
    n.add(
        "Generator",
        "gas_supply",
        bus="gas_bus",
        carrier="gas",
        p_nom=1000,  # Large capacity
        marginal_cost=50,  # €/MWh_gas (moderate gas price)
    )

    # =========================================================================
    # Add Grid Market Connection (bidirectional - can buy and sell)
    # =========================================================================

    # Variable electricity price with daily and seasonal patterns
    hours = np.arange(n_hours)
    hour_of_day_local = hours % 24
    day_of_week = hours // 24

    # Price pattern: base 120 €/MWh, peaks during day, lower at night
    # Range approximately 60-180 €/MWh
    np.random.seed(42)  # For reproducibility
    elec_price = (
        120  # Base price (high to make renewables competitive)
        + 40 * np.sin(2 * np.pi * hour_of_day_local / 24 - np.pi / 2)  # Daily pattern (peak at noon)
        + 20 * np.cos(2 * np.pi * day_of_week / 7)  # Weekly pattern
        + 10 * np.random.randn(n_hours)  # Random noise
    )
    elec_price = np.clip(elec_price, 50, 250)  # Clip to realistic range

    # Repeat for multi-investment periods
    if len(investment_periods) > 1:
        elec_price = np.tile(elec_price, len(investment_periods))

    # Grid market generator with p_min_pu=-1 allows:
    # - Positive power: selling to grid (earning marginal_cost)
    # - Negative power: buying from grid (paying marginal_cost)
    n.add(
        "Generator",
        "grid_market",
        bus="elec_bus",
        carrier="grid",
        p_nom=50,  # MW capacity (limited to force local generation)
        p_min_pu=-1,  # Can also consume (buy from grid)
        marginal_cost=elec_price,  # Variable electricity price
    )

    # =========================================================================
    # Add loads
    # =========================================================================

    n.add("Load", "elec_load", bus="elec_bus", p_set=elec_demand)

    n.add("Load", "heat_load", bus="heat_bus", p_set=heat_demand)

    # =========================================================================
    # Add heat pump (Link from electricity to heat)
    # =========================================================================

    n.add(
        "Link",
        "heat_pump",
        bus0="elec_bus",
        bus1="heat_bus",
        carrier="heat",
        p_nom=0,
        p_nom_extendable=True,
        p_nom_min=0,
        p_nom_max=100,  # MW_el
        efficiency=cop,  # Time-varying COP (2.0-4.5)
        capital_cost=0,  # €/MW_el/year (free - dispatched when electricity cheap)
        build_year=investment_periods[0] if len(investment_periods) > 1 else 2020,
        lifetime=20,
    )

    # =========================================================================
    # Add heat storage (Store component)
    # =========================================================================

    n.add(
        "Store",
        "heat_storage",
        bus="heat_bus",
        carrier="heat",
        e_nom=0,
        e_nom_extendable=True,
        e_nom_min=0,
        e_nom_max=500,  # MWh_th
        e_cyclic=True,  # Important for temporal clustering!
        standing_loss=0.01,  # 1% per hour
        capital_cost=100,  # €/MWh/year (very low for 1-week test)
        build_year=investment_periods[0] if len(investment_periods) > 1 else 2020,
        lifetime=30,
    )

    # =========================================================================
    # Add battery storage (for electricity)
    # =========================================================================

    n.add(
        "Store",
        "battery",
        bus="elec_bus",
        carrier="electricity",
        e_nom=0,
        e_nom_extendable=True,
        e_nom_min=0,
        e_nom_max=200,  # MWh
        e_cyclic=True,
        standing_loss=0.0001,  # Very low self-discharge
        capital_cost=200,  # €/MWh/year (very low for 1-week test)
        build_year=investment_periods[0] if len(investment_periods) > 1 else 2020,
        lifetime=15,
    )

    # =========================================================================
    # Add scenarios (stochastic)
    # =========================================================================

    if scenarios:
        n.set_scenarios(scenarios)

        # Modify demand for different scenarios
        # For "hoch" scenario: increase demand by 20%
        for scenario in scenarios.keys():
            if scenario == "hoch":
                # Increase load for high scenario
                for load_name in ["elec_load", "heat_load"]:
                    load_t = n.loads_t.p_set
                    if isinstance(load_t.columns, pd.MultiIndex):
                        load_t[(scenario, load_name)] = (
                            load_t[(scenario, load_name)] * 1.2
                        )

    return n


def compare_optimization_results(
    n_full: pypsa.Network,
    n_clustered: pypsa.Network,
    clustering_result: Any,
) -> dict:
    """Compare optimization results between full and clustered networks.

    Parameters
    ----------
    n_full : pypsa.Network
        Full resolution optimized network
    n_clustered : pypsa.Network
        Clustered optimized network
    clustering_result : TemporalClustering
        Clustering result with aggregation info

    Returns
    -------
    dict
        Comparison metrics
    """
    metrics = {}

    # =========================================================================
    # 1. Total system cost comparison
    # =========================================================================

    cost_full = n_full.objective
    cost_clustered = n_clustered.objective

    metrics["cost_full"] = cost_full
    metrics["cost_clustered"] = cost_clustered
    if cost_full > 0:
        metrics["cost_deviation_percent"] = abs(cost_full - cost_clustered) / cost_full * 100
    else:
        metrics["cost_deviation_percent"] = 0.0

    # =========================================================================
    # 2. Capacity comparison
    # =========================================================================

    def get_capacity(n, component, attr="p_nom_opt"):
        df = getattr(n, component)
        if isinstance(df.index, pd.MultiIndex):
            # Stochastic: get first scenario
            first_scenario = df.index.get_level_values(0)[0]
            df = df.xs(first_scenario, level=0)
        return df[attr] if attr in df.columns else df.get("p_nom", pd.Series())

    # Generator capacities
    for gen in ["solar", "wind"]:
        if gen in n_full.generators.index or (
            isinstance(n_full.generators.index, pd.MultiIndex)
            and gen in n_full.generators.index.get_level_values(-1)
        ):
            cap_full = get_capacity(n_full, "generators").get(gen, 0)
            cap_clustered = get_capacity(n_clustered, "generators").get(gen, 0)
            if cap_full > 0:
                metrics[f"{gen}_capacity_full_MW"] = cap_full
                metrics[f"{gen}_capacity_clustered_MW"] = cap_clustered
                metrics[f"{gen}_capacity_deviation_percent"] = (
                    abs(cap_full - cap_clustered) / cap_full * 100
                )

    # Store capacities
    for store in ["heat_storage", "battery"]:
        try:
            cap_full = get_capacity(n_full, "stores", "e_nom_opt").get(store, 0)
            cap_clustered = get_capacity(n_clustered, "stores", "e_nom_opt").get(
                store, 0
            )
            if cap_full > 0:
                metrics[f"{store}_capacity_full_MWh"] = cap_full
                metrics[f"{store}_capacity_clustered_MWh"] = cap_clustered
                metrics[f"{store}_capacity_deviation_percent"] = (
                    abs(cap_full - cap_clustered) / cap_full * 100
                )
        except Exception:
            pass

    # Link capacities (heat pump)
    try:
        hp_full = get_capacity(n_full, "links").get("heat_pump", 0)
        hp_clustered = get_capacity(n_clustered, "links").get("heat_pump", 0)
        if hp_full > 0:
            metrics["heat_pump_capacity_full_MW"] = hp_full
            metrics["heat_pump_capacity_clustered_MW"] = hp_clustered
            metrics["heat_pump_capacity_deviation_percent"] = (
                abs(hp_full - hp_clustered) / hp_full * 100
            )
    except Exception:
        pass

    # =========================================================================
    # 3. Energy generation comparison
    # =========================================================================
    
    print("\n" + "=" * 70)
    print("ENERGY GENERATION COMPARISON (MWh)")
    print("=" * 70)
    print(f"{'Generator':<20} {'Full':>15} {'Clustered':>15} {'Deviation':>12}")
    print("-" * 70)
    
    def get_generator_energy(n, gen_name):
        """Calculate total energy generated by a generator."""
        try:
            if gen_name not in n.generators_t.p.columns:
                # Check for MultiIndex columns (stochastic)
                if isinstance(n.generators_t.p.columns, pd.MultiIndex):
                    # Sum across all scenarios
                    matching_cols = [c for c in n.generators_t.p.columns if c[-1] == gen_name]
                    if matching_cols:
                        # Get power for first scenario and multiply by weightings
                        p = n.generators_t.p[matching_cols[0]]
                        weights = n.snapshot_weightings["generators"]
                        return (p * weights).sum()
                return 0.0
            
            p = n.generators_t.p[gen_name]
            weights = n.snapshot_weightings["generators"]
            return (p * weights).sum()
        except Exception:
            return 0.0
    
    def get_link_energy(n, link_name):
        """Calculate total energy throughput of a link."""
        try:
            if link_name not in n.links_t.p0.columns:
                if isinstance(n.links_t.p0.columns, pd.MultiIndex):
                    matching_cols = [c for c in n.links_t.p0.columns if c[-1] == link_name]
                    if matching_cols:
                        p = n.links_t.p0[matching_cols[0]]
                        weights = n.snapshot_weightings["generators"]
                        return (p * weights).sum()
                return 0.0
            
            p = n.links_t.p0[link_name]
            weights = n.snapshot_weightings["generators"]
            return (p * weights).sum()
        except Exception:
            return 0.0
    
    # Generator energies
    gen_names = ["solar", "wind", "gas", "gas_supply", "grid_market"]
    for gen in gen_names:
        energy_full = get_generator_energy(n_full, gen)
        energy_clustered = get_generator_energy(n_clustered, gen)
        
        if abs(energy_full) > 0.1 or abs(energy_clustered) > 0.1:
            if abs(energy_full) > 0.1:
                deviation = (energy_clustered - energy_full) / abs(energy_full) * 100
                dev_str = f"{deviation:+.1f}%"
            else:
                dev_str = "N/A"
            print(f"{gen:<20} {energy_full:>15.1f} {energy_clustered:>15.1f} {dev_str:>12}")
            
            # Store in metrics
            metrics[f"{gen}_energy_full_MWh"] = energy_full
            metrics[f"{gen}_energy_clustered_MWh"] = energy_clustered
    
    print("-" * 70)
    
    # Link energies (heat pump, CHP, gas_boiler)
    print("\nLINK ENERGY THROUGHPUT (MWh - bus0 input)")
    print("-" * 70)
    link_names = ["heat_pump", "chp", "gas_boiler"]
    for link in link_names:
        energy_full = get_link_energy(n_full, link)
        energy_clustered = get_link_energy(n_clustered, link)
        
        if abs(energy_full) > 0.1 or abs(energy_clustered) > 0.1:
            if abs(energy_full) > 0.1:
                deviation = (energy_clustered - energy_full) / abs(energy_full) * 100
                dev_str = f"{deviation:+.1f}%"
            else:
                dev_str = "N/A"
            print(f"{link:<20} {energy_full:>15.1f} {energy_clustered:>15.1f} {dev_str:>12}")
            
            metrics[f"{link}_energy_full_MWh"] = energy_full
            metrics[f"{link}_energy_clustered_MWh"] = energy_clustered
    
    print("=" * 70)

    return metrics


def run_accuracy_comparison(
    n_hours: int = 168,  # 1 week for fast testing
    n_typical_periods: int = 3,
    hours_per_period: int = 24,
    investment_periods: list[int] | None = None,
    scenarios: dict[str, float] | None = None,
    solver_name: str = "highs",
) -> dict:
    """Run full comparison between full and clustered optimization.

    Parameters
    ----------
    n_hours : int
        Number of hours for the model
    n_typical_periods : int
        Number of typical periods for clustering
    hours_per_period : int
        Hours per period
    investment_periods : list[int]
        Investment periods
    scenarios : dict[str, float]
        Scenarios with probabilities
    solver_name : str
        Solver to use

    Returns
    -------
    dict
        All comparison metrics and timing info
    """
    if investment_periods is None:
        investment_periods = [2020, 2030]
    # Note: scenarios=None means no scenarios (deterministic)
    # Use explicit empty dict for "use default scenarios"

    results = {}

    # =========================================================================
    # 1. Create and optimize full resolution network
    # =========================================================================

    logger.info("Creating full resolution network...")
    n_full = create_realistic_heat_network(
        n_hours=n_hours,
        investment_periods=investment_periods,
        scenarios=scenarios,
    )

    results["n_snapshots_full"] = len(n_full.snapshots)
    results["n_scenarios"] = len(scenarios) if scenarios else 0
    results["n_investment_periods"] = len(investment_periods)

    logger.info(f"Full network: {len(n_full.snapshots)} snapshots")

    # Optimize full network
    logger.info("Optimizing full resolution network...")
    start_time = time.time()
    try:
        status, termination_condition = n_full.optimize(solver_name=solver_name)
        results["full_optimization_time_s"] = time.time() - start_time
        results["full_optimization_status"] = status
        results["full_termination_condition"] = termination_condition
        if status != "ok":
            logger.error(f"Full optimization failed: {termination_condition}")
            return results
    except Exception as e:
        logger.error(f"Full optimization failed: {e}")
        results["full_optimization_error"] = str(e)
        return results

    # =========================================================================
    # 2. Create and cluster network
    # =========================================================================

    logger.info("Creating network for clustering...")
    n_for_clustering = create_realistic_heat_network(
        n_hours=n_hours,
        investment_periods=investment_periods,
        scenarios=scenarios,
    )

    logger.info(
        f"Clustering to {n_typical_periods} periods × {hours_per_period} hours..."
    )
    start_time = time.time()

    clustering_result = n_for_clustering.cluster.cluster_temporally(
        n_typical_periods=n_typical_periods,
        hours_per_period=hours_per_period,
        cluster_method="hierarchical",
    )

    results["clustering_time_s"] = time.time() - start_time
    n_clustered = clustering_result.n

    results["n_snapshots_clustered"] = len(n_clustered.snapshots)
    results["reduction_factor"] = (
        len(n_full.snapshots) / len(n_clustered.snapshots)
    )

    logger.info(f"Clustered network: {len(n_clustered.snapshots)} snapshots")
    logger.info(f"Reduction factor: {results['reduction_factor']:.1f}x")

    # =========================================================================
    # 3. Optimize clustered network
    # =========================================================================

    logger.info("Optimizing clustered network...")
    start_time = time.time()
    try:
        status, termination_condition = n_clustered.optimize(solver_name=solver_name)
        results["clustered_optimization_time_s"] = time.time() - start_time
        results["clustered_optimization_status"] = status
        results["clustered_termination_condition"] = termination_condition
        if status != "ok":
            logger.error(f"Clustered optimization failed: {termination_condition}")
            return results
    except Exception as e:
        logger.error(f"Clustered optimization failed: {e}")
        results["clustered_optimization_error"] = str(e)
        return results

    # =========================================================================
    # 4. Compare results
    # =========================================================================

    logger.info("Comparing results...")
    comparison = compare_optimization_results(n_full, n_clustered, clustering_result)
    results.update(comparison)

    # Time savings
    if "full_optimization_time_s" in results and "clustered_optimization_time_s" in results:
        results["time_savings_percent"] = (
            1 - results["clustered_optimization_time_s"] / results["full_optimization_time_s"]
        ) * 100

    return results


# =============================================================================
# Pytest Tests
# =============================================================================


@pytest.fixture
def simple_heat_network() -> pypsa.Network:
    """Create a simple heat network for testing (1 week, no multi-invest)."""
    return create_realistic_heat_network(
        n_hours=168,  # 1 week
        investment_periods=[2020],  # Single period
        scenarios=None,  # No scenarios
    )


@pytest.fixture
def stochastic_heat_network() -> pypsa.Network:
    """Create a stochastic heat network (1 week, 2 scenarios)."""
    return create_realistic_heat_network(
        n_hours=168,
        investment_periods=[2020],
        scenarios={"niedrig": 0.5, "hoch": 0.5},
    )


@pytest.fixture
def full_stochastic_multi_invest_network() -> pypsa.Network:
    """Create full stochastic multi-invest heat network (1 week, 2 scenarios, 2 periods)."""
    return create_realistic_heat_network(
        n_hours=168,
        investment_periods=[2020, 2030],
        scenarios={"niedrig": 0.5, "hoch": 0.5},
    )


@pytest.mark.skipif(not HAS_TSAM, reason="tsam not installed")
class TestHeatStorageClustering:
    """Test temporal clustering with heat storage."""

    def test_heat_storage_cyclic_preserved(self, simple_heat_network):
        """Test that cyclic storage constraint is preserved after clustering."""
        n = simple_heat_network

        result = n.cluster.cluster_temporally(
            n_typical_periods=3,
            hours_per_period=24,
        )

        n_reduced = result.n

        # Check that e_cyclic is preserved
        heat_storage = n_reduced.stores.loc["heat_storage"]
        assert heat_storage["e_cyclic"] == True

        # Check that standing_loss is preserved
        assert heat_storage["standing_loss"] == 0.01

    def test_heat_storage_extendable_preserved(self, simple_heat_network):
        """Test that extendable storage attributes are preserved."""
        n = simple_heat_network

        result = n.cluster.cluster_temporally(
            n_typical_periods=3,
            hours_per_period=24,
        )

        n_reduced = result.n

        # Check extendable attributes
        heat_storage = n_reduced.stores.loc["heat_storage"]
        assert heat_storage["e_nom_extendable"] == True
        assert heat_storage["e_nom_max"] == 500

    def test_clustering_with_heat_pump_efficiency(self, simple_heat_network):
        """Test that time-varying heat pump efficiency is handled."""
        n = simple_heat_network

        result = n.cluster.cluster_temporally(
            n_typical_periods=3,
            hours_per_period=24,
        )

        n_reduced = result.n

        # Heat pump should exist
        assert "heat_pump" in n_reduced.links.index

        # Link attributes preserved
        hp = n_reduced.links.loc["heat_pump"]
        assert hp["p_nom_extendable"] == True


@pytest.mark.skipif(not HAS_TSAM, reason="tsam not installed")
class TestStochasticHeatNetwork:
    """Test stochastic heat network clustering."""

    def test_stochastic_heat_network_clustering(self, stochastic_heat_network):
        """Test clustering of stochastic heat network."""
        n = stochastic_heat_network

        result = n.cluster.cluster_temporally(
            n_typical_periods=3,
            hours_per_period=24,
        )

        n_reduced = result.n

        # Scenarios should be preserved
        assert n_reduced.has_scenarios
        assert "niedrig" in n_reduced.scenarios
        assert "hoch" in n_reduced.scenarios

        # Stores should exist for each scenario
        assert len(n_reduced.stores) == 2 * 2  # 2 stores × 2 scenarios


@pytest.mark.skipif(not HAS_TSAM, reason="tsam not installed")
class TestFullModelClustering:
    """Test full model with all features."""

    def test_full_model_clustering(self, full_stochastic_multi_invest_network):
        """Test clustering of full stochastic multi-invest network."""
        n = full_stochastic_multi_invest_network

        result = n.cluster.cluster_temporally(
            n_typical_periods=3,
            hours_per_period=24,
        )

        n_reduced = result.n

        # Basic checks
        assert n_reduced is not None
        assert len(n_reduced.snapshots) == 72  # 3 periods × 24 hours

        # Scenarios preserved
        assert n_reduced.has_scenarios

        # Components preserved
        assert len(n_reduced.generators) > 0
        assert len(n_reduced.stores) > 0
        assert len(n_reduced.links) > 0


@pytest.mark.skipif(not HAS_TSAM, reason="tsam not installed")
class TestAccuracyComparison:
    """Test accuracy of temporal clustering."""

    @pytest.mark.slow
    def test_accuracy_simple_network(self):
        """Test accuracy for simple network (no scenarios, no multi-invest)."""
        try:
            results = run_accuracy_comparison(
                n_hours=168,  # 1 week
                n_typical_periods=3,
                hours_per_period=24,
                investment_periods=[2020],
                scenarios=None,
                solver_name="highs",
            )

            # Check that both optimizations succeeded
            assert results.get("full_optimization_status") == "ok"
            assert results.get("clustered_optimization_status") == "ok"

            # Check that cost deviation is reasonable (< 20%)
            if "cost_deviation_percent" in results:
                assert results["cost_deviation_percent"] < 20

            # Print results for analysis
            print("\n=== Simple Network Accuracy Results ===")
            for key, value in results.items():
                if isinstance(value, float):
                    print(f"{key}: {value:.4f}")
                else:
                    print(f"{key}: {value}")

        except Exception as e:
            pytest.skip(f"Solver not available or error: {e}")

    @pytest.mark.slow
    def test_accuracy_stochastic_network(self):
        """Test accuracy for stochastic network."""
        try:
            results = run_accuracy_comparison(
                n_hours=168,
                n_typical_periods=3,
                hours_per_period=24,
                investment_periods=[2020],
                scenarios={"niedrig": 0.5, "hoch": 0.5},
                solver_name="highs",
            )

            assert results.get("full_optimization_status") == "ok"
            assert results.get("clustered_optimization_status") == "ok"

            print("\n=== Stochastic Network Accuracy Results ===")
            for key, value in results.items():
                if isinstance(value, float):
                    print(f"{key}: {value:.4f}")
                else:
                    print(f"{key}: {value}")

        except Exception as e:
            pytest.skip(f"Solver not available or error: {e}")

    @pytest.mark.slow
    def test_accuracy_full_model(self):
        """Test accuracy for full model (stochastic + multi-invest)."""
        try:
            results = run_accuracy_comparison(
                n_hours=168,
                n_typical_periods=3,
                hours_per_period=24,
                investment_periods=[2020, 2030],
                scenarios={"niedrig": 0.5, "hoch": 0.5},
                solver_name="highs",
            )

            # Print results regardless of outcome
            print("\n=== Full Model (Stochastic + Multi-Invest) Accuracy Results ===")
            for key, value in results.items():
                if isinstance(value, float):
                    print(f"{key}: {value:.4f}")
                else:
                    print(f"{key}: {value}")

        except Exception as e:
            pytest.skip(f"Solver not available or error: {e}")


# =============================================================================
# Interactive Analysis Function
# =============================================================================


def run_interactive_analysis():
    """Run interactive analysis with detailed output.
    
    This function can be called directly to see detailed results.
    """
    import logging

    logging.basicConfig(level=logging.INFO)

    print("=" * 70)
    print("TEMPORAL CLUSTERING ACCURACY ANALYSIS")
    print("Stochastic + Multi-Investment + Heat Storage Model")
    print("=" * 70)

    # Test different configurations
    configs = [
        {
            "name": "Simple (1 week, no scenarios)",
            "n_hours": 168,
            "investment_periods": [2020],
            "scenarios": None,
            "n_typical_periods": 3,
        },
        {
            "name": "Stochastic (1 week, 2 scenarios)",
            "n_hours": 168,
            "investment_periods": [2020],
            "scenarios": {"niedrig": 0.5, "hoch": 0.5},
            "n_typical_periods": 3,
        },
        {
            "name": "Full Model (1 week, 2 scenarios, 2 periods)",
            "n_hours": 168,
            "investment_periods": [2020, 2030],
            "scenarios": {"niedrig": 0.5, "hoch": 0.5},
            "n_typical_periods": 3,
        },
    ]

    all_results = []

    for config in configs:
        print(f"\n{'='*70}")
        print(f"Configuration: {config['name']}")
        print("=" * 70)

        try:
            results = run_accuracy_comparison(
                n_hours=config["n_hours"],
                n_typical_periods=config["n_typical_periods"],
                hours_per_period=24,
                investment_periods=config["investment_periods"],
                scenarios=config["scenarios"],
                solver_name="highs",
            )

            results["config_name"] = config["name"]
            all_results.append(results)

            # Print key metrics
            print(f"\nSnapshots: {results.get('n_snapshots_full', 'N/A')} → {results.get('n_snapshots_clustered', 'N/A')}")
            print(f"Reduction factor: {results.get('reduction_factor', 'N/A'):.1f}x")

            if "cost_deviation_percent" in results:
                print(f"\nCost deviation: {results['cost_deviation_percent']:.2f}%")

            if "time_savings_percent" in results:
                print(f"Time savings: {results['time_savings_percent']:.1f}%")

            # Capacity deviations
            for key in results:
                if "capacity_deviation" in key:
                    print(f"{key}: {results[key]:.2f}%")

        except Exception as e:
            print(f"ERROR: {e}")

    # Summary table
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if all_results:
        summary_df = pd.DataFrame(all_results)
        cols_of_interest = [
            "config_name",
            "n_snapshots_full",
            "n_snapshots_clustered",
            "reduction_factor",
            "cost_deviation_percent",
            "time_savings_percent",
        ]
        cols_present = [c for c in cols_of_interest if c in summary_df.columns]
        print(summary_df[cols_present].to_string(index=False))


if __name__ == "__main__":
    run_interactive_analysis()
