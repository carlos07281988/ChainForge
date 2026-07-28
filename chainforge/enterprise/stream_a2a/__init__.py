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
"""Streaming Agent-to-Agent Protocol — WebSocket-based real-time agent chains with backpressure."""

from chainforge.enterprise.stream_a2a.protocol import StreamFrame, StreamMessage, StreamProtocol
from chainforge.enterprise.stream_a2a.agent import StreamingAgent
from chainforge.enterprise.stream_a2a.bridge import StreamBridge
from chainforge.enterprise.stream_a2a.backpressure import BackpressurePolicy

__all__ = [
    "StreamFrame",
    "StreamMessage",
    "StreamProtocol",
    "StreamingAgent",
    "StreamBridge",
    "BackpressurePolicy",
]
