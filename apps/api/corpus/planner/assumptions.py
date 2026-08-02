"""Versioned assumption sets. Every plan records which version produced it."""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

# repo_root/config — three levels up from corpus/planner/
CONFIG_DIR = Path(__file__).resolve().parents[4] / "config"


class Assumptions(BaseModel):
    version: str
    inflation_expectation_pct: Decimal
    equity_real_return_pct: Decimal
    debt_return_pct: Decimal
    gold_real_return_pct: Decimal
    effective_ltcg_drag: Decimal
    effective_stcg_drag: Decimal
    assumed_equity_max_dd: Decimal
    buffer_liquid_vehicles: str
    confidence: str

    @property
    def equity_nominal_pct(self) -> Decimal:
        """Compound of real return and inflation."""
        real = 1 + self.equity_real_return_pct / 100
        infl = 1 + self.inflation_expectation_pct / 100
        return (real * infl - 1) * 100

    @property
    def debt_hurdle_pct(self) -> Decimal:
        """After-tax expected equity return: the honest prepay comparison.

        docs/03: hurdle = nominal equity expectation x (1 - ltcg drag).
        Prepaying a loan at r% is a guaranteed, tax-free r%; equity has to beat
        it after tax to justify not prepaying.
        """
        return self.equity_nominal_pct * (1 - self.effective_ltcg_drag)


@lru_cache
def load_assumptions(version: str = "v1") -> Assumptions:
    path = CONFIG_DIR / f"assumptions.{version}.yaml"
    return Assumptions.model_validate(yaml.safe_load(path.read_text()))
