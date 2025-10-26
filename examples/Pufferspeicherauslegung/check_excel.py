import pandas as pd

xl = pd.ExcelFile('pypsa_results_export.xlsx')

print('\nExported Excel Sheets:')
print('='*50)
for i, sheet in enumerate(xl.sheet_names, 1):
    print(f'{i:2d}. {sheet}')

print(f'\nTotal: {len(xl.sheet_names)} sheets')
