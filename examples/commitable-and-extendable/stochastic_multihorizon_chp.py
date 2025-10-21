"""Stochastic Multi-Horizon CHP Investment Planning.

This example combines THREE advanced PyPSA v1.0 features:
1. **Stochastic optimization**: Multiple scenarios for uncertain parameters (gas prices, demand)
2. **Multi-investment periods**: Pathway planning across 2025, 2030, 2035, 2040
3. **Unit commitment**: Committable components with start-up/shut-down decisions

The network represents a district energy system transitioning towards lower emissions
over multiple decades while accounting for uncertainty in fuel prices and demand growth,
with detailed unit commitment modeling for CHP plants and gas turbines.

Scenarios:
- **Low cost**: Moderate gas prices (50 EUR/MWh), low demand growth
- **Medium cost**: Average gas prices (80 EUR/MWh), medium demand growth  
- **High cost**: High gas prices (120 EUR/MWh), high demand growth

Run this module directly to build, optimize, and export the scenario::

    python stochastic_multihorizon_chp.py

The export will be written to ``stochastic_multihorizon_chp.nc`` in the same directory.
"""

from __future__ import annotations

import pathlib
import sys

# Allow running the script without installing PyPSA by adding the repository root
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

import pypsa

# === Configuration ===
INVESTMENT_PERIODS = [2025, 2030, 2035, 2040]
SNAPSHOTS_PER_PERIOD = 168  # One week per period (hourly resolution)
DISCOUNT_RATE = 0.05

# Scenario definitions for stochastic optimization
SCENARIOS = ["low_cost", "medium_cost", "high_cost"]
SCENARIO_WEIGHTS = {"low_cost": 0.3, "medium_cost": 0.4, "high_cost": 0.3}

# Gas price scenarios (EUR/MWh_th)
GAS_PRICE_SCENARIOS = {
    "low_cost": {2025: 50, 2030: 48, 2035: 45, 2040: 42},
    "medium_cost": {2025: 80, 2030: 85, 2035: 88, 2040: 90},
    "high_cost": {2025: 120, 2030: 135, 2035: 145, 2040: 150},
}

# Demand growth scenarios (multiplier relative to base year 2025)
DEMAND_GROWTH_SCENARIOS = {
    "low_cost": {2025: 1.0, 2030: 1.05, 2035: 1.08, 2040: 1.10},
    "medium_cost": {2025: 1.0, 2030: 1.12, 2035: 1.22, 2040: 1.30},
    "high_cost": {2025: 1.0, 2030: 1.18, 2035: 1.35, 2040: 1.50},
}

# CHP technical parameters - CONSTANT P/Q RATIO formulation
CHP_ELECTRIC_EFF = 0.4  # 38% electrical efficiency
CHP_THERMAL_EFF = 0.5 # 48% thermal efficiency
CHP_TOTAL_EFF = CHP_ELECTRIC_EFF + CHP_THERMAL_EFF  # 86% total efficiency
CHP_QP_RATIO = CHP_THERMAL_EFF / CHP_ELECTRIC_EFF  # Q/P = 0.48/0.38 ≈ 1.263
CHP_PQ_RATIO = CHP_ELECTRIC_EFF / CHP_THERMAL_EFF  # P/Q = 0.38/0.48 ≈ 0.792

RESULT_FILE = pathlib.Path(__file__).with_suffix(".nc")
PLOT_FILE = RESULT_FILE.with_name(f"{RESULT_FILE.stem}_capacity_evolution.png")

CARRIER_COLORS: dict[str, str] = {
    "electric": "#1f77b4",
    "gas": "#ff7f0e",
    "heat": "#d62728",
    "wind": "#17becf",
    "solar": "#bcbd22",
    "market": "#9467bd",
}


def build_hourly_profiles(period_year: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Create hourly profiles for one week (168 hours)."""
    
    # Base daily patterns repeated for 7 days
    daily_electric_load = np.array([
        9.5, 9.1, 8.7, 8.3, 8.0, 8.2, 9.0, 10.5, 11.8, 12.5, 13.2, 13.5,
        13.0, 12.6, 12.0, 11.5, 11.0, 10.8, 10.5, 10.2, 9.8, 9.6, 9.4, 9.2,
    ])
    
    daily_heat_load = np.array([
        14.0, 13.5, 13.0, 12.5, 12.0, 12.5, 13.5, 15.0, 16.5, 17.5, 18.0, 18.5,
        18.0, 17.2, 16.8, 16.0, 15.5, 15.0, 14.5, 14.0, 13.8, 13.5, 13.2, 13.0,
    ])
    
    # Wind availability increases over time (representing better sites/technology)
    wind_improvement = 1.0 + (period_year - 2025) * 0.015
    daily_wind = np.array([
        0.05, 0.08, 0.10, 0.12, 0.18, 0.25, 0.35, 0.45, 0.60, 0.72, 0.80, 0.78,
        0.70, 0.62, 0.55, 0.48, 0.40, 0.32, 0.24, 0.18, 0.12, 0.08, 0.05, 0.03,
    ]) * min(wind_improvement, 1.3)
    
    # Solar availability increases over time (better technology)
    solar_improvement = 1.0 + (period_year - 2025) * 0.02
    daily_solar = np.array([
        0.0, 0.0, 0.0, 0.0, 0.0, 0.02, 0.15, 0.35, 0.55, 0.72, 0.85, 0.92,
        0.95, 0.92, 0.82, 0.68, 0.48, 0.25, 0.08, 0.0, 0.0, 0.0, 0.0, 0.0,
    ]) * min(solar_improvement, 1.4)
    
    # Market price patterns (fewer negative prices, more realistic)
    daily_market_price = np.array([
        78, 74, 70, 68, 65, 64, 66, 72, 85, 92, 100, 105,
        110, 108, 102, 95, 88, 82, 75, 70, 65, 68, 72, 74,
    ])
    
    # Tile for 7 days
    electric_load = np.tile(daily_electric_load, 7)
    heat_load = np.tile(daily_heat_load, 7)
    wind_profile = np.tile(daily_wind, 7)
    solar_profile = np.tile(daily_solar, 7)
    market_price = np.tile(daily_market_price, 7)
    
    return electric_load, heat_load, wind_profile, solar_profile, market_price


def create_snapshots_multi_index(
    periods: list[int], snapshots_per_period: int
) -> pd.MultiIndex:
    """Create a MultiIndex for snapshots across investment periods."""
    
    snapshot_data = []
    for period in periods:
        period_start = pd.Timestamp(f"{period}-01-01")
        period_snapshots = pd.date_range(
            start=period_start, periods=snapshots_per_period, freq="h"
        )
        snapshot_data.extend([(period, snap) for snap in period_snapshots])
    
    return pd.MultiIndex.from_tuples(
        snapshot_data, names=["period", "timestep"]
    )


def calculate_investment_period_weightings(
    periods: list[int], discount_rate: float
) -> pd.DataFrame:
    """Calculate objective weightings for each investment period with discounting."""
    
    years_between = []
    for i in range(len(periods) - 1):
        years_between.append(periods[i + 1] - periods[i])
    years_between.append(5)  # Last period lasts 5 years
    
    weightings = pd.DataFrame(
        {"years": years_between},
        index=periods
    )
    
    # Calculate discounted objective weighting
    cumulative_years = 0
    for period, row in weightings.iterrows():
        nyears = row["years"]
        discount_factors = [
            1 / (1 + discount_rate) ** t 
            for t in range(cumulative_years, cumulative_years + nyears)
        ]
        weightings.at[period, "objective"] = sum(discount_factors)
        cumulative_years += nyears
    
    return weightings


def _ensure_carrier_colors(n: pypsa.Network) -> None:
    """Ensure carrier colors are set."""
    if "color" not in n.carriers.columns:
        n.carriers["color"] = np.nan
    for carrier, color in CARRIER_COLORS.items():
        if carrier in n.carriers.index:
            n.carriers.loc[carrier, "color"] = color


def build_base_network() -> pypsa.Network:
    """Build the base network structure (before stochastic scenarios)."""
    
    n = pypsa.Network()
    
    # Set up multi-period snapshots
    snapshots = create_snapshots_multi_index(
        INVESTMENT_PERIODS, SNAPSHOTS_PER_PERIOD
    )
    n.set_snapshots(snapshots)
    n.investment_periods = INVESTMENT_PERIODS
    n.investment_period_weightings = calculate_investment_period_weightings(
        INVESTMENT_PERIODS, DISCOUNT_RATE
    )
    
    # Add carriers
    for carrier in ["electric", "gas", "heat", "wind", "solar", "market"]:
        co2 = 0.20 if carrier == "gas" else 0.0
        n.add("Carrier", carrier, co2_emissions=co2)
    
    _ensure_carrier_colors(n)
    
    # Add buses
    n.add("Bus", "bus_electric", carrier="electric")
    n.add("Bus", "bus_gas", carrier="gas")
    n.add("Bus", "bus_heat", carrier="heat")
    
    # Build time series for each period (will be scenario-dependent later)
    electric_load_series = pd.Series(0.0, index=n.snapshots)
    heat_load_series = pd.Series(0.0, index=n.snapshots)
    wind_profile_series = pd.Series(0.0, index=n.snapshots)
    solar_profile_series = pd.Series(0.0, index=n.snapshots)
    market_price_series = pd.Series(0.0, index=n.snapshots)
    
    for period in INVESTMENT_PERIODS:
        electric, heat, wind, solar, market = build_hourly_profiles(period)
        
        period_snapshots = n.snapshots[n.snapshots.get_level_values(0) == period]
        electric_load_series.loc[period_snapshots] = electric
        heat_load_series.loc[period_snapshots] = heat
        wind_profile_series.loc[period_snapshots] = wind
        solar_profile_series.loc[period_snapshots] = solar
        market_price_series.loc[period_snapshots] = market
    
    # Add loads (will be scaled by scenario later)
    n.add("Load", "electric_demand", bus="bus_electric", p_set=electric_load_series)
    n.add("Load", "heat_demand", bus="bus_heat", p_set=heat_load_series)
    
    # === Renewable generators (extendable) ===
    
    # Wind - can be built in any period
    n.add(
        "Generator",
        "wind_turbine",
        bus="bus_electric",
        carrier="wind",
        p_nom_extendable=True,
        p_nom=0.0,  # Start with nothing
        capital_cost=1400,  # Increased from 850
        marginal_cost=1.0,  # Increased from 0.5
        p_max_pu=wind_profile_series,
        lifetime=25,
        build_year=2025,
    )
    
    # Solar - becomes available from 2030
    n.add(
        "Generator",
        "solar_pv",
        bus="bus_electric",
        carrier="solar",
        p_nom_extendable=True,
        p_nom=0.0,
        capital_cost=350,
        marginal_cost=0.3,
        p_max_pu=solar_profile_series,
        lifetime=25,
        build_year=2025,
    )
    
    # === Gas supply ===
    
    # Gas import (marginal cost will be scenario-dependent)
    n.add(
        "Generator",
        "gas_supply",
        bus="bus_gas",
        carrier="gas",
        p_nom_extendable=True,
        capital_cost=0.1,
        marginal_cost=80.0,  # Base price, will be overridden by scenarios
        p_nom_max=500,
        lifetime=50,
        build_year=2025,
    )
    
    # === Power-to-gas ===
    
    n.add(
        "Link",
        "p2g",
        bus0="bus_electric",
        bus1="bus_gas",
        efficiency=0.60,
        capital_cost=550,
        p_nom_extendable=True,
        lifetime=20,
        build_year=2030,  # Available from 2030
    )
    
    # === Wholesale market connection ===
    
    n.add(
        "Generator",
        "grid_trade",
        bus="bus_electric",
        carrier="market",
        p_nom_extendable=True,
        p_nom_min=0.0,
        p_nom_max=10.0,  # Reduced from 500 - limited grid connection
        p_min_pu=-1.0,  # Can import or export
        p_max_pu=1.0,
        capital_cost=200.0,  # Added cost for grid connection
        marginal_cost=market_price_series,  # Time-varying prices
        lifetime=50,
        build_year=2025,
    )
    
    # === Storage ===
    
    n.add(
        "Store",
        "gas_storage",
        bus="bus_gas",
        e_nom_extendable=True,
        e_initial=40,
        capital_cost=25,
        standing_loss=0.001,
        lifetime=30,
        build_year=2025,
    )
    
    n.add(
        "Store",
        "thermal_buffer",
        bus="bus_heat",
        carrier="heat",
        e_nom_extendable=True,
        e_initial=15,
        capital_cost=18,
        standing_loss=0.012,
        lifetime=25,
        build_year=2025,
    )
    
    # === CHP plant (extendable + committable) - CONSTANT P/Q RATIO formulation ===
    # Now fully supported: committable + extendable + multi-investment + stochastic!
    
    # CHP electric output link
    n.add(
        "Link",
        "chp_generator",
        bus0="bus_gas",
        bus1="bus_electric",
        efficiency=CHP_TOTAL_EFF,  # Electric efficiency (normalized)
        committable=True,  # Now enabled with the bug fix!
        capital_cost=0,
        p_nom_extendable=True,
        p_min_pu=0.35,  # Minimum part load
        marginal_cost=10,
        lifetime=25,
        build_year=2025,
    )
    
    # CHP heat output link
    n.add(
        "Link",
        "chp_boiler",
        bus0="bus_gas",
        bus1="bus_heat",
        carrier="heat",
        efficiency=CHP_TOTAL_EFF,  # Thermal efficiency (normalized)
        committable=True,  # Now enabled with the bug fix!
        p_nom_extendable=True,
        p_min_pu=0.35,
        lifetime=25,
        build_year=2025,
    )
    
    # === Auxiliary heating ===
    
    # Heat-only boiler (non-committable, available from 2025)
    n.add(
        "Link",
        "aux_heat_boiler",
        bus0="bus_gas",
        bus1="bus_heat",
        carrier="heat",
        efficiency=0.8,
        capital_cost=160,
        p_nom_extendable=True,
        marginal_cost=15,
        lifetime=20,
        build_year=2025,
    )
    
    # Peak gas turbine (now with committable enabled!)
    n.add(
        "Link",
        "gas_peaker",
        bus0="bus_gas",
        bus1="bus_electric",
        carrier="electricity",
        efficiency=0.35,
        committable=True,
        capital_cost=200,
        p_nom_extendable=True,
        marginal_cost=3,
        lifetime=30,
        build_year=2025,
    )
    
    
    # === CO2 emission constraint (tightening over time) ===
    # Note: GlobalConstraints with stochastic scenarios can cause dimension conflicts
    # in PyPSA. For this example, we demonstrate the optimization without CO2 limits.
    # In a production setting, you could implement CO2 limits via custom constraints
    # or by limiting the capacity of high-emission generators.
    
    # Progressive emission limits per period (commented out due to PyPSA limitation)
    # co2_limits = {
    #     2025: 800_000,   # MWh_th * 0.20 tCO2/MWh_th over period
    #     2030: 600_000,
    #     2035: 350_000,
    #     2040: 150_000,
    # }
    # 
    # for period, limit in co2_limits.items():
    #     n.add(
    #         "GlobalConstraint",
    #         f"co2_limit_{period}",
    #         type="primary_energy",
    #         sense="<=",
    #         constant=limit,
    #         carrier_attribute="co2_emissions",
    #         investment_period=period,
    #     )
    
    return n


def apply_scenario_parameters(
    n: pypsa.Network, scenario: str
) -> pypsa.Network:
    """Apply scenario-specific parameters to the network."""
    
    # Create a copy to avoid modifying the base network
    n_scenario = n.copy()
    
    gas_prices = GAS_PRICE_SCENARIOS[scenario]
    demand_growth = DEMAND_GROWTH_SCENARIOS[scenario]
    
    # Apply gas prices per period
    for period in INVESTMENT_PERIODS:
        period_mask = n_scenario.snapshots.get_level_values(0) == period
        period_snapshots = n_scenario.snapshots[period_mask]
        
        # Update gas supply marginal cost
        # Note: In multi-investment with scenarios, we need to handle this carefully
        # We'll use a weighted average approach here for simplicity
        gas_price = gas_prices[period]
        
        # Scale demand by growth factor
        growth = demand_growth[period]
        base_electric = n.loads_t.p_set.loc[period_snapshots, "electric_demand"]
        base_heat = n.loads_t.p_set.loc[period_snapshots, "heat_demand"]
        
        n_scenario.loads_t.p_set.loc[period_snapshots, "electric_demand"] = (
            base_electric * growth
        )
        n_scenario.loads_t.p_set.loc[period_snapshots, "heat_demand"] = (
            base_heat * growth
        )
    
    # For gas prices, we create a weighted average across periods
    # In a more sophisticated implementation, you could make marginal_cost time-varying
    avg_gas_price = np.mean(list(gas_prices.values()))
    n_scenario.generators.at["gas_supply", "marginal_cost"] = avg_gas_price
    
    return n_scenario


def create_stochastic_network() -> pypsa.Network:
    """Create a network with stochastic scenarios."""
    
    # Build base network
    n_base = build_base_network()
    
    # Store base demand profiles and market prices before enabling scenarios
    base_electric_demand = n_base.loads_t.p_set["electric_demand"].copy()
    base_heat_demand = n_base.loads_t.p_set["heat_demand"].copy()
    base_market_price = n_base.generators_t.marginal_cost["grid_trade"].copy()
    
    # Enable stochastic optimization - this changes the structure to MultiIndex
    n_base.set_scenarios(SCENARIO_WEIGHTS)
    
    # After set_scenarios(), we need to populate time-varying marginal costs for gas
    # Create scenario-specific gas marginal costs
    gas_marginal_cost_series = pd.DataFrame(
        index=n_base.snapshots,
        columns=pd.MultiIndex.from_product([SCENARIOS, ["gas_supply"]])
    )
    
    # Apply scenario-specific parameters
    for scenario in SCENARIOS:
        gas_prices = GAS_PRICE_SCENARIOS[scenario]
        demand_growth = DEMAND_GROWTH_SCENARIOS[scenario]
        
        # Update demand for each period in this scenario
        for period in INVESTMENT_PERIODS:
            period_mask = n_base.snapshots.get_level_values(0) == period
            period_snapshots = n_base.snapshots[period_mask]
            
            growth = demand_growth[period]
            gas_price = gas_prices[period]
            
            # Get base values and scale by growth
            base_electric_period = base_electric_demand.loc[period_snapshots]
            base_heat_period = base_heat_demand.loc[period_snapshots]
            
            # Set scenario-specific demand
            # After set_scenarios(), loads_t.p_set has MultiIndex columns: (scenario, load_name)
            n_base.loads_t.p_set.loc[period_snapshots, (scenario, "electric_demand")] = (
                base_electric_period.values * growth
            )
            n_base.loads_t.p_set.loc[period_snapshots, (scenario, "heat_demand")] = (
                base_heat_period.values * growth
            )
            
            # Set scenario and period-specific gas price
            gas_marginal_cost_series.loc[period_snapshots, (scenario, "gas_supply")] = gas_price
        
        # Keep market prices (same across scenarios for simplicity)
        n_base.generators_t.marginal_cost.loc[:, (scenario, "grid_trade")] = (
            base_market_price.values
        )
    
    # Add gas supply marginal costs as time-varying
    for scenario in SCENARIOS:
        n_base.generators_t.marginal_cost[(scenario, "gas_supply")] = (
            gas_marginal_cost_series[(scenario, "gas_supply")]
        )
    
    return n_base


def add_chp_coupling_constraints(n: pypsa.Network) -> None:
    """Add CHP coupling constraints to the optimization model - CONSTANT P/Q RATIO formulation."""
    
    model = n.optimize.create_model()
    
    link_p = model.variables["Link-p"]
    link_p_nom = model.variables["Link-p_nom"]
    link_status = model.variables["Link-status"]  # Now available with committable=True!
    
    # After set_scenarios(), link names become MultiIndex (scenario, name)
    # We need to get efficiency from any scenario (they're all the same)
    if isinstance(n.links.index, pd.MultiIndex):
        # Get first scenario's efficiency values
        first_scenario = n.links.index.get_level_values(0)[0]
        generator_eff = float(n.links.loc[(first_scenario, "chp_generator"), "efficiency"])
        boiler_eff = float(n.links.loc[(first_scenario, "chp_boiler"), "efficiency"])
    else:
        generator_eff = float(n.links.at["chp_generator", "efficiency"])
        boiler_eff = float(n.links.at["chp_boiler", "efficiency"])
    
    generator_p = link_p.sel(name="chp_generator")
    boiler_p = link_p.sel(name="chp_boiler")
    generator_p_nom = link_p_nom.sel(name="chp_generator")
    boiler_p_nom = link_p_nom.sel(name="chp_boiler")
    
    electric_output = generator_eff * generator_p
    heat_output = boiler_eff * boiler_p

    # CONSTRAINT 1: Nominal capacity ratio (Q_nom = CHP_QP_RATIO * P_nom)
    # This ensures heat capacity is proportional to electric capacity
    # Using multiplicative form to avoid division by zero
    model.add_constraints(
        boiler_p_nom - CHP_QP_RATIO * generator_p_nom == 0,
        name="chp-nominal-capacity-ratio",
    )

    # CONSTRAINT 2: Fixed power ratio at all times (Q(t) = CHP_QP_RATIO * P(t))
    # This enforces constant heat-to-power ratio during operation
    # Using multiplicative form to avoid division by zero
    model.add_constraints(
        heat_output - CHP_QP_RATIO * electric_output == 0,
        name="chp-fixed-power-ratio",
    )
    
    # CONSTRAINT 3: Commitment synchronization (both sides must have same status)
    # This ensures generator and boiler turn on/off together
    generator_status = link_status.sel(name="chp_generator")
    boiler_status = link_status.sel(name="chp_boiler")
    
    model.add_constraints(
        generator_status - boiler_status == 0,
        name="chp-synchronized-commitment",
    )
    
    # Solve the model
    n.optimize.solve_model(
        solver_options={
            "mip_rel_gap": 0.1,  # 10% gap for faster solving
            "threads": 16,
            "parallel": "on",
            "time_limit": 1800,  # 30 minutes time limit
        }
    )


def optimize_deterministic_scenario(scenario: str) -> pypsa.Network:
    """Optimize for a single scenario (perfect foresight, no stochasticity)."""
    
    print(f"\n--- Optimizing deterministic scenario: {scenario.upper()} ---")
    
    # Build base network WITHOUT scenarios
    n = build_base_network()
    
    # Apply this scenario's parameters
    gas_prices = GAS_PRICE_SCENARIOS[scenario]
    demand_growth = DEMAND_GROWTH_SCENARIOS[scenario]
    
    # Update demand and gas prices for each period
    for period in INVESTMENT_PERIODS:
        period_mask = n.snapshots.get_level_values(0) == period
        period_snapshots = n.snapshots[period_mask]
        
        growth = demand_growth[period]
        gas_price = gas_prices[period]
        
        # Scale demand
        n.loads_t.p_set.loc[period_snapshots, "electric_demand"] *= growth
        n.loads_t.p_set.loc[period_snapshots, "heat_demand"] *= growth
        
        # Set gas price (create time-varying marginal cost)
        if "gas_supply" not in n.generators_t.marginal_cost.columns:
            n.generators_t.marginal_cost["gas_supply"] = 0.0
        n.generators_t.marginal_cost.loc[period_snapshots, "gas_supply"] = gas_price
    
    # Optimize
    add_chp_coupling_constraints(n)
    
    print(f"  Objective: {n.objective:.2f} EUR")
    
    return n


def build_and_optimize_with_comparison() -> tuple[pypsa.Network, dict[str, pypsa.Network]]:
    """Build and optimize both stochastic and deterministic scenarios for comparison."""
    
    print("=" * 70)
    print("PART 1: DETERMINISTIC OPTIMIZATION (Perfect Foresight per Scenario)")
    print("=" * 70)
    
    deterministic_networks = {}
    for scenario in SCENARIOS:
        n_det = optimize_deterministic_scenario(scenario)
        deterministic_networks[scenario] = n_det
    
    print("\n" + "=" * 70)
    print("PART 2: STOCHASTIC OPTIMIZATION (Robust Solution)")
    print("=" * 70)
    
    print("\nBuilding stochastic multi-horizon network...")
    n_stoch = create_stochastic_network()
    
    print(f"Network has {len(n_stoch.investment_periods)} investment periods")
    print(f"Network has {len(SCENARIOS)} scenarios: {SCENARIOS}")
    print(f"Total snapshots: {len(n_stoch.snapshots)}")
    
    print("\nAdding CHP coupling constraints and optimizing...")
    add_chp_coupling_constraints(n_stoch)
    
    print("\nStochastic optimization complete!")
    print(f"Expected objective value: {n_stoch.objective:.2f} EUR")
    
    return n_stoch, deterministic_networks


def build_and_optimize() -> pypsa.Network:
    """Build and optimize the stochastic multi-horizon network."""
    
    print("Building stochastic multi-horizon network...")
    n = create_stochastic_network()
    
    print(f"Network has {len(n.investment_periods)} investment periods")
    print(f"Network has {len(SCENARIOS)} scenarios: {SCENARIOS}")
    print(f"Total snapshots: {len(n.snapshots)}")
    
    print("\nAdding CHP coupling constraints and optimizing...")
    add_chp_coupling_constraints(n)
    
    print("\nOptimization complete!")
    print(f"Objective value: {n.objective:.2f} EUR")
    
    return n


def save_interactive_dispatch_plots(
    n: pypsa.Network,
    output_path: pathlib.Path | None = None
) -> pathlib.Path:
    """Create interactive Plotly plots showing dispatch differences across scenarios and periods.
    
    This creates an HTML file with interactive plots showing:
    - Generator dispatch per scenario and investment period
    - Link dispatch (CHP, P2G) per scenario and period
    - Storage state of charge evolution
    - Commitment status for committable units
    """
    
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        print("\nWarning: plotly not installed. Install with: pip install plotly")
        print("Skipping interactive dispatch plots.")
        return None
    
    if output_path is None:
        output_path = PLOT_FILE.with_name(f"{PLOT_FILE.stem}_dispatch_interactive.html")
    
    # Check if we have scenarios
    has_scenarios = isinstance(n.generators.index, pd.MultiIndex)
    
    if not has_scenarios:
        print("\nNote: Network has no scenarios. Interactive dispatch plot requires scenarios.")
        return None
    
    scenarios = n.generators.index.get_level_values(0).unique()
    n_scenarios = len(scenarios)
    n_periods = len(INVESTMENT_PERIODS)
    
    # Create figure with subplots: one row per scenario, one column per period
    fig = make_subplots(
        rows=n_scenarios,
        cols=n_periods,
        subplot_titles=[
            f"{scenario.upper()}<br>Period {period}"
            for scenario in scenarios
            for period in INVESTMENT_PERIODS
        ],
        vertical_spacing=0.08,
        horizontal_spacing=0.05,
        specs=[[{"secondary_y": True} for _ in range(n_periods)] for _ in range(n_scenarios)],
    )
    
    # Color mapping for components
    colors = {
        'wind': '#17becf',
        'solar': '#bcbd22',
        'gas_supply': '#ff7f0e',
        'grid_trade': '#9467bd',
        'gas_peaker': '#e377c2',
        'chp_generator': '#d62728',
        'chp_boiler': '#ff9896',
        'p2g': '#98df8a',
        'aux_heat_boiler': '#ffbb78',
    }
    
    # Process each scenario and period
    for scenario_idx, scenario in enumerate(scenarios):
        for period_idx, period in enumerate(INVESTMENT_PERIODS):
            row = scenario_idx + 1
            col = period_idx + 1
            
            # Get snapshots for this period
            period_mask = n.snapshots.get_level_values(0) == period
            period_snapshots = n.snapshots[period_mask]
            
            # Time axis (just hours 0-167 for one week)
            hours = np.arange(len(period_snapshots))
            
            # === GENERATORS ===
            gen_names = n.generators.xs(scenario, level=0).index
            for gen_name in gen_names:
                gen = (scenario, gen_name)
                
                # Skip if not extendable or zero capacity
                if not n.generators.at[gen, "p_nom_extendable"]:
                    continue
                if n.generators.at[gen, "p_nom_opt"] < 0.01:
                    continue
                
                # Get dispatch data
                if gen in n.generators_t.p.columns:
                    dispatch = n.generators_t.p[gen].loc[period_snapshots].values
                else:
                    continue
                
                color = colors.get(gen_name, '#808080')
                
                fig.add_trace(
                    go.Scatter(
                        x=hours,
                        y=dispatch,
                        name=gen_name,
                        mode='lines',
                        line=dict(color=color, width=1.5),
                        stackgroup='generation',
                        legendgroup=gen_name,
                        showlegend=(scenario_idx == 0 and period_idx == 0),
                        hovertemplate=f'{gen_name}<br>%{{y:.2f}} MW<extra></extra>',
                    ),
                    row=row,
                    col=col,
                    secondary_y=False,
                )
            
            # === LINKS (CHP, P2G, Boilers) ===
            link_names = n.links.xs(scenario, level=0).index
            for link_name in link_names:
                link = (scenario, link_name)
                
                if not n.links.at[link, "p_nom_extendable"]:
                    continue
                if n.links.at[link, "p_nom_opt"] < 0.01:
                    continue
                
                # Get dispatch data
                if link in n.links_t.p0.columns:
                    dispatch = n.links_t.p0[link].loc[period_snapshots].values
                else:
                    continue
                
                color = colors.get(link_name, '#FF6B6B')
                
                # Links can be negative (P2G uses electricity)
                # Show them differently based on direction
                if 'p2g' in link_name:
                    # P2G consumes electricity - show as negative
                    dispatch = -dispatch
                
                fig.add_trace(
                    go.Scatter(
                        x=hours,
                        y=dispatch,
                        name=link_name,
                        mode='lines',
                        line=dict(color=color, width=1.5, dash='dot'),
                        stackgroup='generation',
                        legendgroup=link_name,
                        showlegend=(scenario_idx == 0 and period_idx == 0),
                        hovertemplate=f'{link_name}<br>%{{y:.2f}} MW<extra></extra>',
                    ),
                    row=row,
                    col=col,
                    secondary_y=False,
                )
            
            # === LOAD (as negative for comparison) ===
            load_names = n.loads.xs(scenario, level=0).index
            for load_name in ['electric_demand']:  # Focus on electric load
                if load_name not in load_names:
                    continue
                
                load = (scenario, load_name)
                
                if load in n.loads_t.p.columns:
                    demand = -n.loads_t.p[load].loc[period_snapshots].values
                else:
                    continue
                
                fig.add_trace(
                    go.Scatter(
                        x=hours,
                        y=demand,
                        name='Electric Demand',
                        mode='lines',
                        line=dict(color='black', width=2),
                        legendgroup='demand',
                        showlegend=(scenario_idx == 0 and period_idx == 0),
                        hovertemplate='Demand<br>%{y:.2f} MW<extra></extra>',
                    ),
                    row=row,
                    col=col,
                    secondary_y=False,
                )
            
            # === STORAGE STATE OF CHARGE (on secondary y-axis) ===
            store_names = n.stores.xs(scenario, level=0).index
            for store_name in store_names:
                store = (scenario, store_name)
                
                if not n.stores.at[store, "e_nom_extendable"]:
                    continue
                if n.stores.at[store, "e_nom_opt"] < 0.01:
                    continue
                
                # Get SOC data
                if store in n.stores_t.e.columns:
                    soc = n.stores_t.e[store].loc[period_snapshots].values
                else:
                    continue
                
                color = '#2ca02c' if 'gas' in store_name else '#ff7f0e'
                
                fig.add_trace(
                    go.Scatter(
                        x=hours,
                        y=soc,
                        name=f'{store_name} (SOC)',
                        mode='lines',
                        line=dict(color=color, width=1.5, dash='dash'),
                        legendgroup=store_name,
                        showlegend=(scenario_idx == 0 and period_idx == 0),
                        hovertemplate=f'{store_name} SOC<br>%{{y:.2f}} MWh<extra></extra>',
                    ),
                    row=row,
                    col=col,
                    secondary_y=True,
                )
    
    # Update layout
    fig.update_layout(
        title_text="Stochastic Dispatch: Operational Differences Across Scenarios & Investment Periods",
        title_font_size=18,
        height=350 * n_scenarios,
        showlegend=True,
        hovermode='x unified',
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1.0,
            xanchor="left",
            x=1.02,
        ),
    )
    
    # Update axes
    for i in range(1, n_scenarios + 1):
        for j in range(1, n_periods + 1):
            # Primary y-axis (Power)
            fig.update_yaxes(
                title_text="Power [MW]" if j == 1 else "",
                row=i,
                col=j,
                secondary_y=False,
            )
            
            # Secondary y-axis (Energy/SOC)
            fig.update_yaxes(
                title_text="SOC [MWh]" if j == n_periods else "",
                row=i,
                col=j,
                secondary_y=True,
            )
            
            # X-axis
            fig.update_xaxes(
                title_text="Hour" if i == n_scenarios else "",
                row=i,
                col=j,
            )
    
    # Save to HTML
    fig.write_html(str(output_path))
    
    print(f"\n{'='*70}")
    print("INTERACTIVE DISPATCH PLOTS SAVED")
    print(f"{'='*70}")
    print(f"File: {output_path}")
    print("\nThe interactive HTML plot shows:")
    print("  - Generator dispatch (stacked area) per scenario & period")
    print("  - Electric demand (black line)")
    print("  - Storage state of charge (dashed lines, right y-axis)")
    print("  - Hover to see exact values")
    print("  - Click legend to show/hide components")
    print(f"{'='*70}\n")
    
    return output_path


def save_interactive_commitment_plots(
    n: pypsa.Network,
    output_path: pathlib.Path | None = None
) -> pathlib.Path | None:
    """Create interactive Plotly plots showing unit commitment status across scenarios.
    
    This creates a heatmap showing when committable units (CHP, gas peaker) are
    ON or OFF in each scenario and period.
    """
    
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        print("\nWarning: plotly not installed. Skipping commitment plots.")
        return None
    
    if output_path is None:
        output_path = PLOT_FILE.with_name(f"{PLOT_FILE.stem}_commitment_status.html")
    
    # Check if we have scenarios
    has_scenarios = isinstance(n.generators.index, pd.MultiIndex)
    
    if not has_scenarios:
        print("\nNote: Network has no scenarios. Commitment plot requires scenarios.")
        return None
    
    scenarios = n.generators.index.get_level_values(0).unique()
    n_scenarios = len(scenarios)
    n_periods = len(INVESTMENT_PERIODS)
    
    # Find committable components
    committable_gens = []
    committable_links = []
    
    # Check generators
    for scenario in [scenarios[0]]:  # Just check first scenario
        gen_names = n.generators.xs(scenario, level=0).index
        for gen_name in gen_names:
            gen = (scenario, gen_name)
            if n.generators.at[gen, "committable"]:
                if n.generators.at[gen, "p_nom_opt"] > 0.01:
                    committable_gens.append(gen_name)
    
    # Check links
    for scenario in [scenarios[0]]:
        link_names = n.links.xs(scenario, level=0).index
        for link_name in link_names:
            link = (scenario, link_name)
            if n.links.at[link, "committable"]:
                if n.links.at[link, "p_nom_opt"] > 0.01:
                    committable_links.append(link_name)
    
    if not committable_gens and not committable_links:
        print("\nNote: No committable units found with non-zero capacity.")
        return None
    
    all_committable = committable_gens + committable_links
    n_units = len(all_committable)
    
    # Create subplots: one row per unit, columns for scenarios×periods
    fig = make_subplots(
        rows=n_units,
        cols=n_scenarios * n_periods,
        subplot_titles=[
            f"{scenario.upper()} - {period}"
            for scenario in scenarios
            for period in INVESTMENT_PERIODS
        ],
        vertical_spacing=0.03,
        horizontal_spacing=0.01,
        row_titles=all_committable,
    )
    
    # Process each unit
    for unit_idx, unit_name in enumerate(all_committable):
        row = unit_idx + 1
        
        for scenario_idx, scenario in enumerate(scenarios):
            for period_idx, period in enumerate(INVESTMENT_PERIODS):
                col = scenario_idx * n_periods + period_idx + 1
                
                # Get snapshots for this period
                period_mask = n.snapshots.get_level_values(0) == period
                period_snapshots = n.snapshots[period_mask]
                hours = np.arange(len(period_snapshots))
                
                # Get status data
                status = None
                
                if unit_name in committable_gens:
                    gen = (scenario, unit_name)
                    if gen in n.generators_t.status.columns:
                        status = n.generators_t.status[gen].loc[period_snapshots].values
                
                elif unit_name in committable_links:
                    link = (scenario, unit_name)
                    if link in n.links_t.status.columns:
                        status = n.links_t.status[link].loc[period_snapshots].values
                
                if status is None:
                    continue
                
                # Create heatmap
                fig.add_trace(
                    go.Heatmap(
                        z=status.reshape(1, -1),
                        x=hours,
                        y=[unit_name],
                        colorscale=[[0, 'lightgray'], [1, 'darkgreen']],
                        showscale=(unit_idx == 0 and col == 1),
                        hovertemplate=f'{unit_name}<br>Hour: %{{x}}<br>Status: %{{z}}<extra></extra>',
                        colorbar=dict(
                            title="Status",
                            tickvals=[0, 1],
                            ticktext=["OFF", "ON"],
                        ) if (unit_idx == 0 and col == 1) else None,
                    ),
                    row=row,
                    col=col,
                )
    
    # Update layout
    fig.update_layout(
        title_text="Unit Commitment Status: Scenario-Dependent ON/OFF Decisions",
        title_font_size=18,
        height=150 * n_units,
        showlegend=False,
    )
    
    # Update axes
    for i in range(1, n_units + 1):
        for j in range(1, n_scenarios * n_periods + 1):
            fig.update_xaxes(
                title_text="Hour" if i == n_units else "",
                row=i,
                col=j,
                showticklabels=(i == n_units),
            )
            fig.update_yaxes(
                showticklabels=False,
                row=i,
                col=j,
            )
    
    # Save to HTML
    fig.write_html(str(output_path))
    
    print(f"\n{'='*70}")
    print("INTERACTIVE COMMITMENT STATUS PLOTS SAVED")
    print(f"{'='*70}")
    print(f"File: {output_path}")
    print("\nThe interactive HTML plot shows:")
    print(f"  - ON/OFF status for {n_units} committable units")
    print("  - Green = ON, Gray = OFF")
    print("  - Different patterns across scenarios show scenario-dependent decisions")
    print("  - Hover to see exact status at each hour")
    print(f"{'='*70}\n")
    
    return output_path


def save_capacity_comparison_plot(
    n_stoch: pypsa.Network,
    deterministic_networks: dict[str, pypsa.Network],
    output_path: pathlib.Path | None = None
) -> pathlib.Path:
    """Plot comparison between stochastic and deterministic solutions.
    
    Shows how the stochastic (robust) solution differs from scenario-specific
    deterministic (perfect foresight) solutions.
    """
    
    output_path = output_path or PLOT_FILE
    
    _ensure_carrier_colors(n_stoch)
    
    import matplotlib.pyplot as plt
    import matplotlib
    
    if matplotlib.get_backend().lower() != "agg":
        try:
            matplotlib.use("Agg", force=True)
        except Exception:
            pass
    
    # Create comparison plot: one row per scenario
    n_scenarios = len(SCENARIOS)
    fig, axes = plt.subplots(n_scenarios, 2, figsize=(18, 6 * n_scenarios))
    if n_scenarios == 1:
        axes = axes.reshape(1, -1)
    
    # Get stochastic solution capacities per scenario
    stoch_scenarios = n_stoch.generators.index.get_level_values(0).unique()
    
    for scenario_idx, scenario in enumerate(SCENARIOS):
        # Deterministic solution for this scenario
        n_det = deterministic_networks[scenario]
        
        # Extract deterministic capacities
        det_gen_caps = {}
        det_link_caps = {}
        
        for gen in n_det.generators.index:
            if n_det.generators.at[gen, "p_nom_extendable"]:
                cap = n_det.generators.at[gen, "p_nom_opt"]
                if cap > 0.1:
                    carrier = n_det.generators.at[gen, "carrier"]
                    det_gen_caps[gen] = {
                        "capacity": cap,
                        "carrier": carrier
                    }
        
        for link in n_det.links.index:
            if n_det.links.at[link, "p_nom_extendable"]:
                cap = n_det.links.at[link, "p_nom_opt"]
                if cap > 0.1:
                    carrier = n_det.links.at[link, "carrier"] if "carrier" in n_det.links.columns else "heat"
                    det_link_caps[link] = {
                        "capacity": cap,
                        "carrier": carrier
                    }
        
        # Extract stochastic capacities for this scenario
        stoch_gen_caps = {}
        stoch_link_caps = {}
        
        gen_names = n_stoch.generators.xs(scenario, level=0).index
        for gen_name in gen_names:
            gen = (scenario, gen_name)
            if n_stoch.generators.at[gen, "p_nom_extendable"]:
                cap = n_stoch.generators.at[gen, "p_nom_opt"]
                if cap > 0.1:
                    carrier = n_stoch.generators.at[gen, "carrier"]
                    stoch_gen_caps[gen_name] = {
                        "capacity": cap,
                        "carrier": carrier
                    }
        
        link_names = n_stoch.links.xs(scenario, level=0).index
        for link_name in link_names:
            link = (scenario, link_name)
            if n_stoch.links.at[link, "p_nom_extendable"]:
                cap = n_stoch.links.at[link, "p_nom_opt"]
                if cap > 0.1:
                    carrier = n_stoch.links.at[link, "carrier"] if "carrier" in n_stoch.links.columns else "heat"
                    stoch_link_caps[link_name] = {
                        "capacity": cap,
                        "carrier": carrier
                    }
        
        # Plot generators
        ax_gen = axes[scenario_idx, 0]
        
        # Combine all generator names
        all_gen_names = set(det_gen_caps.keys()) | set(stoch_gen_caps.keys())
        
        if all_gen_names:
            x = np.arange(len(all_gen_names))
            width = 0.35
            
            det_values = []
            stoch_values = []
            labels = []
            colors = []
            
            for gen_name in sorted(all_gen_names):
                labels.append(gen_name)
                
                # Deterministic value
                det_val = det_gen_caps.get(gen_name, {}).get("capacity", 0.0)
                det_values.append(det_val)
                
                # Stochastic value
                stoch_val = stoch_gen_caps.get(gen_name, {}).get("capacity", 0.0)
                stoch_values.append(stoch_val)
                
                # Color from carrier
                carrier = (det_gen_caps.get(gen_name) or stoch_gen_caps.get(gen_name, {})).get("carrier", "electric")
                color = n_stoch.carriers.loc[carrier, "color"] if carrier in n_stoch.carriers.index else "#808080"
                colors.append(color)
            
            # Create grouped bar chart
            bars1 = ax_gen.bar(x - width/2, det_values, width, label='Deterministic', alpha=0.8, color=colors, edgecolor='black', linewidth=1.5)
            bars2 = ax_gen.bar(x + width/2, stoch_values, width, label='Stochastic', alpha=0.6, color=colors, edgecolor='blue', linewidth=1.5, linestyle='--')
            
            ax_gen.set_ylabel("Capacity [MW]", fontsize=11, fontweight='bold')
            ax_gen.set_title(f"Scenario: {scenario.upper()} - Generator Capacities", fontsize=12, fontweight="bold")
            ax_gen.set_xticks(x)
            ax_gen.set_xticklabels(labels, rotation=45, ha='right')
            ax_gen.legend(loc="upper left", fontsize=10)
            ax_gen.grid(axis="y", alpha=0.3)
        
        # Plot links
        ax_link = axes[scenario_idx, 1]
        
        # Combine all link names
        all_link_names = set(det_link_caps.keys()) | set(stoch_link_caps.keys())
        
        if all_link_names:
            x = np.arange(len(all_link_names))
            width = 0.35
            
            det_values = []
            stoch_values = []
            labels = []
            colors = []
            
            for link_name in sorted(all_link_names):
                labels.append(link_name)
                
                # Deterministic value
                det_val = det_link_caps.get(link_name, {}).get("capacity", 0.0)
                det_values.append(det_val)
                
                # Stochastic value
                stoch_val = stoch_link_caps.get(link_name, {}).get("capacity", 0.0)
                stoch_values.append(stoch_val)
                
                # Color from carrier
                carrier = (det_link_caps.get(link_name) or stoch_link_caps.get(link_name, {})).get("carrier", "heat")
                color = n_stoch.carriers.loc[carrier, "color"] if carrier in n_stoch.carriers.index else "#FF6B6B"
                colors.append(color)
            
            # Create grouped bar chart
            bars1 = ax_link.bar(x - width/2, det_values, width, label='Deterministic', alpha=0.8, color=colors, edgecolor='black', linewidth=1.5)
            bars2 = ax_link.bar(x + width/2, stoch_values, width, label='Stochastic', alpha=0.6, color=colors, edgecolor='blue', linewidth=1.5, linestyle='--')
            
            ax_link.set_ylabel("Capacity [MW]", fontsize=11, fontweight='bold')
            ax_link.set_title(f"Scenario: {scenario.upper()} - Link Capacities (CHP, P2G, Boilers)", fontsize=12, fontweight="bold")
            ax_link.set_xticks(x)
            ax_link.set_xticklabels(labels, rotation=45, ha='right')
            ax_link.legend(loc="upper left", fontsize=10)
            ax_link.grid(axis="y", alpha=0.3)
    
    plt.suptitle("Stochastic vs Deterministic Capacity Investment Decisions", fontsize=16, fontweight='bold', y=0.995)
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    
    print(f"\n{'='*70}")
    print("PLOT INTERPRETATION:")
    print(f"{'='*70}")
    print("- DETERMINISTIC (solid bars): Optimal solution if we KNOW which scenario occurs")
    print("- STOCHASTIC (dashed bars): Robust solution that works for ALL scenarios")
    print("- Differences show the 'cost of uncertainty' - extra/less capacity needed")
    print("  to hedge against multiple possible futures")
    print(f"{'='*70}\n")
    
    return output_path


def save_capacity_evolution_plot(
    n: pypsa.Network, output_path: pathlib.Path | None = None
) -> pathlib.Path:
    """Plot capacity evolution across investment periods and scenarios.
    
    For multi-investment optimization, p_nom_opt shows the FINAL capacity.
    We need to extract when each capacity was built by looking at build_year
    and the optimal investment decision per period.
    """
    
    output_path = output_path or PLOT_FILE
    
    _ensure_carrier_colors(n)
    
    import matplotlib.pyplot as plt
    import matplotlib
    
    if matplotlib.get_backend().lower() != "agg":
        try:
            matplotlib.use("Agg", force=True)
        except Exception:
            pass
    
    # Check if we have scenarios
    has_scenarios = isinstance(n.generators.index, pd.MultiIndex)
    
    if has_scenarios:
        # Extract scenario names
        scenarios = n.generators.index.get_level_values(0).unique()
        
        # Create plot with subplots for each scenario
        n_scenarios = len(scenarios)
        fig, axes = plt.subplots(n_scenarios, 2, figsize=(16, 5 * n_scenarios))
        if n_scenarios == 1:
            axes = axes.reshape(1, -1)
        
        for scenario_idx, scenario in enumerate(scenarios):
            # Extract data for this scenario
            gen_data = {}
            link_data = {}
            
            # Get generator names for this scenario
            gen_names = n.generators.xs(scenario, level=0).index
            for gen_name in gen_names:
                gen = (scenario, gen_name)
                if n.generators.at[gen, "p_nom_extendable"]:
                    cap = n.generators.at[gen, "p_nom_opt"]
                    carrier = n.generators.at[gen, "carrier"]
                    build_year = n.generators.at[gen, "build_year"]
                    
                    if gen_name not in gen_data:
                        gen_data[gen_name] = {
                            "capacity": cap,
                            "carrier": carrier,
                            "build_year": build_year
                        }
            
            # Get link names for this scenario
            link_names = n.links.xs(scenario, level=0).index
            for link_name in link_names:
                link = (scenario, link_name)
                if n.links.at[link, "p_nom_extendable"]:
                    cap = n.links.at[link, "p_nom_opt"]
                    build_year = n.links.at[link, "build_year"]
                    carrier = n.links.at[link, "carrier"] if "carrier" in n.links.columns else "heat"
                    
                    if link_name not in link_data:
                        link_data[link_name] = {
                            "capacity": cap,
                            "carrier": carrier,
                            "build_year": build_year
                        }
            
            # Create cumulative capacity per period
            gen_cap_per_period = {period: {} for period in INVESTMENT_PERIODS}
            for gen_name, data in gen_data.items():
                build_year = data["build_year"]
                capacity = data["capacity"]
                carrier = data["carrier"]
                
                # Add capacity to this period and all following periods
                for period in INVESTMENT_PERIODS:
                    if period >= build_year:
                        gen_cap_per_period[period][gen_name] = {
                            "capacity": capacity,
                            "carrier": carrier
                        }
            
            link_cap_per_period = {period: {} for period in INVESTMENT_PERIODS}
            for link_name, data in link_data.items():
                build_year = data["build_year"]
                capacity = data["capacity"]
                carrier = data["carrier"]
                
                for period in INVESTMENT_PERIODS:
                    if period >= build_year:
                        link_cap_per_period[period][link_name] = {
                            "capacity": capacity,
                            "carrier": carrier
                        }
            
            # Plot generators
            ax_gen = axes[scenario_idx, 0]
            gen_series = {}
            gen_colors = {}
            
            # First, collect all generator names across all periods
            all_gen_names = set()
            for period in INVESTMENT_PERIODS:
                all_gen_names.update(gen_cap_per_period[period].keys())
            
            # Now build series with consistent length
            for gen_name in all_gen_names:
                gen_series[gen_name] = []
                # Get carrier and color from first period where it appears
                for period in INVESTMENT_PERIODS:
                    if gen_name in gen_cap_per_period[period]:
                        carrier = gen_cap_per_period[period][gen_name]["carrier"]
                        gen_colors[gen_name] = n.carriers.loc[carrier, "color"] if carrier in n.carriers.index else "#808080"
                        break
                
                # Fill in values for all periods
                for period in INVESTMENT_PERIODS:
                    if gen_name in gen_cap_per_period[period]:
                        gen_series[gen_name].append(gen_cap_per_period[period][gen_name]["capacity"])
                    else:
                        gen_series[gen_name].append(0.0)
            
            if gen_series:
                x_pos = np.arange(len(INVESTMENT_PERIODS))
                width = 0.8 / len(gen_series)
                
                for idx, (gen_name, values) in enumerate(gen_series.items()):
                    offset = (idx - len(gen_series)/2) * width + width/2
                    ax_gen.bar(x_pos + offset, values, width, 
                              label=gen_name, color=gen_colors[gen_name])
                
                ax_gen.set_ylabel("Capacity [MW]", fontsize=11)
                ax_gen.set_xlabel("Investment Period", fontsize=11)
                ax_gen.set_title(f"Scenario: {scenario} - Generator Capacities", fontsize=12, fontweight="bold")
                ax_gen.set_xticks(x_pos)
                ax_gen.set_xticklabels(INVESTMENT_PERIODS)
                ax_gen.legend(loc="upper left", fontsize=9)
                ax_gen.grid(axis="y", alpha=0.3)
            
            # Plot links
            ax_link = axes[scenario_idx, 1]
            link_series = {}
            link_colors = {}
            
            # First, collect all link names across all periods
            all_link_names = set()
            for period in INVESTMENT_PERIODS:
                all_link_names.update(link_cap_per_period[period].keys())
            
            # Now build series with consistent length
            for link_name in all_link_names:
                link_series[link_name] = []
                # Get carrier and color from first period where it appears
                for period in INVESTMENT_PERIODS:
                    if link_name in link_cap_per_period[period]:
                        carrier = link_cap_per_period[period][link_name]["carrier"]
                        link_colors[link_name] = n.carriers.loc[carrier, "color"] if carrier in n.carriers.index else "#FF6B6B"
                        break
                
                # Fill in values for all periods
                for period in INVESTMENT_PERIODS:
                    if link_name in link_cap_per_period[period]:
                        link_series[link_name].append(link_cap_per_period[period][link_name]["capacity"])
                    else:
                        link_series[link_name].append(0.0)
            
            if link_series:
                x_pos = np.arange(len(INVESTMENT_PERIODS))
                width = 0.8 / len(link_series)
                
                for idx, (link_name, values) in enumerate(link_series.items()):
                    offset = (idx - len(link_series)/2) * width + width/2
                    ax_link.bar(x_pos + offset, values, width,
                               label=link_name, color=link_colors[link_name])
                
                ax_link.set_ylabel("Capacity [MW]", fontsize=11)
                ax_link.set_xlabel("Investment Period", fontsize=11)
                ax_link.set_title(f"Scenario: {scenario} - Link Capacities (CHP, P2G, Boilers)", 
                                 fontsize=12, fontweight="bold")
                ax_link.set_xticks(x_pos)
                ax_link.set_xticklabels(INVESTMENT_PERIODS)
                ax_link.legend(loc="upper left", fontsize=9)
                ax_link.grid(axis="y", alpha=0.3)
        
    else:
        # Without scenarios - simpler plot
        fig, axes = plt.subplots(2, 1, figsize=(14, 10))
        
        # Extract generator data
        gen_cap_per_period = {period: {} for period in INVESTMENT_PERIODS}
        for gen in n.generators.index:
            if n.generators.at[gen, "p_nom_extendable"]:
                cap = n.generators.at[gen, "p_nom_opt"]
                carrier = n.generators.at[gen, "carrier"]
                build_year = n.generators.at[gen, "build_year"]
                
                for period in INVESTMENT_PERIODS:
                    if period >= build_year and cap > 0.1:
                        gen_cap_per_period[period][gen] = {
                            "capacity": cap,
                            "carrier": carrier
                        }
        
        # Plot generators
        ax_gen = axes[0]
        gen_series = {}
        gen_colors = {}
        
        # First, collect all generator names across all periods
        all_gen_names = set()
        for period in INVESTMENT_PERIODS:
            all_gen_names.update(gen_cap_per_period[period].keys())
        
        # Now build series with consistent length
        for gen_name in all_gen_names:
            gen_series[gen_name] = []
            # Get carrier and color from first period where it appears
            for period in INVESTMENT_PERIODS:
                if gen_name in gen_cap_per_period[period]:
                    carrier = gen_cap_per_period[period][gen_name]["carrier"]
                    gen_colors[gen_name] = n.carriers.loc[carrier, "color"] if carrier in n.carriers.index else "#808080"
                    break
            
            # Fill in values for all periods
            for period in INVESTMENT_PERIODS:
                if gen_name in gen_cap_per_period[period]:
                    gen_series[gen_name].append(gen_cap_per_period[period][gen_name]["capacity"])
                else:
                    gen_series[gen_name].append(0.0)
        
        if gen_series:
            x_pos = np.arange(len(INVESTMENT_PERIODS))
            width = 0.8 / len(gen_series)
            
            for idx, (gen_name, values) in enumerate(gen_series.items()):
                offset = (idx - len(gen_series)/2) * width + width/2
                ax_gen.bar(x_pos + offset, values, width,
                          label=gen_name, color=gen_colors[gen_name])
            
            ax_gen.set_ylabel("Capacity [MW]", fontsize=12)
            ax_gen.set_xlabel("Investment Period", fontsize=12)
            ax_gen.set_title("Generator Capacity Evolution", fontsize=14, fontweight="bold")
            ax_gen.set_xticks(x_pos)
            ax_gen.set_xticklabels(INVESTMENT_PERIODS)
            ax_gen.legend(loc="upper left", fontsize=10)
            ax_gen.grid(axis="y", alpha=0.3)
        
        # Similar for links...
        link_cap_per_period = {period: {} for period in INVESTMENT_PERIODS}
        for link in n.links.index:
            if n.links.at[link, "p_nom_extendable"]:
                cap = n.links.at[link, "p_nom_opt"]
                carrier = n.links.at[link, "carrier"] if "carrier" in n.links.columns else "heat"
                build_year = n.links.at[link, "build_year"]
                
                for period in INVESTMENT_PERIODS:
                    if period >= build_year and cap > 0.1:
                        link_cap_per_period[period][link] = {
                            "capacity": cap,
                            "carrier": carrier
                        }
        
        ax_link = axes[1]
        link_series = {}
        link_colors = {}
        
        # First, collect all link names across all periods
        all_link_names = set()
        for period in INVESTMENT_PERIODS:
            all_link_names.update(link_cap_per_period[period].keys())
        
        # Now build series with consistent length
        for link_name in all_link_names:
            link_series[link_name] = []
            # Get carrier and color from first period where it appears
            for period in INVESTMENT_PERIODS:
                if link_name in link_cap_per_period[period]:
                    carrier = link_cap_per_period[period][link_name]["carrier"]
                    link_colors[link_name] = n.carriers.loc[carrier, "color"] if carrier in n.carriers.index else "#FF6B6B"
                    break
            
            # Fill in values for all periods
            for period in INVESTMENT_PERIODS:
                if link_name in link_cap_per_period[period]:
                    link_series[link_name].append(link_cap_per_period[period][link_name]["capacity"])
                else:
                    link_series[link_name].append(0.0)
        
        if link_series:
            x_pos = np.arange(len(INVESTMENT_PERIODS))
            width = 0.8 / len(link_series)
            
            for idx, (link_name, values) in enumerate(link_series.items()):
                offset = (idx - len(link_series)/2) * width + width/2
                ax_link.bar(x_pos + offset, values, width,
                           label=link_name, color=link_colors[link_name])
            
            ax_link.set_ylabel("Capacity [MW]", fontsize=12)
            ax_link.set_xlabel("Investment Period", fontsize=12)
            ax_link.set_title("Link Capacity Evolution (CHP, P2G, Boilers)", 
                            fontsize=14, fontweight="bold")
            ax_link.set_xticks(x_pos)
            ax_link.set_xticklabels(INVESTMENT_PERIODS)
            ax_link.legend(loc="upper left", fontsize=10)
            ax_link.grid(axis="y", alpha=0.3)
    
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    
    print(f"\nNote: In multi-investment optimization, p_nom_opt shows the FINAL installed capacity.")
    print("The plot shows when each technology becomes available (build_year),")
    print("but capacities remain constant as they represent the optimal end-state investment.")
    
    return output_path


def print_summary(n: pypsa.Network) -> None:
    """Print optimization results summary."""
    
    print("\n" + "=" * 70)
    print("STOCHASTIC MULTI-HORIZON OPTIMIZATION RESULTS")
    print("=" * 70)
    
    print(f"\nTotal system cost: {n.objective / 1e6:.2f} M€ (discounted)")
    
    print("\n--- Capacity Investments by Period ---")
    
    # Check if we have MultiIndex (scenarios)
    has_scenarios = isinstance(n.generators.index, pd.MultiIndex)
    
    if has_scenarios:
        print("\n=== SCENARIO-SPECIFIC CAPACITIES ===")
        print("=" * 70)
        
        scenarios = n.generators.index.get_level_values(0).unique()
        
        # Show capacity differences between scenarios
        for scenario in scenarios:
            print(f"\n>>> Scenario: {scenario.upper()}")
            print("-" * 60)
            
            # Generators
            gen_names = n.generators.xs(scenario, level=0).index
            for gen_name in gen_names:
                gen = (scenario, gen_name)
                if n.generators.at[gen, "p_nom_extendable"]:
                    cap = n.generators.at[gen, "p_nom_opt"]
                    if cap > 0.01:
                        carrier = n.generators.at[gen, "carrier"]
                        print(f"  {gen_name:20s} ({carrier:10s}): {cap:8.2f} MW")
            
            # Links
            link_names = n.links.xs(scenario, level=0).index
            for link_name in link_names:
                link = (scenario, link_name)
                if n.links.at[link, "p_nom_extendable"]:
                    cap = n.links.at[link, "p_nom_opt"]
                    if cap > 0.01:
                        print(f"  {link_name:20s}: {cap:8.2f} MW")
            
            # Stores
            store_names = n.stores.xs(scenario, level=0).index
            for store_name in store_names:
                store = (scenario, store_name)
                if n.stores.at[store, "e_nom_extendable"]:
                    cap = n.stores.at[store, "e_nom_opt"]
                    if cap > 0.01:
                        print(f"  {store_name:20s}: {cap:8.2f} MWh")
        
        print("\n" + "=" * 70)
        print("NOTE: In perfect-foresight multi-investment optimization,")
        print("      all capacities are decided at t=0 based on all future periods.")
        print("      Capacities remain constant across periods but may differ by scenario.")
        print("=" * 70)
    
    else:
        # Original non-scenario output
        for period in INVESTMENT_PERIODS:
            print(f"\n  Period {period}:")
            
            # Generators
            for gen in n.generators.index:
                if n.generators.at[gen, "p_nom_extendable"]:
                    cap = n.generators.at[gen, "p_nom_opt"]
                    if cap > 0.01:
                        carrier = n.generators.at[gen, "carrier"]
                        print(f"    {gen:20s} ({carrier:10s}): {cap:8.2f} MW")
            
            # Links
            for link in n.links.index:
                if n.links.at[link, "p_nom_extendable"]:
                    cap = n.links.at[link, "p_nom_opt"]
                    if cap > 0.01:
                        print(f"    {link:20s}: {cap:8.2f} MW")
            
            # Stores
            for store in n.stores.index:
                if n.stores.at[store, "e_nom_extendable"]:
                    cap = n.stores.at[store, "e_nom_opt"]
                    if cap > 0.01:
                        print(f"    {store:20s}: {cap:8.2f} MWh")
    
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    print("=" * 70)
    print("STOCHASTIC MULTI-HORIZON CHP OPTIMIZATION WITH COMPARISON")
    print("=" * 70)
    print(f"Investment periods: {INVESTMENT_PERIODS}")
    print(f"Scenarios: {SCENARIOS}")
    print(f"Scenario weights: {SCENARIO_WEIGHTS}")
    print("=" * 70)
    
    # Run both deterministic and stochastic optimizations
    n_stoch, deterministic_networks = build_and_optimize_with_comparison()
    
    print_summary(n_stoch)
    
    # Print comparison summary
    print("\n" + "=" * 70)
    print("DETERMINISTIC vs STOCHASTIC COMPARISON")
    print("=" * 70)
    
    print("\nDETERMINISTIC SOLUTIONS (scenario-specific):")
    print("-" * 70)
    
    for scenario in SCENARIOS:
        n_det = deterministic_networks[scenario]
        print(f"\nScenario: {scenario.upper()}")
        print(f"  Objective: {n_det.objective:,.2f} EUR")
        
        # Show key capacity differences
        wind_cap = n_det.generators.at["wind_turbine", "p_nom_opt"]
        chp_cap = n_det.links.at["chp_generator", "p_nom_opt"]
        p2g_cap = n_det.links.at["p2g", "p_nom_opt"]
        
        print(f"  Wind: {wind_cap:.2f} MW | CHP: {chp_cap:.2f} MW | P2G: {p2g_cap:.2f} MW")
    
    print(f"\nSTOCHASTIC SOLUTION (robust across all scenarios):")
    print(f"  Expected objective: {n_stoch.objective:,.2f} EUR")
    
    # Show stochastic capacities (same for all scenarios in two-stage)
    first_scenario = SCENARIOS[0]
    
    wind_cap_stoch = n_stoch.generators.at[(first_scenario, "wind_turbine"), "p_nom_opt"]
    chp_cap_stoch = n_stoch.links.at[(first_scenario, "chp_generator"), "p_nom_opt"]
    p2g_cap_stoch = n_stoch.links.at[(first_scenario, "p2g"), "p_nom_opt"]
    
    print(f"  Wind: {wind_cap_stoch:.2f} MW | CHP: {chp_cap_stoch:.2f} MW | P2G: {p2g_cap_stoch:.2f} MW")
    print(f"  (Note: These are the same for all scenarios - First-Stage decisions)")
    
    print("\n" + "-" * 70)
    
    print(f"\nStochastic expected objective: {n_stoch.objective:,.2f} EUR")
    print("  (Robust solution for all scenarios)")
    
    # Calculate expected value of perfect information (EVPI)
    scenarios_list = list(SCENARIOS)
    weights = [SCENARIO_WEIGHTS[s] for s in scenarios_list]
    expected_det_obj = sum(
        deterministic_networks[s].objective * SCENARIO_WEIGHTS[s] 
        for s in scenarios_list
    )
    
    evpi = n_stoch.objective - expected_det_obj
    print(f"\nExpected Value of Perfect Information (EVPI): {evpi:,.2f} EUR")
    print(f"  = Stochastic objective - Weighted average of deterministic objectives")
    print(f"  = {n_stoch.objective:,.2f} - {expected_det_obj:,.2f}")
    print(f"  This is the 'cost of uncertainty' - what we'd save if we knew")
    print(f"  the future scenario in advance.")
    print("=" * 70)
    
    # Note: NetCDF export can fail with stochastic networks due to mixed dtypes
    # in time-varying marginal costs. We'll attempt export but catch errors.
    try:
        n_stoch.export_to_netcdf(str(RESULT_FILE))
        print(f"\nExported stochastic network to {RESULT_FILE}")
    except (ValueError, TypeError) as e:
        print(f"\nWarning: Could not export to NetCDF: {e}")
        print("This is a known limitation with stochastic networks.")
        print("Results are still available in the network object.")
    
    # Create comparison plot
    plot_path = save_capacity_comparison_plot(n_stoch, deterministic_networks)
    print(f"Saved capacity comparison plot to {plot_path}")
    
    # Create interactive dispatch plots
    dispatch_plot_path = save_interactive_dispatch_plots(n_stoch)
    if dispatch_plot_path:
        print(f"Saved interactive dispatch plot to {dispatch_plot_path}")
    
    # Create interactive commitment status plots
    commitment_plot_path = save_interactive_commitment_plots(n_stoch)
    if commitment_plot_path:
        print(f"Saved interactive commitment plot to {commitment_plot_path}")
    
    print("\nDone!")
