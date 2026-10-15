"""Token controls are opt-in data; byte limits remain independent safeguards."""

import pytest
from pydantic import ValidationError

from portable_ai_harness.core.config import ProjectConfig


def test_token_budgets_default_to_disabled_without_disabling_byte_limits():
    limits = ProjectConfig(project="example").context_limits
    assert limits.input_token_budget is None
    assert limits.output_token_budget is None
    assert limits.max_file_bytes == 32000
    assert limits.max_total_bytes == 128000


@pytest.mark.parametrize(
    "input_budget,output_budget",
    [
        (None, None),
        (4000, None),
        (None, 1000),
        (4000, 1000),
    ],
)
def test_each_token_budget_is_independently_optional(input_budget, output_budget):
    config = ProjectConfig(
        project="example",
        context_limits={
            "input_token_budget": input_budget,
            "output_token_budget": output_budget,
        },
    )
    restored = ProjectConfig.model_validate_json(config.model_dump_json())
    assert restored.context_limits.input_token_budget == input_budget
    assert restored.context_limits.output_token_budget == output_budget


@pytest.mark.parametrize(
    "field,value",
    [
        ("input_token_budget", 0),
        ("output_token_budget", -1),
        ("input_token_budget", "4000"),
    ],
)
def test_enabled_token_budgets_require_positive_integers(field, value):
    with pytest.raises(ValidationError):
        ProjectConfig(project="example", context_limits={field: value})
