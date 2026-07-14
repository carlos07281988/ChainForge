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
"""Tests for AWS Bedrock provider."""

import pytest
from chainforge.providers.bedrock import BedrockProvider


class TestBedrockProvider:
    def test_creation(self):
        p = BedrockProvider()
        assert "claude" in p.model
        assert p.max_tokens == 4096

    def test_custom_model(self):
        p = BedrockProvider(model="anthropic.claude-3-haiku-20240307-v1:0", region="us-west-2")
        assert "haiku" in p.model
        assert p.region == "us-west-2"

    def test_model_string_default(self):
        p = BedrockProvider()
        assert p.model == "anthropic.claude-sonnet-4-20250514-v1:0"

    @pytest.mark.asyncio
    async def test_requires_boto3(self):
        """Tests that a meaningful error is raised when boto3 is missing."""
        p = BedrockProvider()
        try:
            import boto3  # noqa: F401
            # boto3 installed — skip the test
            pytest.skip("boto3 is installed")
        except ImportError:
            with pytest.raises(ImportError, match="boto3"):
                await p.generate([])
