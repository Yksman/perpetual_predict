"""Data models for A/B testing experiments."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Available seed modules for context builder
SEED_MODULES = [
    "price_action",
    "candle_structure",
    "trend",
    "momentum",
    "volatility",
    "cvd",
    "liquidation",
    "sentiment",
    "market_structure",
    "divergences",
    "support_resistance",
    "recent_candles",
    "portfolio",
    "macro",
    "news",
]

# A/B 테스트 검증 중인 모듈 — baseline 예측에서 제외됨
# A/B 테스트 통과 후 이 set에서 제거하면 DEFAULT_MODULES에 자동 포함
EXPERIMENTAL_MODULES = {"macro", "news"}

# baseline 예측에 사용되는 모듈 (검증 완료된 모듈만)
DEFAULT_MODULES = [m for m in SEED_MODULES if m not in EXPERIMENTAL_MODULES]


@dataclass
class Experiment:
    """A/B test experiment definition."""

    experiment_id: str
    name: str
    description: str = ""
    status: str = "active"  # active | paused | completed
    control_modules: list[str] = field(default_factory=lambda: list(DEFAULT_MODULES))
    variant_modules: list[str] = field(default_factory=lambda: list(DEFAULT_MODULES))
    min_samples: int = 30
    significance_level: float = 0.05
    primary_metric: str = "net_return"  # accuracy | net_return | sharpe
    created_at: datetime | None = None
    completed_at: datetime | None = None
    winner: str | None = None  # 'control' | 'variant' | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "control_modules": json.dumps(self.control_modules),
            "variant_modules": json.dumps(self.variant_modules),
            "min_samples": self.min_samples,
            "significance_level": self.significance_level,
            "primary_metric": self.primary_metric,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "winner": self.winner,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Experiment:
        control_modules = data.get("control_modules", "[]")
        if isinstance(control_modules, str):
            control_modules = json.loads(control_modules)

        variant_modules = data.get("variant_modules", "[]")
        if isinstance(variant_modules, str):
            variant_modules = json.loads(variant_modules)

        return cls(
            experiment_id=data["experiment_id"],
            name=data["name"],
            description=data.get("description", ""),
            status=data.get("status", "active"),
            control_modules=control_modules,
            variant_modules=variant_modules,
            min_samples=data.get("min_samples", 30),
            significance_level=data.get("significance_level", 0.05),
            primary_metric=data.get("primary_metric", "net_return"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            winner=data.get("winner"),
        )


@dataclass
class ExperimentAccount:
    """Independent paper trading account for an experiment arm."""

    experiment_id: str
    arm: str  # 'control' | 'variant'
    initial_balance: float = 1000.0
    current_balance: float = 1000.0
    created_at: datetime | None = None


@dataclass
class ExperimentResult:
    """Statistical analysis result for an experiment."""

    experiment_id: str
    sample_size: int
    control_accuracy: float
    variant_accuracy: float
    control_return: float
    variant_return: float
    control_sharpe: float
    variant_sharpe: float
    p_value: float | None = None
    is_significant: bool = False
    recommended_winner: str | None = None  # 'control' | 'variant' | None
