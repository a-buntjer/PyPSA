"""District Heating Network System with Multiple Production Sites.

This example implements a comprehensive district heating network with:
- 2 production sites (Standort A, B) with multiple heat generation technologies
- 3 consumers (C1: residential, C2: commercial, C3: industrial) with different load profiles
- Star/tree topology heat network with Links for heat transmission
- Central electricity and gas grids with market connections
- Grid connection charges (capital_cost = capacity charge, marginal_cost = energy charge)

Technologies at production sites (all committable=True, extendable=True):
- Heat pumps (COP and capacity depend on outdoor and supply/return temperatures)
- Electric boilers
- CHP plants (natural gas, biomethane, biogas with annual quantity constraints)
- Gas boilers
- Thermal storage (capacity depends on supply/return temperature difference)

Auxiliary power consumption (pumps) at production sites is modeled as Load
proportional to heat production, supplied by CHP plants.

Time resolution: 7 days (168h) for testing, easily scalable to 8760h.
"""

from __future__ import annotations

import pathlib
import sys

# Allow running without installing PyPSA
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import pypsa

import matplotlib

if matplotlib.get_backend().lower() != "agg":
    try:
        matplotlib.use("Agg", force=True)
    except Exception:
        pass
import matplotlib.pyplot as plt

# =============================================================================
# CONFIGURATION
# =============================================================================

# Time configuration
DAYS = 7  # Start with 7 days for testing, change to 365 for full year
HOURS_PER_DAY = 24
SNAPSHOTS = pd.date_range("2025-01-01", periods=DAYS * HOURS_PER_DAY, freq="h")

# Files
RESULT_FILE = pathlib.Path(__file__).with_suffix(".nc")
PLOT_DIR = pathlib.Path(__file__).parent / "plots"

# Economic parameters for annuity calculation
INTEREST_RATE = 0.05  # 5% discount rate
LIFETIME_YEARS = 20  # Economic lifetime for investments

# Physical constants
WATER_DENSITY = 1000  # kg/m³
WATER_SPECIFIC_HEAT = 4.18  # kJ/(kg·K)

# CHP parameters (from committable_extendable_chp1.py)
CHP_THERMAL_EFF = 0.48  # 48% thermal efficiency
CHP_ELECTRIC_EFF = 0.38  # 38% electrical efficiency
CHP_TOTAL_EFF = CHP_ELECTRIC_EFF + CHP_THERMAL_EFF
CHP_QP_RATIO = CHP_THERMAL_EFF / CHP_ELECTRIC_EFF  # Heat/Power ratio
CHP_COUPLING_BAND = 0.15  # ±15% flexibility
CHP_THERMAL_BIAS = 0.20  # Additional heat in part load

# Economic parameters
GRID_CHARGE_ELECTRIC_CAPACITY = (
    115.61  # EUR/kW/year - electricity capacity charge
)
GRID_CHARGE_ELECTRIC_ENERGY = 13.8  # EUR/MWh - electricity energy charge
GRID_CHARGE_GAS_CAPACITY = 24.79  # EUR/kW/year - gas capacity charge
GRID_CHARGE_GAS_ENERGY = 3.0  # EUR/MWh - gas energy charge

# Fuel prices (EUR/MWh)
PRICE_NATURAL_GAS = 35.0  # Natural gas
PRICE_BIOMETHANE = 90.0  # Biomethane (upgraded biogas)
PRICE_BIOGAS = 55.0  # Raw biogas

# Biogas weekly limit (MWh per week)
BIOGAS_WEEKLY_LIMIT = 500.0  # 500 MWh/week ≈ 3 MW average

# KWK-G and EEG subsidies (EUR/MWh) - negative marginal cost = revenue
SUBSIDY_CHP_NATURAL_GAS = -40.0  # KWK-Zuschlag für Erdgas-KWK
SUBSIDY_CHP_BIOMETHANE = -120.0  # EEG-Vergütung für Biomethan-KWK
SUBSIDY_CHP_BIOGAS = -150.0  # EEG-Vergütung für Biogas-KWK

# Auxiliary power consumption (pump electricity)
AUX_POWER_RATIO = 0.015  # 1.5% of heat production

# Design temperatures for thermal storage sizing
T_SUPPLY_DESIGN = 90.0  # °C - Design supply temperature
T_RETURN_DESIGN = 50.0  # °C - Design return temperature

# Heat pump parameters
HP_CARNOT_EFFICIENCY = 0.50  # Gütegrad (typically 0.45-0.55)

# Carrier colors
CARRIER_COLORS = {
    "electric": "#1f77b4",
    "gas_natural": "#ff7f0e",
    "gas_biomethane": "#2ca02c",
    "gas_biogas": "#8c564b",
    "heat": "#d62728",
    "market_electric": "#9467bd",
}

# =============================================================================
# ECONOMIC FUNCTIONS
# =============================================================================


def calculate_annuity_factor(interest_rate: float, lifetime: int) -> float:
    """Calculate annuity factor for capital cost conversion.
    
    Converts investment costs to annualized costs using:
    annuity_factor = (i * (1 + i)^n) / ((1 + i)^n - 1)
    
    Parameters
    ----------
    interest_rate : float
        Annual interest rate (e.g., 0.05 for 5%)
    lifetime : int
        Economic lifetime in years
        
    Returns
    -------
    float
        Annuity factor
    """
    if interest_rate == 0:
        return 1.0 / lifetime
    return (interest_rate * (1 + interest_rate) ** lifetime) / (
        (1 + interest_rate) ** lifetime - 1
    )


def scale_capital_cost(
    capital_cost_annual: float, 
    snapshot_duration_hours: float,
    n_snapshots: int, 
    hours_per_year: int = 8760
) -> float:
    """Scale annualized capital cost to simulation period.
    
    Takes into account both the number of snapshots AND their frequency/duration.
    
    Parameters
    ----------
    capital_cost_annual : float
        Annual capital cost [EUR/MW/year]
    snapshot_duration_hours : float
        Duration of each snapshot in hours (e.g., 1.0 for hourly, 0.25 for 15-min, 3.0 for 3-hourly)
    n_snapshots : int
        Number of snapshots in simulation
    hours_per_year : int
        Hours per year (default: 8760)
        
    Returns
    -------
    float
        Scaled capital cost for simulation period
    """
    total_hours = n_snapshots * snapshot_duration_hours
    return capital_cost_annual * (total_hours / hours_per_year)


# =============================================================================
# TEMPERATURE AND LOAD PROFILES
# =============================================================================


def build_outdoor_temperature(index: pd.Index) -> pd.Series:
    """Generate outdoor temperature profile [°C].

    Winter: -5 to 5°C, Summer: 15 to 25°C, with daily variation.
    """
    hours = len(index)
    days = hours / 24

    # Annual temperature wave (cosine with minimum in winter)
    day_of_year = np.arange(hours) / 24
    annual_wave = -10 * np.cos(
        2 * np.pi * day_of_year / 365.25
    )  # ±10°C variation

    # Daily variation (±3°C, warmest at 14:00)
    hour_of_day = np.arange(hours) % 24
    daily_wave = 3 * np.cos(2 * np.pi * (hour_of_day - 14) / 24)

    # Base temperature (annual average)
    base_temp = 10.0  # °C

    outdoor_temp = base_temp + annual_wave + daily_wave

    return pd.Series(outdoor_temp, index=index, name="T_outdoor")


def build_supply_temperature(T_outdoor: pd.Series) -> pd.Series:
    """Calculate supply temperature based on outdoor temperature [°C].

    Heating curve: T_supply INCREASES with DECREASING outdoor temperature.
    Winter (cold): 90°C at -15°C
    Summer (warm): 75°C at +15°C (minimum for domestic hot water)
    """
    # Corrected: Supply temperature goes UP when it's colder
    T_supply = 90.0 - 0.50 * (T_outdoor + 15.0)  # -15°C → 90°C, +15°C → 75°C
    T_supply = T_supply.clip(lower=75.0, upper=90.0)  # Min 75°C for hot water

    return pd.Series(T_supply, index=T_outdoor.index, name="T_supply")


def build_return_temperature(T_outdoor: pd.Series) -> pd.Series:
    """Calculate return temperature based on outdoor temperature [°C].

    Return temperature: DECREASES with DECREASING outdoor temperature.
    Winter (cold): Low return temp (45°C at -15°C) - heat is extracted efficiently
    Summer (warm): High return temp (55°C at +15°C) - less heat extracted
    """
    # Corrected: Return temperature goes DOWN when it's colder (more heat extracted)
    T_return = 55.0 + 0.33 * (T_outdoor + 15.0)  # -15°C → 45°C, +15°C → 55°C
    T_return = T_return.clip(lower=40.0, upper=60.0)  # Realistic bounds

    return pd.Series(T_return, index=T_outdoor.index, name="T_return")


def build_heat_load_residential(
    index: pd.Index, T_outdoor: pd.Series
) -> pd.Series:
    """Generate residential heat load profile [MW].

    Characteristics:
    - Strong temperature dependence
    - Morning peak (6-8h), evening peak (18-20h)
    - Weekend slightly different
    """
    hours = len(index)

    # Base load depends on outdoor temperature (heating curve)
    # At -5°C: 15 MW, at +15°C: 5 MW
    base_load = 10.0 + 0.25 * (15.0 - T_outdoor.values)

    # Daily profile (hourly factors)
    hour_of_day = np.arange(hours) % 24
    daily_profile = np.array(
        [
            0.85,
            0.80,
            0.75,
            0.70,
            0.70,
            0.80,  # 0-5h: night
            1.10,
            1.20,
            1.15,
            1.05,
            1.00,
            0.95,  # 6-11h: morning peak
            0.90,
            0.85,
            0.85,
            0.85,
            0.90,
            1.00,  # 12-17h: afternoon
            1.15,
            1.20,
            1.15,
            1.05,
            0.95,
            0.90,  # 18-23h: evening peak
        ]
    )
    daily_factors = daily_profile[hour_of_day]

    heat_load = base_load * daily_factors

    return pd.Series(heat_load, index=index, name="heat_load_residential")


def build_heat_load_commercial(
    index: pd.Index, T_outdoor: pd.Series
) -> pd.Series:
    """Generate commercial heat load profile [MW].

    Characteristics:
    - Moderate temperature dependence
    - Business hours (7-18h)
    - Low on weekends
    """
    hours = len(index)

    # Base load depends on outdoor temperature
    # At -5°C: 12 MW, at +15°C: 4 MW
    base_load = 8.0 + 0.20 * (15.0 - T_outdoor.values)

    # Daily profile
    hour_of_day = np.arange(hours) % 24
    daily_profile = np.array(
        [
            0.50,
            0.50,
            0.50,
            0.50,
            0.50,
            0.60,  # 0-5h: off
            0.80,
            1.00,
            1.20,
            1.30,
            1.30,
            1.30,  # 6-11h: ramp-up
            1.30,
            1.30,
            1.30,
            1.30,
            1.20,
            1.00,  # 12-17h: business hours
            0.80,
            0.70,
            0.60,
            0.55,
            0.50,
            0.50,  # 18-23h: ramp-down
        ]
    )
    daily_factors = daily_profile[hour_of_day]

    # Weekend reduction
    day_of_week = (np.arange(hours) // 24) % 7
    weekend_factor = np.where(
        (day_of_week == 5) | (day_of_week == 6), 0.4, 1.0
    )

    heat_load = base_load * daily_factors * weekend_factor

    return pd.Series(heat_load, index=index, name="heat_load_commercial")


def build_heat_load_industrial(
    index: pd.Index, T_outdoor: pd.Series
) -> pd.Series:
    """Generate industrial heat load profile [MW].

    Characteristics:
    - Weak temperature dependence (process heat)
    - Continuous operation (24/7)
    - Small daily variation
    """
    hours = len(index)

    # Base load (mostly independent of outdoor temperature)
    # Process heat: constant 18 MW, space heating: 0.15 * (15 - T_outdoor)
    base_load = 18.0 + 0.15 * (15.0 - T_outdoor.values)

    # Small daily variation (shifts, maintenance)
    hour_of_day = np.arange(hours) % 24
    daily_profile = np.array(
        [
            0.95,
            0.95,
            0.95,
            0.95,
            0.95,
            1.00,  # 0-5h: night shift
            1.05,
            1.10,
            1.10,
            1.10,
            1.10,
            1.10,  # 6-11h: day shift
            1.10,
            1.10,
            1.10,
            1.10,
            1.05,
            1.05,  # 12-17h: afternoon shift
            1.00,
            0.95,
            0.95,
            0.95,
            0.95,
            0.95,  # 18-23h: evening shift
        ]
    )
    daily_factors = daily_profile[hour_of_day]

    heat_load = base_load * daily_factors

    return pd.Series(heat_load, index=index, name="heat_load_industrial")


def build_electricity_price(index: pd.Index) -> pd.Series:
    """Generate time-varying electricity market price [EUR/MWh].

    Day-ahead market with daily and weekly patterns.
    """
    hours = len(index)

    # Base price
    base_price = 90.0  # EUR/MWh

    # Daily pattern (peak hours expensive)
    hour_of_day = np.arange(hours) % 24
    daily_pattern = np.array(
        [
            -20,
            -22,
            -24,
            -25,
            -25,
            -22,  # 0-5h: low
            -10,
            5,
            20,
            30,
            35,
            35,  # 6-11h: morning ramp
            30,
            25,
            20,
            20,
            25,
            35,  # 12-17h: afternoon
            40,
            35,
            25,
            10,
            -10,
            -15,  # 18-23h: evening peak
        ]
    )
    daily_variation = daily_pattern[hour_of_day]

    # Weekly pattern (weekend cheaper)
    day_of_week = (np.arange(hours) // 24) % 7
    weekend_discount = np.where(
        (day_of_week == 5) | (day_of_week == 6), -15, 0
    )

    electricity_price = base_price + daily_variation + weekend_discount
    electricity_price = np.maximum(electricity_price, 5.0)  # Minimum 5 EUR/MWh

    return pd.Series(electricity_price, index=index, name="electricity_price")


def calculate_thermal_storage_capacity_factor(
    T_supply: pd.Series, T_return: pd.Series
) -> pd.Series:
    """Calculate time-varying thermal storage capacity factor.

    Storage capacity depends on temperature difference: Q = m·cp·ΔT
    Returns e_max_pu as ratio to design conditions.
    """
    delta_T_actual = T_supply - T_return
    delta_T_design = T_SUPPLY_DESIGN - T_RETURN_DESIGN

    capacity_factor = delta_T_actual / delta_T_design
    capacity_factor = capacity_factor.clip(lower=0.5, upper=1.0)

    return pd.Series(
        capacity_factor, index=T_supply.index, name="storage_capacity_factor"
    )


def calculate_heat_pump_cop(
    T_outdoor: pd.Series, T_supply: pd.Series
) -> pd.Series:
    """Calculate heat pump COP based on Carnot efficiency.

    COP = η_carnot × T_supply_K / (T_supply_K - T_outdoor_K)
    """
    T_supply_K = T_supply + 273.15
    T_outdoor_K = T_outdoor + 273.15

    cop = HP_CARNOT_EFFICIENCY * T_supply_K / (T_supply_K - T_outdoor_K)
    cop = cop.clip(lower=2.0, upper=5.0)  # Realistic bounds

    return pd.Series(cop, index=T_outdoor.index, name="heat_pump_cop")


def calculate_heat_pump_capacity_factor(
    T_outdoor: pd.Series, T_supply: pd.Series
) -> pd.Series:
    """Calculate heat pump capacity reduction at low outdoor temperatures.

    At very low temperatures, compressor capacity is limited.
    Typical: 100% at +7°C, 80% at -7°C, 60% at -15°C
    """
    # Linear reduction below +7°C
    capacity_factor = 1.0 - 0.02 * (7.0 - T_outdoor)
    capacity_factor = capacity_factor.clip(lower=0.60, upper=1.0)

    return pd.Series(
        capacity_factor,
        index=T_outdoor.index,
        name="heat_pump_capacity_factor",
    )


# =============================================================================
# NETWORK CONSTRUCTION
# =============================================================================


def build_network() -> pypsa.Network:
    """Construct the district heating network with all components."""

    n = pypsa.Network()
    n.set_snapshots(list(SNAPSHOTS))

    # Calculate annuity factor and time scaling
    annuity_factor = calculate_annuity_factor(INTEREST_RATE, LIFETIME_YEARS)
    n_snapshots = len(SNAPSHOTS)
    
    # Determine snapshot frequency (duration in hours)
    if n_snapshots > 1:
        snapshot_freq = pd.Timedelta(SNAPSHOTS[1] - SNAPSHOTS[0])
        snapshot_duration_hours = snapshot_freq.total_seconds() / 3600.0
    else:
        snapshot_duration_hours = 1.0  # Default to 1 hour if only one snapshot
    
    # Helper function to convert investment costs to scaled capital costs
    # (with annuity calculation for equipment)
    def capex_to_capital_cost(investment_cost_per_mw: float) -> float:
        """Convert investment cost [EUR/MW] to scaled capital cost [EUR/MW].
        
        For equipment investments: Applies annuity factor, then scales to simulation period.
        
        Parameters
        ----------
        investment_cost_per_mw : float
            Investment cost in EUR/MW
            
        Returns
        -------
        float
            Annualized and time-scaled capital cost for PyPSA
        """
        annual_cost = investment_cost_per_mw * annuity_factor
        return scale_capital_cost(annual_cost, snapshot_duration_hours, n_snapshots)
    
    # Helper function for already-annual costs (e.g., grid charges)
    # (no annuity calculation, only time scaling)
    def annual_to_capital_cost(annual_cost_per_mw: float) -> float:
        """Convert annual cost [EUR/MW/year] to scaled capital cost [EUR/MW].
        
        For costs that are already annual (e.g., grid connection charges):
        Only scales to simulation period, NO annuity calculation.
        
        Parameters
        ----------
        annual_cost_per_mw : float
            Annual cost in EUR/MW/year
            
        Returns
        -------
        float
            Time-scaled capital cost for PyPSA
        """
        return scale_capital_cost(annual_cost_per_mw, snapshot_duration_hours, n_snapshots)

    # Generate profiles
    T_outdoor = build_outdoor_temperature(SNAPSHOTS)
    T_supply = build_supply_temperature(T_outdoor)
    T_return = build_return_temperature(T_outdoor)

    heat_load_c1 = build_heat_load_residential(SNAPSHOTS, T_outdoor)
    heat_load_c2 = build_heat_load_commercial(SNAPSHOTS, T_outdoor)
    heat_load_c3 = build_heat_load_industrial(SNAPSHOTS, T_outdoor)

    electricity_price = build_electricity_price(SNAPSHOTS)

    storage_capacity_factor = calculate_thermal_storage_capacity_factor(
        T_supply, T_return
    )
    hp_cop = calculate_heat_pump_cop(T_outdoor, T_supply)
    hp_capacity_factor = calculate_heat_pump_capacity_factor(
        T_outdoor, T_supply
    )

    # -------------------------------------------------------------------------
    # CARRIERS
    # -------------------------------------------------------------------------
    n.add("Carrier", "electric")
    n.add("Carrier", "gas_natural", co2_emissions=0.20)  # kg CO2/kWh
    n.add("Carrier", "gas_biomethane", co2_emissions=0.0)  # Carbon neutral
    n.add("Carrier", "gas_biogas", co2_emissions=0.0)  # Carbon neutral
    n.add("Carrier", "heat")
    n.add("Carrier", "market_electric")

    # Set colors
    if "color" not in n.carriers.columns:
        n.carriers["color"] = np.nan
    for carrier, color in CARRIER_COLORS.items():
        if carrier in n.carriers.index:
            n.carriers.loc[carrier, "color"] = color

    # -------------------------------------------------------------------------
    # BUSES
    # -------------------------------------------------------------------------

    # Central market buses
    n.add("Bus", "bus_electric_market", carrier="market_electric")
    n.add("Bus", "bus_gas_natural_market", carrier="gas_natural")
    n.add("Bus", "bus_gas_biomethane_market", carrier="gas_biomethane")
    n.add("Bus", "bus_gas_biogas_market", carrier="gas_biogas")

    # Production site A - electrical and gas buses
    n.add("Bus", "bus_electric_site_a", carrier="electric")
    n.add("Bus", "bus_gas_natural_site_a", carrier="gas_natural")
    n.add("Bus", "bus_gas_biomethane_site_a", carrier="gas_biomethane")
    n.add("Bus", "bus_gas_biogas_site_a", carrier="gas_biogas")
    n.add("Bus", "bus_heat_site_a", carrier="heat")

    # CHP electricity buses at Site A (for subsidies)
    n.add("Bus", "bus_electric_chp_natural_gas_site_a", carrier="electric")
    n.add("Bus", "bus_electric_chp_biomethane_site_a", carrier="electric")
    n.add("Bus", "bus_electric_chp_biogas_site_a", carrier="electric")

    # Production site B - electrical and gas buses
    n.add("Bus", "bus_electric_site_b", carrier="electric")
    n.add("Bus", "bus_gas_natural_site_b", carrier="gas_natural")
    n.add("Bus", "bus_gas_biomethane_site_b", carrier="gas_biomethane")
    n.add("Bus", "bus_gas_biogas_site_b", carrier="gas_biogas")
    n.add("Bus", "bus_heat_site_b", carrier="heat")

    # CHP electricity buses at Site B (for subsidies)
    n.add("Bus", "bus_electric_chp_natural_gas_site_b", carrier="electric")
    n.add("Bus", "bus_electric_chp_biomethane_site_b", carrier="electric")
    n.add("Bus", "bus_electric_chp_biogas_site_b", carrier="electric")

    # Consumer buses (heat only)
    n.add("Bus", "bus_heat_consumer_1", carrier="heat")
    n.add("Bus", "bus_heat_consumer_2", carrier="heat")
    n.add("Bus", "bus_heat_consumer_3", carrier="heat")

    # -------------------------------------------------------------------------
    # HEAT DEMANDS
    # -------------------------------------------------------------------------
    n.add(
        "Load", "load_heat_c1", bus="bus_heat_consumer_1", p_set=heat_load_c1
    )
    n.add(
        "Load", "load_heat_c2", bus="bus_heat_consumer_2", p_set=heat_load_c2
    )
    n.add(
        "Load", "load_heat_c3", bus="bus_heat_consumer_3", p_set=heat_load_c3
    )

    # -------------------------------------------------------------------------
    # ENERGY MARKETS (Generators with unlimited capacity)
    # -------------------------------------------------------------------------
    n.add(
        "Generator",
        "market_electricity",
        bus="bus_electric_market",
        carrier="market_electric",
        p_nom_extendable=True,
        p_nom_max=1000,
        capital_cost=0,
        marginal_cost=electricity_price,
    )

    n.add(
        "Generator",
        "market_gas_natural",
        bus="bus_gas_natural_market",
        carrier="gas_natural",
        p_nom_extendable=True,
        p_nom_max=1000,
        capital_cost=0,
        marginal_cost=PRICE_NATURAL_GAS,
    )

    n.add(
        "Generator",
        "market_gas_biomethane",
        bus="bus_gas_biomethane_market",
        carrier="gas_biomethane",
        p_nom_extendable=True,
        p_nom_max=1000,
        capital_cost=0,
        marginal_cost=PRICE_BIOMETHANE,
    )

    n.add(
        "Generator",
        "market_gas_biogas",
        bus="bus_gas_biogas_market",
        carrier="gas_biogas",
        p_nom_extendable=True,
        p_nom_max=1000,
        capital_cost=0,
        marginal_cost=PRICE_BIOGAS,
    )

    # -------------------------------------------------------------------------
    # GRID CONNECTION LINKS (with capacity and energy charges)
    # -------------------------------------------------------------------------

    # Electricity grid connections for both sites
    for site in ["a", "b"]:
        n.add(
            "Link",
            f"grid_electric_to_site_{site}",
            bus0="bus_electric_market",
            bus1=f"bus_electric_site_{site}",
            carrier="electric",
            efficiency=1.0,
            p_nom_extendable=True,
            capital_cost=annual_to_capital_cost(GRID_CHARGE_ELECTRIC_CAPACITY),
            marginal_cost=GRID_CHARGE_ELECTRIC_ENERGY,
        )

    # Gas grid connections (natural gas, biomethane, biogas) for both sites
    for site in ["a", "b"]:
        for gas_type in ["natural", "biomethane", "biogas"]:
            n.add(
                "Link",
                f"grid_gas_{gas_type}_to_site_{site}",
                bus0=f"bus_gas_{gas_type}_market",
                bus1=f"bus_gas_{gas_type}_site_{site}",
                carrier=f"gas_{gas_type}",
                efficiency=1.0,
                p_nom_extendable=True,
                capital_cost=annual_to_capital_cost(GRID_CHARGE_GAS_CAPACITY),
                marginal_cost=GRID_CHARGE_GAS_ENERGY,
            )

    # -------------------------------------------------------------------------
    # HEAT NETWORK LINKS (transmission from sites to consumers)
    # -------------------------------------------------------------------------

    # Star topology: Site A → C1, C2; Site B → C2, C3
    # Limited capacity, losses due to distance

    n.add(
        "Link",
        "heat_site_a_to_c1",
        bus0="bus_heat_site_a",
        bus1="bus_heat_consumer_1",
        carrier="heat",
        efficiency=0.98,  # 2% heat loss
        p_nom_extendable=True,
        p_nom_max=30,  # Maximum transmission capacity
        capital_cost=capex_to_capital_cost(100000),  # Pipeline investment cost EUR/MW (100 EUR/kW)
        marginal_cost=0.5,  # Pumping cost EUR/MWh
    )

    n.add(
        "Link",
        "heat_site_a_to_c2",
        bus0="bus_heat_site_a",
        bus1="bus_heat_consumer_2",
        carrier="heat",
        efficiency=0.97,  # 3% heat loss (longer distance)
        p_nom_extendable=True,
        p_nom_max=25,
        capital_cost=capex_to_capital_cost(120000),  # EUR/MW (120 EUR/kW)
        marginal_cost=0.6,
    )

    n.add(
        "Link",
        "heat_site_b_to_c2",
        bus0="bus_heat_site_b",
        bus1="bus_heat_consumer_2",
        carrier="heat",
        efficiency=0.98,
        p_nom_extendable=True,
        p_nom_max=25,
        capital_cost=capex_to_capital_cost(100000),  # EUR/MW (100 EUR/kW)
        marginal_cost=0.5,
    )

    n.add(
        "Link",
        "heat_site_b_to_c3",
        bus0="bus_heat_site_b",
        bus1="bus_heat_consumer_3",
        carrier="heat",
        efficiency=0.96,  # 4% heat loss (longest distance)
        p_nom_extendable=True,
        p_nom_max=35,
        capital_cost=capex_to_capital_cost(150000),  # EUR/MW (150 EUR/kW)
        marginal_cost=0.7,
    )

    # -------------------------------------------------------------------------
    # THERMAL STORAGE (at production sites)
    # -------------------------------------------------------------------------

    for site in ["a", "b"]:
        n.add(
            "Store",
            f"thermal_storage_site_{site}",
            bus=f"bus_heat_site_{site}",
            carrier="heat",
            e_nom_extendable=True,
            e_nom_max=100,  # Maximum storage capacity [MWh]
            e_initial=0,  # Start empty
            e_min_pu=0.0,
            e_max_pu=storage_capacity_factor,  # Temperature-dependent capacity
            capital_cost=capex_to_capital_cost(40000),  # EUR/MWh (40 EUR/kWh)
            standing_loss=0.02,  # 2% per hour
        )

    # =========================================================================
    # PRODUCTION TECHNOLOGIES AT SITE A
    # =========================================================================

    # -------------------------------------------------------------------------
    # Heat Pump at Site A
    # -------------------------------------------------------------------------
    n.add(
        "Link",
        "heat_pump_site_a",
        bus0="bus_electric_site_a",
        bus1="bus_heat_site_a",
        carrier="heat",
        efficiency=1.0,  # Will be overridden by time series
        p_nom_extendable=True,
        p_nom_max=20,  # Maximum heat pump size
        capital_cost=capex_to_capital_cost(800000),  # EUR/MW_th (800 EUR/kW_th)
        marginal_cost=2,  # Maintenance EUR/MWh_th
        committable=True,
        p_min_pu=0.3,  # Minimum 30% when running
        start_up_cost=20,
        shut_down_cost=10,
    )
    # Set time-varying efficiency (COP)
    n.links_t.efficiency["heat_pump_site_a"] = hp_cop.values
    # Set time-varying capacity
    n.links_t.p_max_pu["heat_pump_site_a"] = hp_capacity_factor.values

    # -------------------------------------------------------------------------
    # Electric Boiler at Site A
    # -------------------------------------------------------------------------
    n.add(
        "Link",
        "electric_boiler_site_a",
        bus0="bus_electric_site_a",
        bus1="bus_heat_site_a",
        carrier="heat",
        efficiency=0.99,  # 99% efficiency
        p_nom_extendable=True,
        p_nom_max=15,
        capital_cost=capex_to_capital_cost(200000),  # EUR/MW_th (200 EUR/kW_th)
        marginal_cost=1,
        committable=True,
        p_min_pu=0.2,
        start_up_cost=10,
        shut_down_cost=5,
    )

    # -------------------------------------------------------------------------
    # CHP Natural Gas at Site A
    # -------------------------------------------------------------------------
    # Generator part (electricity) - outputs to dedicated CHP bus
    n.add(
        "Link",
        "chp_natural_gas_gen_site_a",
        bus0="bus_gas_natural_site_a",
        bus1="bus_electric_chp_natural_gas_site_a",
        carrier="electric",
        efficiency=CHP_TOTAL_EFF,
        p_nom_extendable=True,
        p_nom_max=30,
        capital_cost=capex_to_capital_cost(600000),  # EUR/MW_el (600 EUR/kW_el)
        marginal_cost=5,  # O&M EUR/MWh (fuel cost at market bus)
        committable=True,
        p_min_pu=0.40,
        start_up_cost=100,
        shut_down_cost=50,
    )

    # Feed-in link with KWK subsidy (to market bus to receive market price)
    n.add(
        "Link",
        "chp_natural_gas_feed_in_site_a",
        bus0="bus_electric_chp_natural_gas_site_a",
        bus1="bus_electric_market",  # To market: receives market price + subsidy
        carrier="electric",
        efficiency=1.0,
        p_nom_extendable=True,
        capital_cost=0,
        marginal_cost=SUBSIDY_CHP_NATURAL_GAS,  # Additional revenue on top of market price
        committable=False,
    )

    # Boiler part (heat)
    n.add(
        "Link",
        "chp_natural_gas_boiler_site_a",
        bus0="bus_gas_natural_site_a",
        bus1="bus_heat_site_a",
        carrier="heat",
        efficiency=CHP_TOTAL_EFF,
        p_nom_extendable=True,
        p_nom_max=30,
        capital_cost=0,  # Included in generator
        marginal_cost=3,  # O&M EUR/MWh (fuel cost at market bus)
        committable=True,
        p_min_pu=0.4,
        start_up_cost=0,
        shut_down_cost=0,
    )

    # -------------------------------------------------------------------------
    # CHP Biomethane at Site A
    # -------------------------------------------------------------------------
    n.add(
        "Link",
        "chp_biomethane_gen_site_a",
        bus0="bus_gas_biomethane_site_a",
        bus1="bus_electric_chp_biomethane_site_a",
        carrier="electric",
        efficiency=CHP_TOTAL_EFF,
        p_nom_extendable=True,
        p_nom_max=20,
        capital_cost=capex_to_capital_cost(700000),  # EUR/MW_el (700 EUR/kW_el, slightly higher than natural gas)
        marginal_cost=5,  # O&M EUR/MWh (fuel cost at market bus)
        committable=True,
        p_min_pu=0.40,
        start_up_cost=100,
        shut_down_cost=50,
    )

    # Feed-in link with EEG subsidy (to market bus to receive market price)
    n.add(
        "Link",
        "chp_biomethane_feed_in_site_a",
        bus0="bus_electric_chp_biomethane_site_a",
        bus1="bus_electric_market",  # To market: receives market price + subsidy
        carrier="electric",
        efficiency=1.0,
        p_nom_extendable=True,
        capital_cost=0,
        marginal_cost=SUBSIDY_CHP_BIOMETHANE,  # Additional revenue on top of market price
        committable=False,
    )

    n.add(
        "Link",
        "chp_biomethane_boiler_site_a",
        bus0="bus_gas_biomethane_site_a",
        bus1="bus_heat_site_a",
        carrier="heat",
        efficiency=CHP_TOTAL_EFF,
        p_nom_extendable=True,
        p_nom_max=20,
        capital_cost=0,
        marginal_cost=3,  # O&M EUR/MWh (fuel cost at market bus)
        committable=True,
        p_min_pu=0.4,
        start_up_cost=0,
        shut_down_cost=0,
    )

    # -------------------------------------------------------------------------
    # CHP Biogas at Site A (with weekly quantity constraint)
    # -------------------------------------------------------------------------
    n.add(
        "Link",
        "chp_biogas_gen_site_a",
        bus0="bus_gas_biogas_site_a",
        bus1="bus_electric_chp_biogas_site_a",
        carrier="electric",
        efficiency=CHP_TOTAL_EFF,
        p_nom_extendable=True,
        p_nom_max=10,
        capital_cost=capex_to_capital_cost(750000),  # EUR/MW_el (750 EUR/kW_el)
        marginal_cost=6,  # O&M EUR/MWh (fuel cost at market bus)
        committable=True,
        p_min_pu=0.40,
        start_up_cost=80,
        shut_down_cost=40,
    )

    # Feed-in link with EEG subsidy (to market bus to receive market price)
    n.add(
        "Link",
        "chp_biogas_feed_in_site_a",
        bus0="bus_electric_chp_biogas_site_a",
        bus1="bus_electric_market",  # To market: receives market price + subsidy
        carrier="electric",
        efficiency=1.0,
        p_nom_extendable=True,
        capital_cost=0,
        marginal_cost=SUBSIDY_CHP_BIOGAS,  # Additional revenue on top of market price
        committable=False,
    )

    n.add(
        "Link",
        "chp_biogas_boiler_site_a",
        bus0="bus_gas_biogas_site_a",
        bus1="bus_heat_site_a",
        carrier="heat",
        efficiency=CHP_TOTAL_EFF,
        p_nom_extendable=True,
        p_nom_max=10,
        capital_cost=0,
        marginal_cost=4,  # O&M EUR/MWh (fuel cost at market bus)
        committable=True,
        p_min_pu=0.0,
        start_up_cost=0,
        shut_down_cost=0,
    )

    # -------------------------------------------------------------------------
    # Gas Boiler (Natural Gas) at Site A
    # -------------------------------------------------------------------------
    n.add(
        "Link",
        "gas_boiler_site_a",
        bus0="bus_gas_natural_site_a",
        bus1="bus_heat_site_a",
        carrier="heat",
        efficiency=0.95,
        p_nom_extendable=True,
        p_nom_max=25,
        capital_cost=capex_to_capital_cost(250000),  # EUR/MW_th (250 EUR/kW_th)
        marginal_cost=3,  # O&M EUR/MWh (fuel cost at market bus)
        committable=True,
        p_min_pu=0.20,
        start_up_cost=30,
        shut_down_cost=15,
    )

    # =========================================================================
    # PRODUCTION TECHNOLOGIES AT SITE B
    # =========================================================================

    # Same technologies as Site A but with different names

    # Heat Pump at Site B
    n.add(
        "Link",
        "heat_pump_site_b",
        bus0="bus_electric_site_b",
        bus1="bus_heat_site_b",
        carrier="heat",
        efficiency=1.0,
        p_nom_extendable=True,
        p_nom_max=20,
        capital_cost=capex_to_capital_cost(800000),  # EUR/MW_th (800 EUR/kW_th)
        marginal_cost=2,
        committable=True,
        p_min_pu=0.3,
        start_up_cost=20,
        shut_down_cost=10,
    )
    n.links_t.efficiency["heat_pump_site_b"] = hp_cop.values
    n.links_t.p_max_pu["heat_pump_site_b"] = hp_capacity_factor.values

    # Electric Boiler at Site B
    n.add(
        "Link",
        "electric_boiler_site_b",
        bus0="bus_electric_site_b",
        bus1="bus_heat_site_b",
        carrier="heat",
        efficiency=0.99,
        p_nom_extendable=True,
        p_nom_max=15,
        capital_cost=capex_to_capital_cost(200000),  # EUR/MW_th (200 EUR/kW_th)
        marginal_cost=1,
        committable=True,
        p_min_pu=0.2,
        start_up_cost=10,
        shut_down_cost=5,
    )

    # CHP Natural Gas at Site B
    n.add(
        "Link",
        "chp_natural_gas_gen_site_b",
        bus0="bus_gas_natural_site_b",
        bus1="bus_electric_chp_natural_gas_site_b",
        carrier="electric",
        efficiency=CHP_TOTAL_EFF,
        p_nom_extendable=True,
        p_nom_max=30,
        capital_cost=capex_to_capital_cost(600000),  # EUR/MW_el (600 EUR/kW_el)
        marginal_cost=5,  # O&M EUR/MWh (fuel cost at market bus)
        committable=True,
        p_min_pu=0.40,
        start_up_cost=100,
        shut_down_cost=50,
    )

    # Feed-in link with KWK subsidy (to market bus to receive market price)
    n.add(
        "Link",
        "chp_natural_gas_feed_in_site_b",
        bus0="bus_electric_chp_natural_gas_site_b",
        bus1="bus_electric_market",  # To market: receives market price + subsidy
        carrier="electric",
        efficiency=1.0,
        p_nom_extendable=True,
        capital_cost=0,
        marginal_cost=SUBSIDY_CHP_NATURAL_GAS,  # Additional revenue on top of market price
        committable=False,
    )

    n.add(
        "Link",
        "chp_natural_gas_boiler_site_b",
        bus0="bus_gas_natural_site_b",
        bus1="bus_heat_site_b",
        carrier="heat",
        efficiency=CHP_TOTAL_EFF,
        p_nom_extendable=True,
        p_nom_max=30,
        capital_cost=0,
        marginal_cost=3,  # O&M EUR/MWh (fuel cost at market bus)
        committable=True,
        p_min_pu=0.4,
        start_up_cost=0,
        shut_down_cost=0,
    )

    # CHP Biomethane at Site B
    n.add(
        "Link",
        "chp_biomethane_gen_site_b",
        bus0="bus_gas_biomethane_site_b",
        bus1="bus_electric_chp_biomethane_site_b",
        carrier="electric",
        efficiency=CHP_TOTAL_EFF,
        p_nom_extendable=True,
        p_nom_max=20,
        capital_cost=capex_to_capital_cost(700000),  # EUR/MW_el (700 EUR/kW_el)
        marginal_cost=5,  # O&M EUR/MWh (fuel cost at market bus)
        committable=True,
        p_min_pu=0.40,
        start_up_cost=100,
        shut_down_cost=50,
    )

    # Feed-in link with EEG subsidy (to market bus to receive market price)
    n.add(
        "Link",
        "chp_biomethane_feed_in_site_b",
        bus0="bus_electric_chp_biomethane_site_b",
        bus1="bus_electric_market",  # To market: receives market price + subsidy
        carrier="electric",
        efficiency=1.0,
        p_nom_extendable=True,
        capital_cost=0,
        marginal_cost=SUBSIDY_CHP_BIOMETHANE,  # Additional revenue on top of market price
        committable=False,
    )

    n.add(
        "Link",
        "chp_biomethane_boiler_site_b",
        bus0="bus_gas_biomethane_site_b",
        bus1="bus_heat_site_b",
        carrier="heat",
        efficiency=CHP_TOTAL_EFF,
        p_nom_extendable=True,
        p_nom_max=20,
        capital_cost=0,
        marginal_cost=3,  # O&M EUR/MWh (fuel cost at market bus)
        committable=True,
        p_min_pu=0.0,
        start_up_cost=0,
        shut_down_cost=0,
    )

    # CHP Biogas at Site B
    n.add(
        "Link",
        "chp_biogas_gen_site_b",
        bus0="bus_gas_biogas_site_b",
        bus1="bus_electric_chp_biogas_site_b",
        carrier="electric",
        efficiency=CHP_TOTAL_EFF,
        p_nom_extendable=True,
        p_nom_max=10,
        capital_cost=capex_to_capital_cost(750000),  # EUR/MW_el (750 EUR/kW_el)
        marginal_cost=6,  # O&M EUR/MWh (fuel cost at market bus)
        committable=True,
        p_min_pu=0.40,
        start_up_cost=80,
        shut_down_cost=40,
    )

    # Feed-in link with EEG subsidy (to market bus to receive market price)
    n.add(
        "Link",
        "chp_biogas_feed_in_site_b",
        bus0="bus_electric_chp_biogas_site_b",
        bus1="bus_electric_market",  # To market: receives market price + subsidy
        carrier="electric",
        efficiency=1.0,
        p_nom_extendable=True,
        capital_cost=0,
        marginal_cost=SUBSIDY_CHP_BIOGAS,  # Additional revenue on top of market price
        committable=False,
    )

    n.add(
        "Link",
        "chp_biogas_boiler_site_b",
        bus0="bus_gas_biogas_site_b",
        bus1="bus_heat_site_b",
        carrier="heat",
        efficiency=CHP_TOTAL_EFF,
        p_nom_extendable=True,
        p_nom_max=10,
        capital_cost=0,
        marginal_cost=4,  # O&M EUR/MWh (fuel cost at market bus)
        committable=True,
        p_min_pu=0.4,
        start_up_cost=0,
        shut_down_cost=0,
    )

    # Gas Boiler at Site B
    n.add(
        "Link",
        "gas_boiler_site_b",
        bus0="bus_gas_natural_site_b",
        bus1="bus_heat_site_b",
        carrier="heat",
        efficiency=0.95,
        p_nom_extendable=True,
        p_nom_max=25,
        capital_cost=capex_to_capital_cost(250000),  # EUR/MW_th (250 EUR/kW_th)
        marginal_cost=3,  # O&M EUR/MWh (fuel cost at market bus)
        committable=True,
        p_min_pu=0.20,
        start_up_cost=30,
        shut_down_cost=15,
    )

    # -------------------------------------------------------------------------
    # AUXILIARY LOADS (Pump electricity at production sites)
    # -------------------------------------------------------------------------
    # These will be calculated after optimization based on heat production
    # For now, add placeholder loads (will be updated in constraint function)

    n.add("Load", "aux_load_site_a", bus="bus_electric_site_a", p_set=0.0)
    n.add("Load", "aux_load_site_b", bus="bus_electric_site_b", p_set=0.0)

    return n


# =============================================================================
# CUSTOM CONSTRAINTS
# =============================================================================


def add_custom_constraints(n: pypsa.Network) -> None:
    """Add custom constraints for CHP coupling and biogas limits.

    CHP coupling constraints enforce a FIXED ratio between electrical and thermal power,
    both in part-load and full-load operation: Q(t) = CHP_QP_RATIO * P(t)
    """

    model = n.optimize.create_model()

    link_p = model.variables["Link-p"]
    link_p_nom = model.variables["Link-p_nom"]

    # -------------------------------------------------------------------------
    # CHP COUPLING CONSTRAINTS (for each CHP plant)
    # -------------------------------------------------------------------------

    chp_pairs = [
        ("chp_natural_gas_gen_site_a", "chp_natural_gas_boiler_site_a"),
        ("chp_biomethane_gen_site_a", "chp_biomethane_boiler_site_a"),
        ("chp_biogas_gen_site_a", "chp_biogas_boiler_site_a"),
        ("chp_natural_gas_gen_site_b", "chp_natural_gas_boiler_site_b"),
        ("chp_biomethane_gen_site_b", "chp_biomethane_boiler_site_b"),
        ("chp_biogas_gen_site_b", "chp_biogas_boiler_site_b"),
    ]

    for gen_name, boiler_name in chp_pairs:
        if gen_name not in n.links.index or boiler_name not in n.links.index:
            continue

        gen_eff = float(n.links.at[gen_name, "efficiency"])
        boiler_eff = float(n.links.at[boiler_name, "efficiency"])

        gen_p = link_p.sel(name=gen_name)
        boiler_p = link_p.sel(name=boiler_name)
        gen_p_nom = link_p_nom.sel(name=gen_name)
        boiler_p_nom = link_p_nom.sel(name=boiler_name)

        electric_output = gen_eff * gen_p
        heat_output = boiler_eff * boiler_p

        # ---------------------------
        # FESTES P/Q-VERHÄLTNIS für CHP
        # ---------------------------
        # Erzwingt ein starres Verhältnis zwischen elektrischer und thermischer Leistung,
        # sowohl in Teillast als auch in Volllast: Q = RHO * P

        # CONSTRAINT 1: Nominale Kapazitäts-Proportionalität
        # Die nominalen Kapazitäten müssen im Verhältnis Q_nom/P_nom = CHP_QP_RATIO stehen
        model.add_constraints(
            boiler_eff * boiler_p_nom - CHP_QP_RATIO * gen_eff * gen_p_nom
            == 0,
            name=f"chp-nominal-capacity-ratio-{gen_name}",
        )

        # CONSTRAINT 2: Festes Q/P-Verhältnis zu jedem Zeitpunkt
        # Erzwingt: Q(t) = RHO * P(t) für alle Zeitpunkte (Teillast und Volllast)
        model.add_constraints(
            heat_output - CHP_QP_RATIO * electric_output == 0,
            name=f"chp-fixed-power-ratio-{gen_name}",
        )

        # Status synchronization: generator and boiler must be on/off together
        # If generator is committable, ensure boiler follows the same status
        if n.links.at[gen_name, "committable"]:
            # Get status variables
            gen_status = model.variables["Link-status"].sel(name=gen_name)
            boiler_status = model.variables["Link-status"].sel(
                name=boiler_name
            )

            # Generator status = Boiler status
            model.add_constraints(
                gen_status - boiler_status == 0,
                name=f"chp-status-sync-{gen_name}",
            )

    # -------------------------------------------------------------------------
    # BIOGAS WEEKLY LIMIT CONSTRAINTS
    # -------------------------------------------------------------------------

    # For 7-day simulation: weekly limit applies to entire period
    # For annual simulation: separate constraint for each week

    weeks = int(np.ceil(len(n.snapshots) / 168))  # Number of weeks

    biogas_links = [
        "chp_biogas_gen_site_a",
        "chp_biogas_boiler_site_a",
        "chp_biogas_gen_site_b",
        "chp_biogas_boiler_site_b",
    ]

    # Filter to existing links
    biogas_links = [link for link in biogas_links if link in n.links.index]

    if biogas_links:
        for week in range(weeks):
            start_hour = week * 168
            end_hour = min((week + 1) * 168, len(n.snapshots))
            week_snapshots = n.snapshots[start_hour:end_hour]

            # Sum of biogas consumption across all biogas links in this week
            biogas_consumption = sum(
                link_p.sel(name=link, snapshot=week_snapshots).sum()
                for link in biogas_links
            )

            model.add_constraints(
                biogas_consumption <= BIOGAS_WEEKLY_LIMIT,
                name=f"biogas-weekly-limit-week-{week}",
            )

    # -------------------------------------------------------------------------
    # AUXILIARY POWER CONSUMPTION
    # -------------------------------------------------------------------------
    # This is complex: aux load depends on heat production, which is a variable
    # Approach: Add as post-processing or soft constraint
    # For simplicity, we'll add it as a linear constraint:
    # aux_load(t) = AUX_POWER_RATIO × sum(heat_production_at_site(t))

    # This requires adding auxiliary load as variable, not fixed load
    # For now, we'll skip this in the model and add it as post-processing

    # Solve the model
    n.optimize.solve_model(
        solver_name="highs",
        solver_options={"mip_rel_gap": 0.05, "threads": 16, "parallel": "on"},
    )


# =============================================================================
# OPTIMIZATION AND ANALYSIS
# =============================================================================


def build_and_optimize() -> pypsa.Network:
    """Build network and run optimization with custom constraints."""

    print("=" * 80)
    print("DISTRICT HEATING NETWORK OPTIMIZATION")
    print("=" * 80)
    print(f"Simulation period: {DAYS} days ({len(SNAPSHOTS)} snapshots)")
    print(f"Biogas weekly limit: {BIOGAS_WEEKLY_LIMIT} MWh/week")
    print()
    
    # Calculate and display annuity information
    annuity_factor = calculate_annuity_factor(INTEREST_RATE, LIFETIME_YEARS)
    
    # Determine snapshot frequency
    n_snapshots = len(SNAPSHOTS)
    if n_snapshots > 1:
        snapshot_freq = pd.Timedelta(SNAPSHOTS[1] - SNAPSHOTS[0])
        snapshot_duration_hours = snapshot_freq.total_seconds() / 3600.0
    else:
        snapshot_duration_hours = 1.0
    
    total_hours = n_snapshots * snapshot_duration_hours
    time_scale = total_hours / 8760
    
    print(f"Time resolution:")
    print(f"  Snapshot frequency: {snapshot_duration_hours:.2f} hours ({snapshot_duration_hours*60:.0f} minutes)")
    print(f"  Number of snapshots: {n_snapshots}")
    print(f"  Total simulation time: {total_hours:.1f} hours ({total_hours/24:.1f} days)")
    print()
    
    print(f"Economic parameters:")
    print(f"  Interest rate: {INTEREST_RATE*100:.1f}%")
    print(f"  Lifetime: {LIFETIME_YEARS} years")
    print(f"  Annuity factor: {annuity_factor:.6f}")
    print(f"  Time scale factor: {time_scale:.6f} ({total_hours:.1f}/{8760} hours)")
    print(f"  Equipment investment factor (annuity × time): {annuity_factor * time_scale:.6f}")
    print(f"  Grid charges factor (time only): {time_scale:.6f}")
    print()

    n = build_network()
    print(
        f"Network built: {len(n.buses)} buses, {len(n.links)} links, {len(n.loads)} loads"
    )
    print()

    add_custom_constraints(n)

    print("\nOptimization completed successfully!")
    print(f"Total system cost: {n.objective:,.2f} EUR")

    return n


def print_results_summary(n: pypsa.Network) -> None:
    """Print summary of optimization results."""

    print("\n" + "=" * 80)
    print("OPTIMIZATION RESULTS SUMMARY")
    print("=" * 80)

    # Total costs
    print(f"\nTotal System Cost: {n.objective:,.2f} EUR")

    # Heat production by technology
    print("\n" + "-" * 80)
    print("HEAT PRODUCTION BY TECHNOLOGY [MWh]")
    print("-" * 80)

    heat_links = [
        link
        for link in n.links.index
        if "heat" in link or "boiler" in link or "pump" in link
    ]

    for link in sorted(heat_links):
        if link in n.links_t.p1.columns:
            production = n.links_t.p1[link].sum()
            capacity = n.links.at[link, "p_nom_opt"]
            if production > 0.01:
                print(
                    f"{link:40s}: {production:10.2f} MWh  (capacity: {capacity:6.2f} MW)"
                )

    # Installed capacities
    print("\n" + "-" * 80)
    print("INSTALLED CAPACITIES [MW]")
    print("-" * 80)

    for link in sorted(n.links.index):
        capacity = n.links.at[link, "p_nom_opt"]
        if capacity > 0.01:
            print(f"{link:40s}: {capacity:10.2f} MW")

    # Grid usage
    print("\n" + "-" * 80)
    print("GRID CONNECTIONS [MWh total, MW peak]")
    print("-" * 80)

    grid_links = [link for link in n.links.index if "grid_" in link]
    for link in sorted(grid_links):
        if link in n.links_t.p0.columns:
            usage = n.links_t.p0[link].sum()
            peak = n.links_t.p0[link].max()
            if usage > 0.01:
                print(f"{link:40s}: {usage:10.2f} MWh  (peak: {peak:6.2f} MW)")

    print("\n" + "=" * 80)


def save_plots(n: pypsa.Network) -> None:
    """Create and save visualization plots."""

    PLOT_DIR.mkdir(exist_ok=True)

    # Heat supply by consumer
    for consumer in ["consumer_1", "consumer_2", "consumer_3"]:
        bus_name = f"bus_heat_{consumer}"

        if bus_name not in n.buses.index:
            continue

        # Get all heat supply to this consumer
        supply = n.statistics.supply(
            components=["Link", "Store"],
            groupby_time=False,
            groupby=False,
            at_port=True,
            nice_names=False,
            drop_zero=True,
            bus_carrier="heat",
        )

        if supply.empty:
            continue

        supply = supply.T.clip(lower=0.0)

        fig, ax = plt.subplots(figsize=(12, 6))
        supply.plot.area(ax=ax, linewidth=0, alpha=0.8)
        ax.set_ylabel("Heat Supply [MW]")
        ax.set_xlabel("Time")
        ax.set_title(f"Heat Supply - {consumer.replace('_', ' ').title()}")
        ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0))
        fig.tight_layout()

        plot_file = PLOT_DIR / f"heat_supply_{consumer}.png"
        fig.savefig(plot_file, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved plot: {plot_file}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    n = build_and_optimize()

    # Export network
    n.export_to_netcdf(str(RESULT_FILE))
    print(f"\nExported network to: {RESULT_FILE}")

    # Print results
    print_results_summary(n)

    # Save plots
    save_plots(n)

    print("\n" + "=" * 80)
    print("COMPLETE")
    print("=" * 80)

    gens = n.generators
    gens_t = n.generators_t

    stores = n.stores
    stores_t = n.stores_t

    links = n.links
    links_t = n.links_t

    loads = n.loads
    loads_t = n.loads_t
