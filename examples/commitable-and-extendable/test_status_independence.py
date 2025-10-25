"""Verify that status is truly scenario-dependent in the optimization model."""

import sys
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pypsa
import pandas as pd
import numpy as np


def test_status_independence_across_scenarios():
    """Test if status can be DIFFERENT across scenarios."""
    
    print("=" * 70)
    print("Testing: Can Status be DIFFERENT across scenarios?")
    print("=" * 70)
    
    # Create network with extreme price differences
    n = pypsa.Network()
    
    snapshots = pd.date_range("2025-01-01", periods=6, freq="h")
    n.set_snapshots(snapshots)
    
    # Add buses
    n.add("Bus", "bus_electric", carrier="electric")
    n.add("Bus", "bus_gas", carrier="gas")
    
    # Add load (varying)
    load_pattern = [8, 12, 18, 20, 15, 10]
    n.add("Load", "demand", bus="bus_electric", p_set=load_pattern)
    
    # Add gas supply (will have different costs per scenario)
    n.add("Generator", "gas_supply", bus="bus_gas", p_nom=100)
    
    # Add committable gas turbine (high startup cost!)
    n.add(
        "Generator",
        "gas_turbine",
        bus="bus_electric",
        carrier="gas",
        p_nom_extendable=True,
        committable=True,
        marginal_cost=10,  # Operating cost
        capital_cost=50,
        p_min_pu=0.4,  # Minimum 40% when ON
        up_time_before=0,  # Can start immediately
        down_time_before=0,
    )
    
    # Add cheap renewable (high availability - CAN cover load alone)
    n.add(
        "Generator",
        "renewable",
        bus="bus_electric",
        p_nom_extendable=True,
        marginal_cost=0,
        capital_cost=100,
        p_max_pu=[0.9, 0.9, 0.9, 0.9, 0.9, 0.9],  # High constant availability
    )
    
    # Enable scenarios
    scenarios = {"cheap_gas": 0.5, "expensive_gas": 0.5}
    n.set_scenarios(scenarios)
    
    print("\n1. Scenario setup:")
    print("   cheap_gas: Gas costs 20 EUR/MWh")
    print("   expensive_gas: Gas costs 200 EUR/MWh (10x more!)")
    
    # Set VERY different gas prices
    n.generators.loc[("cheap_gas", "gas_supply"), "marginal_cost"] = 20
    n.generators.loc[("expensive_gas", "gas_supply"), "marginal_cost"] = 200
    
    print("\n2. Hypothesis:")
    print("   If status is scenario-dependent (wait-and-see):")
    print("     → cheap_gas: Gas turbine should run (gas is cheap)")
    print("     → expensive_gas: Gas turbine should stay OFF (gas too expensive)")
    print("")
    print("   If status is scenario-INDEPENDENT (non-anticipativity):")
    print("     → Both scenarios: Same on/off pattern")
    
    # Optimize
    print("\n3. Optimizing...")
    status = n.optimize()
    
    print(f"   Status: {status}")
    print(f"   Objective: {n.objective:.2f}")
    
    # Check status across scenarios
    print("\n4. Gas turbine STATUS by scenario:")
    
    if hasattr(n.generators_t, "status") and not n.generators_t.status.empty:
        status = n.generators_t.status
        
        for scenario in scenarios:
            if (scenario, "gas_turbine") in status.columns:
                scenario_status = status[(scenario, "gas_turbine")]
                print(f"\n   {scenario}:")
                print(f"   {scenario_status.to_list()}")
                print(f"   Total hours ON: {scenario_status.sum()}")
    
    # Check dispatch
    print("\n5. Gas turbine DISPATCH by scenario:")
    
    if hasattr(n.generators_t, "p") and not n.generators_t.p.empty:
        dispatch = n.generators_t.p
        
        for scenario in scenarios:
            if (scenario, "gas_turbine") in dispatch.columns:
                scenario_dispatch = dispatch[(scenario, "gas_turbine")]
                print(f"\n   {scenario}:")
                print(f"   {[f'{p:.1f}' for p in scenario_dispatch.to_list()]}")
                print(f"   Average: {scenario_dispatch.mean():.2f} MW")
    
    # Investment
    print("\n6. Gas turbine INVESTMENT (should be same):")
    print(f"   cheap_gas: {n.generators.loc[('cheap_gas', 'gas_turbine'), 'p_nom_opt']:.2f} MW")
    print(f"   expensive_gas: {n.generators.loc[('expensive_gas', 'gas_turbine'), 'p_nom_opt']:.2f} MW")
    
    # Analysis
    print("\n7. CONCLUSION:")
    
    if hasattr(n.generators_t, "status") and not n.generators_t.status.empty:
        status = n.generators_t.status
        cheap_status = status[("cheap_gas", "gas_turbine")]
        expensive_status = status[("expensive_gas", "gas_turbine")]
        
        if not cheap_status.equals(expensive_status):
            print("   ✅ Status is DIFFERENT across scenarios → scenario-dependent!")
            print("   ✅ This is CORRECT for wait-and-see decisions!")
            different_hours = (cheap_status != expensive_status).sum()
            print(f"   ✅ Status differs in {different_hours} out of {len(cheap_status)} hours")
        else:
            print("   ❌ Status is IDENTICAL across scenarios → scenario-INDEPENDENT!")
            print("   ❌ This means status is treated as first-stage decision (non-anticipativity)")
            print("   ❌ This is SUBOPTIMAL for operational decisions!")
    
    print("=" * 70)
    
    return n


if __name__ == "__main__":
    n = test_status_independence_across_scenarios()
