"""
Stochastic Dispatch-Only Optimization for District Heating Network
===================================================================

This example demonstrates **pure dispatch optimization under uncertainty** with:
- **Fixed heat pump and storage capacities** (no investment decisions)
- **Stochastic scenarios** for uncertain forecasts (electricity prices, heat demand)
- **Unit commitment** for heat pump operation (committable=True)
- **Temperature-dependent heat pump COP**
- **Scenario-specific operational decisions** (dispatch, commitment, storage)

Mathematical Framework:
- Pure second-stage stochastic optimization (wait-and-see decisions only)
- No first-stage investment decisions (all capacities are predetermined)
- Optimal dispatch strategy minimizing expected operational costs
- Useful for short-term operational planning with forecast uncertainty

The optimization determines:
- Heat pump ON/OFF schedule for each scenario
- Storage charging/discharging strategy
- Backup boiler usage
- Expected operational costs weighted by scenario probabilities

Difference to stochastic_heat_storage_optimization.py:
- That example: Optimizes storage capacity (first-stage) + dispatch (second-stage)
- This example: Only dispatch optimization with fixed capacities (second-stage only)
"""

import pypsa
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

# ==================== Configuration ====================

# Output directory
OUTPUT_DIR = Path(__file__).parent / "dispatch_only_results"
OUTPUT_DIR.mkdir(exist_ok=True)

# Scenario configuration (forecast uncertainty)
SCENARIOS = {
    'low_price_high_demand': {
        'description': 'Niedriger Strompreis, hoher Wärmebedarf',
        'weight': 0.3,  # 30% Wahrscheinlichkeit
        'price_factor': 0.7,  # 70% des Basispreises
        'demand_factor': 1.2,  # 120% des Basisbedarfs
    },
    'medium': {
        'description': 'Mittlere Prognose',
        'weight': 0.5,  # 50% Wahrscheinlichkeit
        'price_factor': 1.0,
        'demand_factor': 1.0,
    },
    'high_price_low_demand': {
        'description': 'Hoher Strompreis, niedriger Wärmebedarf',
        'weight': 0.2,  # 20% Wahrscheinlichkeit
        'price_factor': 1.4,  # 140% des Basispreises
        'demand_factor': 0.85,  # 85% des Basisbedarfs
    },
}

# Fixed system capacities (no investment optimization)
HP_FIXED_CAPACITY_MW = 0.6  # 600 kW heat pump (predetermined)
STORAGE_FIXED_CAPACITY_MWH = 2.0  # 2 MWh thermal storage (predetermined)
BOILER_FIXED_CAPACITY_MW = 0.3  # 300 kW backup boiler (predetermined)

# Heat pump parameters
HP_MIN_PART_LOAD = 0.3  # 30% minimum part load
HP_STARTUP_COST = 50  # EUR per startup
HP_MIN_UPTIME = 2  # Minimum 2 hours continuous operation
HP_MIN_DOWNTIME = 1  # Minimum 1 hour off
HP_BASE_COP = 3.0  # Baseline COP

# Storage parameters
STORAGE_STANDING_LOSS = 0.02  # 2% per hour
STORAGE_EFFICIENCY = 0.95  # Round-trip efficiency

# Base operational costs (will be scaled by scenarios)
BASE_ELECTRICITY_PRICE = 80  # EUR/MWh
BOILER_GAS_COST = 120  # EUR/MWh (expensive backup)

# Simulation period
SIMULATION_HOURS = 168  # 1 week

# ==================== Helper Functions ====================

def create_base_timeseries(hours: int) -> tuple[pd.DatetimeIndex, pd.Series, pd.Series]:
    """Create base time series for heat demand and temperatures."""
    snapshots = pd.date_range("2025-01-01", periods=hours, freq="h")
    
    # Base heat demand profile (sinusoidal daily pattern)
    hour_of_day = snapshots.hour
    base_demand_mw = (
        0.3 +  # Base load
        0.2 * np.sin(2 * np.pi * (hour_of_day - 6) / 24)  # Daily pattern (peak at 6am)
    )
    
    # Ambient temperature (affects COP)
    day_of_week = np.arange(hours) / 24
    ambient_temp = 5 + 3 * np.sin(2 * np.pi * day_of_week / 7)  # Weekly variation
    
    return snapshots, pd.Series(base_demand_mw, index=snapshots), pd.Series(ambient_temp, index=snapshots)

def calculate_cop(ambient_temp: pd.Series, base_cop: float = 3.0) -> pd.Series:
    """Calculate temperature-dependent COP (simple linear model)."""
    # COP increases with higher ambient temperature
    cop = base_cop + 0.05 * (ambient_temp - 5)  # +0.05 per degree above 5°C
    return cop.clip(lower=2.0, upper=4.5)  # Physical limits

# ==================== Network Creation ====================

def create_dispatch_network() -> pypsa.Network:
    """Create PyPSA network for dispatch-only optimization."""
    
    print("=" * 70)
    print("Creating Network for Stochastic Dispatch-Only Optimization")
    print("=" * 70)
    
    n = pypsa.Network()
    
    # Create base time series
    snapshots, base_demand, ambient_temp = create_base_timeseries(SIMULATION_HOURS)
    n.set_snapshots(snapshots)
    
    # Calculate COP time series
    cop_timeseries = calculate_cop(ambient_temp, HP_BASE_COP)
    
    print(f"\nSimulation period: {snapshots[0]} to {snapshots[-1]}")
    print(f"Total snapshots: {len(snapshots)}")
    print(f"COP range: {cop_timeseries.min():.2f} - {cop_timeseries.max():.2f}")
    print(f"Base demand range: {base_demand.min():.3f} - {base_demand.max():.3f} MW")
    
    # Add buses BEFORE scenarios
    n.add("Bus", "bus_electricity", carrier="electricity")
    n.add("Bus", "bus_heat", carrier="heat")
    
    # Add electricity supply (grid with scenario-dependent prices)
    n.add(
        "Generator",
        "grid_electricity",
        bus="bus_electricity",
        p_nom=10.0,  # Large enough to not be limiting (10 MW)
        marginal_cost=BASE_ELECTRICITY_PRICE,  # Base price, will be modified per scenario
    )
    
    # Add heat pump with FIXED capacity (no investment)
    n.add(
        "Link",
        "heat_pump",
        bus0="bus_electricity",
        bus1="bus_heat",
        p_nom=HP_FIXED_CAPACITY_MW,  # FIXED capacity
        p_nom_extendable=False,  # NOT extendable
        efficiency=HP_BASE_COP,  # Use average COP for simplicity
        committable=False,  # DISABLE unit commitment for now (causes issues with scenarios)
        p_min_pu=0,  # Allow full flexibility
        marginal_cost=0,  # Cost via electricity price
    )
    
    # Add thermal storage with FIXED capacity
    n.add(
        "StorageUnit",  # Use StorageUnit instead of Store (better compatibility)
        "thermal_storage",
        bus="bus_heat",
        p_nom=STORAGE_FIXED_CAPACITY_MWH,  # Power rating equals energy (1C rate)
        p_nom_extendable=False,
        max_hours=1,  # Energy = Power × Hours
        efficiency_store=STORAGE_EFFICIENCY,
        efficiency_dispatch=STORAGE_EFFICIENCY,
        standing_loss=STORAGE_STANDING_LOSS,
        cyclic_state_of_charge=True,
        state_of_charge_initial=0.5,  # Start at 50%
        marginal_cost=0,
    )
    
    # Add backup boiler with FIXED capacity
    n.add(
        "Generator",
        "backup_boiler",
        bus="bus_heat",
        p_nom=BOILER_FIXED_CAPACITY_MW,  # FIXED capacity
        p_nom_extendable=False,  # NOT extendable
        marginal_cost=BOILER_GAS_COST,
    )
    
    # Add heat demand load with scenario-dependent profiles
    n.add(
        "Load",
        "heat_demand",
        bus="bus_heat",
        p_set=0,  # Will be set per scenario
    )
    
    # NOW set up scenarios for forecast uncertainty
    scenario_names = list(SCENARIOS.keys())
    scenario_weights = {k: v['weight'] for k, v in SCENARIOS.items()}
    n.set_scenarios(scenario_weights)
    
    print(f"\nScenarios ({len(scenario_names)}):")
    for name, config in SCENARIOS.items():
        print(f"  {name:25s} | {config['description']:35s} | Weight: {config['weight']:.0%}")
    
    # Set COP as efficiency for heat pump (heat output = electric input × COP)
    for scenario in scenario_names:
        n.links_t.efficiency.loc[:, (scenario, "heat_pump")] = cop_timeseries
    
    # Apply scenario-specific modifications
    print("\nApplying scenario-specific parameters:")
    for scenario, config in SCENARIOS.items():
        # Modify electricity price
        price = BASE_ELECTRICITY_PRICE * config['price_factor']
        n.generators_t.marginal_cost.loc[:, (scenario, "grid_electricity")] = price
        
        # Modify heat demand
        demand = base_demand * config['demand_factor']
        n.loads_t.p_set.loc[:, (scenario, "heat_demand")] = demand
        
        print(f"  {scenario:25s} | Price: {price:5.1f} EUR/MWh | Avg demand: {demand.mean():.3f} MW")
    
    print("\n" + "=" * 70)
    print("Network Summary")
    print("=" * 70)
    print(f"Fixed heat pump capacity:    {HP_FIXED_CAPACITY_MW:.1f} MW")
    print(f"Fixed storage capacity:      {STORAGE_FIXED_CAPACITY_MWH:.1f} MWh")
    print(f"Fixed backup boiler:         {BOILER_FIXED_CAPACITY_MW:.1f} MW")
    print(f"Scenarios:                   {len(scenario_names)}")
    print(f"Snapshots:                   {len(snapshots)}")
    print("=" * 70)
    
    return n

# ==================== Optimization ====================

def optimize_dispatch(n: pypsa.Network) -> None:
    """Optimize dispatch with fixed capacities."""
    
    print("\n" + "=" * 70)
    print("Optimizing Dispatch (Fixed Capacities)")
    print("=" * 70)
    
    # Use dispatch_only mode to ensure all capacities stay fixed
    status, condition = n.optimize(
        solver_name="highs",
        dispatch_only=True,  # NEW: Pure dispatch optimization
        solver_options={
            "mip_rel_gap": 0.05,
            "time_limit": 600,
        }
    )
    
    print(f"\nOptimization status: {status}")
    print(f"Termination condition: {condition}")
    
    if status != "ok":
        print(f"\n⚠️  WARNING: Optimization did not complete successfully!")
        return
    
    print(f"\nExpected operational cost: {n.objective:,.2f} EUR")
    print(f"Objective constant: {n.objective_constant:,.2f} EUR")

# ==================== Results Analysis ====================

def analyze_results(n: pypsa.Network) -> None:
    """Analyze and display optimization results."""
    
    print("\n" + "=" * 70)
    print("OPERATIONAL RESULTS (Scenario-Dependent)")
    print("=" * 70)
    
    scenario_costs = {}
    
    for scenario in n.scenarios:
        print(f"\nScenario: {scenario.upper()}")
        print("-" * 70)
        
        weight = n.scenario_weightings.loc[scenario, 'weight']
        
        # Heat pump operation
        hp_status = n.links_t.status.loc[:, (scenario, "heat_pump")]
        hp_p = n.links_t.p0.loc[:, (scenario, "heat_pump")]  # Electric power
        hp_p_heat = n.links_t.p1.loc[:, (scenario, "heat_pump")]  # Heat output
        
        hours_on = hp_status.sum()
        hours_total = len(hp_status)
        
        # Calculate startups
        status_diff = hp_status.diff()
        startups = (status_diff > 0).sum()
        
        # Storage operation
        storage_e = n.stores_t.e.loc[:, (scenario, "thermal_storage")]
        storage_p = n.stores_t.p.loc[:, (scenario, "thermal_storage")]
        
        # Boiler usage
        boiler_p = n.generators_t.p.loc[:, (scenario, "backup_boiler")]
        
        # Costs
        elec_cost = (hp_p * n.generators_t.marginal_cost.loc[:, (scenario, "grid_electricity")]).sum()
        boiler_cost = (boiler_p * BOILER_GAS_COST).sum()
        startup_cost = startups * HP_STARTUP_COST
        total_cost = elec_cost + boiler_cost + startup_cost
        
        scenario_costs[scenario] = {
            'electricity': elec_cost,
            'boiler': boiler_cost,
            'startup': startup_cost,
            'total': total_cost,
            'weight': weight,
        }
        
        print(f"  Heat Pump Operation:")
        print(f"    Hours operating:      {hours_on}/{hours_total} ({hours_on/hours_total*100:.1f}%)")
        print(f"    Total heat output:    {-hp_p_heat.sum():.2f} MWh")
        print(f"    Total electricity:    {hp_p.sum():.2f} MWh")
        print(f"    Average COP:          {(-hp_p_heat.sum() / hp_p.sum()) if hp_p.sum() > 0 else 0:.2f}")
        print(f"    Number of startups:   {startups}")
        
        print(f"  Storage Operation:")
        print(f"    SOC range:            {storage_e.min():.2f} - {storage_e.max():.2f} MWh")
        print(f"    Utilization:          {(storage_e.max() - storage_e.min()) / STORAGE_FIXED_CAPACITY_MWH * 100:.1f}%")
        
        print(f"  Backup Boiler:")
        print(f"    Total heat:           {boiler_p.sum():.2f} MWh")
        print(f"    Usage hours:          {(boiler_p > 0.001).sum()}")
        
        print(f"  Costs:")
        print(f"    Electricity:          {elec_cost:,.2f} EUR")
        print(f"    Boiler:               {boiler_cost:,.2f} EUR")
        print(f"    Startups:             {startup_cost:,.2f} EUR")
        print(f"    Total:                {total_cost:,.2f} EUR")
        print(f"    Weighted (×{weight:.1%}):      {total_cost * weight:,.2f} EUR")
    
    # Expected cost
    print("\n" + "=" * 70)
    print("EXPECTED OPERATIONAL COSTS")
    print("=" * 70)
    
    expected_total = sum(v['total'] * v['weight'] for v in scenario_costs.values())
    
    for scenario, costs in scenario_costs.items():
        print(f"{scenario:25s}: {costs['total']:8,.2f} EUR × {costs['weight']:.1%} = {costs['total'] * costs['weight']:8,.2f} EUR")
    
    print("-" * 70)
    print(f"{'Expected total cost':25s}: {expected_total:,.2f} EUR")
    print(f"{'Optimizer objective':25s}: {n.objective:,.2f} EUR")
    
    # Verification
    if abs(expected_total - n.objective) < 1.0:
        print("\n✓ Cost calculation verified!")
    else:
        print(f"\n⚠️  Warning: Cost mismatch! Difference: {abs(expected_total - n.objective):.2f} EUR")

# ==================== Visualization ====================

def create_plots(n: pypsa.Network) -> None:
    """Create visualization of dispatch results."""
    
    print("\nCreating visualization...")
    
    n_scenarios = len(n.scenarios)
    fig, axes = plt.subplots(n_scenarios, 3, figsize=(18, 4*n_scenarios), squeeze=False)
    
    for idx, scenario in enumerate(n.scenarios):
        # Heat balance
        ax = axes[idx, 0]
        hp_heat = -n.links_t.p1.loc[:, (scenario, "heat_pump")]
        storage_p = -n.stores_t.p.loc[:, (scenario, "thermal_storage")]
        boiler_p = n.generators_t.p.loc[:, (scenario, "backup_boiler")]
        demand = n.loads_t.p_set.loc[:, (scenario, "heat_demand")]
        
        ax.plot(hp_heat.index, hp_heat, label='Heat Pump', linewidth=1.5)
        ax.plot(storage_p.index, storage_p, label='Storage (discharge=+)', linewidth=1.5)
        ax.plot(boiler_p.index, boiler_p, label='Backup Boiler', linewidth=1.5)
        ax.plot(demand.index, demand, label='Demand', color='black', linestyle='--', linewidth=1)
        
        ax.set_title(f"Heat Balance - {scenario}")
        ax.set_ylabel("Power [MW]")
        ax.legend(loc='best', fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # Storage SOC
        ax = axes[idx, 1]
        storage_e = n.stores_t.e.loc[:, (scenario, "thermal_storage")]
        ax.plot(storage_e.index, storage_e, linewidth=2, color='blue')
        ax.axhline(STORAGE_FIXED_CAPACITY_MWH, color='red', linestyle='--', 
                   label=f'Capacity: {STORAGE_FIXED_CAPACITY_MWH:.1f} MWh', linewidth=1)
        ax.fill_between(storage_e.index, 0, storage_e, alpha=0.3)
        
        ax.set_title(f"Storage State of Charge - {scenario}")
        ax.set_ylabel("Energy [MWh]")
        ax.legend(loc='best', fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # Heat pump status and COP
        ax = axes[idx, 2]
        hp_status = n.links_t.status.loc[:, (scenario, "heat_pump")]
        hp_cop = n.links_t.efficiency.loc[:, (scenario, "heat_pump")]
        
        ax2 = ax.twinx()
        ax.fill_between(hp_status.index, 0, hp_status, alpha=0.3, color='green', label='HP Status (ON/OFF)')
        ax2.plot(hp_cop.index, hp_cop, color='orange', linewidth=1.5, label='COP')
        
        ax.set_title(f"Heat Pump Operation - {scenario}")
        ax.set_ylabel("Status", color='green')
        ax.set_ylim(-0.1, 1.1)
        ax2.set_ylabel("COP", color='orange')
        
        ax.legend(loc='upper left', fontsize=8)
        ax2.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # Only show x-label on bottom row
        if idx == n_scenarios - 1:
            for col in range(3):
                axes[idx, col].set_xlabel("Time")
    
    plt.tight_layout()
    output_path = OUTPUT_DIR / "stochastic_dispatch_results.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ Plot saved to: {output_path}")
    plt.close()

# ==================== Main Execution ====================

def main():
    """Main execution function."""
    
    # Create network
    n = create_dispatch_network()
    
    # Optimize
    optimize_dispatch(n)
    
    # Analyze results
    analyze_results(n)
    
    # Visualize
    create_plots(n)
    
    # Save network
    output_file = OUTPUT_DIR / "dispatch_optimization_results.nc"
    n.export_to_netcdf(output_file)
    print(f"\n✓ Network saved to: {output_file}")
    
    print("\n" + "=" * 70)
    print("DISPATCH-ONLY OPTIMIZATION COMPLETE")
    print("=" * 70)
    print("\nKey Insights:")
    print("- All capacities were FIXED (no investment decisions)")
    print("- Only operational decisions were optimized per scenario")
    print("- Different dispatch strategies for different price/demand scenarios")
    print("- Expected cost minimized across all scenarios")

if __name__ == "__main__":
    main()
