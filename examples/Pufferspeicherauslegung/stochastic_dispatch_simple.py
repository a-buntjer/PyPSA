"""
Simplified Stochastic Dispatch-Only Optimization Example
=========================================================

This example demonstrates pure stochastic dispatch optimization with fixed capacities,
WITHOUT storage components (to avoid PyPSA v1.0 compatibility issues).

Use case: Short-term operational planning under electricity price forecast uncertainty
Decision: How to dispatch heat pump vs. backup boiler hour-by-hour across different price scenarios

Fixed capacities (pre-existing infrastructure):
- Heat pump: 0.6 MW
- Backup gas boiler: 0.3 MW
- No storage (simplified)

Scenarios:
1. Low price (70 EUR/MWh) - High demand - 30% probability
2. Medium price (80 EUR/MWh) - Medium demand - 50% probability  
3. High price (100 EUR/MWh) - Low demand - 20% probability
"""

import numpy as np
import pandas as pd
import pypsa

def create_time_series(hours=168):
    """Create time series for one week with hourly resolution."""
    index = pd.date_range("2025-01-01", periods=hours, freq="h")
    
    # Base heat demand pattern (daily cycle)
    hour_of_day = np.arange(hours) % 24
    base_demand = 0.2 + 0.15 * np.sin((hour_of_day - 6) * np.pi / 12)  # 0.05 - 0.35 MW
    
    # COP time series (temperature dependent, simplified)
    cop = 3.0 + 0.1 * np.sin((hour_of_day - 14) * np.pi / 12)  # 2.9 - 3.1
    
    return index, base_demand, cop


def create_network():
    """Create network with fixed capacities for dispatch optimization."""
    print("\n" + "=" * 70)
    print("Creating Network for Stochastic Dispatch (Simplified)")
    print("=" * 70)
    
    # Network without storage
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2025-01-01", periods=168, freq="h"))
    
    index, base_demand, cop = create_time_series(168)
    
    print(f"\nSimulation period: {index[0]} to {index[-1]}")
    print(f"Total snapshots: {len(index)}")
    print(f"COP range: {cop.min():.2f} - {cop.max():.2f}")
    print(f"Base demand range: {base_demand.min():.3f} - {base_demand.max():.3f} MW")
    
    # Add buses
    n.add("Bus", "bus_electricity", carrier="AC")
    n.add("Bus", "bus_heat", carrier="heat")
    
    # Heat pump (FIXED capacity)
    n.add(
        "Link",
        "heat_pump",
        bus0="bus_electricity",
        bus1="bus_heat",
        p_nom=0.6,  # Fixed 600 kW
        p_nom_extendable=False,
        efficiency=pd.Series(cop, index=index),
        capital_cost=0,
        carrier="heat_pump"
    )
    
    # Backup gas boiler (FIXED capacity)
    n.add(
        "Generator",
        "gas_boiler",
        bus="bus_heat",
        p_nom=0.3,  # Fixed 300 kW
        p_nom_extendable=False,
        marginal_cost=100,  # 100 EUR/MWh gas cost + emissions
        capital_cost=0,
        carrier="gas"
    )
    
    # Electricity grid connection (unlimited, but with marginal cost from scenarios)
    n.add(
        "Generator",
        "grid",
        bus="bus_electricity",
        p_nom=10.0,  # Large enough to not constrain
        p_nom_extendable=False,
        marginal_cost=80,  # Will be overridden by scenarios
        capital_cost=0,
        carrier="AC"
    )
    
    # Heat demand (will be modified by scenarios)
    n.add(
        "Load",
        "heat_demand",
        bus="bus_heat",
        p_set=pd.Series(base_demand, index=index),
        carrier="heat"
    )
    
    # Define scenarios AFTER components are added
    print(f"\nScenarios (3):")
    
    # Scenario descriptions (for display)
    scenario_info = {
        "low_price_high_demand": "Niedriger Strompreis, hoher Wärmebedarf",
        "medium": "Mittlere Prognose",
        "high_price_low_demand": "Hoher Strompreis, niedriger Wärmebedarf"
    }
    
    # Scenario weights (for PyPSA)
    scenarios = pd.DataFrame(
        {"weight": [0.3, 0.5, 0.2]},
        index=pd.Index(["low_price_high_demand", "medium", "high_price_low_demand"], name="scenario")
    )
    
    for scenario in scenarios.index:
        print(f"  {scenario:25s} | {scenario_info[scenario]:40s} | Weight: {scenarios.loc[scenario, 'weight']*100:.0f}%")
    
    n.set_scenarios(scenarios)
    
    # Apply scenario-specific parameters
    print(f"\nApplying scenario-specific parameters:")
    
    for scenario in scenarios.index:
        # Electricity price scenarios
        if scenario == "low_price_high_demand":
            price = 70.0
            demand_factor = 1.2
        elif scenario == "medium":
            price = 80.0
            demand_factor = 1.0
        else:  # high_price_low_demand
            price = 100.0
            demand_factor = 0.85
        
        # Update grid electricity price
        n.generators.loc[(scenario, "grid"), "marginal_cost"] = price
        
        # Update heat demand
        demand = base_demand * demand_factor
        n.loads_t.p_set.loc[:, (scenario, "heat_demand")] = demand
        
        print(f"  {scenario:25s} | Price: {price:4.0f} EUR/MWh | Avg demand: {demand.mean():.3f} MW")
    
    return n


def optimize_dispatch(n):
    """Run dispatch-only optimization (all capacities fixed)."""
    print("\n" + "=" * 70)
    print("Optimizing Dispatch (Fixed Capacities)")
    print("=" * 70)
    
    status, condition = n.optimize(
        dispatch_only=True,
        solver_name="highs"
    )
    
    print(f"\nOptimization Status: {status}")
    print(f"Condition: {condition}")
    
    if status == "ok":
        print(f"\n" + "=" * 70)
        print("Results")
        print("=" * 70)
        
        # Objective value per scenario
        print(f"\nExpected total cost (weighted): {n.objective:.2f} EUR")
        
        # Results per scenario
        for scenario in n.scenarios:
            print(f"\n--- Scenario: {scenario} ---")
            
            # Total electricity consumption
            grid_gen = n.generators_t.p.loc[:, (scenario, "grid")].sum()
            print(f"  Total electricity from grid: {grid_gen:.2f} MWh")
            
            # Heat pump usage (p0 is input, p1 is output - negative by convention)
            hp_elec = n.links_t.p0.loc[:, (scenario, "heat_pump")].sum()
            hp_heat = -n.links_t.p1.loc[:, (scenario, "heat_pump")].sum()  # Negative sign for output
            print(f"  Heat pump electricity: {hp_elec:.2f} MWh")
            print(f"  Heat pump heat output: {hp_heat:.2f} MWh")
            print(f"  Heat pump avg COP: {hp_heat/hp_elec if hp_elec > 0 else 0:.2f}")
            
            # Boiler usage  
            boiler_heat = n.generators_t.p.loc[:, (scenario, "gas_boiler")].sum()
            print(f"  Gas boiler heat output: {boiler_heat:.2f} MWh")
            
            # Total heat demand
            total_demand = n.loads_t.p.loc[:, (scenario, "heat_demand")].sum()
            print(f"  Total heat demand: {total_demand:.2f} MWh")
            
            # Electricity price
            elec_price = n.generators.loc[(scenario, "grid"), "marginal_cost"]
            print(f"  Electricity price: {elec_price:.0f} EUR/MWh")
            
            # Cost breakdown
            elec_cost = grid_gen * elec_price
            gas_cost = boiler_heat * 100  # 100 EUR/MWh
            total_cost = elec_cost + gas_cost
            print(f"  Electricity cost: {elec_cost:.2f} EUR")
            print(f"  Gas cost: {gas_cost:.2f} EUR")
            print(f"  Total cost: {total_cost:.2f} EUR")
        
        print(f"\n" + "=" * 70)
        print("Key Insights")
        print("=" * 70)
        print("- Low price scenario: Heat pump heavily used (cheap electricity)")
        print("- High price scenario: More backup boiler usage (expensive electricity)")
        print("- Optimal dispatch adapts to price forecasts while respecting fixed capacities")
        print("- Expected cost is weighted average across probability distribution")
    
    return status, condition


def main():
    """Main execution."""
    # Create network
    n = create_network()
    
    print("\n" + "=" * 70)
    print("Network Summary")
    print("=" * 70)
    print(f"Fixed heat pump capacity:    {n.links.loc[('low_price_high_demand', 'heat_pump'), 'p_nom']:.1f} MW")
    print(f"Fixed backup boiler:         {n.generators.loc[('low_price_high_demand', 'gas_boiler'), 'p_nom']:.1f} MW")
    print(f"Scenarios:                   {len(n.scenarios)}")
    print(f"Snapshots:                   {len(n.snapshots)}")
    print("=" * 70)
    
    # Optimize
    status, condition = optimize_dispatch(n)
    
    if status == "ok":
        print(f"\n✓ Dispatch-only optimization successful!")
        print(f"✓ All capacities were fixed (no investment decisions)")
        print(f"✓ Optimal dispatch found for {len(n.scenarios)} scenarios")
    else:
        print(f"\n✗ Optimization failed: {status}")
    
    return n


if __name__ == "__main__":
    n = main()
