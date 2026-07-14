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
"""Tests for the pipeline module."""

import pytest

from chainforge.core.pipeline import Pipeline


class TestPipeline:
    @pytest.mark.asyncio
    async def test_pipeline_run(self):
        pipe = Pipeline(
            name="test",
            steps=[
                lambda x: x.upper(),
                lambda x: f"[{x}]",
            ],
        )
        result = await pipe.run("hello")
        assert result == "[HELLO]"

    @pytest.mark.asyncio
    async def test_pipeline_single_step(self):
        pipe = Pipeline(name="identity", steps=[lambda x: x])
        result = await pipe.run(42)
        assert result == 42

    @pytest.mark.asyncio
    async def test_pipeline_composition(self):
        add_one = Pipeline(name="add", steps=[lambda x: x + 1])
        double = Pipeline(name="double", steps=[lambda x: x * 2])
        combined = add_one >> double
        assert combined.name == "add >> double"
        result = await combined.run(5)
        assert result == 12  # (5+1)*2 = 12

    @pytest.mark.asyncio
    async def test_pipeline_stream(self):
        pipe = Pipeline(name="test", steps=[lambda x: x.upper()])
        stream = pipe.stream("hello")
        events = await stream.collect()
        assert len(events) == 3  # status, text, done
        assert events[0].type.value == "status"
        assert events[1].type.value == "text"

    def test_pipeline_sync_call(self):
        pipe = Pipeline(name="test", steps=[lambda x: x * 2])
        result = pipe(21)
        assert result == 42

    def test_empty_pipeline(self):
        pipe = Pipeline(name="empty", steps=[])
        import asyncio
        result = asyncio.run(pipe.run("hello"))
        assert result == "hello"

    def test_pipeline_operator_with_function(self):
        pipe = Pipeline(name="base", steps=[lambda x: x + 1])
        result = pipe >> (lambda x: x * 2)
        assert result.name == "base >> <lambda>"
        import asyncio
        assert asyncio.run(result.run(5)) == 12
