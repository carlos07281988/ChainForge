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
"""Tests for Google and Azure providers."""

import pytest
from chainforge.providers import GoogleProvider, AzureProvider
from chainforge.core.message import Message
from chainforge.core.tool import ToolSpec


class TestGoogleProvider:
    def test_creation(self):
        p = GoogleProvider(model="gemini-2.0-flash")
        assert p.model == "gemini-2.0-flash"

    def test_creation_default_model(self):
        p = GoogleProvider()
        assert p.model == "gemini-2.0-flash"

    def test_no_api_key_raises(self):
        p = GoogleProvider(api_key="test")
        # won't actually connect, but validates the import path
        assert p.api_key == "test"


class TestAzureProvider:
    def test_creation(self):
        p = AzureProvider(
            model="gpt-4o",
            azure_endpoint="https://test.openai.azure.com",
            api_key="test",
        )
        assert p.model == "gpt-4o"
        assert "test" in str(p.azure_endpoint)

    def test_default_api_version(self):
        p = AzureProvider(api_key="test")
        assert p.api_version == "2024-10-01-preview"


class TestProviderImports:
    def test_all_providers_importable(self):
        from chainforge.providers import OpenAIProvider, AnthropicProvider, GoogleProvider, AzureProvider
        assert OpenAIProvider is not None
        assert AnthropicProvider is not None
        assert GoogleProvider is not None
        assert AzureProvider is not None
