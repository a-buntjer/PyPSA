"""
Analyse der Infeasibility nach Änderungen.

PROBLEM:
- chp_generator: committable=True, p_min_pu=0.40
- chp_boiler: committable=False, p_min_pu=0.0
- Fuel-Balance: fuel_p = generator_p + boiler_p

KONFLIKT:
Wenn Generator EIN ist (status=1):
- Generator muss mindestens 40% laufen
- Generator bei 40% verbraucht 4.0 MW Gas
- Fuel Balance: fuel_p = generator_p + boiler_p
- Wenn Generator 4.0 MW verbraucht, muss fuel_p = 4.0 MW
- Aber die Coupling-Constraints verlangen:
  * Q >= RHO_LOW * P → Mindest-Wärme
  * Q <= RHO_HIGH * P + BIAS → Maximale Wärme
  * Bei P=1.52 MW elektrisch: Q zwischen 1.63-2.66 MW
  * Das erfordert boiler_p zwischen 3.40-5.55 MW
  * Aber Fuel-Balance erlaubt nur boiler_p = fuel_p - generator_p = 4.0 - 4.0 = 0 MW!

LÖSUNG:
Option 1: chp_boiler auch committable=True machen und p_min_pu anpassen
Option 2: Die Coupling-Constraints lockern
Option 3: Die Fuel-Balance anders modellieren
"""

print(__doc__)

# Berechnung der kritischen Werte
BCHP_ELECTRIC_EFF = 0.38
BCHP_THERMAL_EFF = 0.48
BCHP_QP_RATIO = 1.2632
BCHP_COUPLING_BAND = 0.15

RHO_LOW = BCHP_QP_RATIO * (1 - BCHP_COUPLING_BAND)
RHO_HIGH = BCHP_QP_RATIO * (1 + BCHP_COUPLING_BAND)

print(f"\n=== PARAMETER ===")
print(f"BCHP_ELECTRIC_EFF = {BCHP_ELECTRIC_EFF:.2f}")
print(f"BCHP_THERMAL_EFF = {BCHP_THERMAL_EFF:.2f}")
print(f"BCHP_QP_RATIO = {BCHP_QP_RATIO:.4f}")
print(f"BCHP_COUPLING_BAND = {BCHP_COUPLING_BAND:.2f}")
print(f"RHO_LOW = {RHO_LOW:.4f}")
print(f"RHO_HIGH = {RHO_HIGH:.4f}")

print(f"\n=== SZENARIO: Generator bei 40% Mindestlast ===")
generator_p_nom = 10.0  # Annahme
generator_p_min = 0.40 * generator_p_nom
print(f"Generator P_nom = {generator_p_nom:.2f} MW (Brennstoff-Input)")
print(f"Generator p_min (40%) = {generator_p_min:.2f} MW (Brennstoff-Input)")

generator_electric = generator_p_min * BCHP_ELECTRIC_EFF
print(f"Generator elektrische Leistung = {generator_electric:.2f} MW")

# Coupling-Anforderungen
heat_min = RHO_LOW * generator_electric
heat_max = RHO_HIGH * generator_electric
print(f"\nCoupling-Anforderungen:")
print(f"  Minimale Wärme Q_min = {heat_min:.2f} MW")
print(f"  Maximale Wärme Q_max = {heat_max:.2f} MW")

# Boiler-Input Anforderungen
boiler_p_min = heat_min / BCHP_THERMAL_EFF
boiler_p_max = heat_max / BCHP_THERMAL_EFF
print(f"\nBoiler Brennstoff-Input Anforderungen:")
print(f"  Minimale boiler_p = {boiler_p_min:.2f} MW")
print(f"  Maximale boiler_p = {boiler_p_max:.2f} MW")

# Fuel Balance
fuel_p_required = generator_p_min + boiler_p_min
print(f"\nFuel Balance:")
print(f"  fuel_p = generator_p + boiler_p")
print(f"  fuel_p (minimum) = {generator_p_min:.2f} + {boiler_p_min:.2f} = {fuel_p_required:.2f} MW")

# Aber wenn Generator alleine läuft:
fuel_p_if_generator_alone = generator_p_min
boiler_p_implied = fuel_p_if_generator_alone - generator_p_min
print(f"\nWENN nur Generator läuft (boiler_p minimal):")
print(f"  fuel_p = {fuel_p_if_generator_alone:.2f} MW")
print(f"  boiler_p (aus Balance) = {boiler_p_implied:.2f} MW")
print(f"  → Aber Coupling verlangt mindestens {boiler_p_min:.2f} MW!")
print(f"  → KONFLIKT! Infeasible!")

print("\n=== LÖSUNGSANSÄTZE ===")
print("\nOption A: Boiler wieder committable=True, p_min_pu anpassen")
print("  - chp_boiler: committable=True")
print("  - chp_boiler: p_min_pu = 0.40 (gleich wie Generator)")
print("  - Status-Synchronisation behalten")
print("  → Problem: Wieder die alte Übereinschränkung!")

print("\nOption B: Fuel Balance anpassen")
print("  - NICHT: fuel_p = generator_p + boiler_p")
print("  - SONDERN: fuel_p >= generator_p (Fuel kann mehr liefern)")
print("  - SONDERN: fuel_p >= boiler_p (Fuel kann mehr liefern)")
print("  - UND: Mindestens soviel wie für Coupling nötig")
print("  → Problem: Fuel Balance wird sinnlos")

print("\nOption C: p_min_pu für Generator auf 0.0 setzen")
print("  - chp_generator: p_min_pu = 0.0")
print("  - Dann kann Generator auch bei 0% laufen")
print("  - Coupling-Constraints erlauben dann auch Q=0")
print("  → Verliert Commitment-Charakter (immer an)")

print("\nOption D: Coupling-Constraints nur bei Status=1 aktiv")
print("  - Coupling nur erzwingen wenn Generator läuft")
print("  - Mit Big-M Formulierung")
print("  - Wenn Generator aus, Boiler frei")

print("\nOption E: Nominale Proportionalität OHNE Fuel Balance")
print("  - NUR: eff_gen * QP * P_nom_gen = eff_boil * P_nom_boil")
print("  - KEINE Fuel Balance mehr")
print("  - Generator und Boiler unabhängig")
print("  - Coupling über Q/P Verhältnis")
print("  → Eleganteste Lösung!")

print("\n==> EMPFEHLUNG: Option E")
print("Entferne die Fuel-Balance-Constraint vollständig.")
print("Behalte nur die nominale Proportionalität und die Coupling-Constraints.")
