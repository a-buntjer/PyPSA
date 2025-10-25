"""Test to inspect variable dimensions in the optimization model."""

import pypsa
import numpy as np

# Create simple network
n = pypsa.Network()
n.set_snapshots(range(3))

# Add bus
n.add("Bus", "bus")

# Add load
n.add("Load", "load", bus="bus", p_set=[10, 15, 12])

# Add gas supply (cheap in scenario 1, expensive in scenario 2)
n.add(
    "Generator",
    "gas_supply",
    bus="bus",
    carrier="gas",
    p_nom=50,
    marginal_cost=20,  # Will be changed per scenario
)

# Add committable + extendable gas turbine
n.add(
    "Generator",
    "gas_turbine",
    bus="bus",
    carrier="gas",
    p_nom_extendable=True,
    p_nom_min=0,
    p_nom_max=30,
    committable=True,
    min_up_time=2,
    min_down_time=2,
    up_time_before=0,
    down_time_before=3,
    marginal_cost=50,
    capital_cost=100,
)

# Enable scenarios
scenarios = {"cheap": 0.5, "expensive": 0.5}
n.set_scenarios(scenarios)

# Set different gas prices
n.generators.loc[("cheap", "gas_supply"), "marginal_cost"] = 20
n.generators.loc[("expensive", "gas_supply"), "marginal_cost"] = 200

print("=" * 70)
print("Variable Dimensions Check")
print("=" * 70)

# Optimize
n.optimize(solver_name="highs")

print("\n1. Status variable (should be scenario-dependent):")
status_var = n.model["Generator-status"]
print(f"   Shape: {status_var.shape}")
print(f"   Dims: {status_var.dims}")
print(f"   Coords: {list(status_var.coords.keys())}")
if "scenario" in status_var.dims:
    print(f"   ✓ Has scenario dimension!")
else:
    print(f"   ✗ NO scenario dimension - BUG!")

print("\n2. p_nom variable (should be scenario-INDEPENDENT):")
p_nom_var = n.model["Generator-p_nom"]
print(f"   Shape: {p_nom_var.shape}")
print(f"   Dims: {p_nom_var.dims}")
print(f"   Coords: {list(p_nom_var.coords.keys())}")
if "scenario" in p_nom_var.dims:
    print(f"   ✗ Has scenario dimension - should NOT have it!")
else:
    print(f"   ✓ NO scenario dimension (correct for first-stage investment)")

print("\n3. Dispatch variable (should be scenario-dependent):")
p_var = n.model["Generator-p"]
print(f"   Shape: {p_var.shape}")
print(f"   Dims: {p_var.dims}")
print(f"   Coords: {list(p_var.coords.keys())}")
if "scenario" in p_var.dims:
    print(f"   ✓ Has scenario dimension!")
else:
    print(f"   ✗ NO scenario dimension - BUG!")

print("\n4. Actual status values:")
for scenario in ["cheap", "expensive"]:
    status_sol = n.generators_t.status.loc[:, (scenario, "gas_turbine")].values
    print(f"   {scenario}: {status_sol}")

print("\n5. Constraint check - look at a Big-M constraint:")
if "Generator-com-ext-p-lower" in n.model.constraints:
    constraint = n.model.constraints["Generator-com-ext-p-lower"]
    print(f"   Constraint dims: {constraint.dims}")
    print(f"   Constraint coords: {list(constraint.coords.keys())}")
    if "scenario" in constraint.dims:
        print(f"   ✓ Constraint has scenario dimension!")
    else:
        print(f"   ✗ Constraint missing scenario dimension!")
else:
    print("   Constraint not found")

print("=" * 70)
