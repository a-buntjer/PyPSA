"""Teste, ob das BHKW mit den aktuellen Parametern überhaupt nutzbar ist."""

import numpy as np

print("=" * 80)
print("DURCHFÜHRBARKEITS-TEST MIT NEUEN PARAMETERN")
print("=" * 80)

# Neue Parameter
NOMINAL_HEAT_TO_ELECTRIC_RATIO = 1.2
BCHP_QP_RATIO = 1.2
BCHP_COUPLING_BAND = 0.30
BCHP_THERMAL_BIAS = 0.50

generator_eff = 0.468
boiler_eff = 0.920

RHO_LOW = BCHP_QP_RATIO * (1.0 - BCHP_COUPLING_BAND)
RHO_HIGH = BCHP_QP_RATIO * (1.0 + BCHP_COUPLING_BAND)

print("\n1. NEUE PARAMETER:")
print("-" * 80)
print(f"NOMINAL_HEAT_TO_ELECTRIC_RATIO: {NOMINAL_HEAT_TO_ELECTRIC_RATIO}")
print(f"BCHP_QP_RATIO:                  {BCHP_QP_RATIO}")
print(f"BCHP_COUPLING_BAND:             ±{BCHP_COUPLING_BAND*100:.0f}%")
print(f"RHO_LOW:                        {RHO_LOW:.3f}")
print(f"RHO_HIGH:                       {RHO_HIGH:.3f}")
print(f"BCHP_THERMAL_BIAS:              {BCHP_THERMAL_BIAS}")

print("\n2. LAST-PROFILE-KOMPATIBILITÄT:")
print("-" * 80)

base_electric_load = np.array([9.5, 9.1, 8.7, 8.3, 8.0, 8.2, 9.0, 10.5, 11.8, 12.5, 13.2, 13.5, 13.0, 12.6, 12.0, 11.5, 11.0, 10.8, 10.5, 10.2, 9.8, 9.6, 9.4, 9.2])
base_heat_load = np.array([14.0, 13.5, 13.0, 12.5, 12.0, 12.5, 13.5, 15.0, 16.5, 17.5, 18.0, 18.5, 18.0, 17.2, 16.8, 16.0, 15.5, 15.0, 14.5, 14.0, 13.8, 13.5, 13.2, 13.0])

q_p_ratios = base_heat_load / base_electric_load
print(f"Q/P-Verhältnis der Lasten: min={q_p_ratios.min():.3f}, max={q_p_ratios.max():.3f}, mittel={q_p_ratios.mean():.3f}")
print(f"Erforderliches Q/P für BHKW: {RHO_LOW:.3f} bis {RHO_HIGH:.3f}")

count_compatible = np.sum((q_p_ratios >= RHO_LOW) & (q_p_ratios <= RHO_HIGH))
print(f"\nStunden mit kompatiblem Q/P-Verhältnis: {count_compatible}/24")

if count_compatible > 0:
    print(f"✓ BHKW kann in {count_compatible} Stunden arbeiten")
else:
    print(f"✗ BHKW kann in KEINER Stunde arbeiten - immer noch zu restriktiv!")

print(f"\nDetail: Q/P-Verhältnis pro Stunde:")
for i in range(24):
    ratio = q_p_ratios[i]
    status = "✓" if RHO_LOW <= ratio <= RHO_HIGH else "✗"
    print(f"  Stunde {i:2d}: Q/P = {ratio:.3f} {status}")

# Weitere Analyse
print("\n3. PROBLEM-DIAGNOSE:")
print("-" * 80)

# Prüfe die nominale Proportionalitäts-Constraint
print("Nominale Proportionalität-Constraint:")
print(f"  generator_eff * nom_r * P_nom_gen = boiler_eff * P_nom_boiler")
print(f"  {generator_eff} * {NOMINAL_HEAT_TO_ELECTRIC_RATIO} * P_nom_gen = {boiler_eff} * P_nom_boiler")

factor = generator_eff * NOMINAL_HEAT_TO_ELECTRIC_RATIO / boiler_eff
print(f"  P_nom_boiler = {factor:.4f} * P_nom_gen")

# Prüfe: Wenn P_gen = P_nom_gen und P_boiler = factor * P_nom_gen
# dann ist Q/P = (boiler_eff * P_boiler) / (generator_eff * P_gen)
#              = (boiler_eff * factor * P_nom_gen) / (generator_eff * P_nom_gen)
#              = boiler_eff * factor / generator_eff

q_p_nominal = boiler_eff * factor / generator_eff
print(f"\nQ/P bei nominaler Auslastung (aus Proportionalität):")
print(f"  Q/P = {q_p_nominal:.4f}")

if RHO_LOW <= q_p_nominal <= RHO_HIGH:
    print(f"  ✓ Liegt im erlaubten Bereich [{RHO_LOW:.3f}, {RHO_HIGH:.3f}]")
else:
    print(f"  ✗ Liegt NICHT im erlaubten Bereich [{RHO_LOW:.3f}, {RHO_HIGH:.3f}]!")
    print(f"     WIDERSPRUCH: Die nominale Proportionalität ist inkompatibel mit den Kopplungs-Constraints!")

print("\n4. MÖGLICHE URSACHEN:")
print("-" * 80)

# Die nominale Proportionalität erzwingt ein fixes Q/P-Verhältnis
# das durch nom_r bestimmt ist. Aber die Kopplungs-Constraints
# erzwingen ein anderes Verhältnis (RHO ± Band).

print(f"Die nominale Proportionalität erzwingt Q/P = {q_p_nominal:.3f}")
print(f"Die Kopplungs-Constraints erlauben Q/P zwischen {RHO_LOW:.3f} und {RHO_HIGH:.3f}")

if abs(q_p_nominal - BCHP_QP_RATIO) > 0.01:
    print(f"\n⚠ HAUPTPROBLEM: Die nominale Proportionalität (Q/P={q_p_nominal:.3f}) ist")
    print(f"   NICHT konsistent mit dem gewünschten BCHP_QP_RATIO ({BCHP_QP_RATIO})!")
    print(f"\nDies passiert, weil:")
    print(f"  - NOMINAL_HEAT_TO_ELECTRIC_RATIO = {NOMINAL_HEAT_TO_ELECTRIC_RATIO}")
    print(f"  - generator_eff = {generator_eff}")
    print(f"  - boiler_eff = {boiler_eff}")
    print(f"  - Q/P = (boiler_eff / generator_eff) * NOMINAL_HEAT_TO_ELECTRIC_RATIO")
    print(f"  - Q/P = ({boiler_eff} / {generator_eff}) * {NOMINAL_HEAT_TO_ELECTRIC_RATIO}")
    print(f"  - Q/P = {boiler_eff / generator_eff:.3f} * {NOMINAL_HEAT_TO_ELECTRIC_RATIO}")
    print(f"  - Q/P = {q_p_nominal:.3f}")
    
    print(f"\n→ Die nominale Proportionalitäts-Constraint und die Kopplungs-Constraints")
    print(f"   sind WIDERSPRÜCHLICH!")

print("\n5. LÖSUNG:")
print("-" * 80)
print("Option 1: Entferne EINE der beiden widersprüchlichen Constraints:")
print("  a) Entferne die nominale Proportionalität (chp-heat-power-output-proportionality)")
print("  b) Entferne die starren Kopplungs-Constraints (bhkw-lower/upper-coupling)")
print("\nOption 2: Mache die Constraints konsistent:")
print(f"  - Setze BCHP_QP_RATIO = {q_p_nominal:.4f} (um mit nominaler Proportionalität konsistent zu sein)")
print(f"  - Oder passe die Wirkungsgrade an")

print("\n" + "=" * 80)
