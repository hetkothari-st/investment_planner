"""LLM role configuration — versioned in config/llm.v1.yaml."""

from decimal import Decimal
from functools import lru_cache

import yaml
from pydantic import BaseModel

from corpus.planner.assumptions import CONFIG_DIR


class RoleConfig(BaseModel):
    model: str
    temperature: Decimal
    max_tokens: int


class LlmConfig(BaseModel):
    version: str
    extraction: RoleConfig
    composition: RoleConfig
    falsifier_phrasing: RoleConfig


@lru_cache
def load_llm_config(version: str = "v1") -> LlmConfig:
    return LlmConfig.model_validate(
        yaml.safe_load((CONFIG_DIR / f"llm.{version}.yaml").read_text())
    )
