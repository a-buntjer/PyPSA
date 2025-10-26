"""Test script to verify if status variables are scenario-dependent."""

import sys
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pypsa
import pandas as pd
import numpy as np


def test_status_scenario_dependency():
    """Test if status variables have scenario dimension."""
    
    print("=" * 70)
    print("Testing Status Variable Scenario Dependency")
    print("=" * 70)
    
    # Create simple network
    n = pypsa.Network()
    
    # Set snapshots (just 4 hours for quick test)
    snapshots = pd.date_range("2025-01-01", periods=4, freq="h")
    n.set_snapshots(snapshots)
    
    # Add buses
    n.add("Bus", "bus_electric", carrier="electric")
    n.add("Bus", "bus_gas", carrier="gas")
    
    # Add load
    n.add("Load", "demand", bus="bus_electric", p_set=[10, 15, 20, 12])
    
    # Add gas supply
    n.add("Generator", "gas_supply", bus="bus_gas", p_nom=100, marginal_cost=50)
    
    # Add committable generator
    n.add(
        "Generator",
        "gas_turbine",
        bus="bus_electric",
        carrier="gas",
        p_nom_extendable=True,
        committable=True,
        marginal_cost=100,
        capital_cost=10,
    )
    
    # Add committable link (CHP)
    n.add(
        "Link",
        "chp",
        bus0="bus_gas",
        bus1="bus_electric",
        efficiency=0.4,
        p_nom_extendable=True,
        committable=True,
        marginal_cost=80,
        capital_cost=15,
        p_min_pu=0.3,
    )
    
    print("\n1. Network structure WITHOUT scenarios:")
    print(f"   Generators index: {n.generators.index.tolist()}")
    print(f"   Links index: {n.links.index.tolist()}")
    print(f"   Is MultiIndex? Generators: {isinstance(n.generators.index, pd.MultiIndex)}")
    print(f"   Is MultiIndex? Links: {isinstance(n.links.index, pd.MultiIndex)}")
    
    # Enable scenarios
    scenarios = {"low_cost": 0.5, "high_cost": 0.5}
    n.set_scenarios(scenarios)
    
    print("\n2. Network structure WITH scenarios:")
    print(f"   Generators index: {n.generators.index[:4].tolist()}...")  # First 4
    print(f"   Links index: {n.links.index.tolist()}")
    print(f"   Is MultiIndex? Generators: {isinstance(n.generators.index, pd.MultiIndex)}")
    print(f"   Is MultiIndex? Links: {isinstance(n.links.index, pd.MultiIndex)}")
    
    # Set scenario-specific marginal costs
    for scenario in scenarios:
        if scenario == "low_cost":
            n.generators.loc[(scenario, "gas_supply"), "marginal_cost"] = 30
        else:
            n.generators.loc[(scenario, "gas_supply"), "marginal_cost"] = 100
    
    print("\n3. Scenario-specific parameters:")
    print(f"   Gas supply cost (low_cost): {n.generators.loc[('low_cost', 'gas_supply'), 'marginal_cost']}")
    print(f"   Gas supply cost (high_cost): {n.generators.loc[('high_cost', 'gas_supply'), 'marginal_cost']}")
    
    # Optimize
    print("\n4. Running optimization...")
    status = n.optimize()
    
    print(f"   Status: {status}")
    print(f"   Objective: {n.objective:.2f}")
    
    # Check status variables structure
    print("\n5. Status variable structure AFTER optimization:")
    
    # Generator status
    if hasattr(n, "generators_t") and hasattr(n.generators_t, "status"):
        gen_status = n.generators_t.status
        print(f"   Generator status columns: {gen_status.columns.tolist()}")
        print(f"   Is MultiIndex? {isinstance(gen_status.columns, pd.MultiIndex)}")
        
        if "gas_turbine" in gen_status.columns:
            print("\n   Gas turbine status (no scenarios in columns):")
            print(gen_status["gas_turbine"])
        elif isinstance(gen_status.columns, pd.MultiIndex):
            print("\n   Gas turbine status BY SCENARIO:")
            for scenario in scenarios:
                if (scenario, "gas_turbine") in gen_status.columns:
                    print(f"\n   Scenario '{scenario}':")
                    print(gen_status[(scenario, "gas_turbine")])
    
    # Link status
    if hasattr(n, "links_t") and hasattr(n.links_t, "status"):
        link_status = n.links_t.status
        print(f"\n   Link status columns: {link_status.columns.tolist()}")
        print(f"   Is MultiIndex? {isinstance(link_status.columns, pd.MultiIndex)}")
        
        if "chp" in link_status.columns:
            print("\n   CHP status (no scenarios in columns):")
            print(link_status["chp"])
        elif isinstance(link_status.columns, pd.MultiIndex):
            print("\n   CHP status BY SCENARIO:")
            for scenario in scenarios:
                if (scenario, "chp") in link_status.columns:
                    print(f"\n   Scenario '{scenario}':")
                    print(link_status[(scenario, "chp")])
    
    # Check dispatch (should be scenario-dependent)
    print("\n6. Dispatch (should be scenario-dependent):")
    if hasattr(n, "generators_t") and hasattr(n.generators_t, "p"):
        gen_p = n.generators_t.p
        print(f"   Generator dispatch columns (first 4): {gen_p.columns[:4].tolist()}")
        print(f"   Is MultiIndex? {isinstance(gen_p.columns, pd.MultiIndex)}")
    
    # Check investment decisions (should be scenario-INDEPENDENT)
    print("\n7. Investment decisions (should be scenario-INDEPENDENT):")
    print(f"   Gas turbine p_nom_opt:")
    if isinstance(n.generators.index, pd.MultiIndex):
        for scenario in scenarios:
            val = n.generators.loc[(scenario, "gas_turbine"), "p_nom_opt"]
            print(f"      {scenario}: {val:.2f} MW")
    else:
        print(f"      {n.generators.loc['gas_turbine', 'p_nom_opt']:.2f} MW (no scenarios)")
    
    print("\n8. CONCLUSION:")
    if hasattr(n, "generators_t") and hasattr(n.generators_t, "status"):
        has_scenario_status = isinstance(n.generators_t.status.columns, pd.MultiIndex)
        if has_scenario_status:
            print("   ✅ Status variables ARE scenario-dependent (correct!)")
        else:
            print("   ❌ Status variables are NOT scenario-dependent (current bug!)")
    else:
        print("   ⚠️ No status variables found in generators_t")
    
    print("=" * 70)
    
    return n


if __name__ == "__main__":
    n = test_status_scenario_dependency()
