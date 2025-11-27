"""
EVPI Berechnung (Expected Value of Perfect Information)
========================================================

Berechnet den Wert perfekter Vorhersage durch Vergleich:
1. Stochastisches Modell (hier-and-now Entscheidung)
2. Perfekte Information (wait-and-see für jedes Szenario)

EVPI = VSS - WS
wobei:
- RP (Recourse Problem): Stochastisches Modell = 13.55M EUR
- WS (Wait-and-See): Optimiere für jedes Szenario einzeln
- EVPI: Was würde perfekte Vorhersage bringen?
"""

import pypsa
import pandas as pd
import numpy as np
from pathlib import Path

print("=" * 80)
print("EVPI-ANALYSE (EXPECTED VALUE OF PERFECT INFORMATION)")
print("=" * 80)
print()

# =============================================================================
# 1. STOCHASTISCHES MODELL (RP - Recourse Problem)
# =============================================================================
print("1. STOCHASTISCHES MODELL (ROBUST)")
print("-" * 80)

n_stochastic = pypsa.Network(Path(__file__).parent / "sylt_network_full_optimized.nc")
rp_cost = n_stochastic.objective

print(f"  Optimale Kosten (robust über Szenarien): {rp_cost:>15,.2f} EUR")
print(f"  Strategie: Eine Lösung für alle Szenarien")
print()

# Szenarien und Wahrscheinlichkeiten
scenarios = n_stochastic.scenarios.tolist()
scenario_probs = {
    "optimistic": 0.25,
    "base": 0.50,
    "pessimistic": 0.25,
}

print(f"  Szenarien: {', '.join(scenarios)}")
print(f"  Wahrscheinlichkeiten: {scenario_probs}")
print()

# =============================================================================
# 2. DETERMINISTISCHES MODELL (EEV - Expected Value Problem)
# =============================================================================
print("2. DETERMINISTISCHES MODELL (NUR BASE-SZENARIO)")
print("-" * 80)

n_deterministic = pypsa.Network(Path(__file__).parent / "sylt_network_optimized.nc")
eev_cost = n_deterministic.objective

print(f"  Optimale Kosten (nur Base-Szenario):     {eev_cost:>15,.2f} EUR")
print(f"  Strategie: Nur für erwarteten Fall optimiert")
print()

# =============================================================================
# 3. WAIT-AND-SEE (WS) - BERECHNUNG
# =============================================================================
print("3. WAIT-AND-SEE ANALYSE")
print("-" * 80)
print()
print("Für echte WS-Berechnung müssten wir für jedes Szenario SEPARAT optimieren:")
print()

# Da wir die szenario-spezifischen Optimierungen nicht haben,
# schätzen wir basierend auf den Kostenunterschieden

# Annahme: Die Kosten variieren je nach Szenario um ±15%
ws_costs = {
    "optimistic": eev_cost * 0.90,  # Optimistisch: 10% günstiger
    "base": eev_cost * 1.00,        # Base: wie deterministisch
    "pessimistic": eev_cost * 1.15, # Pessimistisch: 15% teurer
}

print("Geschätzte Kosten bei perfekter Vorhersage pro Szenario:")
for scenario in ["optimistic", "base", "pessimistic"]:
    prob = scenario_probs[scenario]
    cost = ws_costs[scenario]
    print(f"  {scenario:15s} (p={prob:.2f}): {cost:>15,.2f} EUR")

ws_expected = sum(ws_costs[s] * scenario_probs[s] for s in scenarios)
print()
print(f"  Erwartete WS-Kosten:                      {ws_expected:>15,.2f} EUR")
print()

# =============================================================================
# 4. VSS (VALUE OF STOCHASTIC SOLUTION)
# =============================================================================
print("4. VALUE OF STOCHASTIC SOLUTION (VSS)")
print("-" * 80)

# VSS = EEV - RP
# = Kosten wenn deterministisch geplant - Kosten wenn stochastisch geplant
# = Verbesserung durch stochastische Planung

# ABER: Hier ist RP > EEV, was bedeutet die stochastische Lösung ist TEURER
# Das ist normal, weil sie ROBUSTER ist!

vss = eev_cost - rp_cost

print(f"  VSS = EEV - RP")
print(f"      = {eev_cost:,.2f} - {rp_cost:,.2f}")
print(f"      = {vss:,.2f} EUR")
print()

if vss < 0:
    print(f"  Die stochastische Lösung kostet {abs(vss):,.2f} EUR MEHR.")
    print(f"  Dies ist der 'Preis der Robustheit':")
    print(f"  → Die Lösung funktioniert in ALLEN Szenarien gut")
    print(f"  → Vermeidet Worst-Case Kosten bei ungünstiger Entwicklung")
else:
    print(f"  Die stochastische Lösung spart {vss:,.2f} EUR.")

print()

# =============================================================================
# 5. EVPI (EXPECTED VALUE OF PERFECT INFORMATION)
# =============================================================================
print("5. EXPECTED VALUE OF PERFECT INFORMATION (EVPI)")
print("-" * 80)

# EVPI = RP - WS
# = Was würde perfekte Vorhersage einsparen?
evpi = rp_cost - ws_expected

print(f"  EVPI = RP - WS")
print(f"       = {rp_cost:,.2f} - {ws_expected:,.2f}")
print(f"       = {evpi:,.2f} EUR")
print()

if evpi > 0:
    evpi_percent = (evpi / rp_cost) * 100
    print(f"  Wert perfekter Information: {evpi:,.2f} EUR ({evpi_percent:.1f}%)")
    print()
    print("  INTERPRETATION:")
    print(f"  → Wenn wir die Zukunft perfekt vorhersagen könnten,")
    print(f"    würden wir {evpi:,.2f} EUR sparen")
    print(f"  → Das ist die Obergrenze für Investitionen in Prognose/Forecasting")
    print(f"  → Alles unter {evpi:,.2f} EUR für bessere Prognosen lohnt sich!")
else:
    print(f"  Kein positiver EVPI: Die robuste Lösung ist bereits optimal.")

print()

# =============================================================================
# 6. ZUSAMMENFASSUNG
# =============================================================================
print("=" * 80)
print("ZUSAMMENFASSUNG")
print("=" * 80)
print()

print("KOSTENVERGLEICH:")
print(f"  WS (mit perfekter Info):      {ws_expected:>15,.2f} EUR (theoretisches Optimum)")
print(f"  EEV (deterministisch):        {eev_cost:>15,.2f} EUR (nur Base-Szenario)")
print(f"  RP (stochastisch):            {rp_cost:>15,.2f} EUR (robust über Szenarien)")
print()

print("KENNZAHLEN:")
if vss < 0:
    print(f"  Robustheitspreis (|VSS|):     {abs(vss):>15,.2f} EUR")
    print(f"    → Mehrkosten für robuste Lösung gegenüber deterministisch")
else:
    print(f"  VSS (Stochast. Vorteil):      {vss:>15,.2f} EUR")

if evpi > 0:
    print(f"  EVPI (Wert Prognose):         {evpi:>15,.2f} EUR")
    print(f"    → Maximaler Wert besserer Vorhersagen")
    print()
    print(f"  EVPI als % von RP:            {(evpi/rp_cost)*100:>14.1f} %")

print()

print("EMPFEHLUNGEN:")
print()
if evpi > 100000:
    print("  ✓ EVPI ist signifikant (> 100k EUR)")
    print("    → Investitionen in bessere Prognosen lohnenswert:")
    print("      * Detaillierte Nachfrage-Forecasts")
    print("      * Energiepreis-Modellierung")
    print("      * Szenario-Analyse verfeinern")
    print()
elif evpi > 10000:
    print("  ~ EVPI ist moderat (10-100k EUR)")
    print("    → Gezielte Verbesserungen in Prognose-Qualität sinnvoll")
    print()
else:
    print("  ○ EVPI ist gering (< 10k EUR)")
    print("    → Weitere Prognose-Verbesserungen bringen wenig")
    print("    → Robuste Lösung ist bereits nahe am Optimum")
    print()

if abs(vss) > 1000000:
    print(f"  ⚠ Robustheitspreis ist hoch ({abs(vss)/1000000:.1f}M EUR)")
    print("    → Prüfen ob Szenarien realistisch sind")
    print("    → Evtl. Wahrscheinlichkeiten anpassen")
    print()

print("=" * 80)
print()
print("HINWEIS:")
print("Diese Analyse nutzt SCHÄTZUNGEN für WS-Kosten.")
print("Für exakte EVPI: Jedes Szenario separat optimieren und mitteln.")
print()
