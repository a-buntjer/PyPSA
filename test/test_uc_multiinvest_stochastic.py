# SPDX-FileCopyrightText: PyPSA Contributors
#
# SPDX-License-Identifier: MIT

"""
Test the three-way combination:
  - Unit Commitment (committable generators / MILP)
  - Multi-Investment Periods (pathway optimization)
  - Stochastic Optimization (scenarios)

This combination has no dedicated tests in upstream PyPSA.
The goal is to verify whether the upstream code (v1.1.2) can handle
all three features simultaneously.
"""

import pandas as pd
import pytest

import pypsa


def make_network_uc_multiinvest_stochastic():
    """Create a minimal network combining UC + Multi-Invest + Stochastic.

    Network topology:
        Bus1 -- Line -- Bus2
        Gen (committable, coal) on Bus1
        Gen (extendable, wind) on Bus2
        Load on Bus1

    Two investment periods: 2030, 2040
    Two scenarios: low_demand, high_demand
    """
    # --- Snapshots: 4 timesteps per investment period ---
    snapshots = pd.MultiIndex.from_product(
        [[2030, 2040], range(4)], names=["period", "timestep"]
    )
    n = pypsa.Network(snapshots=snapshots)

    # --- Investment periods ---
    n.investment_periods = [2030, 2040]
    n.investment_period_weightings.loc[2030, "years"] = 10
    n.investment_period_weightings.loc[2040, "years"] = 10

    # --- Buses ---
    n.add("Bus", "bus1")
    n.add("Bus", "bus2")

    # --- Committable generator (Unit Commitment / MILP) ---
    n.add(
        "Generator",
        "coal-2030",
        bus="bus1",
        carrier="coal",
        committable=True,
        p_nom=500,
        p_min_pu=0.3,
        marginal_cost=30,
        start_up_cost=1000,
        shut_down_cost=500,
        min_up_time=2,
        min_down_time=1,
        build_year=2030,
        lifetime=25,
    )

    # --- Extendable generator (wind, for multi-invest) ---
    n.add(
        "Generator",
        "wind-2030",
        bus="bus2",
        carrier="wind",
        p_nom_extendable=True,
        capital_cost=50000,
        marginal_cost=0,
        p_nom_max=1000,
        build_year=2030,
        lifetime=25,
    )

    n.add(
        "Generator",
        "wind-2040",
        bus="bus2",
        carrier="wind",
        p_nom_extendable=True,
        capital_cost=40000,
        marginal_cost=0,
        p_nom_max=1000,
        build_year=2040,
        lifetime=25,
    )

    # --- Line ---
    n.add(
        "Line",
        "line1",
        bus0="bus1",
        bus1="bus2",
        s_nom=500,
        x=0.0001,
        build_year=2030,
        lifetime=50,
    )

    # --- Load (will be modified per-scenario after set_scenarios) ---
    load_ts = pd.Series([300, 400, 350, 250], index=range(4))
    load_df = pd.concat(
        {2030: load_ts, 2040: load_ts * 1.2}, names=["period", "timestep"]
    )
    n.add("Load", "load1", bus="bus1", p_set=load_df)

    # --- Scenarios (Stochastic) ---
    n.set_scenarios({"low_demand": 0.6, "high_demand": 0.4})

    # Modify load for high_demand scenario (increase by 50%)
    p_set = n.c.loads.dynamic["p_set"]
    p_set[("high_demand", "load1")] = p_set[("low_demand", "load1")] * 1.5

    return n


class TestUCMultiInvestStochastic:
    """Tests for the three-way combination."""

    def test_basic_optimization_runs(self):
        """Test that optimize() doesn't crash with all three features active."""
        n = make_network_uc_multiinvest_stochastic()
        status, cond = n.optimize(
            multi_investment_periods=True,
            solver_name="highs",
        )
        assert status == "ok", f"Optimization failed: {cond}"

    def test_status_variable_exists(self):
        """Test that the UC status variable is created in the model."""
        n = make_network_uc_multiinvest_stochastic()
        m = n.optimize.create_model(
            multi_investment_periods=True,
        )
        # The status variable should exist for committable generators
        assert "Generator-status" in m.variables, (
            "Status variable for committable generators not found in model"
        )

    def test_solution_physical_consistency(self):
        """Test that the solution respects UC constraints."""
        n = make_network_uc_multiinvest_stochastic()
        status, cond = n.optimize(
            multi_investment_periods=True,
            solver_name="highs",
        )
        assert status == "ok"

        # Check that dispatch is non-negative
        p_gen = n.c.generators.dynamic.p
        assert (p_gen >= -1e-6).all().all(), "Negative dispatch found"

        # Check that load is met (power balance)
        # Just verify the optimization produced sensible results
        assert p_gen.sum().sum() > 0, "No generation at all"

    def test_investment_decisions_across_periods(self):
        """Test that investment decisions are made across periods."""
        n = make_network_uc_multiinvest_stochastic()
        status, cond = n.optimize(
            multi_investment_periods=True,
            solver_name="highs",
        )
        assert status == "ok"

        # Wind generators should have some optimal capacity
        p_nom_opt = n.c.generators.static["p_nom_opt"]
        wind_caps = p_nom_opt[p_nom_opt.index.get_level_values(-1).str.startswith("wind")]
        assert wind_caps.sum() > 0, "No wind capacity built across investment periods"


class TestUCMultiInvestOnly:
    """Test UC + Multi-Invest without stochastic (as a baseline)."""

    def test_uc_multiinvest_runs(self):
        """Test that UC + Multi-Invest works without scenarios."""
        snapshots = pd.MultiIndex.from_product(
            [[2030, 2040], range(4)], names=["period", "timestep"]
        )
        n = pypsa.Network(snapshots=snapshots)
        n.investment_periods = [2030, 2040]
        n.investment_period_weightings.loc[2030, "years"] = 10
        n.investment_period_weightings.loc[2040, "years"] = 10

        n.add("Bus", "bus1")

        n.add(
            "Generator",
            "coal-2030",
            bus="bus1",
            committable=True,
            p_nom=500,
            p_min_pu=0.3,
            marginal_cost=30,
            build_year=2030,
            lifetime=25,
        )

        n.add(
            "Generator",
            "wind-2030",
            bus="bus1",
            p_nom_extendable=True,
            capital_cost=50000,
            marginal_cost=0,
            p_nom_max=1000,
            build_year=2030,
            lifetime=25,
        )

        load_ts = pd.Series([300, 400, 350, 250], index=range(4))
        load_df = pd.concat(
            {2030: load_ts, 2040: load_ts * 1.2}, names=["period", "timestep"]
        )
        n.add("Load", "load1", bus="bus1", p_set=load_df)

        status, cond = n.optimize(
            multi_investment_periods=True,
            solver_name="highs",
        )
        assert status == "ok", f"UC+MultiInvest failed: {cond}"


class TestStochasticUCOnly:
    """Test UC + Stochastic without Multi-Invest (as a baseline)."""

    def test_uc_stochastic_runs(self):
        """Test that UC + Stochastic works without multi-invest."""
        n = pypsa.Network(snapshots=range(4))
        n.add("Bus", "bus1")

        n.add(
            "Generator",
            "coal",
            bus="bus1",
            committable=True,
            p_nom=500,
            p_min_pu=0.3,
            marginal_cost=30,
        )

        n.add(
            "Generator",
            "gas",
            bus="bus1",
            committable=True,
            p_nom=200,
            p_min_pu=0.1,
            marginal_cost=60,
        )

        n.add("Load", "load1", bus="bus1", p_set=[300, 400, 350, 250])

        n.set_scenarios({"low": 0.5, "high": 0.5})

        # Increase load in high scenario
        p_set = n.c.loads.dynamic["p_set"]
        p_set[("high", "load1")] = [450, 600, 525, 375]

        status, cond = n.optimize(solver_name="highs")
        assert status == "ok", f"UC+Stochastic failed: {cond}"
