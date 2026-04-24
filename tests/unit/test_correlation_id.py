"""Tests for correlation ID middleware.

Covers:
- get_correlation_id returns empty by default
- correlation_id_var context management
"""
from __future__ import annotations

import pytest

from jobos.api.middleware import correlation_id_var, get_correlation_id


class TestCorrelationId:
    def test_get_correlation_id_returns_empty_by_default(self):
        # In a fresh context, the default should be empty string
        assert get_correlation_id() == ""

    def test_correlation_id_var_set_and_get(self):
        token = correlation_id_var.set("test-correlation-123")
        try:
            assert get_correlation_id() == "test-correlation-123"
        finally:
            correlation_id_var.reset(token)

        # After reset, should return to default
        assert get_correlation_id() == ""

    def test_correlation_id_var_multiple_values(self):
        token1 = correlation_id_var.set("first-id")
        try:
            assert get_correlation_id() == "first-id"

            token2 = correlation_id_var.set("second-id")
            try:
                assert get_correlation_id() == "second-id"
            finally:
                correlation_id_var.reset(token2)

            # After resetting inner, should be back to outer
            assert get_correlation_id() == "first-id"
        finally:
            correlation_id_var.reset(token1)

    def test_correlation_id_var_default_value(self):
        # The default for the ContextVar is ""
        assert correlation_id_var.get() == ""
