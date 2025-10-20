"""Vollständige Diagnose: Warum wird das BHKW nicht genutzt?"""

import pypsa
import numpy as np
import pandas as pd

# Lade das Netzwerk
n = pypsa.Network("committable_extendable_chp1.nc")

print("=" * 80)
print("VOLLSTÄNDIGE BHKW-DIAGNOSE")
print("=" * 80)

# 1. Prüfe, ob BHKW installiert wurde
print("\n1. KAPAZITÄTEN:")
print("-" * 80)
chp_fuel_pnom = n.links.loc["chp_fuel", "p_nom_opt"]
chp_gen_pnom = n.links.loc["chp_generator", "p_nom_opt"]
chp_boiler_pnom = n.links.loc["chp_boiler", "p_nom_opt"]
aux_boiler_pnom = n.links.loc["aux_heat_boiler", "p_nom_opt"]

print(f"chp_fuel p_nom_opt:       {chp_fuel_pnom:8.4f} MW")
print(f"chp_generator p_nom_opt:  {chp_gen_pnom:8.4f} MW")
print(f"chp_boiler p_nom_opt:     {chp_boiler_pnom:8.4f} MW")
print(f"aux_heat_boiler p_nom_opt:{aux_boiler_pnom:8.4f} MW")

# 2. Prüfe die Kosten
print("\n2. KOSTEN-VERGLEICH:")
print("-" * 80)

# BHKW-Kosten (annualisiert)
chp_gen_capex = n.links.loc["chp_generator", "capital_cost"]
chp_boiler_capex = n.links.loc["chp_boiler", "capital_cost"]
chp_fuel_marginal = n.links.loc["chp_fuel", "marginal_cost"]

# Aux-Boiler-Kosten
aux_boiler_capex = n.links.loc["aux_heat_boiler", "capital_cost"]
aux_boiler_marginal = n.links.loc["aux_heat_boiler", "marginal_cost"]

# Generator-Kosten
wind_capex = n.generators.loc["wind_turbine", "capital_cost"]
market_capex = n.generators.loc["grid_trade", "capital_cost"]

print("BHKW:")
print(f"  chp_generator capital_cost:  {chp_gen_capex} EUR/MW/Jahr")
print(f"  chp_boiler capital_cost:     {chp_boiler_capex} EUR/MW/Jahr")
print(f"  chp_fuel marginal_cost:      {chp_fuel_marginal} EUR/MWh")
print(f"  Gesamt CAPEX:                 {chp_gen_capex + chp_boiler_capex} EUR/MW/Jahr")

print(f"\nAlternativen:")
print(f"  aux_heat_boiler CAPEX:       {aux_boiler_capex} EUR/MW/Jahr")
print(f"  aux_heat_boiler marginal:    {aux_boiler_marginal} EUR/MWh")
print(f"  wind CAPEX:                  {wind_capex} EUR/MW/Jahr")
print(f"  market CAPEX:                {market_capex} EUR/MW/Jahr")

# 3. Berechne die effektiven Kosten pro MWh
print("\n3. EFFEKTIVE KOSTEN PRO MWh (bei 50% Auslastung):")
print("-" * 80)

hours = 8760 * 0.5  # 50% Auslastung

# BHKW Stromkosten (pro MWh Strom)
chp_gen_eff = n.links.loc["chp_generator", "efficiency"]
chp_boiler_eff = n.links.loc["chp_boiler", "efficiency"]

fuel_per_mwh_elec = 1.0 / chp_gen_eff
bhkw_fuel_cost = fuel_per_mwh_elec * chp_fuel_marginal
bhkw_capex_elec = chp_gen_capex / hours

print(f"BHKW Strom:")
print(f"  Brennstoff:  {bhkw_fuel_cost:.2f} EUR/MWh")
print(f"  CAPEX:       {bhkw_capex_elec:.2f} EUR/MWh")
print(f"  Gesamt:      {bhkw_fuel_cost + bhkw_capex_elec:.2f} EUR/MWh")

# Durchschnittlicher Marktpreis
avg_market = n.generators_t.marginal_cost["grid_trade"].mean()
print(f"\nMarkt Strom:  {avg_market:.2f} EUR/MWh (Durchschnitt)")

# BHKW Wärmekosten
# Bei Q/P = 1.2 und P = 1 MW: Q = 1.2 MW
# Fuel_total = Fuel_gen + Fuel_boiler
# Mit Proportionalität: P_boiler = 0.6104 * P_gen
# => Fuel_boiler = 0.6104 * Fuel_gen = 0.6104 * fuel_per_mwh_elec

fuel_per_mwh_heat = 0.6104 * fuel_per_mwh_elec  # aus Proportionalität
bhkw_fuel_cost_heat = fuel_per_mwh_heat * chp_fuel_marginal
bhkw_capex_heat = chp_boiler_capex / hours

print(f"\nBHKW Wärme:")
print(f"  Brennstoff:  {bhkw_fuel_cost_heat:.2f} EUR/MWh")
print(f"  CAPEX:       {bhkw_capex_heat:.2f} EUR/MWh")
print(f"  Gesamt:      {bhkw_fuel_cost_heat + bhkw_capex_heat:.2f} EUR/MWh")

# Aux-Boiler Wärme
aux_capex_heat = aux_boiler_capex / hours
print(f"\nAux-Boiler Wärme:")
print(f"  Marginal:    {aux_boiler_marginal:.2f} EUR/MWh")
print(f"  CAPEX:       {aux_capex_heat:.2f} EUR/MWh")
print(f"  Gesamt:      {aux_boiler_marginal + aux_capex_heat:.2f} EUR/MWh")

# 4. Prüfe Constraints
print("\n4. CONSTRAINT-ANALYSE:")
print("-" * 80)

chp_gen_pmin = n.links.loc["chp_generator", "p_min_pu"]
chp_boiler_pmin = n.links.loc["chp_boiler", "p_min_pu"]

print(f"chp_generator p_min_pu:  {chp_gen_pmin} (muss mindestens {chp_gen_pmin*100:.0f}% laufen wenn aktiv)")
print(f"chp_boiler p_min_pu:     {chp_boiler_pmin} (muss mindestens {chp_boiler_pmin*100:.0f}% laufen wenn aktiv)")

if chp_gen_pnom > 0.1:  # wenn installiert
    min_gen = chp_gen_pnom * chp_gen_pmin * chp_gen_eff
    min_boiler = chp_boiler_pnom * chp_boiler_pmin * chp_boiler_eff
    print(f"\nBei Installation würde das bedeuten:")
    print(f"  Min. Strom:  {min_gen:.2f} MW")
    print(f"  Min. Wärme:  {min_boiler:.2f} MW")
else:
    print(f"\n⚠ BHKW wurde gar nicht installiert (p_nom_opt ≈ 0)")

# 5. Prüfe ob Start-Up-Costs zu hoch sind
print("\n5. START-UP-COSTS:")
print("-" * 80)
chp_gen_startup = n.links.loc["chp_generator", "start_up_cost"]
chp_gen_shutdown = n.links.loc["chp_generator", "shut_down_cost"]
chp_boiler_startup = n.links.loc["chp_boiler", "start_up_cost"]
chp_boiler_shutdown = n.links.loc["chp_boiler", "shut_down_cost"]

print(f"chp_generator start_up_cost:   {chp_gen_startup} EUR")
print(f"chp_generator shut_down_cost:  {chp_gen_shutdown} EUR")
print(f"chp_boiler start_up_cost:      {chp_boiler_startup} EUR")
print(f"chp_boiler shut_down_cost:     {chp_boiler_shutdown} EUR")

# 6. Prüfe die tatsächliche Nutzung von Wind und Market
print("\n6. TATSÄCHLICHE STROM-ERZEUGUNG:")
print("-" * 80)
wind_gen = n.generators_t.p["wind_turbine"].sum()
market_gen = n.generators_t.p["grid_trade"].sum()
wind_pnom = n.generators.loc["wind_turbine", "p_nom_opt"]
market_pnom = n.generators.loc["grid_trade", "p_nom_opt"]

print(f"Wind:        p_nom={wind_pnom:7.2f} MW, Erzeugung={wind_gen:10.2f} MWh")
print(f"Market:      p_nom={market_pnom:7.2f} MW, Erzeugung={market_gen:10.2f} MWh")
print(f"Gesamt Strombedarf: {n.loads_t.p_set['electric_demand'].sum():.2f} MWh")

# 7. Prüfe die tatsächliche Wärme-Erzeugung
print("\n7. TATSÄCHLICHE WÄRME-ERZEUGUNG:")
print("-" * 80)
aux_heat = n.links_t.p1["aux_heat_boiler"].sum()
print(f"Aux-Boiler:  p_nom={aux_boiler_pnom:7.2f} MW, Erzeugung={aux_heat:10.2f} MWh")
print(f"Gesamt Wärmebedarf: {n.loads_t.p_set['heat_demand'].sum():.2f} MWh")

# 8. Diagnose
print("\n8. DIAGNOSE:")
print("-" * 80)

total_bhkw_capex = chp_gen_capex + chp_boiler_capex  # 900 EUR/MW/Jahr
total_alt_capex = wind_capex  # 900 EUR/MW/Jahr (Wind) + Market (0)

print(f"BHKW CAPEX gesamt:       {total_bhkw_capex} EUR/MW/Jahr")
print(f"Wind CAPEX:              {wind_capex} EUR/MW/Jahr")
print(f"\n→ CAPEX ist fast gleich!")

# Aber: BHKW hat zusätzlich Brennstoffkosten + Start-Up-Costs + Commitment-Constraints
print(f"\nBHKW Nachteile:")
print(f"  - Brennstoffkosten:    {chp_fuel_marginal} EUR/MWh")
print(f"  - Start-Up-Costs:      {chp_gen_startup + chp_boiler_startup} EUR")
print(f"  - Commitment (binär):  reduziert Flexibilität")
print(f"  - p_min_pu:            zwingt zu Mindestlast")
print(f"  - Starre Kopplung:     Strom+Wärme müssen passen")

print(f"\nAlternative Vorteile:")
print(f"  Wind:")
print(f"    - Keine Brennstoffkosten")
print(f"    - Keine Commitment-Constraints")
print(f"    - Flexible Nutzung")
print(f"  Market:")
print(f"    - Kein CAPEX")
print(f"    - Variable Kosten (kann negative Preise nutzen!)")
print(f"    - Extrem flexibel (kann auch verkaufen)")

# Prüfe negative Preise
negative_hours = (n.generators_t.marginal_cost["grid_trade"] < 0).sum()
print(f"\nMarkt hat {negative_hours} Stunden mit NEGATIVEN Preisen!")
print(f"→ In diesen Stunden wird man fürs VERBRAUCHEN bezahlt!")

print("\n9. HAUPTGRUND:")
print("-" * 80)
print("Das BHKW ist NICHT wettbewerbsfähig, weil:")
print("  1. Brennstoffkosten (5 EUR/MWh) machen es teurer als Wind (0 EUR/MWh)")
print("  2. Market kann negative Preise nutzen (Arbitrage)")
print("  3. BHKW ist durch Commitment + Mindestlast + Kopplung unflexibel")
print("  4. Aux-Boiler hat hohe marginal costs (60 EUR/MWh), aber wenig CAPEX")
print("     → Für sporadische Wärmenutzung ist das günstiger als BHKW mit festem CAPEX")

print("\n10. LÖSUNGEN:")
print("-" * 80)
print("Um das BHKW attraktiv zu machen:")
print("  a) Brennstoffkosten reduzieren (z.B. auf 1-2 EUR/MWh)")
print("  b) BHKW CAPEX reduzieren (z.B. auf 300-400 EUR/MW/Jahr)")
print("  c) Aux-Boiler marginal_cost erhöhen (z.B. auf 100-150 EUR/MWh)")
print("  d) Marktpreise realistischer machen (weniger negative Preise)")
print("  e) Commitment-Constraints lockern (p_min_pu reduzieren)")

print("\n" + "=" * 80)
