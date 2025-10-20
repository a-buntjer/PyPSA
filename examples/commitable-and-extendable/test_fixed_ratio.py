"""Test der neuen CHP Constraints."""

import sys
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

print("Importiere PyPSA...")
try:
    import pypsa
    print("✓ PyPSA erfolgreich importiert")
except Exception as e:
    print(f"✗ Fehler beim Import von PyPSA: {e}")
    sys.exit(1)

print("\nImportiere committable_extendable_chp1...")
try:
    from committable_extendable_chp1 import (
        BCHP_QP_RATIO,
        BCHP_THERMAL_EFF,
        BCHP_ELECTRIC_EFF,
        build_network,
        add_chp_coupling_constraints,
    )
    print("✓ Module erfolgreich importiert")
except Exception as e:
    print(f"✗ Fehler beim Import: {e}")
    sys.exit(1)

print("\n" + "="*80)
print("TEST DER NEUEN CONSTRAINTS")
print("="*80)

print(f"\nParameter:")
print(f"  BCHP_ELECTRIC_EFF: {BCHP_ELECTRIC_EFF}")
print(f"  BCHP_THERMAL_EFF:  {BCHP_THERMAL_EFF}")
print(f"  BCHP_QP_RATIO:     {BCHP_QP_RATIO:.4f}")

print(f"\nErwartetes festes Verhältnis: Q/P = {BCHP_QP_RATIO:.4f}")
print(f"  (Thermische Leistung / Elektrische Leistung)")

print("\n" + "-"*80)
print("Baue Netzwerk...")
try:
    n = build_network()
    print("✓ Netzwerk erfolgreich gebaut")
    print(f"  Links: {len(n.links)}")
    print(f"  Snapshots: {len(n.snapshots)}")
except Exception as e:
    print(f"✗ Fehler beim Bauen des Netzwerks: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "-"*80)
print("Füge CHP Constraints hinzu und optimiere...")
try:
    add_chp_coupling_constraints(n)
    print("✓ Optimierung erfolgreich abgeschlossen")
except Exception as e:
    print(f"✗ Fehler bei der Optimierung: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "-"*80)
print("Analysiere Ergebnisse...")

# Extrahiere die Link-Variablen
chp_gen = n.links_t.p0["chp_generator"]
chp_boiler = n.links_t.p0["chp_boiler"]

# Berechne elektrische und thermische Leistung (Output)
gen_eff = n.links.at["chp_generator", "efficiency"]
boiler_eff = n.links.at["chp_boiler", "efficiency"]

electric_output = gen_eff * chp_gen
thermal_output = boiler_eff * chp_boiler

# Berechne Q/P Verhältnis (nur für Stunden wo beide > 0)
mask = (electric_output > 0.01) & (thermal_output > 0.01)
if mask.sum() > 0:
    qp_ratios = thermal_output[mask] / electric_output[mask]
    
    print(f"\nStunden mit BHKW-Betrieb: {mask.sum()} von {len(n.snapshots)}")
    print(f"\nQ/P-Verhältnis im Betrieb:")
    print(f"  Minimum:  {qp_ratios.min():.6f}")
    print(f"  Maximum:  {qp_ratios.max():.6f}")
    print(f"  Mittel:   {qp_ratios.mean():.6f}")
    print(f"  Std.-Abw: {qp_ratios.std():.6f}")
    print(f"\nErwartet: {BCHP_QP_RATIO:.6f}")
    
    # Prüfe ob das Verhältnis konstant ist (mit kleiner Toleranz)
    tolerance = 1e-4
    is_constant = (qp_ratios.max() - qp_ratios.min()) < tolerance
    
    if is_constant:
        print(f"\n✓✓✓ ERFOLG: Q/P-Verhältnis ist KONSTANT (±{tolerance})!")
        print(f"    Das BHKW arbeitet mit festem Verhältnis in Teillast und Volllast.")
    else:
        print(f"\n✗✗✗ FEHLER: Q/P-Verhältnis variiert um {qp_ratios.max() - qp_ratios.min():.6f}!")
        print(f"    Das feste Verhältnis wird NICHT eingehalten.")
else:
    print("\n⚠ Warnung: BHKW war in keiner Stunde aktiv!")

# Prüfe nominale Kapazitäten
gen_p_nom = n.links.at["chp_generator", "p_nom_opt"]
boiler_p_nom = n.links.at["chp_boiler", "p_nom_opt"]

print(f"\nNominale Kapazitäten (Brennstoff-Input):")
print(f"  Generator: {gen_p_nom:.2f} MW")
print(f"  Boiler:    {boiler_p_nom:.2f} MW")

# Berechne nominale Output-Kapazitäten
gen_output_nom = gen_eff * gen_p_nom
boiler_output_nom = boiler_eff * boiler_p_nom

print(f"\nNominale Output-Kapazitäten:")
print(f"  Elektrisch: {gen_output_nom:.2f} MW_el")
print(f"  Thermisch:  {boiler_output_nom:.2f} MW_th")

if gen_output_nom > 0:
    qp_nom = boiler_output_nom / gen_output_nom
    print(f"\nNominales Q/P-Verhältnis: {qp_nom:.6f}")
    print(f"Erwartet:                 {BCHP_QP_RATIO:.6f}")
    
    if abs(qp_nom - BCHP_QP_RATIO) < tolerance:
        print(f"✓ Nominales Verhältnis ist korrekt!")
    else:
        print(f"✗ Nominales Verhältnis weicht ab!")

print("\n" + "="*80)
print("Test abgeschlossen!")
print("="*80)
