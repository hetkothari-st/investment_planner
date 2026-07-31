"""Golden values for the cost model and XIRR."""

from datetime import date
from decimal import Decimal

from corpus.sim.analytics import xirr
from corpus.sim.costs import buy_costs, sell_costs, slipped_price

D = Decimal


def test_buy_costs_golden():
    c = buy_costs(D("500.25"), 100)
    assert c.stt == D("50.025")
    assert c.exchange == D("1.48574250")
    assert c.sebi == D("0.050025")
    assert c.stamp == D("7.50375")
    assert c.gst == D("0.2764381500")
    assert c.total == D("59.34")


def test_sell_costs_golden():
    c = sell_costs(D("529.735"), 100)
    assert c.stt == D("52.9735")
    assert c.dp_charge == D("15.93")
    assert c.stamp == 0
    assert c.total == D("70.82")


def test_slippage_floor():
    assert slipped_price(D("500"), "BUY") == D("500.2500")
    assert slipped_price(D("500"), "SELL") == D("499.7500")


def test_xirr_one_year_ten_percent():
    flows = [(date(2025, 1, 1), D("-100000")), (date(2026, 1, 1), D("110000"))]
    r = xirr(flows)
    assert r is not None and abs(r - 0.10) < 1e-6


def test_xirr_staggered_flows():
    # two ins, one out; sanity: rate between the naive bounds
    flows = [
        (date(2025, 1, 1), D("-50000")),
        (date(2025, 7, 1), D("-50000")),
        (date(2026, 1, 1), D("108000")),
    ]
    r = xirr(flows)
    assert r is not None and 0.05 < r < 0.20


def test_xirr_degenerate():
    assert xirr([(date(2025, 1, 1), D("-100"))]) is None
    assert xirr([(date(2025, 1, 1), D("100")), (date(2026, 1, 1), D("100"))]) is None
