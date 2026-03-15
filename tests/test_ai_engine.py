"""Test AI decision engine"""
import pytest
from ai.decision_engine import AIDecisionEngine


@pytest.mark.asyncio
async def test_rule_based_decision():
    """Test rule-based fallback decision"""
    engine = AIDecisionEngine(
        lm_studio_url="http://localhost:1234/v1",
        model="test-model",
        api_key="test-key",
        enabled=False  # Force rule-based
    )
    
    # Good conditions - should deploy
    market_data = {
        "symbol": "BTC/USDT",
        "price": 67000,
        "rsi": 50,
        "atr": 500,
        "available_capital": 5000
    }
    
    decision = await engine.should_deploy_worker(market_data)
    assert decision["decision"] == "deploy"
    assert decision["confidence"] > 0
    assert decision["symbol"] == "BTC/USDT"


@pytest.mark.asyncio
async def test_rule_based_wait():
    """Test rule-based wait decision"""
    engine = AIDecisionEngine(
        lm_studio_url="http://localhost:1234/v1",
        model="test-model",
        api_key="test-key",
        enabled=False
    )
    
    # Bad conditions - should wait
    market_data = {
        "symbol": "BTC/USDT",
        "price": 67000,
        "rsi": 80,  # Overbought
        "atr": 500,
        "available_capital": 5000
    }
    
    decision = await engine.should_deploy_worker(market_data)
    assert decision["decision"] == "wait"


@pytest.mark.asyncio
async def test_insufficient_capital():
    """Test decision with insufficient capital"""
    engine = AIDecisionEngine(
        lm_studio_url="http://localhost:1234/v1",
        model="test-model",
        api_key="test-key",
        enabled=False
    )
    
    market_data = {
        "symbol": "BTC/USDT",
        "price": 67000,
        "rsi": 50,
        "atr": 500,
        "available_capital": 500  # Too low
    }
    
    decision = await engine.should_deploy_worker(market_data)
    assert decision["decision"] == "wait"


def test_prompt_building():
    """Test prompt construction"""
    engine = AIDecisionEngine(
        lm_studio_url="http://localhost:1234/v1",
        model="test-model",
        api_key="test-key",
        enabled=True
    )
    
    market_data = {
        "symbol": "BTC/USDT",
        "price": 67000,
        "rsi": 50,
        "atr": 500,
        "available_capital": 5000
    }
    
    prompt = engine._build_prompt(market_data)
    assert "BTC/USDT" in prompt
    assert "67000" in prompt
    assert "RSI" in prompt
