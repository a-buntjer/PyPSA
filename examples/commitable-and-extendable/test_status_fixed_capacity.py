"""
Test: Can committable status be DIFFERENT across scenarios?

This test checks if the status variable is truly scenario-dependent (wait-and-see)
or if it's forced to be scenario-independent (non-anticipativity).

Key insight: We use a FIXED capacity gas turbine (not extendable) so that the
investment decision doesn't influence the operational decision.
"""

import pypsa
import numpy as np

if __name__ == "__main__":
    print("=" * 70)
    print("Testing: Can Status be DIFFERENT across scenarios?")
    print("=" * 70)
    
    # Create network
    n = pypsa.Network()
    n.set_snapshots(range(6))
    
    # Add bus
    n.add("Bus", "bus_electric", carrier="AC")
    
    # Add load (small enough that renewable alone could cover it)
    load_pattern = [5, 7, 10, 12, 8, 6]
    n.add("Load", "demand", bus="bus_electric", p_set=load_pattern)
    
    # Add committable gas turbine with FIXED capacity (not extendable!)
    # This ensures investment decision doesn't influence operational choice
    # marginal_cost will be set per scenario
    n.add(
        "Generator",
        "gas_turbine",
        bus="bus_electric",
        carrier="gas",
        p_nom=20,  # FIXED capacity - already installed!
        p_nom_extendable=False,  # NOT extendable
        committable=True,
        marginal_cost=30,  # Will be overridden per scenario
        p_min_pu=0.4,  # Minimum 40% when ON
        up_time_before=0,
        down_time_before=0,
    )
    
    # Add renewable with fixed capacity (CAN cover full load with small shortage!)
    n.add(
        "Generator",
        "renewable",
        bus="bus_electric",
        p_nom=13,  # Fixed 13 MW - enough for 13/12 = 108% of peak load!
        p_nom_extendable=False,
        marginal_cost=0,
        p_max_pu=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0],  # Always available
    )
    
    # Add load shedding option (expensive!)
    n.add(
        "Generator",
        "load_shed",
        bus="bus_electric",
        p_nom=20,
        marginal_cost=5000,  # Very expensive emergency option
    )
    
    # Enable scenarios
    scenarios = {"cheap_gas": 0.5, "expensive_gas": 0.5}
    n.set_scenarios(scenarios)
    
    print("\n1. Scenario setup (BOTH have FIXED capacities - no investment decision):")
    print("   - Renewable: 13 MW fixed capacity, 0 EUR/MWh - CAN cover load (max 12 MW)!")
    print("   - Gas turbine: 20 MW fixed capacity")
    print("   - Load shedding: Available at 5000 EUR/MWh (emergency)")
    print()
    print("   cheap_gas: Gas turbine costs 30 EUR/MWh")
    print("   expensive_gas: Gas turbine costs 210 EUR/MWh (7x more!)")
    
    # Set VERY different gas turbine operating costs per scenario
    n.generators.loc[("cheap_gas", "gas_turbine"), "marginal_cost"] = 30
    n.generators.loc[("expensive_gas", "gas_turbine"), "marginal_cost"] = 210
    
    print("\n2. Hypothesis:")
    print("   If status is scenario-dependent (wait-and-see):")
    print("     -> cheap_gas: MIGHT use gas turbine (cheap at 30 EUR/MWh total)")
    print("     -> expensive_gas: Should NOT use gas turbine (expensive at 210 EUR/MWh)")
    print("                      Renewable alone can cover most of the load!")
    print()
    print("   If status is scenario-INDEPENDENT (non-anticipativity):")
    print("     -> Both scenarios: Same on/off pattern")
    
    print("\n3. Building model...")
    n.optimize.create_model()
    
    print("\n   Model variables:")
    for var_name in n.model.variables:
        var = n.model[var_name]
        print(f"   - {var_name}: dims={var.dims}, shape={var.shape}")
    
    print("\n   Model constraints (sample):")
    constr_names = [name for name in dir(n.model.constraints) if not name.startswith('_')][:15]
    for constr_name in constr_names:
        try:
            constr = getattr(n.model.constraints, constr_name)
            if hasattr(constr, 'dims'):
                print(f"   - {constr_name}: dims={constr.dims}")
        except:
            pass
    
    print("\n3. Optimizing...")
    status_result = n.optimize(solver_name="highs")
    
    print(f"   Status: {status_result}")
    print(f"   Objective: {n.objective:.2f}")
    
    # Check status
    print("\n4. Gas turbine STATUS by scenario:")
    print()
    for scenario in ["cheap_gas", "expensive_gas"]:
        status = n.generators_t.status.loc[:, (scenario, "gas_turbine")].values
        print(f"   {scenario}:")
        print(f"   {status}")
        print(f"   Total hours ON: {status.sum()}")
        print()
    
    # Check dispatch and calculate costs
    print("5. Gas turbine DISPATCH by scenario:")
    print()
    total_cost_cheap = 0
    total_cost_expensive = 0
    for scenario in ["cheap_gas", "expensive_gas"]:
        dispatch = n.generators_t.p.loc[:, (scenario, "gas_turbine")].values
        turbine_mc = n.generators.loc[(scenario, "gas_turbine"), "marginal_cost"]
        cost = (dispatch * turbine_mc).sum()
        
        if scenario == "cheap_gas":
            total_cost_cheap = cost
        else:
            total_cost_expensive = cost
            
        print(f"   {scenario}:")
        print(f"   Dispatch: {[f'{x:.1f}' for x in dispatch]}")
        print(f"   Gas turbine marginal cost: {turbine_mc:.1f} EUR/MWh")
        print(f"   Total cost: {cost:.2f} EUR")
        print()
    
    expected_cost = 0.5 * total_cost_cheap + 0.5 * total_cost_expensive
    print(f"   Expected cost (weighted by scenario probability): {expected_cost:.2f} EUR")
    print()
    
    # Check renewable dispatch
    print("6. Renewable DISPATCH by scenario:")
    print()
    for scenario in ["cheap_gas", "expensive_gas"]:
        dispatch = n.generators_t.p.loc[:, (scenario, "renewable")].values
        print(f"   {scenario}:")
        print(f"   {[f'{x:.1f}' for x in dispatch]}")
        print(f"   Average: {dispatch.mean():.2f} MW")
        print()
    
    # Conclusion
    status_cheap = n.generators_t.status.loc[:, ("cheap_gas", "gas_turbine")].values
    status_expensive = n.generators_t.status.loc[:, ("expensive_gas", "gas_turbine")].values
    
    print("7. CONCLUSION:")
    if np.array_equal(status_cheap, status_expensive):
        print("   [X] Status is IDENTICAL across scenarios -> scenario-INDEPENDENT!")
        print("   [X] This means status is treated as first-stage decision (non-anticipativity)")
        print("   [X] This is SUBOPTIMAL for operational decisions!")
    else:
        print("   [OK] Status is DIFFERENT across scenarios -> scenario-DEPENDENT!")
        print("   [OK] This means status is a wait-and-see decision (correct!)")
        print("   [OK] The optimizer can choose different on/off patterns per scenario!")
    print("=" * 70)
