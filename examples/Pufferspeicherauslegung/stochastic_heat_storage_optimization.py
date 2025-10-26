"""
Stochastic Heat Storage Optimization for District Heating Network
==================================================================

This example demonstrates optimal sizing of a thermal buffer storage for a 
district heating network with:
- Fixed heat pump capacity (committable=True for ON/OFF operation)
- Stochastic weather scenarios (Cold, Medium, Warm)
- Temperature-dependent heat pump COP (polynomial efficiency curve)
- Variable storage energy content based on supply/return temperatures
- Time-series data from Excel files (heat demand, temperatures)

The optimization determines:
- Optimal thermal storage capacity (e_nom) for the given heat pump
- Scenario-dependent heat pump operation (status variables)
- Storage charging/discharging strategy across weather scenarios

Mathematical Framework:
- Two-stage stochastic optimization
- First stage (here-and-now): Storage capacity investment
- Second stage (wait-and-see): Heat pump operation, storage dispatch
"""

import pypsa
from pypsa.common import annuity
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')

# ==================== Configuration ====================

# File paths
DATA_DIR = Path(__file__).parent
EXCEL_FILE = "Zeitreihendaten_Szenarien_Speicherauslegung.xlsx"
HP_PARAMS_FILE = DATA_DIR / "Interpolationsformeln Parameter für Wärmepumpen.xlsx"

# Scenario configuration (weather years)
SCENARIOS = {
    'cold': {
        'sheet_name': 'Szenario 1',
        'description': 'Kaltes Wetterjahr (Szenario 1)',
        'weight': 0.25,  # 25% probability
    },
    'medium': {
        'sheet_name': 'Szenario 2',
        'description': 'Mittleres Wetterjahr (Szenario 2)',
        'weight': 0.5,   # 50% probability
    },
    'warm': {
        'sheet_name': 'Szenario 3',
        'description': 'Warmes Wetterjahr (Szenario 3)',
        'weight': 0.25,  # 25% probability
    },
}

# Heat pump configuration
HP_FIXED_CAPACITY_MW = 0.6  # Fixed installed capacity in MW (600 kW)
HP_TYPE = 'Fenagy H600'  # Heat pump type for polynomial coefficients
HP_MIN_PART_LOAD = 0.3  # Minimum part load (30%)
HP_STARTUP_COST = 50  # EUR per startup
HP_MIN_UPTIME = 2  # Minimum 2 hours continuous operation
HP_MIN_DOWNTIME = 1  # Minimum 1 hour off

# Storage configuration
STORAGE_TEMP_SUPPLY_NOMINAL = 70  # °C - Nominal supply temperature
STORAGE_TEMP_RETURN_NOMINAL = 40  # °C - Nominal return temperature
STORAGE_STANDING_LOSS = 0.02  # 2% per hour standing losses

# Non-linear storage cost function: Cost = 5551.7 * V^(-0.35) EUR/m³
# Water: 1 m³ = 1000 kg, c_p = 4.186 kJ/(kg·K), ΔT = 30K (70°C - 40°C)
# 1 m³ water @ 30K = 1000 * 4.186 * 30 / 3600 = 34.88 kWh = 0.03488 MWh
STORAGE_M3_TO_MWH = 0.03488  # Conversion factor m³ to MWh for 30K temperature difference
STORAGE_COST_COEFF = 5551.7   # EUR/m³
STORAGE_COST_EXPONENT = -0.35 # Non-linear exponent

# Financial parameters for annualization
STORAGE_LIFETIME_YEARS = 30    # Lifetime of thermal storage in years
STORAGE_DISCOUNT_RATE = 0.05   # Discount rate (5%)

# Iterative optimization settings
STORAGE_INITIAL_GUESS_M3_PER_MW = 250  # Initial guess: 250 m³ per MW heat pump capacity
STORAGE_ITERATION_TOLERANCE = 0.05     # 5% relative change tolerance
STORAGE_MAX_ITERATIONS = 10            # Maximum number of iterations

# Network configuration
USE_SPOT_PRICES = True            # Use time-varying spot prices from Excel
GRID_ELECTRICITY_PRICE = 80       # EUR/MWh (fallback if spot prices not available)
PEAK_BOILER_COST = 120            # EUR/MWh (expensive backup)

# Optimization settings
MIP_GAP = 0.1  # 10% optimality gap
TIME_LIMIT = 600  # 10 minutes

# Simulation period (full year)
HOURS_TO_SIMULATE = 8760  # 1 year = 8760 hours

# Generate timestamp for output files
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# Output
OUTPUT_FILE = DATA_DIR / f"stochastic_heat_storage_results_{TIMESTAMP}.nc"
PLOT_FILE = DATA_DIR / f"stochastic_heat_storage_optimization_{TIMESTAMP}.png"
PLOTLY_FILE = DATA_DIR / f"heat_balance_interactive_{TIMESTAMP}.html"
EXCEL_OUTPUT_FILE = DATA_DIR / f"pypsa_results_export_{TIMESTAMP}.xlsx"


# ==================== Helper Functions ====================

def load_heat_pump_coefficients(hp_type: str = None) -> dict:
    """Load polynomial coefficients for heat pump COP and thermal power.
    
    The heat pump performance is modeled as:
    P_th = f(T_ambient, T_inlet, T_outlet) - polynomial
    COP = f(T_ambient, T_inlet, T_outlet) - polynomial
    
    Args:
        hp_type: Heat pump type (currently unused, using simplified Excel)
    
    Returns:
        dict: Coefficients for P_th_max and COP polynomials
    """
    excel_path = DATA_DIR / "Interpolationsformeln Parameter für Wärmepumpe.xlsx"
    df = pd.read_excel(excel_path, sheet_name='Parameter')
    
    # New simplified format: columns are ['Term', 'P_th_max', 'COP']
    # Rows contain the polynomial terms
    
    # Map term names to coefficient keys
    term_mapping = {
        'Intercept': 'intercept',
        'Ambient temperature [°C]': 'T_amb',
        'Water inlet temperature [°C]': 'T_in',
        'Water outlet temperature [°C]': 'T_out',
        'Ambient temperature [°C]^2': 'T_amb_sq',
        'Ambient temperature [°C] Water inlet temperature [°C]': 'T_amb_T_in',
        'Ambient temperature [°C] Water outlet temperature [°C]': 'T_amb_T_out',
        'Water inlet temperature [°C]^2': 'T_in_sq',
        'Water inlet temperature [°C] Water outlet temperature [°C]': 'T_in_T_out',
        'Water outlet temperature [°C]^2': 'T_out_sq',
    }
    
    # Extract coefficients
    coeffs = {
        'p_th': {},
        'cop': {}
    }
    
    for idx, row in df.iterrows():
        term_name = row['Term']
        if term_name in term_mapping:
            key = term_mapping[term_name]
            coeffs['p_th'][key] = row['P_th_max']
            coeffs['cop'][key] = row['COP']
    
    # Ensure all required keys exist (set to 0 if missing)
    required_keys = ['intercept', 'T_amb', 'T_in', 'T_out', 'T_amb_sq', 
                     'T_amb_T_in', 'T_amb_T_out', 'T_in_sq', 'T_in_T_out', 'T_out_sq']
    for model in ['p_th', 'cop']:
        for key in required_keys:
            if key not in coeffs[model]:
                coeffs[model][key] = 0.0
    
    return coeffs


def calculate_cop_timeseries(
    T_ambient: np.ndarray,
    T_supply: np.ndarray,
    T_return: np.ndarray,
    coeffs: dict
) -> np.ndarray:
    """Calculate time-dependent COP using polynomial model.
    
    COP = c0 + c1*T_amb + c2*T_in + c3*T_out + c4*T_amb^2 + 
          c5*T_amb*T_in + c6*T_amb*T_out + c7*T_in^2 + 
          c8*T_in*T_out + c9*T_out^2
    
    Args:
        T_ambient: Ambient temperature [°C]
        T_supply: Supply/outlet temperature [°C]
        T_return: Return/inlet temperature [°C]
        coeffs: Polynomial coefficients from load_heat_pump_coefficients
        
    Returns:
        COP time series
    """
    c = coeffs['cop']
    
    cop = (
        c['intercept'] +
        c['T_amb'] * T_ambient +
        c['T_in'] * T_return +
        c['T_out'] * T_supply +
        c['T_amb_sq'] * T_ambient**2 +
        c['T_amb_T_in'] * T_ambient * T_return +
        c['T_amb_T_out'] * T_ambient * T_supply +
        c['T_in_sq'] * T_return**2 +
        c['T_in_T_out'] * T_return * T_supply +
        c['T_out_sq'] * T_supply**2
    )
    
    # Ensure physical limits (COP between 1.5 and 10)
    cop = np.clip(cop, 1.5, 10.0)
    
    return cop


def load_scenario_data(scenario_name: str, scenario_config: dict, n_hours: int) -> dict:
    """Load time-series data for a specific weather scenario.
    
    Args:
        scenario_name: Scenario identifier ('cold', 'medium', 'warm')
        scenario_config: Configuration dict with sheet name and weight
        n_hours: Number of hours to load
        
    Returns:
        dict with time-series data:
            - heat_demand_mw: Heat demand [MW]
            - temp_supply: Supply temperature [°C]
            - temp_return: Return temperature [°C]
            - temp_ambient: Ambient temperature [°C]
            - electricity_price: Electricity spot price [EUR/MWh]
    """
    sheet_name = scenario_config['sheet_name']
    excel_path = DATA_DIR / EXCEL_FILE
    
    # Load data from Excel
    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    
    # Convert column names to lowercase for case-insensitive matching
    df.columns = df.columns.str.lower()
    
    # Extract required columns
    columns_needed = {
        'leistung': 'heat_demand_kw',       # Heat demand in kW
        'vlt': 'temp_supply',                # Supply temperature (Vorlauftemperatur)
        'rlt': 'temp_return',                # Return temperature (Rücklauftemperatur)
        'at': 'temp_ambient',                # Ambient temperature (Außentemperatur)
        'stromspotpreis': 'electricity_price', # Electricity spot price (EUR/MWh)
    }
    
    # Make sure we have enough data
    actual_hours = min(n_hours, len(df))
    if actual_hours < n_hours:
        print(f"Warning: Only {actual_hours} hours available in {sheet_name}, requested {n_hours}")
    
    # Extract and prepare data
    data = {}
    for excel_col, data_key in columns_needed.items():
        if excel_col in df.columns:
            values = df[excel_col].values[:actual_hours]
            
            # Handle NaN values with interpolation
            mask = np.isnan(values)
            if mask.any():
                valid_indices = np.where(~mask)[0]
                invalid_indices = np.where(mask)[0]
                
                if len(valid_indices) == 0:
                    # All NaN - use defaults
                    print(f"Warning: All NaN in {data_key} for scenario {scenario_name}, using default values")
                    if data_key == 'heat_demand_kw':
                        values = np.full(actual_hours, 300.0)  # 300 kW default
                    elif data_key == 'temp_supply':
                        values = np.full(actual_hours, 70.0)   # 70°C default
                    elif data_key == 'temp_return':
                        values = np.full(actual_hours, 50.0)   # 50°C default
                    elif data_key == 'temp_ambient':
                        values = np.full(actual_hours, 5.0)    # 5°C default
                    elif data_key == 'electricity_price':
                        values = np.full(actual_hours, GRID_ELECTRICITY_PRICE)  # Fallback price
                else:
                    # Interpolate missing values
                    values[invalid_indices] = np.interp(
                        invalid_indices,
                        valid_indices,
                        values[valid_indices]
                    )
            
            data[data_key] = values
        elif data_key == 'electricity_price':
            # Optional column - use default if not present
            print(f"Warning: Column '{excel_col}' not found, using constant price {GRID_ELECTRICITY_PRICE} EUR/MWh")
            data[data_key] = np.full(actual_hours, GRID_ELECTRICITY_PRICE)
        else:
            raise ValueError(f"Column '{excel_col}' not found in sheet '{sheet_name}'")
    
    # Convert heat demand from kW to MW
    data['heat_demand_mw'] = data.pop('heat_demand_kw') / 1000.0
    
    # Pad with last value if we got fewer hours than requested
    if actual_hours < n_hours:
        for key in data:
            padding = np.full(n_hours - actual_hours, data[key][-1])
            data[key] = np.concatenate([data[key], padding])
    
    return data


def calculate_storage_cost(volume_m3: float) -> dict:
    """Calculate storage costs based on non-linear cost function with annualization.
    
    Cost function: C = 5551.7 * V^(-0.35) EUR/m³ (total investment)
    
    The total investment is then annualized using PyPSA's annuity function:
    annualized_cost = total_investment * annuity(lifetime, discount_rate)
    
    Args:
        volume_m3: Storage volume in m³
        
    Returns:
        Dictionary with:
            - specific_cost_per_m3: EUR/m³ (total investment)
            - total_cost: EUR (total investment)
            - annualized_cost: EUR/a (annualized)
            - volume_mwh: Equivalent MWh capacity
            - cost_per_mwh: EUR/(MWh·a) (annualized capital cost for PyPSA)
    """
    if volume_m3 <= 0:
        return {
            'specific_cost_per_m3': 0,
            'total_cost': 0,
            'annualized_cost': 0,
            'volume_mwh': 0,
            'cost_per_mwh': 0,
        }
    
    # Calculate specific cost per m³ (total investment)
    specific_cost = STORAGE_COST_COEFF * (volume_m3 ** STORAGE_COST_EXPONENT)
    
    # Total investment cost
    total_cost = specific_cost * volume_m3
    
    # Calculate annuity factor: r / (1 - (1 + r)^(-n))
    annuity_factor = annuity(STORAGE_DISCOUNT_RATE, STORAGE_LIFETIME_YEARS)
    
    # Annualized cost per year
    annualized_cost = total_cost * annuity_factor
    
    # Convert to MWh
    volume_mwh = volume_m3 * STORAGE_M3_TO_MWH
    
    # Annualized cost per MWh for PyPSA capital_cost parameter
    cost_per_mwh = annualized_cost / volume_mwh if volume_mwh > 0 else 0
    
    return {
        'specific_cost_per_m3': specific_cost,
        'total_cost': total_cost,
        'annualized_cost': annualized_cost,
        'annuity_factor': annuity_factor,
        'volume_m3': volume_m3,
        'volume_mwh': volume_mwh,
        'cost_per_mwh': cost_per_mwh,  # This is now EUR/(MWh·a)
    }


def calculate_storage_energy_content(
    e_nom: float,
    temp_supply: np.ndarray,
    temp_return: np.ndarray
) -> np.ndarray:
    """Calculate actual storage energy content based on temperature difference.
    
    E_actual = E_nom * (T_supply - T_return) / (T_supply_nom - T_return_nom)
    
    Args:
        e_nom: Nominal storage capacity [MWh]
        temp_supply: Supply temperature time series [°C]
        temp_return: Return temperature time series [°C]
        
    Returns:
        Actual storage capacity time series [MWh]
    """
    delta_T_nominal = STORAGE_TEMP_SUPPLY_NOMINAL - STORAGE_TEMP_RETURN_NOMINAL
    delta_T_actual = temp_supply - temp_return
    
    # Ensure positive temperature difference
    delta_T_actual = np.maximum(delta_T_actual, 5.0)  # Minimum 5°C difference
    
    e_actual = e_nom * (delta_T_actual / delta_T_nominal)
    
    return e_actual


# ==================== Network Building ====================

def build_stochastic_network(storage_capital_cost_per_mwh: float = None) -> tuple:
    """Build stochastic PyPSA network with multiple weather scenarios.
    
    Args:
        storage_capital_cost_per_mwh: Capital cost for storage in EUR/MWh.
                                      If None, uses initial guess based on heat pump capacity.
    
    Returns:
        Tuple of (network, scenario_data)
    """
    
    print("\n" + "="*70)
    print("STOCHASTIC HEAT STORAGE OPTIMIZATION")
    print("="*70)
    print(f"Fixed heat pump capacity: {HP_FIXED_CAPACITY_MW:.1f} MW")
    print(f"Simulation period: {HOURS_TO_SIMULATE} hours")
    print(f"Scenarios: {len(SCENARIOS)}")
    for name, config in SCENARIOS.items():
        print(f"  - {name}: {config['description']} (weight: {config['weight']})")
    print("="*70)
    
    # Calculate initial storage cost if not provided
    if storage_capital_cost_per_mwh is None:
        initial_volume_m3 = STORAGE_INITIAL_GUESS_M3_PER_MW * HP_FIXED_CAPACITY_MW
        cost_info = calculate_storage_cost(initial_volume_m3)
        storage_capital_cost_per_mwh = cost_info['cost_per_mwh']
        print(f"\nInitial storage cost estimate:")
        print(f"  Volume guess: {initial_volume_m3:.1f} m³ ({cost_info['volume_mwh']:.2f} MWh)")
        print(f"  Specific cost: {cost_info['specific_cost_per_m3']:.2f} EUR/m³ (investment)")
        print(f"  Total investment: {cost_info['total_cost']:,.0f} EUR")
        print(f"  Annuity factor: {cost_info['annuity_factor']:.4f} (lifetime: {STORAGE_LIFETIME_YEARS}a, rate: {STORAGE_DISCOUNT_RATE*100:.1f}%)")
        print(f"  Annualized cost: {cost_info['annualized_cost']:,.0f} EUR/a")
        print(f"  Capital cost for PyPSA: {storage_capital_cost_per_mwh:,.0f} EUR/(MWh·a)")
    
    # Load heat pump coefficients
    hp_coeffs = load_heat_pump_coefficients()
    print(f"\nHeat pump polynomial coefficients loaded:")
    print(f"  COP intercept: {hp_coeffs['cop']['intercept']:.3f}")
    print(f"  P_th intercept: {hp_coeffs['p_th']['intercept']:.1f} W")
    
    # Create network with scenarios
    n = pypsa.Network()
    
    # Create snapshots (one hour resolution)
    snapshots = pd.date_range('2024-01-01', periods=HOURS_TO_SIMULATE, freq='h')
    n.set_snapshots(snapshots)
    
    # ==================== Buses ====================
    
    n.add(
        "Bus",
        "bus_heat",
        carrier="heat",
        x=0,
        y=0,
    )
    
    n.add(
        "Bus",
        "bus_electricity",
        carrier="electricity",
        x=1,
        y=0,
    )
    
    # ==================== Carriers ====================
    
    n.add("Carrier", "heat", color="#d62728")
    n.add("Carrier", "electricity", color="#1f77b4", co2_emissions=0.3)  # kg CO2/MWh
    
    # ==================== Components (must be added BEFORE set_scenarios) ====================
    
    # Heat demand load
    n.add(
        "Load",
        "heat_demand",
        bus="bus_heat",
        carrier="heat",
    )
    
    # Heat pump link
    n.add(
        "Link",
        "heat_pump",
        bus0="bus_electricity",
        bus1="bus_heat",
        carrier="heat",
        p_nom=HP_FIXED_CAPACITY_MW,  # Fixed capacity!
        p_nom_extendable=False,  # Not extendable
        committable=True,  # Can be turned ON/OFF
        p_min_pu=HP_MIN_PART_LOAD,  # Minimum 30% part load when ON
        marginal_cost=0,  # Cost is in electricity price
        start_up_cost=HP_STARTUP_COST,  # EUR per startup
        min_up_time=HP_MIN_UPTIME,  # Minimum uptime
        min_down_time=HP_MIN_DOWNTIME,  # Minimum downtime
    )
    
    # Thermal storage
    n.add(
        "Store",
        "thermal_storage",
        bus="bus_heat",
        carrier="heat",
        e_nom_extendable=True,  # THIS IS WHAT WE OPTIMIZE!
        e_nom_min=0.1,  # Minimum 100 kWh
        e_nom_max=20.0,  # Maximum 20 MWh
        e_initial=0.5,  # Start at 50% SOC
        e_cyclic=False,  # Workaround: cyclic=True has issues with scenarios in PyPSA
        standing_loss=STORAGE_STANDING_LOSS,  # 2% per hour
        capital_cost=storage_capital_cost_per_mwh,  # EUR/MWh (linearized from non-linear function)
    )
    
    # Grid electricity generator (with time-varying spot prices if available)
    n.add(
        "Generator",
        "grid_electricity",
        bus="bus_electricity",
        carrier="electricity",
        p_nom=10,  # 10 MW grid connection
        marginal_cost=GRID_ELECTRICITY_PRICE,  # Fallback constant price
    )
    
    # Peak boiler backup
    n.add(
        "Generator",
        "peak_boiler",
        bus="bus_heat",
        carrier="heat",
        p_nom=5,  # 5 MW peak boiler
        marginal_cost=PEAK_BOILER_COST,  # Expensive!
    )
    
    # ==================== Enable Stochastic Optimization ====================
    
    # NOW set scenarios - this converts component indices to MultiIndex
    scenario_weightings = {name: config['weight'] for name, config in SCENARIOS.items()}
    n.set_scenarios(scenario_weightings)
    
    print(f"\nNetwork created with {len(n.scenarios)} scenarios and {len(n.snapshots)} snapshots")
    print(f"Component indices converted to MultiIndex: {isinstance(n.loads.index, pd.MultiIndex)}")
    
    # ==================== Load Scenario Data ====================
    
    scenario_data = {}
    for scenario_name, scenario_config in SCENARIOS.items():
        print(f"\nLoading data for scenario '{scenario_name}'...")
        data = load_scenario_data(scenario_name, scenario_config, HOURS_TO_SIMULATE)
        scenario_data[scenario_name] = data
        
        print(f"  Heat demand: {data['heat_demand_mw'].mean():.2f} MW (avg), "
              f"{data['heat_demand_mw'].max():.2f} MW (peak)")
        print(f"  Temperature range: {data['temp_ambient'].min():.1f}°C to "
              f"{data['temp_ambient'].max():.1f}°C")
        
        # Calculate COP time series for this scenario
        cop_timeseries = calculate_cop_timeseries(
            data['temp_ambient'],
            data['temp_supply'],
            data['temp_return'],
            hp_coeffs
        )
        scenario_data[scenario_name]['cop'] = cop_timeseries
        
        print(f"  COP range: {cop_timeseries.min():.2f} to {cop_timeseries.max():.2f}, "
              f"avg: {cop_timeseries.mean():.2f}")
    
    # ==================== Populate Time-Dependent Data ====================
    
    # After set_scenarios(), the _t DataFrames have MultiIndex columns: (scenario, component_name)
    
    # Heat demand
    for scenario_name in n.scenarios:
        heat_demand_array = scenario_data[scenario_name]['heat_demand_mw']
        n.loads_t.p_set[(scenario_name, "heat_demand")] = heat_demand_array
    
    # Heat pump efficiency (COP)
    for scenario_name in n.scenarios:
        cop_array = scenario_data[scenario_name]['cop']
        n.links_t.efficiency[(scenario_name, "heat_pump")] = cop_array
    
    # Electricity spot prices (time-varying marginal cost)
    if USE_SPOT_PRICES:
        for scenario_name in n.scenarios:
            price_array = scenario_data[scenario_name]['electricity_price']
            n.generators_t.marginal_cost[(scenario_name, "grid_electricity")] = price_array
        print(f"\nElectricity pricing:")
        print(f"  Using time-varying spot prices from Excel")
        for scenario_name in n.scenarios:
            prices = scenario_data[scenario_name]['electricity_price']
            print(f"  {scenario_name}: {prices.min():.2f} - {prices.max():.2f} EUR/MWh (avg: {prices.mean():.2f})")
    
    print(f"\nHeat pump configured:")
    print(f"  Fixed capacity: {HP_FIXED_CAPACITY_MW:.1f} MW")
    print(f"  Committable: Yes (ON/OFF operation)")
    print(f"  Part load: {HP_MIN_PART_LOAD*100:.0f}% minimum")
    
    print(f"\nThermal storage configured:")
    print(f"  Capacity: OPTIMIZABLE (0.1 - 20 MWh)")
    print(f"  Standing loss: {STORAGE_STANDING_LOSS*100:.1f}% per hour")
    print(f"  Linearized capital cost: {storage_capital_cost_per_mwh:,.0f} EUR/MWh")
    
    print(f"\nBackup systems configured:")
    print(f"  Grid electricity: {GRID_ELECTRICITY_PRICE} EUR/MWh")
    print(f"  Peak boiler: {PEAK_BOILER_COST} EUR/MWh (expensive backup)")
    
    return n, scenario_data


# ==================== Optimization ====================

def optimize_storage(n: pypsa.Network) -> None:
    """Optimize the thermal storage capacity."""
    
    print("\n" + "="*70)
    print("RUNNING STOCHASTIC OPTIMIZATION")
    print("="*70)
    print(f"MIP gap tolerance: {MIP_GAP*100:.1f}%")
    print(f"Time limit: {TIME_LIMIT/60:.0f} minutes")
    print("="*70 + "\n")
    
    # Run optimization
    status = n.optimize(
        solver_name="highs",
        solver_options={
            'mip_rel_gap': MIP_GAP,
            'time_limit': TIME_LIMIT,
        }
    )
    
    # Status is a tuple: (status_string, termination_condition)
    if isinstance(status, tuple):
        status_str, termination = status
    else:
        status_str = status
        termination = None
    
    if status_str != "ok":
        raise RuntimeError(f"Optimization failed with status: {status_str}, termination: {termination}")
    
    print("\n" + "="*70)
    print(f"OPTIMIZATION COMPLETED SUCCESSFULLY ({termination})")
    print("="*70)


# ==================== Results Analysis ====================

def print_results(n: pypsa.Network, scenario_data: dict) -> None:
    """Print and analyze optimization results."""
    
    print("\n" + "="*70)
    print("OPTIMIZATION RESULTS")
    print("="*70)
    
    # Total system cost
    total_cost = n.objective
    print(f"\nTotal system cost: {total_cost:,.0f} EUR")
    
    # Optimal storage capacity (should be same for all scenarios - first stage)
    print("\n" + "-"*70)
    print("OPTIMAL THERMAL STORAGE CAPACITY")
    print("-"*70)
    
    # With stochastic MultiIndex, storage has entries like ('cold', 'thermal_storage')
    storage_capacities = {}
    for scenario in n.scenarios:
        # Access using MultiIndex tuple
        e_nom_opt = n.stores.loc[(scenario, 'thermal_storage'), 'e_nom_opt']
        
        # Convert to m³ and calculate actual cost
        volume_m3 = e_nom_opt / STORAGE_M3_TO_MWH
        cost_info = calculate_storage_cost(volume_m3)
        
        storage_capacities[scenario] = e_nom_opt
        
        print(f"\nScenario: {scenario.upper()}")
        print(f"  Optimal capacity: {e_nom_opt:.2f} MWh ({e_nom_opt*1000:.0f} kWh)")
        print(f"  Equivalent volume: {volume_m3:.1f} m³")
        print(f"  Specific cost: {cost_info['specific_cost_per_m3']:.2f} EUR/m³ (investment)")
        print(f"  Total investment: {cost_info['total_cost']:,.0f} EUR")
        print(f"  Annualized cost: {cost_info['annualized_cost']:,.0f} EUR/a")
    
    # Check if storage capacity is consistent across scenarios (first-stage decision)
    unique_capacities = set(np.round(list(storage_capacities.values()), 2))
    if len(unique_capacities) == 1:
        print(f"\n[OK] Storage capacity is consistent across scenarios (first-stage decision)")
        print(f"  Optimal size: {list(storage_capacities.values())[0]:.2f} MWh")
    else:
        print(f"\n[WARNING] Storage capacities differ across scenarios!")
        print("  This should not happen for first-stage decisions in stochastic optimization.")
        print(f"  Capacities: {storage_capacities}")
    
    # Heat pump operation statistics
    print("\n" + "-"*70)
    print("HEAT PUMP OPERATION (Scenario-Dependent)")
    print("-"*70)
    
    for scenario in n.scenarios:
        # With MultiIndex: links_t.p1 has columns like ('cold', 'heat_pump')
        hp_key = (scenario, 'heat_pump')
        
        # Get heat output and electricity consumption
        if hp_key in n.links_t.p1.columns:
            heat_output = n.links_t.p1[hp_key]
            elec_input = n.links_t.p0[hp_key]
            
            # Operation hours (when producing heat)
            operating_hours = (heat_output > 0.01).sum()
            operating_pct = operating_hours / len(n.snapshots) * 100
            
            # Average COP when operating
            operating_mask = heat_output > 0.01
            if operating_mask.any():
                avg_cop_operating = (heat_output[operating_mask] / -elec_input[operating_mask]).mean()
            else:
                avg_cop_operating = 0
            
            # Total energy
            total_heat = heat_output.sum()
            total_elec = -elec_input.sum()
            
            # Get status if available
            if hp_key in n.links_t.status.columns:
                status_series = n.links_t.status[hp_key]
                startups = (status_series.diff() > 0.5).sum()
            else:
                startups = 0
            
            print(f"\nScenario: {scenario.upper()}")
            print(f"  Operating hours: {operating_hours}/{len(n.snapshots)} ({operating_pct:.1f}%)")
            print(f"  Total heat output: {total_heat:.1f} MWh")
            print(f"  Total electricity: {total_elec:.1f} MWh")
            print(f"  Average COP (operating): {avg_cop_operating:.2f}")
            print(f"  Number of startups: {startups}")
            print(f"  Startup costs: {startups * HP_STARTUP_COST:.0f} EUR")
    
    # Storage utilization
    print("\n" + "-"*70)
    print("STORAGE UTILIZATION (Scenario-Dependent)")
    print("-"*70)
    
    for scenario in n.scenarios:
        storage_name = f"{scenario}_thermal_storage"
        
        if storage_name in n.stores_t.e.columns:
            soc = n.stores_t.e[storage_name]
            e_nom = n.stores.loc[storage_name, 'e_nom_opt']
            
            soc_pct = soc / e_nom * 100
            
            print(f"\nScenario: {scenario.upper()}")
            print(f"  Capacity: {e_nom:.2f} MWh")
            print(f"  SOC range: {soc_pct.min():.1f}% - {soc_pct.max():.1f}%")
            print(f"  Average SOC: {soc_pct.mean():.1f}%")
            print(f"  Full cycles: {(soc.max() - soc.min()) / e_nom:.2f}")
    
    # Backup boiler usage
    print("\n" + "-"*70)
    print("BACKUP BOILER USAGE")
    print("-"*70)
    
    for scenario in n.scenarios:
        boiler_name = f"{scenario}_peak_boiler"
        
        if boiler_name in n.generators_t.p.columns:
            boiler_output = n.generators_t.p[boiler_name]
            total_boiler = boiler_output.sum()
            boiler_hours = (boiler_output > 0.01).sum()
            boiler_cost = total_boiler * PEAK_BOILER_COST
            
            print(f"\nScenario: {scenario.upper()}")
            if total_boiler > 0.01:
                print(f"  Total output: {total_boiler:.1f} MWh")
                print(f"  Operating hours: {boiler_hours}")
                print(f"  Cost: {boiler_cost:,.0f} EUR")
                print(f"  ⚠ Backup boiler used - consider larger storage or HP!")
            else:
                print(f"  ✓ Not used (optimal design)")
    
    # Economic summary
    print("\n" + "="*70)
    print("ECONOMIC SUMMARY")
    print("="*70)
    
    # Calculate weighted costs per scenario
    # scenario_weightings is a Series with scenarios as index
    weighted_total = 0
    for scenario in n.scenarios:
        # Get weight from SCENARIOS config (scenario_weightings may have different structure)
        weight = SCENARIOS[scenario]['weight']
        
        # Get scenario-specific costs using MultiIndex keys
        hp_key = (scenario, 'heat_pump')
        boiler_key = (scenario, 'peak_boiler')
        grid_key = (scenario, 'grid_electricity')
        storage_key = (scenario, 'thermal_storage')
        
        # Operational costs
        elec_cost = 0
        if grid_key in n.generators_t.p.columns:
            elec_energy = n.generators_t.p[grid_key].sum()
            # Use scenario-specific marginal cost if available
            if grid_key in n.generators_t.marginal_cost.columns:
                avg_price = n.generators_t.marginal_cost[grid_key].mean()
                elec_cost = elec_energy * avg_price
            else:
                elec_cost = elec_energy * GRID_ELECTRICITY_PRICE
        
        boiler_cost = 0
        if boiler_key in n.generators_t.p.columns:
            boiler_energy = n.generators_t.p[boiler_key].sum()
            boiler_cost = boiler_energy * PEAK_BOILER_COST
        
        startup_cost = 0
        if hp_key in n.links_t.status.columns:
            startups = (n.links_t.status[hp_key].diff() > 0.5).sum()
            startup_cost = startups * HP_STARTUP_COST
        
        # Capital cost (using non-linear function with annualization)
        e_nom = n.stores.loc[storage_key, 'e_nom_opt']
        volume_m3 = e_nom / STORAGE_M3_TO_MWH
        cost_info = calculate_storage_cost(volume_m3)
        capital_cost = cost_info['annualized_cost']  # Use annualized cost
        
        scenario_total = elec_cost + boiler_cost + startup_cost + capital_cost
        weighted_cost = scenario_total * weight
        weighted_total += weighted_cost
        
        print(f"\nScenario: {scenario.upper()} (weight: {weight:.2%})")
        print(f"  Electricity cost: {elec_cost:,.0f} EUR/a")
        print(f"  Boiler cost: {boiler_cost:,.0f} EUR/a")
        print(f"  Startup cost: {startup_cost:,.0f} EUR/a")
        print(f"  Storage (annualized): {capital_cost:,.0f} EUR/a")
        print(f"  Scenario total: {scenario_total:,.0f} EUR/a")
        print(f"  Weighted cost: {weighted_cost:,.0f} EUR/a")
    
    print(f"\n{'='*70}")
    print(f"Expected total cost (annualized): {weighted_total:,.0f} EUR/a")
    print(f"Optimizer objective: {n.objective:,.0f} EUR/a")
    print(f"{'='*70}\n")


def create_plots(n: pypsa.Network, scenario_data: dict) -> None:
    """Create visualization plots."""
    
    print("\n" + "="*70)
    print("CREATING VISUALIZATION PLOTS")
    print("="*70)
    
    n_scenarios = len(n.scenarios)
    fig, axes = plt.subplots(n_scenarios, 3, figsize=(18, 6*n_scenarios))
    
    if n_scenarios == 1:
        axes = axes.reshape(1, -1)
    
    for idx, scenario in enumerate(n.scenarios):
        hp_name = f"{scenario}_heat_pump"
        storage_name = f"{scenario}_thermal_storage"
        demand_name = f"{scenario}_heat_demand"
        
        # Plot 1: Heat balance
        ax1 = axes[idx, 0]
        
        if hp_name in n.links_t.p1.columns:
            hp_output = -n.links_t.p1[hp_name]  # Multiply by -1 to get positive output
            ax1.plot(n.snapshots, hp_output, label='Heat Pump Output', linewidth=2)
        
        if storage_name in n.stores_t.p.columns:
            storage_discharge = n.stores_t.p[storage_name]
            ax1.plot(n.snapshots, storage_discharge, label='Storage Discharge (+) / Charge (-)', linewidth=1.5)
        
        if demand_name in n.loads_t.p.columns:
            demand = n.loads_t.p[demand_name]
            ax1.plot(n.snapshots, demand, label='Heat Demand', linestyle='--', linewidth=2, color='red')
        
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Power [MW]')
        ax1.set_title(f'Scenario: {scenario.upper()} - Heat Balance')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Storage state of charge
        ax2 = axes[idx, 1]
        
        e_nom = 0.0  # Default value
        if storage_name in n.stores_t.e.columns:
            soc = n.stores_t.e[storage_name]
            e_nom = n.stores.loc[storage_name, 'e_nom_opt']
            soc_pct = soc / e_nom * 100
            
            ax2.fill_between(n.snapshots, 0, soc_pct, alpha=0.3, color='blue')
            ax2.plot(n.snapshots, soc_pct, linewidth=2, color='blue')
            ax2.axhline(y=100, color='r', linestyle='--', label='Max Capacity', linewidth=1)
            ax2.axhline(y=0, color='r', linestyle='--', linewidth=1)
        
        ax2.set_xlabel('Time')
        ax2.set_ylabel('State of Charge [%]')
        ax2.set_title(f'Scenario: {scenario.upper()} - Storage SOC ({e_nom:.2f} MWh)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(-5, 105)
        
        # Plot 3: Heat pump efficiency and operation
        ax3 = axes[idx, 2]
        
        # COP time series
        cop_ts = scenario_data[scenario]['cop']
        ax3_twin = ax3.twinx()
        
        ax3.plot(n.snapshots, cop_ts, label='COP', color='green', linewidth=1.5)
        ax3.set_ylabel('COP [-]', color='green')
        ax3.tick_params(axis='y', labelcolor='green')
        
        # Heat pump status (if available)
        if hp_name in n.links_t.status.columns:
            status = n.links_t.status[hp_name]
            ax3_twin.fill_between(n.snapshots, 0, status, alpha=0.2, color='orange', label='HP ON/OFF')
            ax3_twin.set_ylabel('Heat Pump Status', color='orange')
            ax3_twin.tick_params(axis='y', labelcolor='orange')
            ax3_twin.set_ylim(-0.1, 1.1)
        
        ax3.set_xlabel('Time')
        ax3.set_title(f'Scenario: {scenario.upper()} - Heat Pump Operation')
        ax3.grid(True, alpha=0.3)
        
        lines1, labels1 = ax3.get_legend_handles_labels()
        lines2, labels2 = ax3_twin.get_legend_handles_labels()
        ax3.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
    
    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=150, bbox_inches='tight')
    print(f"\nPlots saved to: {PLOT_FILE}")
    
    plt.close()


def create_interactive_plots(n: pypsa.Network, scenario_data: dict) -> None:
    """Create interactive Plotly plots for heat balance and storage.
    
    For each scenario, creates a subplot with:
    - Top: Stacked area chart of heat generation sources + demand line
    - Bottom: Storage state of charge
    """
    
    print("\n" + "="*70)
    print("CREATING INTERACTIVE PLOTLY VISUALIZATIONS")
    print("="*70)
    
    n_scenarios = len(n.scenarios)
    
    # Create subplots: 2 rows per scenario (heat balance + storage)
    # Heat balance plots need secondary y-axis for electricity price
    specs = []
    for _ in range(n_scenarios):
        specs.append([{"secondary_y": True}])   # Heat balance with secondary axis
        specs.append([{"secondary_y": False}])  # Storage SOC without secondary axis
    
    fig = make_subplots(
        rows=n_scenarios * 2,
        cols=1,
        subplot_titles=[
            f'Scenario: {s.upper()} - Wärmebilanz' if i % 2 == 0 
            else f'Scenario: {s.upper()} - Speicherinhalt'
            for s in n.scenarios for i in range(2)
        ],
        vertical_spacing=0.05,
        specs=specs
    )
    
    for idx, scenario in enumerate(n.scenarios):
        row_heat = idx * 2 + 1
        row_storage = idx * 2 + 2
        
        # Component names with MultiIndex
        hp_key = (scenario, 'heat_pump')
        storage_key = (scenario, 'thermal_storage')
        demand_key = (scenario, 'heat_demand')
        boiler_key = (scenario, 'peak_boiler')
        
        # ==================== Heat Balance Plot ====================
        
        # Prepare data for stacked area chart
        heat_sources = {}
        
        # Heat pump output (p1 is negative in PyPSA convention, multiply by -1 to get positive output)
        if hp_key in n.links_t.p1.columns:
            hp_output = -n.links_t.p1[hp_key].values  # Multiply by -1 to get positive values
            heat_sources['Wärmepumpe'] = np.maximum(hp_output, 0)  # Only positive values
        
        # Storage discharge (positive when discharging to network)
        if storage_key in n.stores_t.p.columns:
            storage_discharge = n.stores_t.p[storage_key].values
            heat_sources['Speicher (Entladung)'] = np.maximum(storage_discharge, 0)
        
        # Backup boiler
        if boiler_key in n.generators_t.p.columns:
            boiler_output = n.generators_t.p[boiler_key].values
            heat_sources['Spitzenkessel'] = np.maximum(boiler_output, 0)
        
        # Add stacked area traces for heat generation
        colors = {
            'Wärmepumpe': '#1f77b4',  # Blue
            'Speicher (Entladung)': '#ff7f0e',  # Orange
            'Spitzenkessel': '#d62728',  # Red
        }
        
        for source_name, values in heat_sources.items():
            fig.add_trace(
                go.Scatter(
                    x=n.snapshots,
                    y=values,
                    name=f'{scenario.upper()}: {source_name}',
                    mode='lines',
                    stackgroup=f'heat_{scenario}',
                    fillcolor=colors.get(source_name, '#888888'),
                    line=dict(width=0.5, color=colors.get(source_name, '#888888')),
                    hovertemplate='<b>%{fullData.name}</b><br>' +
                                  'Zeit: %{x}<br>' +
                                  'Leistung: %{y:.3f} MW<br>' +
                                  '<extra></extra>',
                    legendgroup=scenario,
                ),
                row=row_heat, col=1
            )
        
        # Add heat demand as line (not stacked)
        if demand_key in n.loads_t.p.columns:
            demand = n.loads_t.p[demand_key].values
            fig.add_trace(
                go.Scatter(
                    x=n.snapshots,
                    y=demand,
                    name=f'{scenario.upper()}: Wärmebedarf',
                    mode='lines',
                    line=dict(color='black', width=2, dash='dash'),
                    hovertemplate='<b>Wärmebedarf</b><br>' +
                                  'Zeit: %{x}<br>' +
                                  'Leistung: %{y:.3f} MW<br>' +
                                  '<extra></extra>',
                    legendgroup=scenario,
                ),
                row=row_heat, col=1
            )
        
        # Add storage charging (negative, shown as separate area below zero)
        if storage_key in n.stores_t.p.columns:
            storage_charge = n.stores_t.p[storage_key].values
            charging = np.minimum(storage_charge, 0)  # Only negative values
            if np.any(charging < 0):
                fig.add_trace(
                    go.Scatter(
                        x=n.snapshots,
                        y=charging,
                        name=f'{scenario.upper()}: Speicher (Beladung)',
                        mode='lines',
                        fill='tozeroy',
                        fillcolor='rgba(144, 238, 144, 0.3)',  # Light green
                        line=dict(width=0.5, color='green'),
                        hovertemplate='<b>Speicher Beladung</b><br>' +
                                      'Zeit: %{x}<br>' +
                                      'Leistung: %{y:.3f} MW<br>' +
                                      '<extra></extra>',
                        legendgroup=scenario,
                    ),
                    row=row_heat, col=1
                )
        
        # Add electricity price on secondary y-axis
        grid_key = (scenario, 'grid_electricity')
        if grid_key in n.generators_t.marginal_cost.columns:
            elec_price = n.generators_t.marginal_cost[grid_key].values
            fig.add_trace(
                go.Scatter(
                    x=n.snapshots,
                    y=elec_price,
                    name=f'{scenario.upper()}: Strompreis',
                    mode='lines',
                    line=dict(color='purple', width=1.5, dash='dot'),
                    hovertemplate='<b>Strompreis</b><br>' +
                                  'Zeit: %{x}<br>' +
                                  'Preis: %{y:.2f} EUR/MWh<br>' +
                                  '<extra></extra>',
                    legendgroup=scenario,
                    yaxis='y2'
                ),
                row=row_heat, col=1, secondary_y=True
            )
        
        # Update heat balance y-axes
        fig.update_yaxes(title_text="Leistung [MW]", row=row_heat, col=1, secondary_y=False)
        fig.update_yaxes(title_text="Strompreis [EUR/MWh]", row=row_heat, col=1, secondary_y=True)
        fig.update_xaxes(showticklabels=False, row=row_heat, col=1)
        
        # ==================== Storage SOC Plot ====================
        
        # Use MultiIndex key for storage
        if storage_key in n.stores_t.e.columns:
            soc = n.stores_t.e[storage_key].values
            e_nom = n.stores.loc[storage_key, 'e_nom_opt']
            soc_pct = soc / e_nom * 100
            
            # Storage SOC as filled area
            fig.add_trace(
                go.Scatter(
                    x=n.snapshots,
                    y=soc_pct,
                    name=f'{scenario.upper()}: Speicherfüllstand',
                    mode='lines',
                    fill='tozeroy',
                    fillcolor='rgba(65, 105, 225, 0.3)',  # Royal blue with transparency
                    line=dict(color='royalblue', width=2),
                    hovertemplate='<b>Speicherfüllstand</b><br>' +
                                  'Zeit: %{x}<br>' +
                                  'SOC: %{y:.1f}%<br>' +
                                  f'Kapazität: {e_nom:.2f} MWh<br>' +
                                  '<extra></extra>',
                    legendgroup=scenario,
                    showlegend=True,
                ),
                row=row_storage, col=1
            )
            
            # Add horizontal lines for limits
            fig.add_hline(
                y=100, line_dash="dash", line_color="red", 
                annotation_text="Max", annotation_position="right",
                row=row_storage, col=1
            )
            fig.add_hline(
                y=0, line_dash="dash", line_color="red",
                row=row_storage, col=1
            )
        
        # Update storage y-axis
        fig.update_yaxes(
            title_text="Füllstand [%]", 
            range=[-5, 105],
            row=row_storage, col=1
        )
        
        # Show x-axis only on last subplot
        if idx == n_scenarios - 1:
            fig.update_xaxes(title_text="Zeit", row=row_storage, col=1)
        else:
            fig.update_xaxes(showticklabels=False, row=row_storage, col=1)
    
    # Update overall layout
    fig.update_layout(
        height=400 * n_scenarios * 2,  # Adaptive height
        title_text="Stochastische Wärmespeicher-Optimierung: Wärmebilanz und Speicherinhalt",
        showlegend=True,
        hovermode='x unified',
        template='plotly_white',
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1.0,
            xanchor="left",
            x=1.02,
            bgcolor="rgba(255, 255, 255, 0.8)",
            bordercolor="black",
            borderwidth=1
        )
    )
    
    # Save interactive HTML
    fig.write_html(PLOTLY_FILE)
    print(f"\nInteractive plot saved to: {PLOTLY_FILE}")
    print("  Open in web browser for interactive exploration!")


def export_to_excel(n: pypsa.Network, scenario_data: dict) -> None:
    """Export all PyPSA network data (master data and time series) to Excel.
    
    Creates an Excel file with multiple sheets:
    - Master data sheets for each component type (buses, generators, links, stores, loads)
    - Time series sheets for dynamic data (p, p_set, status, efficiency, etc.)
    - Summary sheet with key results
    
    Args:
        n: Optimized PyPSA network
        scenario_data: Dictionary with scenario input data
    """
    
    print("\n" + "="*70)
    print("EXPORTING DATA TO EXCEL")
    print("="*70)
    
    with pd.ExcelWriter(EXCEL_OUTPUT_FILE, engine='openpyxl') as writer:
        
        # ==================== SUMMARY SHEET ====================
        summary_data = []
        
        # Optimization info
        summary_data.append(['OPTIMIZATION RESULTS', ''])
        summary_data.append(['Total System Cost', f'{n.objective:.2f} EUR/a'])
        summary_data.append(['Number of Scenarios', len(n.scenarios)])
        summary_data.append(['Number of Snapshots', len(n.snapshots)])
        summary_data.append(['Simulation Period', f'{HOURS_TO_SIMULATE} hours'])
        summary_data.append(['', ''])
        
        # Storage capacity
        summary_data.append(['STORAGE CAPACITY (First-Stage)', ''])
        for scenario in n.scenarios:
            storage_key = (scenario, 'thermal_storage')
            e_nom = n.stores.loc[storage_key, 'e_nom_opt']
            volume_m3 = e_nom / STORAGE_M3_TO_MWH
            cost_info = calculate_storage_cost(volume_m3)
            
            summary_data.append([f'Scenario: {scenario}', f'{e_nom:.2f} MWh ({volume_m3:.1f} m³)'])
            summary_data.append([f'  Investment Cost', f'{cost_info["total_cost"]:,.0f} EUR'])
            summary_data.append([f'  Annualized Cost', f'{cost_info["annualized_cost"]:,.0f} EUR/a'])
        
        summary_data.append(['', ''])
        
        # Scenario weights
        summary_data.append(['SCENARIO WEIGHTS', ''])
        for scenario_name, config in SCENARIOS.items():
            summary_data.append([scenario_name, f'{config["weight"]:.2%}'])
        
        df_summary = pd.DataFrame(summary_data, columns=['Parameter', 'Value'])
        df_summary.to_excel(writer, sheet_name='Summary', index=False)
        
        # ==================== MASTER DATA SHEETS ====================
        
        # Buses
        if len(n.buses) > 0:
            df_buses = n.buses.copy()
            df_buses.to_excel(writer, sheet_name='Buses')
            print(f"  Exported {len(df_buses)} buses")
        
        # Carriers
        if len(n.carriers) > 0:
            df_carriers = n.carriers.copy()
            df_carriers.to_excel(writer, sheet_name='Carriers')
            print(f"  Exported {len(df_carriers)} carriers")
        
        # Generators
        if len(n.generators) > 0:
            df_generators = n.generators.copy()
            df_generators.to_excel(writer, sheet_name='Generators')
            print(f"  Exported {len(df_generators)} generators")
        
        # Links
        if len(n.links) > 0:
            df_links = n.links.copy()
            df_links.to_excel(writer, sheet_name='Links')
            print(f"  Exported {len(df_links)} links")
        
        # Stores
        if len(n.stores) > 0:
            df_stores = n.stores.copy()
            df_stores.to_excel(writer, sheet_name='Stores')
            print(f"  Exported {len(df_stores)} stores")
        
        # Loads
        if len(n.loads) > 0:
            df_loads = n.loads.copy()
            df_loads.to_excel(writer, sheet_name='Loads')
            print(f"  Exported {len(df_loads)} loads")
        
        # ==================== TIME SERIES DATA ====================
        
        # Generators time series
        if len(n.generators_t.p.columns) > 0:
            df_gen_p = n.generators_t.p.copy()
            df_gen_p.to_excel(writer, sheet_name='Gen_Dispatch')
            print(f"  Exported generator dispatch ({df_gen_p.shape[0]} timesteps, {df_gen_p.shape[1]} generators)")
        
        if len(n.generators_t.marginal_cost.columns) > 0:
            df_gen_mc = n.generators_t.marginal_cost.copy()
            df_gen_mc.to_excel(writer, sheet_name='Gen_MarginalCost')
            print(f"  Exported generator marginal costs")
        
        # Links time series
        if len(n.links_t.p0.columns) > 0:
            df_link_p0 = n.links_t.p0.copy()
            df_link_p0.to_excel(writer, sheet_name='Link_P0_Electricity')
            print(f"  Exported link p0 (electricity input)")
        
        if len(n.links_t.p1.columns) > 0:
            df_link_p1 = n.links_t.p1.copy()
            df_link_p1.to_excel(writer, sheet_name='Link_P1_Heat')
            print(f"  Exported link p1 (heat output)")
        
        if len(n.links_t.efficiency.columns) > 0:
            df_link_eff = n.links_t.efficiency.copy()
            df_link_eff.to_excel(writer, sheet_name='Link_Efficiency_COP')
            print(f"  Exported link efficiency (COP)")
        
        if len(n.links_t.status.columns) > 0:
            df_link_status = n.links_t.status.copy()
            df_link_status.to_excel(writer, sheet_name='Link_Status')
            print(f"  Exported link status (ON/OFF)")
        
        if len(n.links_t.p_max_pu.columns) > 0:
            df_link_p_max_pu = n.links_t.p_max_pu.copy()
            df_link_p_max_pu.to_excel(writer, sheet_name='Link_P_Max_PU')
            print(f"  Exported link p_max_pu (capacity factor)")
        
        # Stores time series
        if len(n.stores_t.p.columns) > 0:
            df_store_p = n.stores_t.p.copy()
            df_store_p.to_excel(writer, sheet_name='Store_Power')
            print(f"  Exported storage power (charge/discharge)")
        
        if len(n.stores_t.e.columns) > 0:
            df_store_e = n.stores_t.e.copy()
            df_store_e.to_excel(writer, sheet_name='Store_Energy_SOC')
            print(f"  Exported storage energy (SOC)")
        
        # Loads time series
        if len(n.loads_t.p.columns) > 0:
            df_load_p = n.loads_t.p.copy()
            df_load_p.to_excel(writer, sheet_name='Load_Demand')
            print(f"  Exported load demand")
        
        if len(n.loads_t.p_set.columns) > 0:
            df_load_pset = n.loads_t.p_set.copy()
            df_load_pset.to_excel(writer, sheet_name='Load_P_Set')
            print(f"  Exported load p_set (input)")
        
        # ==================== INPUT DATA ====================
        
        # Scenario input data
        for scenario_name, data in scenario_data.items():
            # Create DataFrame with all input time series for this scenario
            df_input = pd.DataFrame(index=n.snapshots)
            df_input['heat_demand_mw'] = data['heat_demand_mw']
            df_input['temp_supply'] = data['temp_supply']
            df_input['temp_return'] = data['temp_return']
            df_input['temp_ambient'] = data['temp_ambient']
            df_input['electricity_price'] = data['electricity_price']
            df_input['cop'] = data['cop']
            
            sheet_name = f'Input_{scenario_name.upper()}'
            df_input.to_excel(writer, sheet_name=sheet_name)
            print(f"  Exported input data for scenario {scenario_name}")
        
        # Configuration parameters
        config_data = [
            ['HEAT PUMP CONFIGURATION', ''],
            ['Fixed Capacity', f'{HP_FIXED_CAPACITY_MW} MW'],
            ['Type', HP_TYPE],
            ['Min Part Load', f'{HP_MIN_PART_LOAD*100}%'],
            ['Startup Cost', f'{HP_STARTUP_COST} EUR'],
            ['Min Uptime', f'{HP_MIN_UPTIME} hours'],
            ['Min Downtime', f'{HP_MIN_DOWNTIME} hours'],
            ['', ''],
            ['STORAGE CONFIGURATION', ''],
            ['Temperature Supply', f'{STORAGE_TEMP_SUPPLY_NOMINAL}°C'],
            ['Temperature Return', f'{STORAGE_TEMP_RETURN_NOMINAL}°C'],
            ['Standing Loss', f'{STORAGE_STANDING_LOSS*100}% per hour'],
            ['Conversion Factor', f'{STORAGE_M3_TO_MWH} MWh/m³'],
            ['Cost Coefficient', f'{STORAGE_COST_COEFF} EUR/m³'],
            ['Cost Exponent', STORAGE_COST_EXPONENT],
            ['Lifetime', f'{STORAGE_LIFETIME_YEARS} years'],
            ['Discount Rate', f'{STORAGE_DISCOUNT_RATE*100}%'],
            ['', ''],
            ['OPTIMIZATION SETTINGS', ''],
            ['MIP Gap', f'{MIP_GAP*100}%'],
            ['Time Limit', f'{TIME_LIMIT/60} minutes'],
            ['Initial Guess', f'{STORAGE_INITIAL_GUESS_M3_PER_MW} m³/MW'],
            ['Convergence Tolerance', f'{STORAGE_ITERATION_TOLERANCE*100}%'],
            ['Max Iterations', STORAGE_MAX_ITERATIONS],
            ['', ''],
            ['PRICING', ''],
            ['Use Spot Prices', 'Yes' if USE_SPOT_PRICES else 'No'],
            ['Grid Electricity Price (fallback)', f'{GRID_ELECTRICITY_PRICE} EUR/MWh'],
            ['Peak Boiler Cost', f'{PEAK_BOILER_COST} EUR/MWh'],
        ]
        
        df_config = pd.DataFrame(config_data, columns=['Parameter', 'Value'])
        df_config.to_excel(writer, sheet_name='Configuration', index=False)
        print(f"  Exported configuration parameters")
    
    print(f"\n{'='*70}")
    print(f"Excel export completed successfully!")
    print(f"File saved to: {EXCEL_OUTPUT_FILE}")
    print(f"{'='*70}")


# ==================== Main Execution ====================

def main():
    """Main execution function with iterative storage cost optimization.
    
    The non-linear storage cost function C = 5551.7 * V^(-0.35) EUR/m³ 
    cannot be directly used in PyPSA's linear optimization. Instead, we use
    an iterative approach:
    
    1. Start with initial guess for storage size
    2. Linearize cost function around that point
    3. Optimize with linearized cost
    4. Check if optimal size is close to linearization point
    5. If not converged, update linearization and repeat
    """
    
    print("\n" + "="*70)
    print("ITERATIVE STORAGE OPTIMIZATION")
    print("="*70)
    print(f"Non-linear cost function: C = {STORAGE_COST_COEFF:.1f} * V^({STORAGE_COST_EXPONENT})")
    print(f"Initial guess: {STORAGE_INITIAL_GUESS_M3_PER_MW:.0f} m³/MW")
    print(f"Convergence tolerance: {STORAGE_ITERATION_TOLERANCE*100:.1f}%")
    print(f"Maximum iterations: {STORAGE_MAX_ITERATIONS}")
    print("="*70)
    
    try:
        # Initial guess
        current_volume_m3 = STORAGE_INITIAL_GUESS_M3_PER_MW * HP_FIXED_CAPACITY_MW
        iteration = 0
        converged = False
        
        n = None
        scenario_data = None
        
        while iteration < STORAGE_MAX_ITERATIONS and not converged:
            iteration += 1
            
            print(f"\n{'='*70}")
            print(f"ITERATION {iteration}/{STORAGE_MAX_ITERATIONS}")
            print(f"{'='*70}")
            
            # Calculate linearized cost for current volume
            cost_info = calculate_storage_cost(current_volume_m3)
            current_cost_per_mwh = cost_info['cost_per_mwh']
            
            print(f"\nLinearization point:")
            print(f"  Volume: {current_volume_m3:.1f} m³ ({cost_info['volume_mwh']:.2f} MWh)")
            print(f"  Specific cost: {cost_info['specific_cost_per_m3']:.2f} EUR/m³")
            print(f"  Linearized cost: {current_cost_per_mwh:,.0f} EUR/MWh")
            
            # Build network with linearized cost
            n, scenario_data = build_stochastic_network(current_cost_per_mwh)
            
            # Optimize
            optimize_storage(n)
            
            # Get optimal size
            # All scenarios should have same storage size (first-stage decision)
            optimal_e_nom = n.stores.loc[(n.scenarios[0], 'thermal_storage'), 'e_nom_opt']
            optimal_volume_m3 = optimal_e_nom / STORAGE_M3_TO_MWH
            
            print(f"\nOptimal result:")
            print(f"  Volume: {optimal_volume_m3:.1f} m³ ({optimal_e_nom:.2f} MWh)")
            
            # Check convergence
            relative_change = abs(optimal_volume_m3 - current_volume_m3) / current_volume_m3
            print(f"  Relative change: {relative_change*100:.2f}%")
            
            if relative_change < STORAGE_ITERATION_TOLERANCE:
                converged = True
                print(f"\n[OK] CONVERGED! Change < {STORAGE_ITERATION_TOLERANCE*100:.1f}%")
            else:
                print(f"\n[INFO] Not converged, updating linearization point...")
                current_volume_m3 = optimal_volume_m3
        
        if not converged:
            print(f"\n[WARNING] Maximum iterations ({STORAGE_MAX_ITERATIONS}) reached without full convergence")
            print(f"[INFO] Continuing with last solution (change: {relative_change*100:.2f}%)")
        
        # Print final results
        print("\n" + "="*70)
        print("FINAL OPTIMIZATION RESULTS")
        print("="*70)
        
        print_results(n, scenario_data)
        
        # Create plots
        create_plots(n, scenario_data)
        
        # Create interactive Plotly visualizations
        create_interactive_plots(n, scenario_data)
        
        # Export all data to Excel
        export_to_excel(n, scenario_data)
        
        # Save network
        try:
            n.export_to_netcdf(OUTPUT_FILE)
            print(f"\nNetwork saved to: {OUTPUT_FILE}")
        except Exception as e:
            print(f"\nWarning: Could not save network to NetCDF: {e}")
            print("Results are still available in memory.")
        
        print("\n" + "="*70)
        print("OPTIMIZATION COMPLETED SUCCESSFULLY!")
        print(f"Converged in {iteration} iteration(s)")
        print("="*70)
        
        return n, scenario_data
        
    except Exception as e:
        print(f"\n{'='*70}")
        print("ERROR DURING OPTIMIZATION")
        print(f"{'='*70}")
        print(f"{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    network, data = main()
