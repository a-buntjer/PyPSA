"""
DEFINITIVER TEST: Sind die BHKW-Constraints überhaupt lösbar?

Wir bauen ein MINIMALES System mit nur BHKW + fixen Lasten und prüfen,
ob die Optimierung eine Lösung findet.
"""

import pypsa
import pandas as pd
import numpy as np

print("=" * 80)
print("MINIMALER FEASIBILITY-TEST")
print("=" * 80)

# Minimales System: Nur BHKW, keine Alternativen
n = pypsa.Network()
n.set_snapshots(pd.date_range("2020-01-01", periods=3, freq="h"))

# Buses
n.add("Bus", "bus_gas")
n.add("Bus", "bus_fuel_internal")
n.add("Bus", "bus_electric")
n.add("Bus", "bus_heat")

# Unbegrenzte Gasversorgung (kostenlos für diesen Test)
n.add("Generator", "gas_source", bus="bus_gas", p_nom=1000, marginal_cost=0)

# Konstante Lasten
n.add("Load", "electric_demand", bus="bus_electric", p_set=3.8)  # Exakt 1 BHKW bei Volllast
n.add("Load", "heat_demand", bus="bus_heat", p_set=4.8)  # Exakt 1 BHKW bei Volllast

# BHKW wie in Ihrem Skript
BCHP_THERMAL_EFF = 0.48
BCHP_ELECTRIC_EFF = 0.38
BCHP_QP_RATIO = BCHP_THERMAL_EFF / BCHP_ELECTRIC_EFF
BCHP_COUPLING_BAND = 0.15
BCHP_THERMAL_BIAS = 0.20

n.add(
    "Link",
    "chp_fuel",
    bus0="bus_gas",
    bus1="bus_fuel_internal",
    efficiency=1.0,
    p_nom=100,  # Fest, nicht extendable für diesen Test
)

n.add(
    "Link",
    "chp_generator",
    bus0="bus_fuel_internal",
    bus1="bus_electric",
    efficiency=BCHP_ELECTRIC_EFF,
    committable=True,
    p_nom=10,  # Fest: 10 MW Input → 3.8 MW Output
    p_min_pu=0.40,
)

n.add(
    "Link",
    "chp_boiler",
    bus0="bus_fuel_internal",
    bus1="bus_heat",
    efficiency=BCHP_THERMAL_EFF,
    committable=True,
    p_nom=10,  # Fest: 10 MW Input → 4.8 MW Output
    p_min_pu=0.10,
)

print("\n1. SYSTEM-SETUP:")
print("-" * 80)
print(f"Elektrische Last: 3.8 MW (= 1 BHKW bei Volllast)")
print(f"Wärmelast:        4.8 MW (= 1 BHKW bei Volllast)")
print(f"Q/P der Last:     {4.8 / 3.8:.4f}")
print(f"BHKW Q/P nominal: {BCHP_QP_RATIO:.4f}")
print(f"BHKW Q/P-Bereich: [{BCHP_QP_RATIO * 0.85:.4f}, {BCHP_QP_RATIO * 1.15:.4f}]")
print(f"\nGenerator p_nom: 10 MW (Input), p_min_pu: 0.40")
print(f"Boiler p_nom:    10 MW (Input), p_min_pu: 0.10")

# Erstelle das Optimierungsmodell
print("\n2. ERSTELLE MODELL MIT CONSTRAINTS:")
print("-" * 80)

try:
    model = n.optimize.create_model()
    
    link_p = model.variables["Link-p"]
    link_status = model.variables.get("Link-status")
    
    # Füge die Constraints hinzu
    fuel_p = link_p.sel(name="chp_fuel")
    generator_p = link_p.sel(name="chp_generator")
    boiler_p = link_p.sel(name="chp_boiler")
    
    electric_output = BCHP_ELECTRIC_EFF * generator_p
    heat_output = BCHP_THERMAL_EFF * boiler_p
    
    # Brennstoff-Bilanz
    model.add_constraints(
        fuel_p - generator_p - boiler_p == 0,
        name="fuel-balance",
    )
    print("✓ Brennstoff-Bilanz hinzugefügt")
    
    # Kopplungs-Constraints
    RHO_LOW = BCHP_QP_RATIO * (1.0 - BCHP_COUPLING_BAND)
    RHO_HIGH = BCHP_QP_RATIO * (1.0 + BCHP_COUPLING_BAND)
    
    P_nom = BCHP_ELECTRIC_EFF * 10  # 3.8 MW
    
    model.add_constraints(
        heat_output - RHO_LOW * electric_output >= 0,
        name="lower-coupling",
    )
    print(f"✓ Untere Kopplung: Q >= {RHO_LOW:.4f} * P")
    
    model.add_constraints(
        heat_output - RHO_HIGH * electric_output - BCHP_THERMAL_BIAS * (P_nom - electric_output) <= 0,
        name="upper-coupling",
    )
    print(f"✓ Obere Kopplung: Q <= {RHO_HIGH:.4f} * P + {BCHP_THERMAL_BIAS} * (P_nom - P)")
    
    # Status-Synchronisation
    if link_status is not None:
        model.add_constraints(
            link_status.loc[:, "chp_generator"] - link_status.loc[:, "chp_boiler"] == 0,
            name="status-sync",
        )
        print("✓ Status-Synchronisation hinzugefügt")
    
    print("\n3. LÖSE OPTIMIERUNG:")
    print("-" * 80)
    
    n.optimize.solve_model(solver_options={"mip_rel_gap": 0.01})
    
    print(f"Status: {n.optimize.status}")
    print(f"Objective: {n.objective:.2f}")
    
    if n.optimize.status == "ok":
        print("\n✓✓✓ OPTIMIERUNG ERFOLGREICH! ✓✓✓")
        print("\n4. LÖSUNG:")
        print("-" * 80)
        
        for t in n.snapshots[:3]:
            gen_p = n.links_t.p0.loc[t, "chp_generator"]
            boil_p = n.links_t.p0.loc[t, "chp_boiler"]
            fuel_p = n.links_t.p0.loc[t, "chp_fuel"]
            
            P = BCHP_ELECTRIC_EFF * gen_p
            Q = BCHP_THERMAL_EFF * boil_p
            
            if link_status is not None:
                gen_status = n.links_t.status.loc[t, "chp_generator"] if "status" in n.links_t else np.nan
                boil_status = n.links_t.status.loc[t, "chp_boiler"] if "status" in n.links_t else np.nan
            else:
                gen_status = np.nan
                boil_status = np.nan
            
            print(f"\nSnapshot {t}:")
            print(f"  fuel_p:        {fuel_p:6.3f} MW")
            print(f"  generator_p:   {gen_p:6.3f} MW (Status: {gen_status})")
            print(f"  boiler_p:      {boil_p:6.3f} MW (Status: {boil_status})")
            print(f"  P (el. Out):   {P:6.3f} MW")
            print(f"  Q (heat Out):  {Q:6.3f} MW")
            if P > 0.001:
                print(f"  Q/P:           {Q/P:6.4f}")
                print(f"  In Bereich?    [{RHO_LOW:.4f}, {RHO_HIGH:.4f}]: {'✓' if RHO_LOW <= Q/P <= RHO_HIGH else '✗'}")
    else:
        print(f"\n✗✗✗ OPTIMIERUNG FEHLGESCHLAGEN: {n.optimize.status} ✗✗✗")
        print("\nDas System ist INFEASIBLE mit den aktuellen Constraints!")
        
except Exception as e:
    print(f"\n✗✗✗ FEHLER: {e} ✗✗✗")
    import traceback
    traceback.print_exc()

print("\n5. ALTERNATIVE: OHNE Status-Synchronisation")
print("-" * 80)

# Teste ohne Status-Synchronisation
n2 = pypsa.Network()
n2.set_snapshots(pd.date_range("2020-01-01", periods=3, freq="h"))

n2.add("Bus", "bus_gas")
n2.add("Bus", "bus_fuel_internal")
n2.add("Bus", "bus_electric")
n2.add("Bus", "bus_heat")

n2.add("Generator", "gas_source", bus="bus_gas", p_nom=1000, marginal_cost=0)
n2.add("Load", "electric_demand", bus="bus_electric", p_set=3.8)
n2.add("Load", "heat_demand", bus="bus_heat", p_set=4.8)

n2.add(
    "Link",
    "chp_fuel",
    bus0="bus_gas",
    bus1="bus_fuel_internal",
    efficiency=1.0,
    p_nom=100,
)

n2.add(
    "Link",
    "chp_generator",
    bus0="bus_fuel_internal",
    bus1="bus_electric",
    efficiency=BCHP_ELECTRIC_EFF,
    committable=False,  # KEIN Commitment!
    p_nom=10,
    p_min_pu=0.0,  # KEINE Mindestlast!
)

n2.add(
    "Link",
    "chp_boiler",
    bus0="bus_fuel_internal",
    bus1="bus_heat",
    efficiency=BCHP_THERMAL_EFF,
    committable=False,  # KEIN Commitment!
    p_nom=10,
    p_min_pu=0.0,  # KEINE Mindestlast!
)

try:
    print("\nTeste OHNE Commitment und Mindestlast...")
    
    model2 = n2.optimize.create_model()
    
    link_p = model2.variables["Link-p"]
    fuel_p = link_p.sel(name="chp_fuel")
    generator_p = link_p.sel(name="chp_generator")
    boiler_p = link_p.sel(name="chp_boiler")
    
    electric_output = BCHP_ELECTRIC_EFF * generator_p
    heat_output = BCHP_THERMAL_EFF * boiler_p
    
    model2.add_constraints(fuel_p - generator_p - boiler_p == 0, name="fuel-balance")
    model2.add_constraints(heat_output - RHO_LOW * electric_output >= 0, name="lower-coupling")
    model2.add_constraints(
        heat_output - RHO_HIGH * electric_output - BCHP_THERMAL_BIAS * (P_nom - electric_output) <= 0,
        name="upper-coupling"
    )
    
    n2.optimize.solve_model(solver_options={"mip_rel_gap": 0.01})
    
    print(f"Status: {n2.optimize.status}")
    
    if n2.optimize.status == "ok":
        print("✓✓✓ OHNE Commitment funktioniert es! ✓✓✓")
        
        for t in n2.snapshots[:3]:
            gen_p = n2.links_t.p0.loc[t, "chp_generator"]
            boil_p = n2.links_t.p0.loc[t, "chp_boiler"]
            P = BCHP_ELECTRIC_EFF * gen_p
            Q = BCHP_THERMAL_EFF * boil_p
            
            print(f"\nSnapshot {t}:")
            print(f"  generator_p: {gen_p:6.3f} MW → P: {P:6.3f} MW")
            print(f"  boiler_p:    {boil_p:6.3f} MW → Q: {Q:6.3f} MW")
            if P > 0.001:
                print(f"  Q/P: {Q/P:6.4f}")
    else:
        print(f"✗ Auch ohne Commitment fehlgeschlagen: {n2.optimize.status}")
        
except Exception as e:
    print(f"✗ Fehler: {e}")

print("\n" + "=" * 80)
print("FAZIT:")
print("=" * 80)
print("""
Das Problem liegt in der KOMBINATION von:
1. Committable Links (binäre Status-Variable)
2. p_min_pu Constraints (Mindestlast)
3. Status-Synchronisation (beide Links gekoppelt)
4. Starre Kopplungs-Constraints (Q/P-Verhältnis)

Diese Kombination macht das System überbestimmt oder infeasible.

LÖSUNGEN:
a) Entferne Status-Synchronisation
b) Setze p_min_pu = 0.0 für beide Links
c) Entferne Commitment-Constraints (committable=False)
d) Lockere die Kopplungs-Constraints weiter
""")
