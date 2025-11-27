"""
Detaillierte Analyse der stochastischen Optimierung
"""

import pypsa
from pathlib import Path
import pandas as pd
import numpy as np

# Lade optimiertes Netzwerk
network_file = Path(__file__).parent / "sylt_network_full_optimized.nc"
n = pypsa.Network(network_file)

print("=" * 80)
print("DETAILLIERTE ERGEBNISANALYSE - SYLT FERNWÄRME")
print("=" * 80)
print()

print(f"Zielfunktion (erwarteter Wert): {n.objective:,.2f} EUR")
print(f"Szenarien: {', '.join(n.scenarios.tolist())}")
print(f"Investment-Perioden: {', '.join(map(str, n.investment_periods.tolist()))}")
print()

# Hilfsfunktion
def get_base_name(idx):
    return idx[1] if isinstance(idx, tuple) else idx

# =============================================================================
# 1. ALLE KAPAZITÄTEN (auch nicht-ausgebaute)
# =============================================================================
print("=" * 80)
print("1. ALLE KAPAZITÄTEN ÜBER PERIODEN")
print("=" * 80)
print()

# Links gruppiert nach Periode
print("LINKS (Erzeuger):")
print()

for period in n.investment_periods:
    print(f"--- PERIODE {period} ---")
    
    # Hole alle Links für diese Periode
    first_scenario = n.scenarios[0]
    
    # Bestandsanlagen
    existing = []
    new_tech = []
    
    for idx in n.links.index:
        base_name = get_base_name(idx)
        if isinstance(idx, tuple) and idx[0] == first_scenario:
            build_year = n.links.loc[idx, "build_year"]
            if build_year == period:
                p_nom_opt = n.links.loc[idx, "p_nom_opt"]
                p_nom_init = n.links.loc[idx, "p_nom"]
                is_extendable = n.links.loc[idx, "p_nom_extendable"]
                
                if is_extendable:
                    new_tech.append((base_name, p_nom_opt, p_nom_init))
                else:
                    existing.append((base_name, p_nom_opt))
    
    if existing:
        print("  Bestandsanlagen (committable):")
        for name, p_nom in sorted(existing):
            print(f"    {name:40s}: {p_nom:7.2f} MW")
    
    if new_tech:
        print("  Neue Technologien (extendable):")
        for name, p_opt, p_init in sorted(new_tech):
            diff = p_opt - p_init
            if abs(diff) > 0.01:
                status = "AUSGEBAUT" if diff > 0 else "REDUZIERT"
                print(f"    {name:40s}: {p_opt:7.2f} MW (geplant: {p_init:.2f} MW) [{status}: {diff:+.2f} MW]")
            else:
                print(f"    {name:40s}: {p_opt:7.2f} MW (wie geplant)")
    
    print()

# =============================================================================
# 2. SPEICHER
# =============================================================================
print("=" * 80)
print("2. SPEICHER-KAPAZITÄTEN")
print("=" * 80)
print()

for period in n.investment_periods:
    first_scenario = n.scenarios[0]
    
    stores_in_period = []
    for idx in n.stores.index:
        base_name = get_base_name(idx)
        if isinstance(idx, tuple) and idx[0] == first_scenario:
            build_year = n.stores.loc[idx, "build_year"]
            if build_year == period:
                e_nom_opt = n.stores.loc[idx, "e_nom_opt"]
                e_nom_init = n.stores.loc[idx, "e_nom"]
                is_extendable = n.stores.loc[idx, "e_nom_extendable"]
                stores_in_period.append((base_name, e_nom_opt, e_nom_init, is_extendable))
    
    if stores_in_period:
        print(f"--- PERIODE {period} ---")
        for name, e_opt, e_init, extendable in sorted(stores_in_period):
            if extendable:
                diff = e_opt - e_init
                if abs(diff) > 0.01:
                    status = "AUSGEBAUT" if diff > 0 else "REDUZIERT"
                    print(f"  {name:40s}: {e_opt:7.2f} MWh (geplant: {e_init:.2f} MWh) [{status}: {diff:+.2f} MWh]")
                else:
                    print(f"  {name:40s}: {e_opt:7.2f} MWh (wie geplant)")
            else:
                print(f"  {name:40s}: {e_opt:7.2f} MWh (Bestand)")
        print()

# =============================================================================
# 3. ZUSAMMENFASSUNG AUSGEBAUTE KAPAZITÄTEN
# =============================================================================
print("=" * 80)
print("3. ZUSAMMENFASSUNG - NUR AUSBAUTEN")
print("=" * 80)
print()

total_expansion_count = 0
first_scenario = n.scenarios[0]

print("NEUE TECHNOLOGIEN MIT AUSBAU:")
for idx in n.links.index:
    if isinstance(idx, tuple) and idx[0] == first_scenario:
        base_name = get_base_name(idx)
        if n.links.loc[idx, "p_nom_extendable"]:
            p_opt = n.links.loc[idx, "p_nom_opt"]
            p_init = n.links.loc[idx, "p_nom"]
            diff = p_opt - p_init
            if diff > 0.01:
                build_year = n.links.loc[idx, "build_year"]
                print(f"  {base_name:40s} ({build_year}): +{diff:6.2f} MW ({p_init:.2f} → {p_opt:.2f} MW)")
                total_expansion_count += 1

print()
print("SPEICHER MIT AUSBAU:")
for idx in n.stores.index:
    if isinstance(idx, tuple) and idx[0] == first_scenario:
        base_name = get_base_name(idx)
        if n.stores.loc[idx, "e_nom_extendable"]:
            e_opt = n.stores.loc[idx, "e_nom_opt"]
            e_init = n.stores.loc[idx, "e_nom"]
            diff = e_opt - e_init
            if diff > 0.01:
                build_year = n.stores.loc[idx, "build_year"]
                print(f"  {base_name:40s} ({build_year}): +{diff:6.2f} MWh ({e_init:.2f} → {e_opt:.2f} MWh)")
                total_expansion_count += 1

if total_expansion_count == 0:
    print("  Keine Speicher ausgebaut.")

print()
print(f"Gesamt: {total_expansion_count} Technologien/Speicher ausgebaut")
print()

# =============================================================================
# 4. KOSTENANALYSE
# =============================================================================
print("=" * 80)
print("4. KOSTENVERGLEICH")
print("=" * 80)
print()

print("VOLLSTÄNDIGES MODELL (3 Szenarien):")
print(f"  Erwartete Gesamtkosten: {n.objective:>15,.2f} EUR")
print()

# Lade Test-Modell zum Vergleich
test_file = Path(__file__).parent / "sylt_network_optimized.nc"
if test_file.exists():
    n_test = pypsa.Network(test_file)
    print("TEST-MODELL (1 Szenario):")
    print(f"  Gesamtkosten:           {n_test.objective:>15,.2f} EUR")
    print()
    print("UNTERSCHIED:")
    diff_abs = n.objective - n_test.objective
    diff_rel = (diff_abs / n_test.objective) * 100
    print(f"  Absolut:                {diff_abs:>15,.2f} EUR")
    print(f"  Relativ:                {diff_rel:>14.1f} %")
    print()
    print("INTERPRETATION:")
    print("  Das stochastische Modell kostet mehr, weil es robuste")
    print("  Kapazitäten plant, die unter verschiedenen Zukunftsszenarien")
    print("  (optimistisch/base/pessimistisch) gut funktionieren.")
else:
    print("Test-Modell nicht gefunden für Vergleich.")

print()
print("=" * 80)
print("FAZIT")
print("=" * 80)
print()
print("Das Modell nutzt hauptsächlich BESTANDSANLAGEN und baut nur")
print("minimal neue Kapazitäten aus. Dies deutet darauf hin, dass:")
print()
print("1. Die Bestandsanlagen ausreichend Kapazität haben")
print("2. Die Biomethane-Umstellung ab 2035 die CO2-Kosten senkt")
print("3. Neue Technologien (Wärmepumpen) wirtschaftlich noch nicht attraktiv sind")
print()
print("Für weitere Analysen:")
print("  - Dispatch-Profile: Welche Anlagen laufen wann?")
print("  - Sensitivitätsanalyse: CO2-Preise, Strompreise variieren")
print("  - EVPI: Wert perfekter Information berechnen")
print()
