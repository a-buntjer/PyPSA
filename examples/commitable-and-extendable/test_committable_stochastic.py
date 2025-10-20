"""
Test if committable + stochastic + multi-investment works in PyPSA.

This is a minimal test to see if the combination is feasible or if there's a bug.
"""

import sys
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import pypsa

def test_simple_committable_stochastic():
    """Test a minimal committable + stochastic network."""
    
    print("Creating minimal network with committable + stochastic...")
    
    # Create network with multi-investment periods
    n = pypsa.Network()
    
    # Create snapshots first (just 24 hours)
    snapshots = pd.date_range("2025-01-01", periods=24, freq="h")
    n.set_snapshots(snapshots)
    
    # Then set investment periods (this will replicate snapshots)
    n.set_investment_periods([2025, 2030])
    
    # Add bus
    n.add("Bus", "bus1")
    
    # Add a simple load
    n.add(
        "Load",
        "load1",
        bus="bus1",
        p_set=100,
    )
    
    # Add a committable generator
    n.add(
        "Generator",
        "gen1",
        bus="bus1",
        p_nom=150,
        marginal_cost=50,
        committable=True,
        min_up_time=2,
        min_down_time=2,
        up_time_before=0,
        down_time_before=5,
    )
    
    print(f"Network has {len(n.snapshots)} snapshots")
    print(f"Investment periods: {n.investment_periods.tolist()}")
    
    # Now enable stochastic scenarios
    print("\nEnabling stochastic scenarios...")
    n.set_scenarios(["scenario_A", "scenario_B"])
    
    print(f"Scenarios: {n.scenarios.tolist()}")
    print(f"Generator index after set_scenarios: {n.generators.index.tolist()}")
    
    # Try to optimize
    print("\nAttempting optimization with committable + stochastic...")
    try:
        n.optimize(solver_name="highs")
        print(f"✅ SUCCESS! Optimization worked!")
        print(f"Objective: {n.objective:.2f}")
        return True
    except IndexError as e:
        print(f"❌ FAILED with IndexError: {e}")
        print(f"This confirms that committable + stochastic has a bug in PyPSA")
        return False
    except Exception as e:
        print(f"❌ FAILED with {type(e).__name__}: {e}")
        return False


def test_committable_multi_investment():
    """Test committable + multi-investment (without stochastic)."""
    
    print("\n" + "="*70)
    print("Testing committable + multi-investment (NO stochastic)...")
    
    n = pypsa.Network()
    
    snapshots = pd.date_range("2025-01-01", periods=24, freq="h")
    n.set_snapshots(snapshots)
    
    n.set_investment_periods([2025, 2030])
    
    n.add("Bus", "bus1")
    
    n.add(
        "Load",
        "load1",
        bus="bus1",
        p_set=100,
    )
    
    n.add(
        "Generator",
        "gen1",
        bus="bus1",
        p_nom=150,
        marginal_cost=50,
        committable=True,
        min_up_time=2,
        min_down_time=2,
        up_time_before=0,
        down_time_before=5,
    )
    
    print(f"Network has {len(n.snapshots)} snapshots")
    print(f"Investment periods: {n.investment_periods.tolist()}")
    
    try:
        n.optimize(solver_name="highs")
        print(f"✅ SUCCESS! committable + multi-investment works!")
        print(f"Objective: {n.objective:.2f}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        return False


def test_committable_stochastic_no_multiinvest():
    """Test committable + stochastic (without multi-investment)."""
    
    print("\n" + "="*70)
    print("Testing committable + stochastic (NO multi-investment)...")
    
    n = pypsa.Network()
    
    # Single period, no multi-investment
    snapshots = pd.date_range("2025-01-01", periods=24, freq="h")
    n.set_snapshots(snapshots)
    
    n.add("Bus", "bus1")
    
    n.add(
        "Load",
        "load1",
        bus="bus1",
        p_set=100,
    )
    
    n.add(
        "Generator",
        "gen1",
        bus="bus1",
        p_nom=150,
        marginal_cost=50,
        committable=True,  # Committable enabled
        min_up_time=2,
        min_down_time=2,
        up_time_before=0,
        down_time_before=5,
    )
    
    # Enable stochastic scenarios
    n.set_scenarios(["scenario_A", "scenario_B"])
    
    print(f"Network has {len(n.snapshots)} snapshots")
    print(f"Scenarios: {n.scenarios.tolist()}")
    print(f"Generator index: {n.generators.index.tolist()}")
    
    try:
        n.optimize(solver_name="highs")
        print(f"✅ SUCCESS! committable + stochastic (no multi-invest) works!")
        print(f"Objective: {n.objective:.2f}")
        return True
    except IndexError as e:
        print(f"❌ FAILED with IndexError: {e}")
        print(f"Bug occurs already with committable + stochastic (even without multi-investment)")
        return False
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_stochastic_only():
    """Test stochastic (without committable)."""
    
    print("\n" + "="*70)
    print("Testing stochastic only (NO committable)...")
    
    n = pypsa.Network()
    
    snapshots = pd.date_range("2025-01-01", periods=24, freq="h")
    n.set_snapshots(snapshots)
    
    n.set_investment_periods([2025, 2030])
    
    n.add("Bus", "bus1")
    
    n.add(
        "Load",
        "load1",
        bus="bus1",
        p_set=100,
    )
    
    n.add(
        "Generator",
        "gen1",
        bus="bus1",
        p_nom=150,
        marginal_cost=50,
        committable=False,  # NOT committable
    )
    
    n.set_scenarios(["scenario_A", "scenario_B"])
    
    print(f"Network has {len(n.snapshots)} snapshots")
    print(f"Investment periods: {n.investment_periods.tolist()}")
    print(f"Scenarios: {n.scenarios.tolist()}")
    
    try:
        n.optimize(solver_name="highs")
        print(f"✅ SUCCESS! stochastic + multi-investment works!")
        print(f"Objective: {n.objective:.2f}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    print("="*70)
    print("TESTING FEATURE COMPATIBILITY IN PyPSA")
    print("="*70)
    
    # Test 1: Committable + Multi-investment (should work)
    result1 = test_committable_multi_investment()
    
    # Test 2: Stochastic + Multi-investment (should work)
    result2 = test_stochastic_only()
    
    # Test 3: Committable + Stochastic (no multi-investment) - NEW TEST!
    result3 = test_committable_stochastic_no_multiinvest()
    
    # Test 4: Committable + Stochastic + Multi-investment (the question!)
    result4 = test_simple_committable_stochastic()
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Committable + Multi-investment:           {'✅ WORKS' if result1 else '❌ FAILS'}")
    print(f"Stochastic + Multi-investment:            {'✅ WORKS' if result2 else '❌ FAILS'}")
    print(f"Committable + Stochastic (single period): {'✅ WORKS' if result3 else '❌ FAILS'}")
    print(f"Committable + Stochastic + Multi-invest:  {'✅ WORKS' if result4 else '❌ FAILS'}")
    print("="*70)
    
    if not result3 and not result4:
        print("\n⚠️  CONCLUSION: PyPSA has a fundamental bug with committable + stochastic!")
        print("The bug occurs even WITHOUT multi-investment. The error is in")
        print("pypsa/optimization/constraints.py at line 469 where it tries to")
        print("index initially_up.values with multi-dimensional array.")
    elif not result4:
        print("\n⚠️  CONCLUSION: Committable + Stochastic works alone, but fails when")
        print("combined with multi-investment. This is a more specific bug in PyPSA")
        print("related to handling committable constraints with both scenarios AND")
        print("investment periods simultaneously.")
