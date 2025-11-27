"""
Test-Optimierung für Sylt-Modell
"""

import pypsa
import time
from pathlib import Path

def main():
    """Führe Optimierung durch."""
    
    print("=" * 80)
    print("STARTE OPTIMIERUNG")
    print("=" * 80)
    print()
    
    # Lade Netzwerk
    network_file = Path(__file__).parent / "sylt_network_simple.nc"
    n = pypsa.Network(str(network_file))
    
    print(f"Netzwerk geladen: {network_file.name}")
    print(f"  Investment-Perioden: {n.investment_periods.tolist()}")
    print(f"  Zeitschritte gesamt: {len(n.snapshots)}")
    print(f"  Links: {len(n.links)}")
    print(f"  Speicher: {len(n.stores)}")
    print()
    
    # Optimierung
    print("Starte Optimierung (kann mehrere Minuten dauern)...")
    start_time = time.time()
    
    status, condition = n.optimize(
        solver_name="highs",
        multi_invest_periods=True,
        transmission_losses=0,
    )
    
    elapsed = time.time() - start_time
    
    print()
    print("=" * 80)
    print("OPTIMIERUNGSERGEBNIS")
    print("=" * 80)
    print(f"Status: {status}")
    print(f"Bedingung: {condition}")
    print(f"Rechenzeit: {elapsed:.1f} Sekunden ({elapsed/60:.1f} Minuten)")
    print(f"Zielfunktion: {n.objective:,.0f} EUR")
    print()
    
    if status == "ok" and condition == "optimal":
        print("✓ Optimierung erfolgreich!")
        
        # Speichere optimiertes Netzwerk
        output_file = Path(__file__).parent / "sylt_network_optimized.nc"
        n.export_to_netcdf(str(output_file))
        print(f"✓ Optimiertes Netzwerk gespeichert: {output_file.name}")
        
        # Zeige einige Ergebnisse
        print()
        print("=" * 80)
        print("KAPAZITÄTEN (Auswahl)")
        print("=" * 80)
        
        # Neue Technologien mit Kapazitätserweiterung
        for link in n.links.index:
            if n.links.loc[link, "p_nom_extendable"]:
                capacity = n.links.loc[link, "p_nom_opt"]
                if capacity > 0.1:
                    print(f"  {link}: {capacity:.2f} MW")
        
        # Speicher
        print()
        for store in n.stores.index:
            if n.stores.loc[store, "e_nom_extendable"]:
                capacity = n.stores.loc[store, "e_nom_opt"]
                if capacity > 0.1:
                    print(f"  {store}: {capacity:.2f} MWh")
    else:
        print("⚠ Optimierung nicht erfolgreich")
        return None
    
    return n


if __name__ == "__main__":
    network = main()
