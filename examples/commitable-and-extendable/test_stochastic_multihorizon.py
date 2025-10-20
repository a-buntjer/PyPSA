"""Quick syntax and import check for the stochastic multihorizon example."""

import sys
import pathlib

# Add repo root to path
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

print("Testing imports...")
import numpy as np
import pandas as pd

print("Testing PyPSA import...")
import pypsa

print(f"PyPSA version: {pypsa.__version__}")

print("\nChecking stochastic_multihorizon_chp module...")
try:
    # Try importing the module to check for syntax errors
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "stochastic_multihorizon_chp",
        pathlib.Path(__file__).parent / "stochastic_multihorizon_chp.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    print("✓ Module imports successfully")
    print(f"✓ Found {len(module.SCENARIOS)} scenarios")
    print(f"✓ Found {len(module.INVESTMENT_PERIODS)} investment periods")
    
    # Test basic network building without optimization
    print("\nTesting base network construction...")
    n = module.build_base_network()
    print(f"✓ Base network created with {len(n.snapshots)} snapshots")
    print(f"✓ Investment periods: {list(n.investment_periods)}")
    print(f"✓ Components: {len(n.generators)} generators, {len(n.links)} links, {len(n.stores)} stores")
    
    print("\n✅ All checks passed!")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
