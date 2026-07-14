# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
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
