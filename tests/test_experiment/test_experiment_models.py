"""Tests for multi-variant Experiment model."""

import json
from datetime import datetime, timezone

from perpetual_predict.experiment.models import DEFAULT_MODULES, Experiment


class TestExperimentVariants:

    def test_create_with_variants_dict(self):
        exp = Experiment(
            experiment_id="exp_test1",
            name="test",
            variants={
                "macro": [*DEFAULT_MODULES, "macro"],
                "news": [*DEFAULT_MODULES, "news"],
            },
        )
        assert len(exp.variants) == 2
        assert "macro" in exp.variants
        assert "news" in exp.variants

    def test_to_dict_serializes_variants_as_json(self):
        exp = Experiment(
            experiment_id="exp_test2",
            name="test",
            variants={"macro": [*DEFAULT_MODULES, "macro"]},
        )
        d = exp.to_dict()
        parsed = json.loads(d["variant_modules"])
        assert isinstance(parsed, dict)
        assert "macro" in parsed

    def test_from_dict_with_new_dict_format(self):
        variants = {"macro": [*DEFAULT_MODULES, "macro"], "news": [*DEFAULT_MODULES, "news"]}
        data = {
            "experiment_id": "exp_test3",
            "name": "test",
            "control_modules": json.dumps(list(DEFAULT_MODULES)),
            "variant_modules": json.dumps(variants),
        }
        exp = Experiment.from_dict(data)
        assert isinstance(exp.variants, dict)
        assert len(exp.variants) == 2

    def test_from_dict_backward_compat_with_list(self):
        old_modules = [*DEFAULT_MODULES, "macro"]
        data = {
            "experiment_id": "exp_old",
            "name": "legacy",
            "control_modules": json.dumps(list(DEFAULT_MODULES)),
            "variant_modules": json.dumps(old_modules),
        }
        exp = Experiment.from_dict(data)
        assert isinstance(exp.variants, dict)
        assert "variant" in exp.variants
        assert exp.variants["variant"] == old_modules

    def test_roundtrip(self):
        original = Experiment(
            experiment_id="exp_rt",
            name="roundtrip",
            variants={
                "macro": [*DEFAULT_MODULES, "macro"],
                "news": [*DEFAULT_MODULES, "news"],
                "macro_news": [*DEFAULT_MODULES, "macro", "news"],
            },
            created_at=datetime(2026, 3, 28, tzinfo=timezone.utc),
        )
        restored = Experiment.from_dict(original.to_dict())
        assert restored.variants == original.variants
        assert len(restored.variants) == 3

    def test_variant_modules_property_compat(self):
        exp = Experiment(
            experiment_id="exp_compat",
            name="compat",
            variants={"macro": [*DEFAULT_MODULES, "macro"]},
        )
        assert exp.variant_modules == [*DEFAULT_MODULES, "macro"]

    def test_variant_modules_property_empty(self):
        exp = Experiment(
            experiment_id="exp_empty",
            name="empty",
            variants={},
        )
        assert exp.variant_modules == []
