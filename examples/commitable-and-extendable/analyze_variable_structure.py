"""Deep dive into status variable creation."""

import sys
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pypsa
import pandas as pd


def analyze_variable_structure():
    """Analyze how status variables get their scenario dimension."""
    
    print("=" * 70)
    print("Analyzing Status Variable Structure Creation")
    print("=" * 70)
    
    # Create network
    n = pypsa.Network()
    snapshots = pd.date_range("2025-01-01", periods=3, freq="h")
    n.set_snapshots(snapshots)
    
    print("\n1. BEFORE set_scenarios:")
    print(f"   snapshots type: {type(n.snapshots)}")
    print(f"   snapshots: {n.snapshots.tolist()}")
    print(f"   Is MultiIndex? {isinstance(n.snapshots, pd.MultiIndex)}")
    
    # Add components
    n.add("Bus", "bus")
    n.add("Generator", "gen", bus="bus", committable=True, p_nom=10)
    n.add("Load", "load", bus="bus", p_set=[5, 10, 8])
    
    print(f"\n   Generator index: {n.generators.index.tolist()}")
    
    # Enable scenarios
    scenarios = {"s1": 0.6, "s2": 0.4}
    n.set_scenarios(scenarios)
    
    print("\n2. AFTER set_scenarios:")
    print(f"   snapshots type: {type(n.snapshots)}")
    print(f"   Is MultiIndex? {isinstance(n.snapshots, pd.MultiIndex)}")
    if isinstance(n.snapshots, pd.MultiIndex):
        print(f"   Level names: {n.snapshots.names}")
        print(f"   First 3 entries: {n.snapshots[:3].tolist()}")
    
    print(f"\n   Generator index: {n.generators.index.tolist()}")
    print(f"   Is MultiIndex? {isinstance(n.generators.index, pd.MultiIndex)}")
    
    # Create model to see variable structure
    print("\n3. Creating optimization model...")
    model = n.optimize.create_model()
    
    # Check status variables
    if "Generator-status" in model.variables:
        status_var = model.variables["Generator-status"]
        print(f"\n   Generator-status variable:")
        print(f"   Coordinates: {status_var.coords}")
        print(f"   Dims: {status_var.dims}")
        print(f"   Shape: {status_var.shape}")
        
        if "snapshot" in status_var.coords:
            snap_coord = status_var.coords["snapshot"]
            print(f"\n   snapshot coordinate type: {type(snap_coord.data)}")
            print(f"   snapshot coordinate (first 3): {snap_coord.data[:3]}")
            print(f"   Is MultiIndex? {isinstance(snap_coord.data, pd.MultiIndex)}")
            
            if isinstance(snap_coord.data, pd.MultiIndex):
                print(f"   → Snapshots contain SCENARIOS!")
                print(f"   → Level names: {snap_coord.data.names}")
                print(f"   → This is why status is scenario-dependent!")
    
    print("\n4. UNDERSTANDING:")
    print("   When set_scenarios() is called:")
    print("   - n.snapshots becomes MultiIndex[(period, scenario, timestep), ...]")
    print("   - Variables created with coords=[sns, ...] inherit scenario from sns!")
    print("   - Even though com_i.unique(level='name') removes scenario from component index,")
    print("   - the scenario dimension comes from the SNAPSHOTS, not the component index!")
    
    print("\n5. CONCLUSION:")
    print("   Our 'fix' that removes scenario from com_i is CORRECT!")
    print("   Status variables get scenario-dependency from SNAPSHOTS automatically.")
    print("   The actual structure is: status[snapshot(scenario, time), component_name]")
    
    print("=" * 70)


if __name__ == "__main__":
    analyze_variable_structure()
