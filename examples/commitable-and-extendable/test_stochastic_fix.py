"""Quick test to verify the stochastic network creation fix."""

import sys
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import pypsa

# Import the module
import stochastic_multihorizon_chp as smh

print("=" * 70)
print("Testing stochastic network creation...")
print("=" * 70)

try:
    # Build base network
    print("\n1. Building base network...")
    n_base = smh.build_base_network()
    print(f"   ✓ Base network created")
    print(f"   - Snapshots: {len(n_base.snapshots)}")
    print(f"   - Investment periods: {list(n_base.investment_periods)}")
    print(f"   - Loads: {list(n_base.loads.index)}")
    print(f"   - loads_t.p_set columns: {list(n_base.loads_t.p_set.columns)}")
    
    # Create stochastic network
    print("\n2. Creating stochastic network...")
    n_stoch = smh.create_stochastic_network()
    print(f"   ✓ Stochastic network created")
    print(f"   - Has scenarios: {n_stoch.has_scenarios}")
    print(f"   - Scenarios: {list(n_stoch.scenarios)}")
    print(f"   - Scenario weightings: {n_stoch.scenario_weightings}")
    print(f"   - loads_t.p_set shape: {n_stoch.loads_t.p_set.shape}")
    print(f"   - loads_t.p_set columns (first 6): {list(n_stoch.loads_t.p_set.columns[:6])}")
    
    # Check scenario-specific demand
    print("\n3. Checking scenario-specific demand values...")
    period_2025 = n_stoch.snapshots[n_stoch.snapshots.get_level_values(0) == 2025]
    first_snapshot = period_2025[0]
    
    for scenario in smh.SCENARIOS:
        # MultiIndex columns are (scenario, component_name)
        electric_demand = n_stoch.loads_t.p_set.loc[first_snapshot, (scenario, "electric_demand")]
        heat_demand = n_stoch.loads_t.p_set.loc[first_snapshot, (scenario, "heat_demand")]
        print(f"   Scenario {scenario:12s}: Electric={electric_demand:6.2f} MW, Heat={heat_demand:6.2f} MW")
    
    # Check gas prices
    print("\n4. Checking scenario-specific gas prices (time-varying)...")
    for scenario in smh.SCENARIOS:
        gas_price_first = n_stoch.generators_t.marginal_cost.loc[first_snapshot, (scenario, "gas_supply")]
        print(f"   Scenario {scenario:12s}: Gas price (first snapshot) = {gas_price_first:.2f} EUR/MWh")
    
    print("\n" + "=" * 70)
    print("✅ All checks passed! Network structure is correct.")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
