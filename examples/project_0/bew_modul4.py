"""
BEW Modul 4 - Arbeitspreisförderung für Wärmepumpen
====================================================

Bundesförderung für effiziente Wärmenetze (BEW) - Modul 4
Reduziert die Stromkosten für Wärmepumpen im Fernwärmenetz

Förderung: Differenz zwischen Strom- und Gaspreis wird teilweise erstattet

Berechnung nach BEW-Richtlinie:
- Förderbetrag = (Strompreis - Gaspreferenzpreis) × Strombedarf × Fördersatz
- Fördersatz: Abhängig von JAZ (Jahresarbeitszahl/COP)
- Maximal: 60% der Mehrkosten

Typische Werte:
- JAZ > 4.0: 60% Förderung
- JAZ 3.5-4.0: 50% Förderung  
- JAZ 3.0-3.5: 40% Förderung
- JAZ < 3.0: 30% Förderung

Annahmen für Sylt:
- Luft-WP: COP 2.5-4.0 (Mittel: 3.3) → 45% Förderung
- Abwasser-WP: COP 3.8 (konstant) → 50% Förderung
- Gaspreferenz: 100 €/MWh (Mittelwert 2027-2045)
"""

import numpy as np

def calculate_bew_subsidized_electricity_price(
    electricity_price: float,
    gas_reference_price: float = 100.0,
    cop: float = 3.5,
    max_subsidy_rate: float = 0.50
) -> float:
    """
    Berechne effektiven Strompreis nach BEW Modul 4 Förderung.
    
    Parameters
    ----------
    electricity_price : float
        Strompreis [EUR/MWh]
    gas_reference_price : float
        Gas-Referenzpreis [EUR/MWh], Standard: 100
    cop : float
        Coefficient of Performance (Jahresarbeitszahl)
    max_subsidy_rate : float
        Maximaler Fördersatz, Standard: 0.50 (50%)
    
    Returns
    -------
    float
        Effektiver Strompreis nach Förderung [EUR/MWh]
    """
    # Stromkosten pro erzeugte MWh Wärme
    electricity_cost_per_heat = electricity_price / cop
    
    # Gas-Kosten pro erzeugte MWh Wärme (als Referenz)
    gas_cost_per_heat = gas_reference_price / 0.90  # 90% Kessel-Wirkungsgrad
    
    # Mehrkosten Strom vs. Gas
    additional_cost = electricity_cost_per_heat - gas_cost_per_heat
    
    if additional_cost <= 0:
        # Strom bereits günstiger als Gas → keine Förderung nötig
        return electricity_price
    
    # Förderbetrag pro MWh Wärme
    subsidy_per_heat = additional_cost * max_subsidy_rate
    
    # Effektive Stromkosten nach Förderung (pro MWh Strom)
    subsidized_electricity_cost_per_heat = electricity_cost_per_heat - subsidy_per_heat
    effective_electricity_price = subsidized_electricity_cost_per_heat * cop
    
    return effective_electricity_price


def calculate_bew_savings_profile(
    electricity_price_profile: np.ndarray,
    cop_profile: np.ndarray,
    gas_reference_price: float = 100.0,
    max_subsidy_rate: float = 0.50
) -> tuple:
    """
    Berechne BEW-Förderung für Zeitreihe.
    
    Returns
    -------
    effective_prices : np.ndarray
        Effektive Strompreise nach Förderung [EUR/MWh]
    subsidy_amounts : np.ndarray
        Förderbeträge pro Zeitschritt [EUR/MWh Strom]
    """
    effective_prices = np.zeros_like(electricity_price_profile)
    subsidy_amounts = np.zeros_like(electricity_price_profile)
    
    for i in range(len(electricity_price_profile)):
        effective_prices[i] = calculate_bew_subsidized_electricity_price(
            electricity_price_profile[i],
            gas_reference_price,
            cop_profile[i],
            max_subsidy_rate
        )
        subsidy_amounts[i] = electricity_price_profile[i] - effective_prices[i]
    
    return effective_prices, subsidy_amounts


# Beispielrechnung
if __name__ == "__main__":
    print("=" * 80)
    print("BEW MODUL 4 - ARBEITSPREISFÖRDERUNG BEISPIELRECHNUNG")
    print("=" * 80)
    print()
    
    # Szenarien
    scenarios = [
        {"name": "Luft-WP Winter", "elec": 120, "cop": 2.5, "gas": 100},
        {"name": "Luft-WP Sommer", "elec": 80, "cop": 4.0, "gas": 100},
        {"name": "Abwasser-WP", "elec": 100, "cop": 3.8, "gas": 100},
    ]
    
    for scenario in scenarios:
        elec_price = scenario["elec"]
        cop = scenario["cop"]
        gas_price = scenario["gas"]
        
        # Ohne Förderung
        cost_per_heat_no_subsidy = elec_price / cop
        
        # Mit Förderung
        effective_elec_price = calculate_bew_subsidized_electricity_price(
            elec_price, gas_price, cop, 0.50
        )
        cost_per_heat_with_subsidy = effective_elec_price / cop
        
        # Referenz: Gas
        cost_per_heat_gas = gas_price / 0.90
        
        # Förderung
        subsidy = elec_price - effective_elec_price
        subsidy_percent = (subsidy / elec_price) * 100
        
        print(f"{scenario['name']:20s}:")
        print(f"  Strompreis:          {elec_price:6.2f} EUR/MWh")
        print(f"  COP:                 {cop:6.2f}")
        print(f"  Gaspreis (Ref):      {gas_price:6.2f} EUR/MWh")
        print()
        print(f"  Kosten pro MWh Wärme:")
        print(f"    Ohne BEW:          {cost_per_heat_no_subsidy:6.2f} EUR/MWh")
        print(f"    Mit BEW:           {cost_per_heat_with_subsidy:6.2f} EUR/MWh")
        print(f"    Gas (Referenz):    {cost_per_heat_gas:6.2f} EUR/MWh")
        print()
        print(f"  BEW-Förderung:       {subsidy:6.2f} EUR/MWh Strom ({subsidy_percent:.1f}%)")
        print(f"  Effektiver Strom:    {effective_elec_price:6.2f} EUR/MWh")
        print()
        
        # Vergleich
        if cost_per_heat_with_subsidy < cost_per_heat_gas:
            savings = cost_per_heat_gas - cost_per_heat_with_subsidy
            print(f"  ✓ WP günstiger als Gas: -{savings:.2f} EUR/MWh")
        else:
            additional = cost_per_heat_with_subsidy - cost_per_heat_gas
            print(f"  ✗ WP teurer als Gas: +{additional:.2f} EUR/MWh")
        
        print()
        print("-" * 80)
        print()
