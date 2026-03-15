"""AI Decision Engine using LM Studio"""
import aiohttp
from typing import Dict, Any, Optional
import json


class AIDecisionEngine:
    """AI-driven worker dispatch decisions using LM Studio"""
    
    def __init__(self, lm_studio_url: str, model: str, api_key: str = None, enabled: bool = True):
        self.lm_studio_url = lm_studio_url
        self.model = model
        self.api_key = api_key or "lm-studio"  # Default key for local LM Studio
        self.enabled = enabled
        self.last_decision_time = 0
        self.decision_cooldown = 300  # 5 minutes
    
    async def should_deploy_worker(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Decide whether to deploy a worker"""
        
        # Fallback to rule-based if LM Studio disabled
        if not self.enabled:
            return self._rule_based_decision(market_data)
        
        try:
            # Build prompt
            prompt = self._build_prompt(market_data)
            
            # Call LM Studio API
            headers = {
                "Content-Type": "application/json"
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.lm_studio_url}/chat/completions",
                    headers=headers,
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "You are a crypto trading advisor. Analyze market data and decide whether to deploy a grid trading worker. Respond in JSON format with: {\"decision\": \"deploy\" or \"wait\", \"confidence\": 0.0-1.0, \"reasoning\": \"explanation\"}"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 200
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        raise Exception(f"LM Studio API error: {resp.status}")
                    
                    result = await resp.json()
                    content = result["choices"][0]["message"]["content"]
                    
                    # Parse JSON response
                    decision = json.loads(content)
                    return {
                        "decision": decision.get("decision", "wait"),
                        "confidence": decision.get("confidence", 0.5),
                        "reasoning": decision.get("reasoning", ""),
                        "strategy": "infinite_grid",
                        "symbol": market_data["symbol"]
                    }
        
        except Exception as e:
            print(f"[AI] LM Studio error: {e}, falling back to rule-based")
            return self._rule_based_decision(market_data)
    
    def _build_prompt(self, market_data: Dict[str, Any]) -> str:
        """Build prompt for LM Studio"""
        rsi = market_data.get('rsi')
        atr = market_data.get('atr')
        change_24h = market_data.get('change_24h')
        volume_24h = market_data.get('volume_24h')

        return f"""Analyze this market data and decide if it's a good time to deploy a grid trading worker:

Symbol: {market_data['symbol']}
Current Price: ${market_data['price']:.2f}
24h Change: {f'{change_24h:.2f}%' if change_24h is not None else 'N/A'}
RSI: {f'{rsi:.1f}' if rsi is not None else 'N/A'}
ATR: {f'${atr:.2f}' if atr is not None else 'N/A'}
Trend: {market_data.get('trend', 'unknown')}
Volume 24h: {f'${volume_24h:,.0f}' if volume_24h is not None else 'N/A'}

Available Capital: ${market_data.get('available_capital', 0):.2f}

Should we deploy a grid trading worker now? Consider:
- Is the market in a good range for grid trading?
- Is volatility (ATR) reasonable?
- Is RSI not in extreme zones?
- Do we have sufficient capital?

Respond in JSON format."""
    
    def _rule_based_decision(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback rule-based decision"""
        price = market_data.get("price", 0) or 0
        rsi = market_data.get("rsi")
        atr = market_data.get("atr")
        available_capital = market_data.get("available_capital", 0) or 0

        # Simple rules — if indicators are missing, default to "wait"
        rsi_ok = (30 < rsi < 70) if rsi is not None else False
        atr_ok = (atr > 0) if atr is not None else False

        should_deploy = (
            available_capital >= 1000 and
            rsi_ok and
            atr_ok and
            price > 0
        )
        
        return {
            "decision": "deploy" if should_deploy else "wait",
            "confidence": 0.6 if should_deploy else 0.4,
            "reasoning": "Rule-based: Market conditions acceptable" if should_deploy else "Rule-based: Waiting for better conditions",
            "strategy": "infinite_grid",
            "symbol": market_data["symbol"]
        }
