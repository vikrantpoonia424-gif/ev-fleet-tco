from dataclasses import replace

import pytest

from ev_tco import EnergyOption, Operations, Vehicle, breakeven_km_per_day, levelised_cost

OPS = Operations(km_per_day=100, discount_rate=0.0, downtime_cost_per_min=0)
CAR = Vehicle("x", "EV", price=100_000, resale_pct=0.0, life_years=1,
              energy_per_km=0.1, maintenance_per_km=1.0, insurance_per_year=0)
GRID = EnergyOption("grid", 10)


def test_zero_discount_matches_hand_calculation():
    km = 100 * 330
    c = levelised_cost(CAR, GRID, OPS)
    assert c["capital"] == pytest.approx(100_000 / km)
    assert c["energy"] == pytest.approx(1.0)          # 0.1 kWh * Rs 10
    assert c["maintenance"] == pytest.approx(1.0)
    assert c["total"] == pytest.approx(sum(v for k, v in c.items() if k != "total"))


def test_swap_skips_battery_replacement():
    car = replace(CAR, life_years=3, battery_cost=50_000, battery_year=2)
    own = levelised_cost(car, GRID, OPS)["capital"]
    swap = levelised_cost(car, replace(GRID, includes_battery=True), OPS)["capital"]
    assert own > swap


def test_breakeven_found_between_cheap_running_and_cheap_capex():
    ev = (replace(CAR, price=200_000, life_years=5), GRID)
    ice = (replace(CAR, price=100_000, life_years=5, energy_per_km=0.05), EnergyOption("fuel", 100))
    km = breakeven_km_per_day(ev, ice, OPS)
    assert km is not None
    o = replace(OPS, km_per_day=km)
    assert levelised_cost(*ev, o)["total"] == pytest.approx(levelised_cost(*ice, o)["total"])
