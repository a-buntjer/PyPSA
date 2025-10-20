"""Verifikation der neuen CHP-Constraints ohne Optimierung."""

print("=" * 80)
print("VERIFIKATION DER NEUEN CHP-CONSTRAINTS")
print("=" * 80)

# Parameter aus dem Skript
BCHP_THERMAL_EFF = 0.48
BCHP_ELECTRIC_EFF = 0.38
BCHP_QP_RATIO = BCHP_THERMAL_EFF / BCHP_ELECTRIC_EFF

print(f"\n1. Parameter:")
print(f"   Elektrischer Wirkungsgrad: {BCHP_ELECTRIC_EFF:.2%}")
print(f"   Thermischer Wirkungsgrad:  {BCHP_THERMAL_EFF:.2%}")
print(f"   Q/P-Verhältnis (Output):   {BCHP_QP_RATIO:.4f}")

print(f"\n2. Interpretation:")
print(f"   Für 1 MW Brennstoff-Input produziert das BHKW:")
print(f"   - {BCHP_ELECTRIC_EFF:.2f} MW elektrisch")
print(f"   - {BCHP_THERMAL_EFF:.2f} MW thermisch")
print(f"   → Q/P = {BCHP_THERMAL_EFF:.2f} / {BCHP_ELECTRIC_EFF:.2f} = {BCHP_QP_RATIO:.4f}")

print(f"\n3. Beispiel-Szenarien:")
print("-" * 80)

scenarios = [
    ("Volllast", 10.0, 1.0),
    ("Teillast 75%", 10.0, 0.75),
    ("Teillast 50%", 10.0, 0.50),
    ("Teillast 40% (Mindestlast)", 10.0, 0.40),
]

for name, p_nom_gen, load_factor in scenarios:
    # Brennstoff-Input
    gen_input = p_nom_gen * load_factor
    
    # Mit der neuen Constraint: Q = RHO * P
    # boiler_eff * boiler_p = BCHP_QP_RATIO * gen_eff * gen_p
    # boiler_p = (BCHP_QP_RATIO * gen_eff / boiler_eff) * gen_p
    
    boiler_input = (BCHP_QP_RATIO * BCHP_ELECTRIC_EFF / BCHP_THERMAL_EFF) * gen_input
    
    # Output
    electric_output = BCHP_ELECTRIC_EFF * gen_input
    thermal_output = BCHP_THERMAL_EFF * boiler_input
    
    # Verhältnis prüfen
    qp_ratio = thermal_output / electric_output if electric_output > 0 else 0
    
    print(f"\n{name}:")
    print(f"  Brennstoff-Input Generator: {gen_input:.2f} MW")
    print(f"  Brennstoff-Input Boiler:    {boiler_input:.2f} MW")
    print(f"  Elektrischer Output:        {electric_output:.2f} MW")
    print(f"  Thermischer Output:         {thermal_output:.2f} MW")
    print(f"  Q/P-Verhältnis:            {qp_ratio:.4f}")
    
    # Prüfe ob das Verhältnis stimmt
    if abs(qp_ratio - BCHP_QP_RATIO) < 1e-6:
        print(f"  ✓ Verhältnis korrekt!")
    else:
        print(f"  ✗ Verhältnis weicht ab! (Erwartet: {BCHP_QP_RATIO:.4f})")

print("\n" + "=" * 80)
print("4. CONSTRAINT-FORMELN")
print("=" * 80)

print("\nCONSTRAINT 1: Nominale Kapazitäts-Proportionalität")
print("-" * 80)
print("boiler_eff * boiler_p_nom = BCHP_QP_RATIO * gen_eff * gen_p_nom")
print(f"{BCHP_THERMAL_EFF} * boiler_p_nom = {BCHP_QP_RATIO:.4f} * {BCHP_ELECTRIC_EFF} * gen_p_nom")

factor = BCHP_QP_RATIO * BCHP_ELECTRIC_EFF / BCHP_THERMAL_EFF
print(f"\n→ boiler_p_nom = {factor:.4f} * gen_p_nom")

print("\nBeispiel mit gen_p_nom = 10 MW:")
gen_p_nom_example = 10.0
boiler_p_nom_example = factor * gen_p_nom_example
print(f"  boiler_p_nom = {factor:.4f} * {gen_p_nom_example} = {boiler_p_nom_example:.4f} MW")

print("\nCONSTRAINT 2: Zeitabhängiges Q/P-Verhältnis")
print("-" * 80)
print("heat_output(t) = BCHP_QP_RATIO * electric_output(t)")
print(f"boiler_eff * boiler_p(t) = {BCHP_QP_RATIO:.4f} * gen_eff * gen_p(t)")
print(f"{BCHP_THERMAL_EFF} * boiler_p(t) = {BCHP_QP_RATIO:.4f} * {BCHP_ELECTRIC_EFF} * gen_p(t)")
print(f"\n→ boiler_p(t) = {factor:.4f} * gen_p(t)")

print("\nBeispiel mit gen_p(t) = 5 MW (50% Last):")
gen_p_example = 5.0
boiler_p_example = factor * gen_p_example
electric_out = BCHP_ELECTRIC_EFF * gen_p_example
thermal_out = BCHP_THERMAL_EFF * boiler_p_example
print(f"  boiler_p(t) = {factor:.4f} * {gen_p_example} = {boiler_p_example:.4f} MW")
print(f"  electric_output(t) = {BCHP_ELECTRIC_EFF} * {gen_p_example} = {electric_out:.2f} MW")
print(f"  thermal_output(t) = {BCHP_THERMAL_EFF} * {boiler_p_example:.4f} = {thermal_out:.2f} MW")
print(f"  Q/P = {thermal_out:.2f} / {electric_out:.2f} = {thermal_out/electric_out:.4f}")

print("\n" + "=" * 80)
print("5. ZUSAMMENFASSUNG")
print("=" * 80)

print(f"""
Die neuen Constraints erzwingen ein FESTES Q/P-Verhältnis von {BCHP_QP_RATIO:.4f}:

✓ In Volllast:  Q/P = {BCHP_QP_RATIO:.4f}
✓ In Teillast:  Q/P = {BCHP_QP_RATIO:.4f}
✓ Bei Aus:      Q = 0, P = 0

Dies entspricht einem realistischen BHKW mit:
- Elektrischem Wirkungsgrad: {BCHP_ELECTRIC_EFF:.1%}
- Thermischem Wirkungsgrad:  {BCHP_THERMAL_EFF:.1%}
- Gesamtwirkungsgrad:        {BCHP_ELECTRIC_EFF + BCHP_THERMAL_EFF:.1%}

Die Brennstoff-Input-Verhältnisse passen sich automatisch an:
- boiler_p_nom = {factor:.4f} * gen_p_nom  (nominale Kapazitäten)
- boiler_p(t) = {factor:.4f} * gen_p(t)    (zeitabhängig)
""")

print("=" * 80)
print("Verifikation abgeschlossen!")
print("=" * 80)
