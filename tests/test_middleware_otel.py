"""Tests for OpenTelemetry middleware."""

import pytest


class TestOTelMiddleware:
    def test_import(self):
        from chainforge.middleware.opentelemetry import otel_tracing_middleware, otel_tracing_middleware_light
        assert callable(otel_tracing_middleware)
        assert callable(otel_tracing_middleware_light)

    def test_middleware_creation(self):
        from chainforge.middleware.opentelemetry import otel_tracing_middleware_light
        mw = otel_tracing_middleware_light(tracer_name="test")
        assert callable(mw)
