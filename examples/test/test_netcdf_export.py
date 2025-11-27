"""Test NetCDF export/import for stochastic networks."""

import sys
sys.path.insert(0, 'C:/Users/A64620/Documents/pypsa_tryout/PyPSA')
import pypsa

print("=" * 70)
print("TEST 1: Import existing stochastic network from NetCDF")
print("=" * 70)

try:
    n = pypsa.Network('../commitable-and-extendable/stochastic_multihorizon_chp.nc')
    print(f'✓ Loaded network from NetCDF')
    print(f'  Has scenarios: {hasattr(n, "scenarios") and n.scenarios is not None}')
    if hasattr(n, 'scenarios') and n.scenarios is not None:
        print(f'  Scenarios: {list(n.scenarios.keys())}')
    print(f'  Objective: {n.objective:.2f}')
    print('✓ SUCCESS: Import works!')
except Exception as e:
    print(f'✗ ERROR during import: {type(e).__name__}')
    print(f'  Message: {e}')
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("TEST 2: Check what was actually saved in the NetCDF file")
print("=" * 70)

import xarray as xr

try:
    ds = xr.open_dataset('../commitable-and-extendable/stochastic_multihorizon_chp.nc')
    print(f"Dataset variables: {list(ds.data_vars)[:10]}...")
    print(f"Dataset dimensions: {dict(ds.dims)}")
    print(f"Dataset coords: {list(ds.coords)[:10]}...")
    ds.close()
except Exception as e:
    print(f"ERROR: {e}")
