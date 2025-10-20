"""Committable and extendable CHP example network.

This example mirrors the ``power-to-gas-boiler-chp`` notebook but
adds unit-commitment and capacity-expansion features for the combined
heat and power (CHP) plant. The network covers a full week (168 hourly
snapshots) of a small district heat system with wind, power-to-gas,
thermal storage, and interactions with a wholesale electricity market.

Run this module directly to build, optimise, and export the scenario
as a NetCDF file for reuse in tests or documentation::

    python committable_extendable_chp.py

The export will be written to ``committable_extendable_chp.nc`` in the
same directory.
"""

from __future__ import annotations

import pathlib
import sys

# Allow running the script without installing PyPSA by adding the repository root
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # type: ignore[import-error]
import pandas as pd  # type: ignore[import-error]

import pypsa

DAYS = 7
HOURS_PER_DAY = 24
SNAPSHOTS = pd.date_range("2020-01-01", periods=DAYS * HOURS_PER_DAY, freq="h")
RESULT_FILE = pathlib.Path(__file__).with_suffix(".nc")
PLOT_FILE = RESULT_FILE.with_name(f"{RESULT_FILE.stem}_generator_dispatch.png")
HEAT_PLOT_FILE = RESULT_FILE.with_name(f"{RESULT_FILE.stem}_heat_supply.png")

CARRIER_COLORS: dict[str, str] = {
    "electric": "#1f77b4",
    "gas": "#ff7f0e",
    "heat": "#d62728",
    "wind": "#17becf",
    "market": "#9467bd",
}

# CHP parameterisation (same notation as in the notebook).
NOMINAL_HEAT_TO_ELECTRIC_RATIO = 0.9
BACKPRESSURE_SLOPE = 1.0
MARGINAL_HEAT_LOSS = 0.1


def build_profiles(
    index: pd.Index,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Create exogenous time-series profiles."""

    # Moderate daily variation for electric and heat demand (MW).
    base_electric_load = np.array(
        [
            9.5,
            9.1,
            8.7,
            8.3,
            8.0,
            8.2,
            9.0,
            10.5,
            11.8,
            12.5,
            13.2,
            13.5,
            13.0,
            12.6,
            12.0,
            11.5,
            11.0,
            10.8,
            10.5,
            10.2,
            9.8,
            9.6,
            9.4,
            9.2,
        ]
    )

    base_heat_load = np.array(
        [
            14.0,
            13.5,
            13.0,
            12.5,
            12.0,
            12.5,
            13.5,
            15.0,
            16.5,
            17.5,
            18.0,
            18.5,
            18.0,
            17.2,
            16.8,
            16.0,
            15.5,
            15.0,
            14.5,
            14.0,
            13.8,
            13.5,
            13.2,
            13.0,
        ]
    )

    base_wind_profile = np.array(
        [
            0.05,
            0.08,
            0.10,
            0.12,
            0.18,
            0.25,
            0.35,
            0.45,
            0.60,
            0.72,
            0.80,
            0.78,
            0.70,
            0.62,
            0.55,
            0.48,
            0.40,
            0.32,
            0.24,
            0.18,
            0.12,
            0.08,
            0.05,
            0.03,
        ]
    )

    base_market_price = np.array(
        [
            78.0,
            74.0,
            70.0,
            68.0,
            65.0,
            64.0,
            66.0,
            72.0,
            85.0,
            92.0,
            100.0,
            105.0,
            110.0,
            108.0,
            102.0,
            95.0,
            40.0,
            30.0,
            10.0,
            0.0,
            -20.0,
            0.0,
            20.0,
            74.0,
        ]
    )

    electric_load = np.tile(base_electric_load, DAYS)
    heat_load = np.tile(base_heat_load, DAYS)
    wind_profile = np.tile(base_wind_profile, DAYS)
    market_price = np.tile(base_market_price, DAYS)

    return (
        pd.Series(electric_load, index=index),
        pd.Series(heat_load, index=index),
        pd.Series(wind_profile, index=index),
        pd.Series(market_price, index=index),
    )


def _ensure_carrier_colors(n: pypsa.Network) -> None:
    if "color" not in n.carriers.columns:
        n.carriers["color"] = np.nan
    for carrier, color in CARRIER_COLORS.items():
        if carrier in n.carriers.index:
            n.carriers.loc[carrier, "color"] = color


def build_network() -> pypsa.Network:
    """Construct the committable + extendable CHP example network."""

    n = pypsa.Network()
    n.set_snapshots(list(SNAPSHOTS))

    electric_load, heat_load, wind_profile, market_price = build_profiles(
        SNAPSHOTS
    )

    # Primary carriers and buses.
    n.add("Carrier", "electric")
    n.add("Carrier", "gas", co2_emissions=0.20)
    n.add("Carrier", "heat")
    n.add("Carrier", "wind")
    n.add("Carrier", "market")

    _ensure_carrier_colors(n)

    n.add("Bus", "bus_electric", carrier="electric")
    n.add("Bus", "bus_gas", carrier="gas")
    n.add("Bus", "bus_heat", carrier="heat")

    # Demand
    n.add("Load", "electric_demand", bus="bus_electric", p_set=electric_load)
    n.add("Load", "heat_demand", bus="bus_heat", p_set=heat_load)

    # Power supply via extendable wind.
    n.add(
        "Generator",
        "wind_turbine",
        bus="bus_electric",
        carrier="wind",
        p_nom_extendable=True,
        capital_cost=900,
        marginal_cost=0.0,
        p_max_pu=wind_profile,
        p_nom_max=50,
    )

    # Power-to-gas conversion (electrolyser/methanation).
    n.add(
        "Link",
        "p2g",
        bus0="bus_electric",
        bus1="bus_gas",
        efficiency=0.58,
        capital_cost=600,
        p_nom_extendable=True,
        p_nom_max=40,
    )

    n.add(
        "Generator",
        "gas_supply",
        bus="bus_gas",
        carrier="gas",
        p_nom_extendable=True,
        capital_cost=0,  # Keine CAPEX für Gas-Lieferung
        marginal_cost=25.0,  # Gaspreis: 25 EUR/MWh
        p_nom_max=1000,  # Unbegrenzt verfügbar
    )
    
    # Gas-fired peak generator for reliability (non-CHP, committable only).
    n.add(
        "Generator",
        "gas_peaker",
        bus="bus_electric",
        carrier="gas",
        p_nom=20,
        marginal_cost=150,
        committable=True,
        p_min_pu=0.0,
        start_up_cost=250,
        shut_down_cost=150,
    )

    n.add(
        "Generator",
        "grid_trade",
        bus="bus_electric",
        carrier="market",
        p_nom_extendable=True,
        p_nom_min=0.0,
        p_nom_max=400.0,
        p_min_pu=-1.0,
        p_max_pu=1.0,
        capital_cost=0.0,
        marginal_cost=market_price,
    )

    # Storage for gas and heat.
    n.add(
        "Store",
        "gas_storage",
        bus="bus_gas",
        e_nom_extendable=True,
        e_initial=60,
        e_min_pu=0.0,
        standing_loss=0.0,
        capital_cost=30,
    )
    n.add(
        "Store",
        "thermal_buffer",
        bus="bus_heat",
        carrier="heat",
        e_nom_extendable=True,
        e_initial=20,
        e_min_pu=0.0,
        capital_cost=20,
        standing_loss=0.01,
    )

    # Combined heat and power plant split into electric + heat links.
    n.add(
        "Link",
        "chp_generator",
        bus0="bus_gas",
        bus1="bus_electric",
        efficiency=0.468,
        committable=True,
        start_up_cost=3,
        shut_down_cost=1,
        capital_cost=520,
        p_nom_extendable=True,
        p_nom_max=80,
        p_min_pu=0.35,
        marginal_cost=45,
    )

    n.add(
        "Link",
        "chp_boiler",
        bus0="bus_gas",
        bus1="bus_heat",
        carrier="heat",
        efficiency=1.0,  # placeholder, will be overwritten to satisfy iso-fuel lines
        committable=True,
        start_up_cost=3.5,
        shut_down_cost=1,
        capital_cost=380,
        p_nom_extendable=True,
        p_nom_min=0.0,
        p_nom_max=80,
        p_min_pu=0.20,
        marginal_cost=45,
    )

    # Optional auxiliary boiler for flexibility (non-committable).
    n.add(
        "Link",
        "aux_heat_boiler",
        bus0="bus_gas",
        bus1="bus_heat",
        carrier="heat",
        efficiency=0.92,
        capital_cost=180,
        p_nom_extendable=True,
        p_nom_max=60,
        marginal_cost=60,
    )

    # Emission cap encourages renewable usage.
    # n.add(
    #     "GlobalConstraint",
    #     "co2_limit",
    #     type="primary_energy",
    #     sense="<=",
    #     constant=5000,
    #     carrier_attribute="co2_emissions",
    # )
    # n.c.global_constraints.static.loc["co2_limit", "bus"] = "bus_gas"

    # Align CHP link efficiencies so that iso-fuel lines hold.
    n.links.at["chp_boiler", "efficiency"] = (
        n.links.at["chp_generator", "efficiency"] / MARGINAL_HEAT_LOSS
    )

    return n


def add_chp_coupling_constraints(n: pypsa.Network) -> None:
    """Add CHP coupling constraints to the PyPSA optimisation model."""

    model = n.optimize.create_model()

    link_p = model.variables["Link-p"]
    link_p_nom = model.variables["Link-p_nom"]
    link_status = (
        model.variables["Link-status"]
        if "Link-status" in model.variables
        else None
    )

    generator_eff = float(n.links.at["chp_generator", "efficiency"])
    boiler_eff = float(n.links.at["chp_boiler", "efficiency"])

    generator_p = link_p.sel(name="chp_generator")
    boiler_p = link_p.sel(name="chp_boiler")
    generator_p_nom = link_p_nom.sel(name="chp_generator")
    boiler_p_nom = link_p_nom.sel(name="chp_boiler")

    electric_output = generator_eff * generator_p
    heat_output = boiler_eff * boiler_p

    # Nominal power proportionality using output capacities.
    model.add_constraints(
        generator_eff * NOMINAL_HEAT_TO_ELECTRIC_RATIO * generator_p_nom
        - boiler_eff * boiler_p_nom
        == 0,
        name="chp-heat-power-output-proportionality",
    )

    # Backpressure constraint: c_m * p_heat <= p_electric (scaled to outputs).
    backpressure_coefficient = BACKPRESSURE_SLOPE * generator_eff / boiler_eff
    model.add_constraints(
        heat_output * backpressure_coefficient - electric_output <= 0,
        name="chp-backpressure",
    )

    # Iso-fuel line: p_electric + c_v * p_heat <= p_nom_electric.
    model.add_constraints(
        electric_output
        + heat_output * MARGINAL_HEAT_LOSS
        - generator_eff * generator_p_nom
        <= 0,
        name="chp-top-iso-fuel-line",
    )

    if link_status is not None:
        # Synchronise commitment state of both CHP links.
        model.add_constraints(
            link_status.loc[:, "chp_generator"]
            - link_status.loc[:, "chp_boiler"]
            == 0,
            name="chp-status-synchronisation",
        )

    n.optimize.solve_model(
        solver_options={"mip_rel_gap": 0.8, "threads": 16, "parallel": "on"}
    )


def build_and_optimize() -> pypsa.Network:
    """Create the network, add CHP coupling, and solve the optimisation."""

    n = build_network()
    add_chp_coupling_constraints(n)
    return n


def save_generator_dispatch_plot(
    n: pypsa.Network, output_path: pathlib.Path | None = None
) -> pathlib.Path:
    """Create and store a stacked area chart of generator dispatch."""

    output_path = output_path or PLOT_FILE

    _ensure_carrier_colors(n)

    dispatch = n.statistics.supply(
        components="Generator",
        groupby_time=False,
        groupby=False,
        at_port=True,
        nice_names=False,
        drop_zero=False,
    )
    if dispatch.empty:
        raise RuntimeError("No generator dispatch available to plot.")

    dispatch = dispatch.T.clip(lower=0.0)
    dispatch.index.name = "snapshot"

    carriers = n.generators.carrier.reindex(dispatch.columns)
    palette = [
        n.carriers.color.get(carrier, "#808080")
        for carrier in carriers.fillna("-")
    ]

    import matplotlib

    if matplotlib.get_backend().lower() != "agg":
        try:
            matplotlib.use("Agg", force=True)
        except Exception:
            pass

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 5))
    dispatch.plot.area(ax=ax, color=palette, linewidth=0)
    ax.set_ylabel("Power output [MW]")
    ax.set_xlabel("Snapshot")
    ax.set_title("Generator dispatch")
    ax.legend(loc="upper right", title="Generator")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    return output_path


def _carrier_for_component(n: pypsa.Network, component: str, name: str) -> str:
    table = getattr(n, f"{component.lower()}s", None)
    if table is None:
        return ""
    if "carrier" in table.columns and name in table.index:
        return str(table.at[name, "carrier"])
    return ""


def save_heat_supply_plot(
    n: pypsa.Network, output_path: pathlib.Path | None = None
) -> pathlib.Path:
    """Create and store a stacked area chart of heat supply."""

    output_path = output_path or HEAT_PLOT_FILE

    _ensure_carrier_colors(n)

    supply = n.statistics.supply(
        components=["Link", "Store"],
        groupby_time=False,
        groupby=False,
        at_port=True,
        nice_names=False,
        drop_zero=False,
        bus_carrier="heat",
    )
    if supply.empty:
        raise RuntimeError("No heat supply available to plot.")

    supply = supply.T.clip(lower=0.0)
    supply.index.name = "snapshot"
    supply.columns = [name for _, name in supply.columns]

    palette = []
    for name in supply.columns:
        carrier = _carrier_for_component(n, "link", name)
        if not carrier:
            carrier = _carrier_for_component(n, "store", name)
        palette.append(n.carriers.color.get(carrier, "#808080"))

    import matplotlib

    if matplotlib.get_backend().lower() != "agg":
        try:
            matplotlib.use("Agg", force=True)
        except Exception:
            pass

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 5))
    supply.plot.area(ax=ax, color=palette, linewidth=0)
    ax.set_ylabel("Heat supply [MW]")
    ax.set_xlabel("Snapshot")
    ax.set_title("Heat supply")
    ax.legend(loc="upper right", title="Asset")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    return output_path


# def main() -> None:
#     n = build_and_optimize()
#     n.export_to_netcdf(str(RESULT_FILE))
#     print(f"Exported solved network to {RESULT_FILE}")
#     plot_path = save_generator_dispatch_plot(n)
#     print(f"Saved generator dispatch plot to {plot_path}")


if __name__ == "__main__":
    n = build_and_optimize()

    n.export_to_netcdf(str(RESULT_FILE))
    print(f"Exported solved network to {RESULT_FILE}")

    generator_plot = save_generator_dispatch_plot(n)
    heat_plot = save_heat_supply_plot(n)
    print(f"Saved generator dispatch plot to {generator_plot}")
    print(f"Saved heat supply plot to {heat_plot}")

    gens = n.generators
    gens_t = n.generators_t

    stores = n.stores
    stores_t = n.stores_t

    links = n.links
    links_t = n.links_t

    loads = n.loads
    loads_t = n.loads_t
