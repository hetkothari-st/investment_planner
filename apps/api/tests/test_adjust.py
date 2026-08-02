"""Golden-value tests for corporate-action back-adjustment.

Hand-checked fixture: a 10->2 split multiplies pre-split prices by 0.2;
a 1:1 bonus halves them; both together multiply by 0.1.
"""

from datetime import date
from decimal import Decimal

import pytest

from corpus.ingest.adjust import ActionRatio, Bar, action_factor, adjusted_closes

D = Decimal


def test_split_factor():
    a = ActionRatio(date(2024, 6, 3), "SPLIT", D("10"), D("2"))
    assert action_factor(a) == D("0.2")


def test_bonus_factor():
    a = ActionRatio(date(2024, 6, 3), "BONUS", D("1"), D("1"))
    assert action_factor(a) == D("0.5")


def test_dividend_never_adjusts():
    a = ActionRatio(date(2024, 6, 3), "DIVIDEND", D("1"), D("1"))
    with pytest.raises(ValueError):
        action_factor(a)


def test_adjusted_closes_golden():
    bars = [
        Bar(date(2024, 5, 30), D("1000.00")),  # before both actions
        Bar(date(2024, 6, 3), D("205.00")),    # on split ex-date: post-split price
        Bar(date(2024, 7, 1), D("210.00")),    # between split and bonus
        Bar(date(2024, 8, 2), D("104.00")),    # on bonus ex-date
    ]
    actions = [
        ActionRatio(date(2024, 6, 3), "SPLIT", D("10"), D("2")),
        ActionRatio(date(2024, 8, 2), "BONUS", D("1"), D("1")),
    ]
    adj = adjusted_closes(bars, actions)
    # 1000 * 0.2 (split) * 0.5 (bonus) = 100
    assert adj[date(2024, 5, 30)] == D("100.0000")
    # 205 * 0.5 (bonus only) = 102.5
    assert adj[date(2024, 6, 3)] == D("102.5000")
    assert adj[date(2024, 7, 1)] == D("105.0000")
    # after the last action: raw close
    assert adj[date(2024, 8, 2)] == D("104.0000")


def test_no_actions_is_identity():
    bars = [Bar(date(2024, 1, 1), D("512.3456"))]
    assert adjusted_closes(bars, [])[date(2024, 1, 1)] == D("512.3456")


def test_rounding_half_up_to_paise_precision():
    bars = [Bar(date(2024, 1, 1), D("100.0001"))]
    actions = [ActionRatio(date(2024, 2, 1), "SPLIT", D("10"), D("5"))]
    # 100.0001 * 0.5 = 50.00005 -> 50.0001 (ROUND_HALF_UP at 4 dp)
    assert adjusted_closes(bars, actions)[date(2024, 1, 1)] == D("50.0001")
