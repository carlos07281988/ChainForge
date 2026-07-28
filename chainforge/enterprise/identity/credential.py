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
"""VerifiableCredential — signed, expiring claims issued by an agent identity."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from chainforge.enterprise.identity.identity import AgentIdentity


class VerifiableCredential(BaseModel):
    """A credential that binds *claims* to a *subject_id*, signed by an issuer.

    The signature covers ``subject_id || claims || issued_at || expires_at``
    and can be verified against the issuer's public key.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    issuer_id: str
    subject_id: str
    claims: dict = Field(default_factory=dict)
    issued_at: float = Field(default_factory=time.time)
    expires_at: float = 0.0
    signature: str = ""

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def issue(
        cls,
        issuer: AgentIdentity,
        subject_id: str,
        claims: dict,
        expires_in_days: int = 180,
    ) -> VerifiableCredential:
        """Issue a new credential signed by *issuer*."""
        now = time.time()
        inst = cls(
            issuer_id=issuer.agent_id,
            subject_id=subject_id,
            claims=claims,
            issued_at=now,
            expires_at=now + expires_in_days * 86400,
        )
        payload = inst._serialize_unsigned()
        inst.signature = issuer.sign(payload)
        return inst

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify(self, issuer_public_key: str) -> bool:
        """Check that the credential signature is valid and not expired."""
        from chainforge.enterprise.identity.identity import AgentIdentity

        # Check expiry.
        if time.time() > self.expires_at > 0:
            return False

        payload = self._serialize_unsigned()
        return AgentIdentity.verify(payload, self.signature, issuer_public_key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _serialize_unsigned(self) -> bytes:
        """Canonical payload that the signature covers."""
        raw = f"{self.subject_id}|{self.claims}|{self.issued_at}|{self.expires_at}"
        return raw.encode("utf-8")
