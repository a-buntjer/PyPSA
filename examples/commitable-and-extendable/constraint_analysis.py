"""Analysiere die BHKW-Constraints auf Durchführbarkeit."""

import numpy as np

print("=" * 80)
print("CONSTRAINT-ANALYSE")
print("=" * 80)

# Parameter aus dem Skript
NOMINAL_HEAT_TO_ELECTRIC_RATIO = 0.9  # nom_r
BCHP_QP_RATIO = 0.9  # RHO
BCHP_COUPLING_BAND = 0.05  # ±5%
BCHP_THERMAL_BIAS = 0.20  # 0.20 MW_th je 1 MW slack

generator_eff = 0.468
boiler_eff = 0.920

RHO_LOW = BCHP_QP_RATIO * (1.0 - BCHP_COUPLING_BAND)
RHO_HIGH = BCHP_QP_RATIO * (1.0 + BCHP_COUPLING_BAND)

print("\n1. BHKW-KOPPLUNGS-PARAMETER:")
print("-" * 80)
print(f"Nominales Q/P-Verhältnis (RHO):     {BCHP_QP_RATIO}")
print(f"Kopplungsband:                      ±{BCHP_COUPLING_BAND*100:.1f}%")
print(f"RHO_LOW:                            {RHO_LOW:.3f}")
print(f"RHO_HIGH:                           {RHO_HIGH:.3f}")
print(f"Thermischer Bias (Teillast):        {BCHP_THERMAL_BIAS}")
print(f"Generator-Wirkungsgrad:             {generator_eff}")
print(f"Boiler-Wirkungsgrad:                {boiler_eff}")

print("\n2. CONSTRAINT 1: Nominale Proportionalität")
print("-" * 80)
print("generator_eff * nom_r * P_nom_gen = boiler_eff * P_nom_boiler")
print(f"{generator_eff} * {NOMINAL_HEAT_TO_ELECTRIC_RATIO} * P_nom_gen = {boiler_eff} * P_nom_boiler")
print(f"0.4212 * P_nom_gen = 0.92 * P_nom_boiler")
print(f"P_nom_boiler = {generator_eff * NOMINAL_HEAT_TO_ELECTRIC_RATIO / boiler_eff:.4f} * P_nom_gen")
print(f"P_nom_boiler = 0.458 * P_nom_gen")
print("\n→ Das bedeutet: Für jeden MW_fuel im Generator muss der Boiler 0.458 MW_fuel haben")

print("\n3. CONSTRAINT 2: Untere Kopplungsgrenze")
print("-" * 80)
print(f"Q >= RHO_LOW * P")
print(f"Q >= {RHO_LOW:.3f} * P")
print(f"→ Wärme-Output muss mindestens {RHO_LOW:.1%} des Strom-Outputs sein")

print("\n4. CONSTRAINT 3: Obere Kopplungsgrenze mit Teillast-Bias")
print("-" * 80)
print(f"Q <= RHO_HIGH * P + BIAS * (P_nom - P)")
print(f"Q <= {RHO_HIGH:.3f} * P + {BCHP_THERMAL_BIAS} * (P_nom - P)")
print("→ In Teillast erlaubt dies mehr Wärme relativ zum Strom")

print("\n5. BEISPIEL-SZENARIEN:")
print("-" * 80)

# Angenommen: P_nom_gen = 80 MW (Brennstoff-Input für Strom)
P_nom_gen = 80  # MW Brennstoff-Input
P_nom_boiler = generator_eff * NOMINAL_HEAT_TO_ELECTRIC_RATIO * P_nom_gen / boiler_eff
print(f"Angenommen P_nom_gen = {P_nom_gen} MW (Brennstoff-Input)")
print(f"Dann P_nom_boiler = {P_nom_boiler:.2f} MW (Brennstoff-Input)")

# Elektrischer Output nominal
P_el_nom = generator_eff * P_nom_gen
print(f"Elektrischer Output nominal: {P_el_nom:.2f} MW")

# Szenarien testen
print("\nSZENARIO A: Volllast")
P_gen = P_nom_gen  # 80 MW Brennstoff-Input
P_el = generator_eff * P_gen  # elektrischer Output
P_el_nom_output = generator_eff * P_nom_gen

# Berechne erlaubten Wärme-Bereich
Q_min = RHO_LOW * P_el
Q_max_full = RHO_HIGH * P_el + BCHP_THERMAL_BIAS * (P_el_nom_output - P_el)

print(f"  Brennstoff für Generator: {P_gen:.2f} MW")
print(f"  Elektrischer Output: {P_el:.2f} MW")
print(f"  Erlaubter Wärme-Bereich: [{Q_min:.2f}, {Q_max_full:.2f}] MW")

# Welcher Brennstoff-Input für Boiler wird benötigt?
# Q = boiler_eff * P_boiler
P_boiler_min = Q_min / boiler_eff
P_boiler_max = Q_max_full / boiler_eff
print(f"  Benötigter Boiler-Input: [{P_boiler_min:.2f}, {P_boiler_max:.2f}] MW")
print(f"  Nominaler Boiler-Input: {P_nom_boiler:.2f} MW")

# Prüfe ob nominaler Boiler-Input im erlaubten Bereich liegt
if P_boiler_min <= P_nom_boiler <= P_boiler_max:
    print(f"  ✓ Nominaler Boiler-Input liegt im erlaubten Bereich")
else:
    print(f"  ⚠ Nominaler Boiler-Input liegt NICHT im erlaubten Bereich!")
    print(f"     Dies macht das Problem INFEASIBLE!")

print("\nSZENARIO B: 50% Teillast (Generator)")
P_gen = 0.5 * P_nom_gen  # 40 MW Brennstoff-Input
P_el = generator_eff * P_gen  # elektrischer Output

Q_min = RHO_LOW * P_el
Q_max_partial = RHO_HIGH * P_el + BCHP_THERMAL_BIAS * (P_el_nom_output - P_el)

print(f"  Brennstoff für Generator: {P_gen:.2f} MW")
print(f"  Elektrischer Output: {P_el:.2f} MW")
print(f"  Erlaubter Wärme-Bereich: [{Q_min:.2f}, {Q_max_partial:.2f}] MW")

P_boiler_min = Q_min / boiler_eff
P_boiler_max = Q_max_partial / boiler_eff
print(f"  Benötigter Boiler-Input: [{P_boiler_min:.2f}, {P_boiler_max:.2f}] MW")

# Bei 50% Generator sollte Boiler auch ca. 50% sein (wegen Proportionalität)
# Aber die Constraints erlauben mehr Flexibilität durch den Bias
P_boiler_expected = 0.5 * P_nom_boiler
print(f"  Erwarteter Boiler-Input (50%): {P_boiler_expected:.2f} MW")

if P_boiler_min <= P_boiler_expected <= P_boiler_max:
    print(f"  ✓ Erwarteter Boiler-Input liegt im erlaubten Bereich")
else:
    print(f"  ⚠ Erwarteter Boiler-Input liegt NICHT im erlaubten Bereich!")

print("\nSZENARIO C: Generator aus, Boiler alleine?")
P_gen = 0.0  # Generator aus
P_el = 0.0

Q_min = RHO_LOW * P_el  # = 0
Q_max_off = RHO_HIGH * P_el + BCHP_THERMAL_BIAS * (P_el_nom_output - P_el)

print(f"  Elektrischer Output: {P_el:.2f} MW")
print(f"  Erlaubter Wärme-Bereich: [{Q_min:.2f}, {Q_max_off:.2f}] MW")
print(f"  → Boiler kann {Q_max_off:.2f} MW Wärme erzeugen wenn Generator aus ist")

print("\n6. PROBLEM-DIAGNOSE:")
print("-" * 80)
print("Die Constraints erzwingen eine SEHR STARRE Kopplung zwischen Strom und Wärme.")
print("Dies bedeutet:")
print("  - BHKW kann nur laufen, wenn SOWOHL Strom ALS AUCH Wärme gebraucht werden")
print("  - Das Verhältnis muss fast genau 0.9 sein (±5%)")
print("  - Wenn die Last-Profile nicht passen, wird das BHKW nicht genutzt")
print("\nMögliche Lösungen:")
print("  1. Kopplungsband vergrößern (z.B. ±20% statt ±5%)")
print("  2. Thermal Bias erhöhen (mehr Flexibilität in Teillast)")
print("  3. Generator und Boiler unabhängiger machen (nur nominale Proportionalität)")
print("  4. Prüfen ob Last-Profile kompatibel sind (Q/P-Verhältnis der Lasten)")

# Prüfe Last-Profile
print("\n7. LAST-PROFILE-KOMPATIBILITÄT:")
print("-" * 80)

base_electric_load = np.array([9.5, 9.1, 8.7, 8.3, 8.0, 8.2, 9.0, 10.5, 11.8, 12.5, 13.2, 13.5, 13.0, 12.6, 12.0, 11.5, 11.0, 10.8, 10.5, 10.2, 9.8, 9.6, 9.4, 9.2])
base_heat_load = np.array([14.0, 13.5, 13.0, 12.5, 12.0, 12.5, 13.5, 15.0, 16.5, 17.5, 18.0, 18.5, 18.0, 17.2, 16.8, 16.0, 15.5, 15.0, 14.5, 14.0, 13.8, 13.5, 13.2, 13.0])

q_p_ratios = base_heat_load / base_electric_load
print(f"Q/P-Verhältnis der Lasten: min={q_p_ratios.min():.3f}, max={q_p_ratios.max():.3f}, mittel={q_p_ratios.mean():.3f}")
print(f"Erforderliches Q/P für BHKW: {RHO_LOW:.3f} bis {RHO_HIGH:.3f}")

if q_p_ratios.mean() < RHO_LOW or q_p_ratios.mean() > RHO_HIGH:
    print(f"⚠ PROBLEM: Das mittlere Q/P-Verhältnis der Lasten ({q_p_ratios.mean():.3f}) liegt")
    print(f"   AUSSERHALB des erlaubten BHKW-Bereichs [{RHO_LOW:.3f}, {RHO_HIGH:.3f}]!")
    print(f"   → BHKW kann nicht optimal arbeiten!")
else:
    print(f"✓ Das mittlere Q/P-Verhältnis passt zum BHKW-Bereich")

print(f"\nDetail: Q/P-Verhältnis pro Stunde:")
for i in range(24):
    ratio = q_p_ratios[i]
    status = "✓" if RHO_LOW <= ratio <= RHO_HIGH else "✗"
    print(f"  Stunde {i:2d}: Q/P = {ratio:.3f} {status}")

print("\n" + "=" * 80)
