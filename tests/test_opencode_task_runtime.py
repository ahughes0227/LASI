"""Tests for exact usage extraction from the OpenCode task adapter."""

import json

from services.runtime.opencode import _usage_receipt


def test_opencode_usage_receipt_uses_runtime_json_without_estimating() -> None:
    raw = json.dumps(
        {
            "type": "message.completed",
            "usage": {
                "tokens": {"input": 125, "output": 75, "cache_read": 25},
                "cost": 0.02,
            },
        }
    )

    receipt = _usage_receipt(raw, source_reference="response.jsonl")

    assert receipt is not None
    assert receipt.input_tokens == 125
    assert receipt.output_tokens == 75
    assert receipt.cached_input_tokens == 25
    assert receipt.total_tokens == 200
    assert receipt.billed_cost_usd == 0.02
    assert receipt.reporting_source == "opencode_runtime_json"


def test_opencode_usage_receipt_is_none_when_runtime_omits_usage() -> None:
    assert _usage_receipt('{"type":"text","text":"done"}', source_reference="x") is None
