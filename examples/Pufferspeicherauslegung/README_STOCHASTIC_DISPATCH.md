# Stochastic Dispatch-Only Optimization Examples

This directory contains examples demonstrating **pure stochastic dispatch optimization** with PyPSA, where all capacities are fixed and only operational decisions are optimized under forecast uncertainty.

## Overview

Traditional PyPSA stochastic optimization (two-stage) combines:
- First-stage: Investment decisions (capacities)
- Second-stage: Dispatch decisions (operation)

The new `dispatch_only=True` parameter enables:
- **No investment decisions** (all capacities are fixed)
- **Only dispatch optimization** under uncertainty
- **Shorter planning horizons** (hours to days vs. years)

## Use Cases

### Short-term Operational Planning
- Day-ahead electricity market with price forecast uncertainty
- Heat demand forecasting with weather uncertainty
- Generation scheduling with renewable forecast uncertainty
- Demand response optimization

### Example Scenarios
1. **Electricity Price Uncertainty**: Low (70 €/MWh), Medium (80 €/MWh), High (100 €/MWh)
2. **Heat Demand Uncertainty**: High demand (+20%), Normal, Low demand (-15%)
3. **Combined**: Price and demand scenarios with joint probabilities

## Available Examples

### 1. `stochastic_dispatch_simple.py` (Recommended)

**✅ Working example** - Simplified heat network without storage

**Components:**
- Fixed heat pump (0.6 MW)
- Fixed backup gas boiler (0.3 MW)
- No storage (avoids PyPSA v1.0 compatibility issues)

**Scenarios:**
- Low price + high demand (30%)
- Medium price + medium demand (50%)
- High price + low demand (20%)

**Run:**
```bash
cd examples/Pufferspeicherauslegung
python stochastic_dispatch_simple.py
```

**Expected Output:**
```
Expected total cost (weighted): 926.91 EUR

Scenario: low_price_high_demand
  Heat pump electricity: 13.53 MWh
  Heat pump heat output: 40.32 MWh
  Heat pump avg COP: 2.98
  Total cost: 947.21 EUR
```

### 2. `stochastic_dispatch_heat_network.py` (Advanced)

**⚠️ Experimental** - Includes thermal storage (may have compatibility issues)

**Additional Components:**
- Thermal storage (2.0 MWh)
- Time-varying COP
- Unit commitment (optional)

**Known Issues:**
PyPSA v1.0 has undocumented compatibility issues between:
- `Store` component and stochastic scenarios (MultiIndex bug)
- `StorageUnit` with scenarios in certain configurations
- Unit commitment (`committable=True`) and scenarios

**Status:** May require PyPSA framework fixes for full functionality

## Implementation Details

### Adding dispatch_only to Your Code

```python
import pypsa
import pandas as pd

# Create network
n = pypsa.Network()

# Add components with FIXED capacities
n.add("Generator", "gen1", bus="bus1", 
      p_nom=100,              # Fixed capacity
      p_nom_extendable=False) # Not extendable

# Define scenarios
scenarios = pd.DataFrame(
    {"weight": [0.3, 0.5, 0.2]},
    index=pd.Index(["low", "medium", "high"], name="scenario")
)
n.set_scenarios(scenarios)

# Apply scenario-specific parameters
for scenario in scenarios.index:
    n.generators.loc[(scenario, "gen1"), "marginal_cost"] = ...
    n.loads_t.p_set.loc[:, (scenario, "load1")] = ...

# Optimize with dispatch_only
status, condition = n.optimize(dispatch_only=True)
```

### Key Requirements

1. **All capacities must be fixed:**
   ```python
   p_nom_extendable=False
   s_nom_extendable=False
   e_nom_extendable=False
   ```

2. **Scenarios must be defined:**
   ```python
   n.set_scenarios(scenarios_df)
   ```

3. **Component setup order:**
   - Add all components first
   - Then call `n.set_scenarios()`
   - Then modify scenario-specific parameters

### Validation

The `dispatch_only=True` mode automatically:
- ✅ Checks all nominal capacities are defined
- ✅ Converts `*_extendable` flags to False
- ✅ Validates scenarios are set
- ✅ Logs informational message

```python
INFO:pypsa.optimization.optimize:Dispatch-only mode: Fixing all extendable capacities
```

## Mathematical Formulation

### Standard Two-Stage Problem
```
min_x E[c1·x + E_ω[c2(ω)·y(ω)]]
s.t. x ∈ X                        (investment constraints)
     y(ω) ∈ Y(x,ω)  ∀ω            (dispatch constraints)
```

### Dispatch-Only Problem (x fixed)
```
min_y E_ω[c2(ω)·y(ω)]
s.t. y(ω) ∈ Y(x̄,ω)  ∀ω            (dispatch constraints)
     x̄ = fixed capacities
```

## Results Interpretation

### Expected Cost
The objective is the **probability-weighted average** cost across all scenarios:

```
E[Cost] = Σ p(ω) · Cost(ω)
```

Example:
- Scenario 1 (30%): 947.21 EUR
- Scenario 2 (50%): 902.10 EUR
- Scenario 3 (20%): 958.48 EUR
- **Expected: 926.91 EUR**

### Per-Scenario Results
Each scenario has its own dispatch solution optimized for that scenario's parameters while respecting the shared fixed capacities.

## Testing

Comprehensive test suite in `test_dispatch_only.py`:

```bash
pytest test_dispatch_only.py -v
```

**Tests:**
- Basic functionality
- Capacity validation
- Scenario requirement
- Extendable flag conversion
- Multi-component networks

All tests passing ✅

## Comparison: Dispatch-Only vs. Investment

| Aspect | Investment Optimization | Dispatch-Only |
|--------|------------------------|---------------|
| Time horizon | Years to decades | Hours to days |
| Decisions | Capacities + Dispatch | Dispatch only |
| Uncertainty | Long-term (demand growth) | Short-term (forecasts) |
| Capacities | Optimized variables | Fixed parameters |
| Use case | Planning | Operations |
| `p_nom_extendable` | True | False |

## Troubleshooting

### "All nominal capacities must be defined"
Ensure all components have `p_nom`, `s_nom`, or `e_nom` set:
```python
n.add("Generator", "gen", bus="bus", p_nom=100)  # Must specify!
```

### "Scenarios must be set"
Call `set_scenarios()` before optimization:
```python
n.set_scenarios(scenarios_df)
```

### Storage Component Issues
PyPSA v1.0 has compatibility issues with `Store` and `StorageUnit` in stochastic mode. Consider:
- Using simplified examples without storage
- Using only `StorageUnit` (not `Store`)
- Avoiding unit commitment with storage + scenarios

### MultiIndex Errors
Ensure components are added **before** calling `set_scenarios()`:
```python
# Correct order
n.add("Generator", ...)
n.add("Load", ...)
n.set_scenarios(...)

# Wrong order (causes MultiIndex errors)
n.set_scenarios(...)
n.add("Generator", ...)  # Don't do this!
```

## Further Development

Potential extensions:
1. **Risk-averse optimization**: Add CVaR constraints
2. **Robust optimization**: Min-max formulation
3. **Rolling horizon**: Update scenarios each time step
4. **Scenario generation**: Monte Carlo or moment matching
5. **Bid optimization**: Generate price-quantity curves

## References

- PyPSA Documentation: https://pypsa.readthedocs.io/
- Two-Stage Stochastic Programming: Birge & Louveaux (2011)
- PyPSA Stochastic Examples: `examples/scigrid-de/` in PyPSA repository

## Support

For issues with:
- `dispatch_only` implementation: See `pypsa/optimization/optimize.py`
- PyPSA stochastic framework: PyPSA GitHub issues
- Examples: This directory's README files

---

**Created:** 2025-01-XX  
**PyPSA Version:** v1.0.1+  
**Status:** dispatch_only feature functional, storage examples experimental
