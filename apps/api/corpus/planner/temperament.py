"""Temperament, elicited by scenario — never a slider.

The scenario is concrete: "Your X becomes Y over four months. What do you do?"
where X is scaled to the user's actual corpus and Y is X after the assumed
equity max drawdown. Each answer maps to the drawdown fraction the user has
demonstrated they would sit through. People lie in percent; rupees are harder
to lie about.
"""

from decimal import Decimal
from enum import StrEnum


class TemperamentChoice(StrEnum):
    SELL_EVERYTHING = "SELL_EVERYTHING"  # would capitulate at the bottom
    SELL_SOME = "SELL_SOME"              # would de-risk under pressure
    HOLD = "HOLD"                        # sits through the assumed drawdown
    BUY_MORE = "BUY_MORE"                # treats the drawdown as opportunity


# Fraction of corpus the user can watch evaporate without acting destructively.
TOLERATED_DD_FRACTION: dict[TemperamentChoice, Decimal] = {
    TemperamentChoice.SELL_EVERYTHING: Decimal("0.10"),
    TemperamentChoice.SELL_SOME: Decimal("0.20"),
    TemperamentChoice.HOLD: Decimal("0.32"),
    TemperamentChoice.BUY_MORE: Decimal("0.45"),
}


def max_tolerable_drawdown_inr(choice: TemperamentChoice, corpus: Decimal) -> Decimal:
    """Convert the scenario answer into rupees against the user's own corpus."""
    return (TOLERATED_DD_FRACTION[choice] * corpus).quantize(Decimal("0.01"))


def scenario_amounts(corpus: Decimal, assumed_dd: Decimal) -> tuple[Decimal, Decimal]:
    """(before, after) figures for the scenario prompt, scaled to the corpus.
    Falls back to the canonical 5,00,000 example when the corpus is tiny."""
    before = corpus if corpus >= Decimal("100000") else Decimal("500000")
    after = (before * (1 - assumed_dd)).quantize(Decimal("1"))
    return before.quantize(Decimal("1")), after
