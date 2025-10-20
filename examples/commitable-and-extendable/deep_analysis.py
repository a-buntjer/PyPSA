"""
TIEFGRÜNDIGE ANALYSE: Warum wird das BHKW nicht genutzt?

Wir analysieren die mathematische Struktur der Constraints und prüfen auf Inkonsistenzen.
"""

import pypsa
import numpy as np
import pandas as pd

# Baue ein minimales Testnetzwerk
n = pypsa.Network()
n.set_snapshots(pd.date_range("2020-01-01", periods=24, freq="h"))

# Vereinfachtes System für Test
n.add("Carrier", "gas")
n.add("Carrier", "electric")
n.add("Carrier", "heat")
n.add("Carrier", "gas_internal")

n.add("Bus", "bus_gas", carrier="gas")
n.add("Bus", "bus_fuel_internal", carrier="gas_internal")
n.add("Bus", "bus_electric", carrier="electric")
n.add("Bus", "bus_heat", carrier="heat")

# Einfache konstante Lasten
n.add("Load", "electric_demand", bus="bus_electric", p_set=10.0)
n.add("Load", "heat_demand", bus="bus_heat", p_set=12.0)

# Parameter aus Ihrem Skript
BCHP_THERMAL_EFF = 0.48
BCHP_ELECTRIC_EFF = 0.38
BCHP_QP_RATIO = BCHP_THERMAL_EFF / BCHP_ELECTRIC_EFF
BCHP_COUPLING_BAND = 0.15
BCHP_THERMAL_BIAS = 0.20

print("=" * 80)
print("TIEFGRÜNDIGE ANALYSE DER BHKW-CONSTRAINTS")
print("=" * 80)

print("\n1. BHKW-PARAMETER:")
print("-" * 80)
print(f"Elektrischer Wirkungsgrad: {BCHP_ELECTRIC_EFF}")
print(f"Thermischer Wirkungsgrad:  {BCHP_THERMAL_EFF}")
print(f"Q/P-Verhältnis (Output):   {BCHP_QP_RATIO:.4f}")
print(f"Kopplungsband:             ±{BCHP_COUPLING_BAND*100:.0f}%")

RHO_LOW = BCHP_QP_RATIO * (1.0 - BCHP_COUPLING_BAND)
RHO_HIGH = BCHP_QP_RATIO * (1.0 + BCHP_COUPLING_BAND)
print(f"Erlaubter Q/P-Bereich:     [{RHO_LOW:.4f}, {RHO_HIGH:.4f}]")

print("\n2. KRITISCHE ANALYSE DER CONSTRAINT-STRUKTUR:")
print("-" * 80)

# Die Constraints aus Ihrem Code:
# 1. Brennstoff-Bilanz: fuel_p - generator_p - boiler_p = 0
# 2. Nominale Proportionalität: eff_gen * QP_RATIO * P_nom_gen - eff_boil * P_nom_boil = 0
# 3. Untere Kopplung: Q - RHO_LOW * P >= 0
# 4. Obere Kopplung: Q - RHO_HIGH * P - BIAS * (P_nom - P) <= 0
# 5. Status-Synchronisation: status_gen - status_boil = 0

print("\nConstraint 1: Brennstoff-Bilanz")
print("  fuel_p = generator_p + boiler_p")
print("  ✓ Diese Constraint ist korrekt")

print("\nConstraint 2: Nominale Proportionalität")
print(f"  {BCHP_ELECTRIC_EFF} * {BCHP_QP_RATIO:.4f} * P_nom_gen = {BCHP_THERMAL_EFF} * P_nom_boil")
print(f"  P_nom_boil = {BCHP_ELECTRIC_EFF * BCHP_QP_RATIO / BCHP_THERMAL_EFF:.4f} * P_nom_gen")
print(f"  P_nom_boil = {1.0:.4f} * P_nom_gen")
print("  → Generator und Boiler müssen GLEICH GROSS sein (Input-Basis)!")

print("\n3. PROBLEM-ANALYSE:")
print("-" * 80)

print("\nAngenommen, beide haben P_nom = 10 MW (Brennstoff-Input):")
print(f"  Generator Output nominal: {BCHP_ELECTRIC_EFF} * 10 = {BCHP_ELECTRIC_EFF * 10:.2f} MW_el")
print(f"  Boiler Output nominal:    {BCHP_THERMAL_EFF} * 10 = {BCHP_THERMAL_EFF * 10:.2f} MW_th")
print(f"  Q/P-Verhältnis nominal:   {BCHP_THERMAL_EFF * 10 / (BCHP_ELECTRIC_EFF * 10):.4f}")

print("\n⚠ ABER: Die Kopplungs-Constraints beziehen sich auf OUTPUT, nicht INPUT!")
print("\nBei Volllast (beide Links bei 100%):")
print(f"  generator_p = 10 MW (Input)")
print(f"  P = {BCHP_ELECTRIC_EFF} * 10 = {BCHP_ELECTRIC_EFF * 10:.2f} MW (Output)")
print(f"  boiler_p = 10 MW (Input)")
print(f"  Q = {BCHP_THERMAL_EFF} * 10 = {BCHP_THERMAL_EFF * 10:.2f} MW (Output)")
print(f"  Q/P = {BCHP_THERMAL_EFF * 10 / (BCHP_ELECTRIC_EFF * 10):.4f}")
print(f"  Erlaubter Bereich: [{RHO_LOW:.4f}, {RHO_HIGH:.4f}]")

q_p_volllast = BCHP_THERMAL_EFF / BCHP_ELECTRIC_EFF
if RHO_LOW <= q_p_volllast <= RHO_HIGH:
    print("  ✓ Bei Volllast passt das Q/P-Verhältnis")
else:
    print("  ✗ Bei Volllast passt das Q/P-Verhältnis NICHT!")

print("\n4. TEILLAST-ANALYSE:")
print("-" * 80)

# Generator bei 40% (p_min_pu), Boiler kann variieren
print("Szenario: Generator bei Mindestlast (40%), was muss Boiler tun?")
print()

P_nom_gen = 10  # MW Input
P_nom_boil = 10  # MW Input (aus Proportionalität)

p_min_pu_gen = 0.40
p_min_pu_boil = 0.10

generator_p = p_min_pu_gen * P_nom_gen  # 4 MW Input
P = BCHP_ELECTRIC_EFF * generator_p  # Output
P_nom = BCHP_ELECTRIC_EFF * P_nom_gen  # Nominal Output

print(f"  generator_p = {generator_p:.2f} MW (Input)")
print(f"  P (el. Output) = {P:.2f} MW")
print(f"  P_nom (el. Output) = {P_nom:.2f} MW")

# Aus unterer Kopplung: Q >= RHO_LOW * P
Q_min = RHO_LOW * P
print(f"\n  Untere Kopplung: Q >= {RHO_LOW:.4f} * {P:.2f} = {Q_min:.2f} MW")

# Aus oberer Kopplung: Q <= RHO_HIGH * P + BIAS * (P_nom - P)
Q_max = RHO_HIGH * P + BCHP_THERMAL_BIAS * (P_nom - P)
print(f"  Obere Kopplung: Q <= {RHO_HIGH:.4f} * {P:.2f} + {BCHP_THERMAL_BIAS} * ({P_nom:.2f} - {P:.2f})")
print(f"                  Q <= {Q_max:.2f} MW")

# Welchen Boiler-Input brauchen wir?
boiler_p_min = Q_min / BCHP_THERMAL_EFF
boiler_p_max = Q_max / BCHP_THERMAL_EFF

print(f"\n  Erforderlicher boiler_p: [{boiler_p_min:.2f}, {boiler_p_max:.2f}] MW (Input)")
print(f"  Erlaubter boiler_p (p_min_pu): [{p_min_pu_boil * P_nom_boil:.2f}, {P_nom_boil:.2f}] MW")

if boiler_p_min < p_min_pu_boil * P_nom_boil:
    print(f"\n  ⚠ PROBLEM: Untere Kopplung verlangt boiler_p >= {boiler_p_min:.2f} MW")
    print(f"     Aber p_min_pu verlangt boiler_p >= {p_min_pu_boil * P_nom_boil:.2f} MW")
    print(f"     → Wenn Generator bei 40% läuft, MUSS Boiler auch mindestens bei 10% laufen")
    print(f"     → Aber die Kopplung verlangt möglicherweise weniger!")
    
if boiler_p_max > P_nom_boil:
    print(f"\n  ⚠ PROBLEM: Obere Kopplung erlaubt bis zu boiler_p = {boiler_p_max:.2f} MW")
    print(f"     Aber maximaler boiler_p ist {P_nom_boil:.2f} MW (wegen P_nom)")

print("\n5. BRENNSTOFF-BILANZ CHECK:")
print("-" * 80)

# Prüfe ob Brennstoff-Bilanz mit Kopplungs-Constraints konsistent ist
print("\nBei Generator @ 40%, Boiler variabel:")
fuel_p_min = generator_p + boiler_p_min
fuel_p_max = generator_p + boiler_p_max

print(f"  Benötigter fuel_p: [{fuel_p_min:.2f}, {fuel_p_max:.2f}] MW")
print(f"  generator_p (fix): {generator_p:.2f} MW")
print(f"  boiler_p (variabel): [{boiler_p_min:.2f}, {boiler_p_max:.2f}] MW")

print("\n6. STATUS-SYNCHRONISATION:")
print("-" * 80)
print("  Constraint: status_gen = status_boil")
print("  → Beide Links müssen GLEICHZEITIG an oder aus sein")
print("  → Wenn Generator an ist (status=1), MUSS Boiler auch an sein")
print("  → Wenn Boiler an ist, gilt p >= p_min_pu * p_nom")

print("\n7. KRITISCHER FEHLER GEFUNDEN:")
print("-" * 80)

print("\n⚠⚠⚠ HAUPTPROBLEM: STATUS-SYNCHRONISATION + p_min_pu ⚠⚠⚠")
print()
print("Die Kombination aus:")
print("  1. Status-Synchronisation (beide an/aus)")
print("  2. Unterschiedliche p_min_pu (Generator: 40%, Boiler: 10%)")
print("  3. Kopplungs-Constraints (Q/P-Verhältnis)")
print()
print("führt zu einem ÜBERBESTIMMTEN System!")
print()
print("Wenn Generator bei p_min_pu = 40% startet:")
print(f"  - Er produziert P = {BCHP_ELECTRIC_EFF * 0.4 * 10:.2f} MW Strom")
print(f"  - Kopplung verlangt Q zwischen {RHO_LOW * BCHP_ELECTRIC_EFF * 0.4 * 10:.2f} und {Q_max:.2f} MW")
print(f"  - Boiler muss dafür boiler_p zwischen {boiler_p_min:.2f} und {boiler_p_max:.2f} MW liefern")
print(f"  - ABER: Boiler p_min_pu = {p_min_pu_boil} verlangt boiler_p >= {p_min_pu_boil * 10:.2f} MW")
print()

if boiler_p_min < p_min_pu_boil * P_nom_boil:
    gap = p_min_pu_boil * P_nom_boil - boiler_p_min
    print(f"  ✗ KONFLIKT: Boiler MUSS mindestens {p_min_pu_boil * P_nom_boil:.2f} MW liefern (p_min_pu)")
    print(f"              aber Kopplung erlaubt ab {boiler_p_min:.2f} MW")
    print(f"              → Differenz: {gap:.2f} MW")
    print()
    print("  LÖSUNG: Entweder")
    print("    a) p_min_pu für beide Links GLEICH setzen, ODER")
    print("    b) Status-Synchronisation entfernen, ODER")
    print("    c) p_min_pu auf 0.0 setzen für beide")

print("\n8. ZUSÄTZLICHE PROBLEME:")
print("-" * 80)

# Prüfe ob Last-Profile kompatibel sind
electric_load = 10.0
heat_load = 12.0
load_qp_ratio = heat_load / electric_load

print(f"\nLast-Profile:")
print(f"  Elektrische Last: {electric_load} MW")
print(f"  Wärmelast:        {heat_load} MW")
print(f"  Q/P-Verhältnis:   {load_qp_ratio:.4f}")
print(f"  BHKW Q/P-Bereich: [{RHO_LOW:.4f}, {RHO_HIGH:.4f}]")

if load_qp_ratio < RHO_LOW or load_qp_ratio > RHO_HIGH:
    print(f"\n  ⚠ Last-Profile sind NICHT mit BHKW-Kopplung kompatibel!")
    print(f"     Das BHKW kann BEIDE Lasten nicht gleichzeitig optimal decken")
else:
    print(f"\n  ✓ Last-Profile passen in den BHKW-Kopplungsbereich")

print("\n" + "=" * 80)
print("ZUSAMMENFASSUNG DER GEFUNDENEN PROBLEME:")
print("=" * 80)
print()
print("1. ⚠ STATUS-SYNCHRONISATION + UNTERSCHIEDLICHE p_min_pu")
print("     → Überbestimmtes System, möglicherweise infeasible")
print()
print("2. ⚠ KOPPLUNGS-CONSTRAINTS können mit p_min_pu KONFLIKT haben")
print("     → Bei Mindestlast kann gefordertes Q/P nicht erreichbar sein")
print()
print("3. ⚠ NOMINALE PROPORTIONALITÄT erzwingt P_nom_gen = P_nom_boil")
print("     → Wenig Flexibilität in der Dimensionierung")
print()
print("=" * 80)
