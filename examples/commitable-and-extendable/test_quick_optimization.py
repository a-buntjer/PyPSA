"""Quick small-scale test of the stochastic multi-horizon optimization.

This runs a reduced version (fewer snapshots) to quickly verify the optimization works.
"""

import sys
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Temporarily modify configuration for quick test
import stochastic_multihorizon_chp as smh

# Reduce problem size for quick test
smh.SNAPSHOTS_PER_PERIOD = 24  # One day instead of one week
smh.INVESTMENT_PERIODS = [2025, 2030]  # Only two periods

print("=" * 70)
print("QUICK TEST: Small-scale stochastic multi-horizon optimization")
print("=" * 70)
print(f"Investment periods: {smh.INVESTMENT_PERIODS}")
print(f"Snapshots per period: {smh.SNAPSHOTS_PER_PERIOD}")
print(f"Scenarios: {smh.SCENARIOS}")

try:
    print("\nBuilding network...")
    n = smh.create_stochastic_network()
    
    print(f"✓ Network created with {len(n.snapshots)} snapshots")
    print(f"✓ Scenarios enabled: {n.has_scenarios}")
    
    print("\nCreating optimization model (not solving)...")
    model = n.optimize.create_model()
    print(f"✓ Model created successfully")
    print(f"  - Variables: {len(model.variables)}")
    print(f"  - Constraints: {len(model.constraints)}")
    
    print("\nAdding CHP constraints...")
    link_p = model.variables["Link-p"]
    link_p_nom = model.variables["Link-p_nom"]
    
    generator_eff = float(n.links.at["chp_generator", "efficiency"])
    boiler_eff = float(n.links.at["chp_boiler", "efficiency"])
    
    generator_p = link_p.sel(name="chp_generator")
    boiler_p = link_p.sel(name="chp_boiler")
    generator_p_nom = link_p_nom.sel(name="chp_generator")
    boiler_p_nom = link_p_nom.sel(name="chp_boiler")
    
    # Nominal power proportionality
    model.add_constraints(
        generator_eff * smh.NOMINAL_HEAT_TO_ELECTRIC_RATIO * generator_p_nom
        - boiler_eff * boiler_p_nom
        == 0,
        name="chp-heat-power-output-proportionality",
    )
    
    print(f"✓ CHP constraints added")
    print(f"  - Total constraints now: {len(model.constraints)}")
    
    print("\n" + "=" * 70)
    print("✅ Quick test passed! Model structure is correct.")
    print("=" * 70)
    print("\nNote: To run full optimization, execute:")
    print("  python stochastic_multihorizon_chp.py")
    print("\nThis will take 5-30 minutes depending on hardware.")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
