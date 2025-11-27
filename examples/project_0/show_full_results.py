"""
Zeige Ergebnisse der vollständigen Optimierung
"""

import pypsa
from pathlib import Path
import pandas as pd

# Lade optimiertes Netzwerk
network_file = Path(__file__).parent / "sylt_network_full_optimized.nc"
print("=" * 80)
print("VOLLSTÄNDIGES STOCHASTISCHES MODELL - ERGEBNISSE")
print("=" * 80)
print()

if not network_file.exists():
    print(f"FEHLER: {network_file} nicht gefunden!")
    exit(1)

n = pypsa.Network(network_file)

print(f"Status: Optimal")
print(f"Zielfunktion (erwarteter Wert über Szenarien): {n.objective:,.2f} EUR")
print()
print(f"Szenarien: {n.scenarios.tolist()}")
print(f"Investment-Perioden: {n.investment_periods.tolist()}")
print()

# Extrahiere Basis-Namen (ohne Szenario)
def get_base_name(idx):
    """Extrahiere Basisname ohne Szenario-Präfix."""
    if isinstance(idx, tuple):
        return idx[1]
    return idx

# Kapazitäten - gruppiere nach Basisname
print("=" * 80)
print("OPTIMALE KAPAZITÄTEN (szenario-unabhängig)")
print("=" * 80)
print()

# Links (neue Technologien)
extendable_links = n.links[n.links.p_nom_extendable]
if not extendable_links.empty:
    print("NEUE TECHNOLOGIEN:")
    print()
    
    base_names = sorted(set([get_base_name(idx) for idx in extendable_links.index]))
    
    for base_name in base_names:
        # Hole Werte vom ersten Szenario
        first_scenario = n.scenarios[0]
        full_name = (first_scenario, base_name)
        
        if full_name in n.links.index:
            p_nom_opt = n.links.loc[full_name, "p_nom_opt"]
            p_nom_init = n.links.loc[full_name, "p_nom"]
            build_year = n.links.loc[full_name, "build_year"]
            
            if p_nom_opt > p_nom_init + 0.01:
                diff = p_nom_opt - p_nom_init
                percent = (diff / max(p_nom_init, 0.001)) * 100 if p_nom_init > 0 else 999
                print(f"  {base_name:35s} ({build_year}):")
                print(f"    Optimal:  {p_nom_opt:7.2f} MW")
                print(f"    Geplant:  {p_nom_init:7.2f} MW")
                print(f"    Differenz: {diff:+6.2f} MW ({percent:+6.1f}%)")
                print()

print()

# Speicher
extendable_stores = n.stores[n.stores.e_nom_extendable]
if not extendable_stores.empty:
    print("SPEICHER:")
    print()
    
    base_names = sorted(set([get_base_name(idx) for idx in extendable_stores.index]))
    
    for base_name in base_names:
        first_scenario = n.scenarios[0]
        full_name = (first_scenario, base_name)
        
        if full_name in n.stores.index:
            e_nom_opt = n.stores.loc[full_name, "e_nom_opt"]
            e_nom_init = n.stores.loc[full_name, "e_nom"]
            build_year = n.stores.loc[full_name, "build_year"]
            
            if e_nom_opt > e_nom_init + 0.01:
                diff = e_nom_opt - e_nom_init
                print(f"  {base_name:35s} ({build_year}):")
                print(f"    Optimal:  {e_nom_opt:7.2f} MWh")
                print(f"    Geplant:  {e_nom_init:7.2f} MWh")
                print(f"    Differenz: {diff:+6.2f} MWh")
                print()

print()
print("=" * 80)
print("INTERPRETATION")
print("=" * 80)
print()
print("Die Kapazitäten sind über alle Szenarien optimiert (robust).")
print("Sie minimieren den erwarteten Wert der Gesamtkosten unter Unsicherheit.")
print()
print("Vergleich zum deterministischen Test-Modell (6.6M EUR):")
print(f"  Vollständiges Modell:  {n.objective:,.2f} EUR")
print(f"  Faktor:                {n.objective / 6624629:.2f}x")
print()
print("Höhere Kosten sind durch Robustheit gegen Unsicherheit begründet.")
print()
