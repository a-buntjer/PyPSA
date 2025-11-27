import sys
sys.path.insert(0, r'c:\Users\A64620\Documents\pypsa_tryout\PyPSA')
sys.path.insert(0, r'c:\Users\A64620\Documents\pypsa_tryout\PyPSA\examples\neues_netz')
from run_neues_netz_optimization import *
import pandas as pd

# Setup und Optimierung
n = create_network()
n = n.optimize.optimize_with_rolling_horizon(
    solver_name='highs',
    multi_scenario=True
)

print('Network optimiert!')
print(f'Scenarios: {n.scenarios if hasattr(n, "scenarios") else "None"}')
print(f'Investment periods: {n.investment_periods if hasattr(n, "investment_periods") else "None"}')

# Teste carrier grouper
from pypsa.statistics.grouping import Groupers
groupers = Groupers()

# Teste manuell
static = n.c['Generator'].static
fall_back = pd.Series('', index=static.index)
carrier_series = static.get('carrier', fall_back).rename('carrier')

print(f'\ncarrier_series type: {type(carrier_series)}')
print(f'carrier_series index type: {type(carrier_series.index)}')
print(f'carrier_series shape: {carrier_series.shape}')
print(f'carrier_series index names: {carrier_series.index.names}')
print(f'carrier_series unique values: {carrier_series.unique()}')

# Nice names
nice_name = n.c.carriers.static.nice_name[lambda ds: ds != '']
print(f'\nnice_name type: {type(nice_name)}')
print(f'nice_name index type: {type(nice_name.index)}')
print(f'nice_name shape: {nice_name.shape}')
print(f'nice_name index: {nice_name.index.tolist()}')
print(f'nice_name values: {nice_name.values}')

nice_name_dict = nice_name.to_dict()
print(f'\nnice_name_dict: {nice_name_dict}')

# Teste replace mit dict
print('\n--- Testing replace with dict ---')
try:
    result = carrier_series.replace(nice_name_dict)
    print(f'replace() erfolgreich!')
    print(f'result unique values: {result.unique()}')
except Exception as e:
    print(f'replace() failed: {e}')
    import traceback
    traceback.print_exc()

# Teste replace mit Series (original)
print('\n--- Testing replace with Series (original) ---')
try:
    result2 = carrier_series.replace(nice_name)
    print(f'replace() with Series erfolgreich!')
    print(f'result unique values: {result2.unique()}')
except Exception as e:
    print(f'replace() with Series failed: {e}')
    import traceback
    traceback.print_exc()

# Teste map
print('\n--- Testing map ---')
try:
    result3 = carrier_series.map(lambda x: nice_name_dict.get(x, x))
    print(f'map() erfolgreich!')
    print(f'result unique values: {result3.unique()}')
except Exception as e:
    print(f'map() failed: {e}')
    import traceback
    traceback.print_exc()
