"""Debug scenario matching issue."""

import sys
sys.path.insert(0, 'C:/Users/A64620/Documents/pypsa_tryout/PyPSA')
import pypsa

n1 = pypsa.Network('../commitable-and-extendable/stochastic_multihorizon_chp.nc')

print("Network 1 scenarios:")
print(f"  Type: {type(n1.scenarios)}")
print(f"  Value: {n1.scenarios}")
print(f"  List: {list(n1.scenarios)}")

n1.export_to_netcdf('test_scenario_check.nc')

n2 = pypsa.Network('test_scenario_check.nc')

print("\nNetwork 2 scenarios:")
print(f"  Type: {type(n2.scenarios)}")
print(f"  Value: {n2.scenarios}")
print(f"  List: {list(n2.scenarios)}")

print("\nComparison:")
print(f"  n1.scenarios == n2.scenarios: {n1.scenarios.equals(n2.scenarios)}")
print(f"  list(n1.scenarios) == list(n2.scenarios): {list(n1.scenarios) == list(n2.scenarios)}")
print(f"  set(n1.scenarios) == set(n2.scenarios): {set(n1.scenarios) == set(n2.scenarios)}")
