"""example/17_consensus.py — ConsensusAgent verification."""
import sys, asyncio
from chainforge.testing import MockLLM, MockResponse
from chainforge.orchestration.consensus import ConsensusAgent, ConsensusStrategy, ModelVote, ConsensusResult
from chainforge.core.agent import Agent
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok: passed += 1; print(f"  \u2705 {n}")
    else: failed += 1; print(f"  \u274c {n}")

def test_consensus_create():
    llm = MockLLM(responses=[MockResponse(content="test")])
    c = ConsensusAgent(
        llm=llm,
        models={"m1": MockLLM(), "m2": MockLLM()},
        strategy=ConsensusStrategy.majority_vote,
    )
    check("c1: 2 models", len(c.models) == 2)
    check("c2: strategy", c.consensus_strategy == ConsensusStrategy.majority_vote)

def test_consensus_strategies():
    check("c3: majority_vote", ConsensusStrategy.majority_vote.value == "majority_vote")
    check("c4: confidence_weighted", ConsensusStrategy.confidence_weighted.value == "confidence_weighted")
    check("c5: detailed", ConsensusStrategy.detailed.value == "detailed")
    check("c6: fallback_chain", ConsensusStrategy.fallback_chain.value == "fallback_chain")

def test_model_vote():
    v = ModelVote(model_name="gpt4o", content="Paris", confidence=0.9)
    check("c7: model_name", v.model_name == "gpt4o")
    check("c8: content", v.content == "Paris")
    check("c9: confidence", v.confidence == 0.9)
    check("c10: tokens default 0", v.tokens_used == 0)

def test_consensus_result():
    r = ConsensusResult(final_answer="Yes", winner="model_a", confidence=0.8)
    check("c11: answer", r.final_answer == "Yes")
    check("c12: winner", r.winner == "model_a")
    check("c13: confidence", r.confidence == 0.8)

def test_majority_vote():
    llm = MockLLM(responses=[MockResponse(content="test")])
    c = ConsensusAgent(llm=llm, models={"a": MockLLM(), "b": MockLLM()})
    result = c._compute_consensus(
        [ModelVote(model_name="a", content="Yes"), ModelVote(model_name="b", content="Yes")],
        ConsensusStrategy.majority_vote,
    )
    check("c14: majority result", result.final_answer == "Yes")
    check("c15: winner set", result.winner is not None)

def test_fallback_chain():
    llm = MockLLM(responses=[MockResponse(content="test")])
    c = ConsensusAgent(llm=llm, models={"a": MockLLM(), "b": MockLLM()})
    result = c._compute_consensus(
        [ModelVote(model_name="a", content="First"), ModelVote(model_name="b", content="")],
        ConsensusStrategy.fallback_chain,
    )
    check("c16: fallback result", result.final_answer == "First")

def test_all_empty():
    llm = MockLLM(responses=[MockResponse(content="test")])
    c = ConsensusAgent(llm=llm, models={"a": MockLLM()})
    result = c._compute_consensus(
        [ModelVote(model_name="a", error="failed")],
        ConsensusStrategy.majority_vote,
    )
    check("c17: error handling", "No model" in result.final_answer)

async def main():
    print("=" * 58)
    print("  ConsensusAgent")
    print("=" * 58)
    test_consensus_create(); test_consensus_strategies()
    test_model_vote(); test_consensus_result()
    test_majority_vote(); test_fallback_chain()
    test_all_empty()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    asyncio.run(main())
