"""
Optimierung des vollständigen 3-Szenarien-Modells
"""

import pypsa
from pathlib import Path
import pandas as pd

# Lade Netzwerk
network_file = Path(__file__).parent / "sylt_network_full.nc"
print("=" * 80)
print("OPTIMIERUNG - VOLLSTÄNDIGES STOCHASTISCHES MODELL")
print("=" * 80)
print()
print(f"Lade Netzwerk: {network_file}")

n = pypsa.Network(network_file)

print()
print("NETZWERK-ÜBERSICHT:")
print(f"  Szenarien: {n.scenarios.tolist()}")
print(f"  Investment-Perioden: {n.investment_periods.tolist()}")
print(f"  Zeitschritte gesamt: {len(n.snapshots)}")
print(f"  Links (Erzeuger): {len(n.links)}")
print(f"  Speicher: {len(n.stores)}")
print()

# Starte Optimierung
print("Starte Optimierung (kann 30-60 Minuten dauern)...")
print("Hinweis: 3 Szenarien = ~3x längere Rechenzeit")
print()

try:
    result = n.optimize(
        solver_name="highs",
        solver_options={
            "presolve": "on",
            "parallel": "on",
            "threads": 12,
            "time_limit": 7200.0,  # 2 Stunden
            "mip_rel_gap": 0.05,  # 5% Gap
        }
    )
    
    print()
    print("=" * 80)
    print("OPTIMIERUNG ABGESCHLOSSEN")
    print("=" * 80)
    print()
    
    if result[0] == "ok":
        print(f"Status: Optimal")
        print(f"Zielfunktion (erwarteter Wert): {n.objective:,.2f} EUR")
        print()
        
        # SOFORT speichern nach erfolgreicher Optimierung
        output_file = Path(__file__).parent / "sylt_network_full_optimized.nc"
        print(f"Speichere optimiertes Netzwerk: {output_file}")
        n.export_to_netcdf(output_file)
        print(f"✓ Erfolgreich gespeichert!")
        print()
        
        # Kapazitätsergebnisse
        print("=" * 80)
        print("OPTIMALE KAPAZITÄTEN")
        print("=" * 80)
        print()
        
        # Neue Technologien - gruppiere nach Basisname (ohne Szenario-Präfix)
        extendable_links = n.links[n.links.p_nom_extendable]
        if not extendable_links.empty:
            print("NEUE TECHNOLOGIEN (extendable):")
            # Extrahiere eindeutige Link-Namen (ohne Szenario)
            base_names = set()
            for link_name in extendable_links.index:
                # Bei MultiIndex ist link_name ein Tuple (scenario, name)
                if isinstance(link_name, tuple):
                    base_names.add(link_name[1])
                else:
                    base_names.add(link_name)
            
            for base_name in sorted(base_names):
                # Hole Werte vom ersten Szenario (Kapazitäten sind gleich über Szenarien)
                first_scenario = n.scenarios[0] if hasattr(n, 'scenarios') else None
                if first_scenario:
                    full_name = (first_scenario, base_name)
                    if full_name in n.links.index:
                        p_nom_opt = n.links.loc[full_name, "p_nom_opt"]
                        p_nom_init = n.links.loc[full_name, "p_nom"]
                        build_year = n.links.loc[full_name, "build_year"]
                        if p_nom_opt > p_nom_init + 0.01:
                            print(f"  {base_name:35s}: {p_nom_opt:8.2f} MW (geplant: {p_nom_init:.1f} MW, Jahr: {build_year})")
        print()
        
        # Speicher
        extendable_stores = n.stores[n.stores.e_nom_extendable]
        if not extendable_stores.empty:
            print("SPEICHER-AUSBAU:")
            base_names = set()
            for store_name in extendable_stores.index:
                if isinstance(store_name, tuple):
                    base_names.add(store_name[1])
                else:
                    base_names.add(store_name)
            
            for base_name in sorted(base_names):
                first_scenario = n.scenarios[0] if hasattr(n, 'scenarios') else None
                if first_scenario:
                    full_name = (first_scenario, base_name)
                    if full_name in n.stores.index:
                        e_nom_opt = n.stores.loc[full_name, "e_nom_opt"]
                        e_nom_init = n.stores.loc[full_name, "e_nom"]
                        build_year = n.stores.loc[full_name, "build_year"]
                        if e_nom_opt > e_nom_init + 0.01:
                            print(f"  {base_name:35s}: {e_nom_opt:8.2f} MWh (geplant: {e_nom_init:.1f} MWh, Jahr: {build_year})")
        print()
        
        print("Für detaillierte Analyse: python show_full_results.py")
        
    else:
        print(f"Optimierung fehlgeschlagen: {result}")
        print("Statuscode:", result[0])
        print("Meldung:", result[1])

except Exception as e:
    print("FEHLER bei Optimierung:")
    print(str(e))
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
