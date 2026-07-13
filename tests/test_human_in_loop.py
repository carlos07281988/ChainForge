"""Tests for human-in-the-loop module."""

import pytest

from chainforge.core.human_in_loop import (
    HumanInTheLoop,
    ApprovalRequest,
    ApprovalDecision,
    HumanInput,
)


class TestApprovalRequest:
    def test_request_creation(self):
        req = ApprovalRequest(tool_name="search", arguments={"q": "test"}, request_id="r1")
        assert req.tool_name == "search"
        assert req.arguments == {"q": "test"}

    def test_request_with_context(self):
        req = ApprovalRequest(tool_name="delete", arguments={}, context="Deleting user data")
        assert req.context == "Deleting user data"


class TestHumanInput:
    def test_approved_default(self):
        inp = HumanInput()
        assert inp.decision == ApprovalDecision.approved
        assert inp.feedback is None

    def test_rejected(self):
        inp = HumanInput(decision=ApprovalDecision.rejected, feedback="Not safe")
        assert inp.feedback == "Not safe"

    def test_modified(self):
        inp = HumanInput(
            decision=ApprovalDecision.modified,
            modified_arguments={"limit": 5},
        )
        assert inp.modified_arguments == {"limit": 5}


class TestHumanInTheLoop:
    def test_init(self):
        hil = HumanInTheLoop()
        assert hil._pending_approvals == {}

    @pytest.mark.asyncio
    async def test_custom_callback(self):
        hil = HumanInTheLoop()

        async def mock_callback(req):
            return HumanInput(decision=ApprovalDecision.approved)

        hil.set_input_callback(mock_callback)
        result = await hil.request_approval(
            ApprovalRequest(tool_name="test", arguments={})
        )
        assert result.decision == ApprovalDecision.approved

    @pytest.mark.asyncio
    async def test_rejection_callback(self):
        hil = HumanInTheLoop()

        async def mock_callback(req):
            return HumanInput(decision=ApprovalDecision.rejected, feedback="Not now")

        hil.set_input_callback(mock_callback)
        result = await hil.request_approval(ApprovalRequest(tool_name="test", arguments={}))
        assert result.decision == ApprovalDecision.rejected
        assert result.feedback == "Not now"

    def test_middleware_creation(self):
        hil = HumanInTheLoop()
        mw = hil.middleware()
        assert callable(mw)
