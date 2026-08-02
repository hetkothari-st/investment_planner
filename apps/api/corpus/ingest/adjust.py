"""Corporate-action back-adjustment of close prices.

Pure functions; the caller persists. Only SPLIT and BONUS change the share count
and therefore the price series. DIVIDEND/RIGHTS/MERGER are recorded in
corporate_actions but do not adjust the close here — dividends are handled as
cash in return computations, and rights/mergers need case-by-case terms that
cannot be reduced to a ratio. That choice is deliberate: a wrong automatic
adjustment is worse than an unadjusted price with the action on record.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

QUANT = Decimal("0.0001")  # NUMERIC(18,4)


@dataclass(frozen=True)
class ActionRatio:
    ex_date: date
    action_type: str  # 'SPLIT' | 'BONUS'
    ratio_from: Decimal
    ratio_to: Decimal


@dataclass(frozen=True)
class Bar:
    trade_date: date
    close: Decimal


def action_factor(action: ActionRatio) -> Decimal:
    """Price multiplier applied to all closes strictly before ex_date.

    SPLIT: face value ratio_from -> ratio_to (e.g. 10 -> 2 means 1 share becomes 5),
           so pre-split prices are multiplied by ratio_to/ratio_from.
    BONUS: ratio_from bonus shares for every ratio_to held (A:B),
           so pre-bonus prices are multiplied by ratio_to/(ratio_from + ratio_to).
    """
    if action.ratio_from is None or action.ratio_to is None:
        raise ValueError(f"{action.action_type} on {action.ex_date} missing ratio")
    if action.ratio_from <= 0 or action.ratio_to <= 0:
        raise ValueError(f"{action.action_type} on {action.ex_date} non-positive ratio")
    if action.action_type == "SPLIT":
        return action.ratio_to / action.ratio_from
    if action.action_type == "BONUS":
        return action.ratio_to / (action.ratio_from + action.ratio_to)
    raise ValueError(f"{action.action_type} does not adjust price")


def adjusted_closes(bars: list[Bar], actions: list[ActionRatio]) -> dict[date, Decimal]:
    """Map trade_date -> adj_close, back-adjusting through every SPLIT/BONUS.

    A bar on or after the last ex_date keeps its raw close. A bar before an
    ex_date is multiplied by the cumulative factor of every action after it.
    """
    price_actions = sorted(
        (a for a in actions if a.action_type in ("SPLIT", "BONUS")),
        key=lambda a: a.ex_date,
    )
    out: dict[date, Decimal] = {}
    for bar in bars:
        factor = Decimal(1)
        for action in price_actions:
            if bar.trade_date < action.ex_date:
                factor *= action_factor(action)
        out[bar.trade_date] = (bar.close * factor).quantize(QUANT, rounding=ROUND_HALF_UP)
    return out
