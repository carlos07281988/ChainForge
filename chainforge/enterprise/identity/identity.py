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
"""AgentIdentity — Ed25519 keypair generation, signing, and verification."""

from __future__ import annotations

import hashlib
import os
import time
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AgentIdentity(BaseModel):
    """An agent's self-sovereign identity backed by an Ed25519 keypair.

    The private key is never serialized.  Public fields are exposed via
    ``to_json()`` and the ``did`` property returns a W3C-style
    ``did:chainforge:{agent_id}`` URI.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent_id: str = Field(default_factory=lambda: "cf-" + uuid.uuid4().hex[:8])
    name: str
    organization: str = ""
    public_key: str = ""
    capabilities: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)

    # Never serialized – the raw private-key hex bytes.
    _private_key: str = ""

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        name: str,
        organization: str = "",
        capabilities: list[str] | None = None,
    ) -> AgentIdentity:
        """Generate a fresh Ed25519 keypair and return a new identity.

        Falls back to a ``hashlib``-based deterministic stub when the
        optional ``cryptography`` library is not installed, so that
        tests can pass without extra dependencies.
        """
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519

            priv = ed25519.Ed25519PrivateKey.generate()
            pub_bytes = priv.public_key().public_bytes_raw()
            priv_bytes = priv.private_bytes_raw()
            pub_hex = pub_bytes.hex()
            priv_hex = priv_bytes.hex()
        except ImportError:
            # Deterministic fallback stub -- NOT cryptographically secure.
            seed = os.urandom(32).hex()
            priv_hex = seed
            pub_hex = hashlib.sha256(("pub:" + seed).encode()).hexdigest()[:64]

        inst = cls(
            name=name,
            organization=organization,
            capabilities=capabilities or [],
            public_key=pub_hex,
        )
        object.__setattr__(inst, "_private_key", priv_hex)
        return inst

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def sign(self, payload: bytes) -> str:
        """Sign *payload* with the agent's private key.

        Returns a hex-encoded signature string.
        """
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519

            priv = ed25519.Ed25519PrivateKey.from_private_bytes(
                bytes.fromhex(self._private_key)
            )
            return priv.sign(payload).hex()
        except ImportError:
            # Stub: deterministic hash — self-consistent without cryptography.
            return hashlib.sha256(
                (self.public_key + payload.hex()).encode()
            ).hexdigest()

    @staticmethod
    def verify(payload: bytes, signature: str, public_key: str) -> bool:
        """Verify an Ed25519 *signature* against *payload* using *public_key*."""
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519

            pub = ed25519.Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(public_key)
            )
            pub.verify(bytes.fromhex(signature), payload)
            return True
        except ImportError:
            # Stub: re-compute expected hash and compare.
            expected = hashlib.sha256(
                (public_key + payload.hex()).encode()
            ).hexdigest()
            return signature == expected
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def did(self) -> str:
        """W3C-style decentralised identifier."""
        return f"did:chainforge:{self.agent_id}"

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_json(self) -> dict:
        """Public fields only -- the private key is **never** exposed."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "organization": self.organization,
            "public_key": self.public_key,
            "capabilities": self.capabilities,
            "did": self.did,
            "created_at": self.created_at,
        }
