# Committable and Extendable Examples

This directory contains advanced PyPSA examples demonstrating the combination of unit commitment (committable components) with capacity expansion (extendable components).

## Examples

### 1. `committable_extendable_chp.py`

**Single-period CHP optimization with unit commitment and capacity expansion**

A district heating system with:
- Combined heat and power (CHP) plant (committable + extendable)
- Wind power (extendable)
- Gas storage and thermal buffer (extendable)
- Power-to-gas conversion
- Wholesale electricity market interaction

**Features:**
- Custom CHP coupling constraints (backpressure, iso-fuel lines)
- Unit commitment with start-up/shut-down costs
- 7-day optimization horizon (168 hourly snapshots)

**Run:**
```bash
python committable_extendable_chp.py
```

**Outputs:**
- `committable_extendable_chp.nc` - Optimized network
- `committable_extendable_chp_generator_dispatch.png` - Generation dispatch plot
- `committable_extendable_chp_heat_supply.png` - Heat supply plot

---

### 2. `stochastic_multihorizon_chp.py` ✨ NEW

**Multi-period pathway planning with stochastic optimization, unit commitment, and capacity expansion**

An advanced example combining three cutting-edge PyPSA v1.0 features:

**1. Stochastic Optimization**
- Three scenarios for uncertain parameters:
  - **Low cost**: Moderate gas prices (50 EUR/MWh), low demand growth
  - **Medium cost**: Average gas prices (80 EUR/MWh), medium demand growth
  - **High cost**: High gas prices (120 EUR/MWh), high demand growth
- Scenario probabilities: 30%, 40%, 30%

**2. Multi-Investment Period Planning**
- Four investment periods: 2025, 2030, 2035, 2040
- Progressive CO₂ emission constraints (800k → 150k tCO₂)
- Discounted objective function (5% discount rate)
- Component lifetimes and build years tracked

**3. Unit Commitment + Capacity Expansion**
- CHP plant with custom coupling constraints
- Gas peaker turbine (committable)
- Wind and solar (extendable, different availability years)
- Storage systems (gas and thermal)
- Power-to-gas (available from 2030)

**Key Features:**
- Technology learning curves (improving renewable efficiency over time)
- Scenario-dependent demand growth
- Progressive decarbonization pathway
- Investment timing optimization

**Run:**
```bash
python stochastic_multihorizon_chp.py
```

**Outputs:**
- `stochastic_multihorizon_chp.nc` - Optimized network with all scenarios
- `stochastic_multihorizon_chp_capacity_evolution.png` - Capacity investments over time

**Expected Runtime:** 
This is a large mixed-integer problem. With default settings (1-hour time limit, 1% MIP gap tolerance), expect 5-30 minutes depending on hardware.

---

## Technical Notes

### CHP Coupling Constraints

Both examples implement realistic CHP plant constraints:

1. **Nominal Capacity Ratio**: Heat output capacity is proportional to electric output capacity
   ```
   Q_nom = α * P_nom
   ```
   where α = 0.9 (heat-to-electric ratio)

2. **Backpressure Constraint**: Minimum heat-to-power ratio during operation
   ```
   c_m * Q ≤ P
   ```
   where c_m = 1.0 (backpressure slope)

3. **Iso-fuel Line**: Maximum combined output
   ```
   P + c_v * Q ≤ P_nom
   ```
   where c_v = 0.1 (marginal heat loss)

4. **Commitment Synchronization**: Electric and heat outputs have synchronized on/off status

### Stochastic Optimization Implementation

The stochastic example uses PyPSA's two-stage stochastic programming framework:

- **First stage (here-and-now decisions)**: Capacity investments are decided once and must work across all scenarios
- **Second stage (wait-and-see decisions)**: Operational dispatch adapts to the realized scenario

This models real-world investment under uncertainty: you build capacity now without knowing which scenario will occur.

### Multi-Investment Period Details

- **Investment periods**: [2025, 2030, 2035, 2040]
- **Snapshots per period**: 168 hours (one representative week)
- **Objective weighting**: Discounted at 5% annually
- **Component tracking**: 
  - `build_year`: When a component becomes available
  - `lifetime`: How long a component remains active
  - Components only operate if: `build_year ≤ current_period < build_year + lifetime`

## Requirements

- PyPSA >= 1.0
- NumPy
- Pandas
- Matplotlib
- A MIP solver (HiGHS is used by default)

## Extending These Examples

### Add More Scenarios
```python
SCENARIOS = ["low", "medium", "high", "extreme"]
SCENARIO_WEIGHTS = {"low": 0.25, "medium": 0.35, "high": 0.25, "extreme": 0.15}
```

### Add More Investment Periods
```python
INVESTMENT_PERIODS = [2025, 2028, 2031, 2034, 2037, 2040]
SNAPSHOTS_PER_PERIOD = 168  # Or increase to 8760 for full year
```

### Add Risk-Averse Optimization
```python
# After n.set_scenarios(...)
n.set_risk_preference(alpha=0.95, omega=0.3)
```
This adds CVaR (Conditional Value at Risk) penalty to the objective.

### Change Solver Settings
```python
solver_options = {
    "mip_rel_gap": 0.5,      # 0.5% optimality gap tolerance
    "time_limit": 7200,       # 2 hours
    "threads": 32,            # Use 32 CPU threads
    "parallel": "on",
}
```

## References

- PyPSA Documentation: https://pypsa.readthedocs.io/
- Stochastic Optimization Guide: https://docs.pypsa.org/en/latest/user-guide/optimization/stochastic.html
- Multi-Investment Periods: https://docs.pypsa.org/en/latest/user-guide/optimization/pathway-planning.html
- Unit Commitment: https://docs.pypsa.org/en/latest/user-guide/optimization/unit-commitment.html

## Testing

The exported network integrates with the tests under `test/test_committable_extendable.py` and can serve as a ready-to-use example for documentation.
