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
