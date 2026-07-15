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
"""Model routing — classify task complexity and route to optimal model.

Usage:
    from chainforge.routing import SmartRouter
    from chainforge.providers import OpenAIProvider, DeepSeekProvider

    router = SmartRouter()
    router.register("fast", OpenAIProvider(model="gpt-4o-mini"))
    router.register("reasoning", DeepSeekProvider(model="deepseek-reasoner"))
    router.register("default", OpenAIProvider(model="gpt-4o"))

    agent = router.create_cost_optimized_agent(tools=[...])
    async for event in await agent.run("What is 2+2?"):
        ...
"""

from chainforge.routing.router import SmartRouter, RouteConfig, RoutingStrategy

__all__ = ["SmartRouter", "RouteConfig", "RoutingStrategy"]
