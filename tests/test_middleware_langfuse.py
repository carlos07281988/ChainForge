# Copyright 2024 ChainForge Contributors
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
"""Tests for Langfuse middleware."""

import pytest


class TestLangfuseMiddleware:
    def test_import(self):
        from chainforge.middleware.langfuse import langfuse_tracing_middleware
        assert callable(langfuse_tracing_middleware)

    def test_middleware_requires_langfuse(self):
        # The middleware tries to import langfuse and raises ImportError if missing
        with pytest.raises(ImportError):
            from chainforge.middleware.langfuse import langfuse_tracing_middleware
            # Call it to trigger the import inside the function
            langfuse_tracing_middleware()
