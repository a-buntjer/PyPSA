"""Stochastic Multi-Horizon CHP Investment Planning.

This example combines two advanced PyPSA v1.0 features:
1. **Stochastic optimization**: Multiple scenarios for uncertain parameters (gas prices, demand)
2. **Multi-investment periods**: Pathway planning across 2025, 2030, 2035, 2040

The network represents a district energy system transitioning towards lower emissions
over multiple decades while accounting for uncertainty in fuel prices and demand growth.

Note: Committable components are disabled in this example because the combination of
committable + extendable + multi-investment + stochastic is not yet fully supported in PyPSA.
For unit commitment examples, see `committable_extendable_chp.py`.

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

# CHP technical parameters
NOMINAL_HEAT_TO_ELECTRIC_RATIO = 0.9
BACKPRESSURE_SLOPE = 1.0
MARGINAL_HEAT_LOSS = 0.1

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
    
    # Market price patterns (negative prices appear occasionally)
    daily_market_price = np.array([
        78, 74, 70, 68, 65, 64, 66, 72, 85, 92, 100, 105,
        110, 108, 102, 95, 40, 30, 10, 0, -20, 0, 20, 74,
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
        capital_cost=850,  # EUR/MW/year (annualized)
        marginal_cost=0.5,
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
        capital_cost=650,
        marginal_cost=0.3,
        p_max_pu=solar_profile_series,
        lifetime=25,
        build_year=2030,
    )
    
    # === Gas supply ===
    
    # Gas import (marginal cost will be scenario-dependent)
    n.add(
        "Generator",
        "gas_supply",
        bus="bus_gas",
        carrier="gas",
        p_nom_extendable=True,
        capital_cost=0,
        marginal_cost=80.0,  # Base price, will be overridden by scenarios
        p_nom_max=1000,
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
        p_nom_max=500.0,
        p_min_pu=-1.0,  # Can import or export
        p_max_pu=1.0,
        capital_cost=0.0,
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
    
    # === CHP plant (extendable only - committable disabled for multi-investment + stochastic) ===
    # Note: Combining committable, extendable, multi-investment AND stochastic
    # is not fully supported yet in PyPSA. We use extendable only here.
    
    # CHP electric output link
    n.add(
        "Link",
        "chp_generator",
        bus0="bus_gas",
        bus1="bus_electric",
        efficiency=0.468,
        committable=False,  # Disabled for multi-investment + stochastic compatibility
        capital_cost=480,
        p_nom_extendable=True,
        p_min_pu=0.35,  # Minimum part load
        marginal_cost=42,
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
        efficiency=1.0,  # Will be adjusted for iso-fuel constraint
        committable=False,  # Disabled for multi-investment + stochastic compatibility
        capital_cost=350,
        p_nom_extendable=True,
        p_min_pu=0.20,  # Minimum part load
        marginal_cost=42,
        lifetime=25,
        build_year=2025,
    )
    
    # Align CHP efficiencies
    n.links.at["chp_boiler", "efficiency"] = (
        n.links.at["chp_generator", "efficiency"] / MARGINAL_HEAT_LOSS
    )
    
    # === Auxiliary heating ===
    
    # Heat-only boiler (non-committable, available from 2030)
    n.add(
        "Link",
        "aux_heat_boiler",
        bus0="bus_gas",
        bus1="bus_heat",
        carrier="heat",
        efficiency=0.93,
        capital_cost=160,
        p_nom_extendable=True,
        marginal_cost=55,
        lifetime=20,
        build_year=2030,
    )
    
    # Peak gas turbine (extendable only - committable disabled for compatibility)
    n.add(
        "Generator",
        "gas_peaker",
        bus="bus_electric",
        carrier="gas",
        p_nom_extendable=True,
        marginal_cost=140,
        committable=False,  # Disabled for multi-investment + stochastic compatibility
        p_min_pu=0.0,
        capital_cost=420,
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
    """Add CHP coupling constraints to the optimization model."""
    
    model = n.optimize.create_model()
    
    link_p = model.variables["Link-p"]
    link_p_nom = model.variables["Link-p_nom"]
    # Note: Link-status not available when committable=False
    
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
    
    # Nominal power proportionality
    model.add_constraints(
        generator_eff * NOMINAL_HEAT_TO_ELECTRIC_RATIO * generator_p_nom
        - boiler_eff * boiler_p_nom
        == 0,
        name="chp-heat-power-output-proportionality",
    )
    
    # Backpressure constraint
    backpressure_coefficient = BACKPRESSURE_SLOPE * generator_eff / boiler_eff
    model.add_constraints(
        heat_output * backpressure_coefficient - electric_output <= 0,
        name="chp-backpressure",
    )
    
    # Iso-fuel line
    model.add_constraints(
        electric_output + heat_output * MARGINAL_HEAT_LOSS
        - generator_eff * generator_p_nom
        <= 0,
        name="chp-top-iso-fuel-line",
    )
    
    # Note: Commitment synchronization not needed when committable=False
    
    # Solve the model
    n.optimize.solve_model(
        solver_options={
            "mip_rel_gap": 2.0,  # 2% gap for faster solving
            "threads": 16,
            "parallel": "on",
            "time_limit": 1800,  # 30 minutes time limit
        }
    )


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


def save_capacity_evolution_plot(
    n: pypsa.Network, output_path: pathlib.Path | None = None
) -> pathlib.Path:
    """Plot capacity evolution across investment periods."""
    
    output_path = output_path or PLOT_FILE
    
    _ensure_carrier_colors(n)
    
    import matplotlib.pyplot as plt
    import matplotlib
    
    if matplotlib.get_backend().lower() != "agg":
        try:
            matplotlib.use("Agg", force=True)
        except Exception:
            pass
    
    # Extract optimal capacities per period
    generators_cap = {}
    links_cap = {}
    
    for period in INVESTMENT_PERIODS:
        # Generators
        for gen in n.generators.index:
            if gen not in generators_cap:
                generators_cap[gen] = {}
            
            if n.generators.at[gen, "p_nom_extendable"]:
                generators_cap[gen][period] = n.generators.at[gen, "p_nom_opt"]
            else:
                generators_cap[gen][period] = n.generators.at[gen, "p_nom"]
        
        # Links (CHP, P2G, etc.)
        for link in n.links.index:
            if link not in links_cap:
                links_cap[link] = {}
            
            if n.links.at[link, "p_nom_extendable"]:
                links_cap[link][period] = n.links.at[link, "p_nom_opt"]
            else:
                links_cap[link][period] = n.links.at[link, "p_nom"]
    
    # Create DataFrame
    gen_df = pd.DataFrame(generators_cap).T
    link_df = pd.DataFrame(links_cap).T
    
    # Plot
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))
    
    # Generator capacities
    ax1 = axes[0]
    gen_df_plot = gen_df.loc[
        [g for g in gen_df.index if gen_df.loc[g].sum() > 0.1]
    ]
    
    if not gen_df_plot.empty:
        colors = [
            n.carriers.color.get(n.generators.at[g, "carrier"], "#808080")
            for g in gen_df_plot.index
        ]
        gen_df_plot.T.plot(kind="bar", ax=ax1, color=colors, width=0.7)
        ax1.set_ylabel("Capacity [MW]")
        ax1.set_xlabel("Investment Period")
        ax1.set_title("Generator Capacity Evolution")
        ax1.legend(title="Generator", bbox_to_anchor=(1.05, 1), loc="upper left")
        ax1.grid(axis="y", alpha=0.3)
    
    # Link capacities
    ax2 = axes[1]
    link_df_plot = link_df.loc[
        [l for l in link_df.index if link_df.loc[l].sum() > 0.1]
    ]
    
    if not link_df_plot.empty:
        colors = [
            n.carriers.color.get(
                n.links.at[l, "carrier"] if "carrier" in n.links.columns 
                else "gas", 
                "#808080"
            )
            for l in link_df_plot.index
        ]
        link_df_plot.T.plot(kind="bar", ax=ax2, color=colors, width=0.7)
        ax2.set_ylabel("Capacity [MW]")
        ax2.set_xlabel("Investment Period")
        ax2.set_title("Link Capacity Evolution (CHP, P2G, Boilers)")
        ax2.legend(title="Link", bbox_to_anchor=(1.05, 1), loc="upper left")
        ax2.grid(axis="y", alpha=0.3)
    
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    
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
    
    for period in INVESTMENT_PERIODS:
        print(f"\n  Period {period}:")
        
        if has_scenarios:
            # With scenarios, show average across scenarios
            print("    (Average across all scenarios)")
            
            # Generators - get unique component names
            gen_names = n.generators.index.get_level_values(1).unique()
            for gen_name in gen_names:
                # Get all scenarios for this generator
                gen_data = n.generators.xs(gen_name, level=1)
                if gen_data.iloc[0]["p_nom_extendable"]:
                    avg_cap = gen_data["p_nom_opt"].mean()
                    if avg_cap > 0.01:
                        carrier = gen_data.iloc[0]["carrier"]
                        print(f"    {gen_name:20s} ({carrier:10s}): {avg_cap:8.2f} MW")
            
            # Links
            link_names = n.links.index.get_level_values(1).unique()
            for link_name in link_names:
                link_data = n.links.xs(link_name, level=1)
                if link_data.iloc[0]["p_nom_extendable"]:
                    avg_cap = link_data["p_nom_opt"].mean()
                    if avg_cap > 0.01:
                        print(f"    {link_name:20s}: {avg_cap:8.2f} MW")
        else:
            # Without scenarios - original code
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
        if has_scenarios:
            # With scenarios
            store_names = n.stores.index.get_level_values(1).unique()
            for store_name in store_names:
                store_data = n.stores.xs(store_name, level=1)
                if store_data.iloc[0]["e_nom_extendable"]:
                    avg_cap = store_data["e_nom_opt"].mean()
                    if avg_cap > 0.01:
                        print(f"    {store_name:20s}: {avg_cap:8.2f} MWh")
        else:
            # Without scenarios
            for store in n.stores.index:
                if n.stores.at[store, "e_nom_extendable"]:
                    cap = n.stores.at[store, "e_nom_opt"]
                    if cap > 0.01:
                        print(f"    {store:20s}: {cap:8.2f} MWh")
    
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    print("Starting stochastic multi-horizon CHP optimization...")
    print(f"Investment periods: {INVESTMENT_PERIODS}")
    print(f"Scenarios: {SCENARIOS}")
    print(f"Scenario weights: {SCENARIO_WEIGHTS}")
    
    n = build_and_optimize()
    
    print_summary(n)
    
    # Note: NetCDF export can fail with stochastic networks due to mixed dtypes
    # in time-varying marginal costs. We'll attempt export but catch errors.
    try:
        n.export_to_netcdf(str(RESULT_FILE))
        print(f"\nExported solved network to {RESULT_FILE}")
    except (ValueError, TypeError) as e:
        print(f"\nWarning: Could not export to NetCDF: {e}")
        print("This is a known limitation with stochastic networks.")
        print("Results are still available in the network object.")
    
    plot_path = save_capacity_evolution_plot(n)
    print(f"Saved capacity evolution plot to {plot_path}")
    
    print("\nDone!")
