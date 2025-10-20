"""Analysiere das BHKW im Netzwerk."""

import pypsa
import pandas as pd

# Lade das Netzwerk
n = pypsa.Network("committable_extendable_chp1.nc")

print("=" * 80)
print("BHKW-ANALYSE")
print("=" * 80)

# Prüfe die installierten Kapazitäten
print("\n1. INSTALLIERTE KAPAZITÄTEN (p_nom_opt):")
print("-" * 80)
for link_name in ["chp_generator", "chp_boiler"]:  # chp_fuel entfernt
    if link_name in n.links.index:
        p_nom = n.links.loc[link_name, "p_nom_opt"]
        print(f"{link_name:20s}: {p_nom:8.2f} MW")

# Prüfe die tatsächliche Nutzung über alle Zeitschritte
print("\n2. TATSÄCHLICHE NUTZUNG (Summe über alle Zeitschritte):")
print("-" * 80)
for link_name in ["chp_generator", "chp_boiler"]:  # chp_fuel entfernt
    if link_name in n.links_t.p0.columns:
        total_energy = n.links_t.p0[link_name].sum()
        max_power = n.links_t.p0[link_name].max()
        print(f"{link_name:20s}: Σ={total_energy:10.2f} MWh, max={max_power:8.2f} MW")

# Prüfe einige Beispiel-Zeitschritte
print("\n3. BEISPIEL-ZEITSCHRITTE (erste 10 Stunden):")
print("-" * 80)
df = pd.DataFrame({
    "gen": n.links_t.p0["chp_generator"][:10],  # chp_fuel entfernt
    "boiler": n.links_t.p0["chp_boiler"][:10],
})
print(df.to_string())

# Prüfe andere Wärmeerzeuger
print("\n4. ANDERE WÄRMEERZEUGER:")
print("-" * 80)
if "aux_heat_boiler" in n.links.index:
    p_nom = n.links.loc["aux_heat_boiler", "p_nom_opt"]
    total_energy = n.links_t.p0["aux_heat_boiler"].sum()
    max_power = n.links_t.p0["aux_heat_boiler"].max()
    print(f"aux_heat_boiler: p_nom={p_nom:.2f} MW, Σ={total_energy:.2f} MWh, max={max_power:.2f} MW")

# Prüfe Stromerzeuger
print("\n5. STROMERZEUGER:")
print("-" * 80)
for gen_name in ["wind_turbine", "gas_peaker", "grid_trade"]:
    if gen_name in n.generators.index:
        p_nom = n.generators.loc[gen_name, "p_nom_opt"]
        total_energy = n.generators_t.p[gen_name].sum()
        max_power = n.generators_t.p[gen_name].max()
        min_power = n.generators_t.p[gen_name].min()
        print(f"{gen_name:20s}: p_nom={p_nom:8.2f} MW, Σ={total_energy:10.2f} MWh, min={min_power:8.2f}, max={max_power:8.2f} MW")

# Prüfe Kosten
print("\n6. KOSTEN-ÜBERSICHT:")
print("-" * 80)
print(f"Gesamtkosten: {n.objective:,.2f} EUR")

print("\n7. LINK-EFFIZIENZEN:")
print("-" * 80)
for link_name in ["chp_generator", "chp_boiler", "aux_heat_boiler"]:  # chp_fuel entfernt
    if link_name in n.links.index:
        eff = n.links.loc[link_name, "efficiency"]
        mc = n.links.loc[link_name, "marginal_cost"]
        cc = n.links.loc[link_name, "capital_cost"]
        print(f"{link_name:20s}: eff={eff:.3f}, marginal_cost={mc:.2f}, capital_cost={cc:.2f}")

print("\n" + "=" * 80)
