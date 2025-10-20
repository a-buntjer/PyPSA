"""Kosten-Vergleich zwischen BHKW und Alternativen."""

import numpy as np

print("=" * 80)
print("KOSTEN-VERGLEICH: BHKW vs. Alternativen")
print("=" * 80)

# BHKW-Parameter
chp_gen_eff = 0.468  # elektrischer Wirkungsgrad
chp_boiler_eff = 0.920  # thermischer Wirkungsgrad
chp_fuel_cost = 5.0  # EUR/MWh Brennstoff
chp_gen_capex = 520  # EUR/MW/Jahr
chp_boiler_capex = 380  # EUR/MW/Jahr

# Alternativen
aux_boiler_eff = 0.92
aux_boiler_marginal = 60.0  # EUR/MWh
aux_boiler_capex = 180  # EUR/MW/Jahr

wind_capex = 900  # EUR/MW/Jahr
wind_marginal = 0.0

market_capex = 0.0  # EUR/MW/Jahr
# market_marginal variiert stark (siehe Profil: -20 bis 110 EUR/MWh)

print("\n1. BHKW-KOSTEN PRO MWh:")
print("-" * 80)

# Um 1 MWh Strom zu erzeugen:
fuel_for_1mwh_elec = 1.0 / chp_gen_eff  # MW Brennstoff für 1 MW Strom
elec_fuel_cost = fuel_for_1mwh_elec * chp_fuel_cost
print(f"Brennstoff für 1 MWh Strom: {fuel_for_1mwh_elec:.3f} MWh @ {chp_fuel_cost} EUR/MWh = {elec_fuel_cost:.2f} EUR")

# Gleichzeitig erzeugte Wärme (bei starrer Kopplung mit Ratio 0.9):
# Q/P = 0.9 (Output-Verhältnis)
# Aber: Wir müssen das auf Input-Basis berechnen!
# Wenn wir F MWh Brennstoff einsetzen und davon x für Strom und (F-x) für Wärme:
# P = 0.468 * x
# Q = 0.92 * (F - x)
# Q/P = 0.9 => Q = 0.9 * P
# => 0.92 * (F - x) = 0.9 * 0.468 * x
# => 0.92*F - 0.92*x = 0.4212*x
# => 0.92*F = 0.92*x + 0.4212*x = 1.3412*x
# => x = 0.92*F / 1.3412 = 0.686*F
# => (F-x) = F - 0.686*F = 0.314*F

# Für 1 MWh Strom brauchen wir also:
# P = 0.468 * x = 1
# => x = 1 / 0.468 = 2.137 MWh Brennstoff für Strom
# => F = 2.137 / 0.686 = 3.115 MWh Gesamt-Brennstoff
# => Brennstoff für Wärme = 3.115 - 2.137 = 0.978 MWh
# => Q = 0.92 * 0.978 = 0.900 MWh Wärme

F_total = fuel_for_1mwh_elec / 0.686
fuel_for_heat = F_total - fuel_for_1mwh_elec
heat_output = chp_boiler_eff * fuel_for_heat

print(f"Gesamt-Brennstoff: {F_total:.3f} MWh @ {chp_fuel_cost} EUR/MWh = {F_total * chp_fuel_cost:.2f} EUR")
print(f"  davon für Strom: {fuel_for_1mwh_elec:.3f} MWh")
print(f"  davon für Wärme: {fuel_for_heat:.3f} MWh")
print(f"Wärme-Output: {heat_output:.3f} MWh")
print(f"Wärme/Strom-Verhältnis: {heat_output:.3f}")

total_fuel_cost = F_total * chp_fuel_cost
print(f"\nBrennstoffkosten für 1 MWh Strom + {heat_output:.3f} MWh Wärme: {total_fuel_cost:.2f} EUR")

# CAPEX allokiert (angenommen 8760 Volllaststunden/Jahr, aber typisch weniger)
hours = 8760 * 0.5  # Annahme: 50% Auslastung
gen_capex_per_mwh = chp_gen_capex / hours
boiler_capex_per_mwh = chp_boiler_capex / hours * heat_output
print(f"CAPEX Strom: {gen_capex_per_mwh:.3f} EUR/MWh")
print(f"CAPEX Wärme: {boiler_capex_per_mwh:.3f} EUR/MWh")
print(f"Gesamt CAPEX: {gen_capex_per_mwh + boiler_capex_per_mwh:.3f} EUR/MWh")

total_chp_cost = total_fuel_cost + gen_capex_per_mwh + boiler_capex_per_mwh
print(f"\nGESAMTKOSTEN BHKW (Strom+Wärme): {total_chp_cost:.2f} EUR")
print(f"davon Strom-Anteil (allokiert): {total_fuel_cost * 0.5 + gen_capex_per_mwh:.2f} EUR/MWh")
print(f"davon Wärme-Anteil (allokiert): {total_fuel_cost * 0.5 + boiler_capex_per_mwh:.2f} EUR/MWh")

print("\n2. ALTERNATIVE: Hilfskessel für Wärme:")
print("-" * 80)
# Für 0.9 MWh Wärme:
fuel_for_aux = heat_output / aux_boiler_eff
aux_cost = heat_output * aux_boiler_marginal
aux_capex_per_mwh = aux_boiler_capex / hours * heat_output
print(f"Kosten für {heat_output:.3f} MWh Wärme: {aux_cost:.2f} EUR (marginal)")
print(f"CAPEX: {aux_capex_per_mwh:.3f} EUR")
print(f"Gesamt: {aux_cost + aux_capex_per_mwh:.2f} EUR")

print("\n3. ALTERNATIVE: Stromhandel (Market):")
print("-" * 80)
# Durchschnittlicher Marktpreis (siehe Profil)
avg_market_price = np.array([
    78.0, 74.0, 70.0, 68.0, 65.0, 64.0, 66.0, 72.0, 85.0, 92.0, 100.0, 105.0,
    110.0, 108.0, 102.0, 95.0, 40.0, 30.0, 10.0, 0.0, -20.0, 0.0, 20.0, 74.0,
]).mean()
print(f"Durchschnittlicher Marktpreis: {avg_market_price:.2f} EUR/MWh")
print(f"CAPEX: {market_capex:.2f} EUR/MW/Jahr")

print("\n4. VERGLEICH:")
print("-" * 80)
print(f"BHKW (Brennstoff + CAPEX):          {total_chp_cost:.2f} EUR für 1 MWh Strom + {heat_output:.2f} MWh Wärme")
print(f"Alternative (Market + Aux-Boiler):  {avg_market_price + aux_cost + aux_capex_per_mwh:.2f} EUR")
print(f"  - Market Strom:                   {avg_market_price:.2f} EUR/MWh")
print(f"  - Aux-Boiler Wärme:               {aux_cost + aux_capex_per_mwh:.2f} EUR")

print("\n5. PROBLEM-DIAGNOSE:")
print("-" * 80)
if total_chp_cost > avg_market_price + aux_cost:
    print("⚠ BHKW ist TEURER als die Alternative!")
    print("  Grund: Brennstoffkosten + CAPEX sind zu hoch verglichen mit Stromhandel + Hilfskessel")
    print("\n  Mögliche Lösungen:")
    print("  a) Brennstoffkosten (chp_fuel marginal_cost) reduzieren")
    print("  b) CAPEX der BHKW-Komponenten reduzieren")
    print("  c) Marktpreise anpassen (realistischer machen)")
    print("  d) Hilfskessel marginal_cost erhöhen")
else:
    print("✓ BHKW ist günstiger - sollte genutzt werden!")
    print("  → Es könnte ein anderes Problem geben (z.B. zu restriktive Constraints)")

print("\n6. DETAILLIERTE RECHNUNG:")
print("-" * 80)
print("BHKW Gesamtkosten:")
print(f"  Brennstoff:        {total_fuel_cost:8.2f} EUR")
print(f"  CAPEX Generator:   {gen_capex_per_mwh:8.2f} EUR")
print(f"  CAPEX Boiler:      {boiler_capex_per_mwh:8.2f} EUR")
print(f"  SUMME:             {total_chp_cost:8.2f} EUR")
print(f"\nAlternative Kosten:")
print(f"  Market:            {avg_market_price:8.2f} EUR")
print(f"  Aux-Boiler:        {aux_cost:8.2f} EUR")
print(f"  Aux-CAPEX:         {aux_capex_per_mwh:8.2f} EUR")
print(f"  SUMME:             {avg_market_price + aux_cost + aux_capex_per_mwh:8.2f} EUR")

delta = total_chp_cost - (avg_market_price + aux_cost + aux_capex_per_mwh)
print(f"\nDifferenz: {delta:+.2f} EUR (negative = BHKW ist günstiger)")

print("\n" + "=" * 80)
