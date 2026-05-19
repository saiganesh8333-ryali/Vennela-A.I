"""LLM Cost & Token Tracking - Monitor API usage and costs."""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class CostRecord:
    """Record of a single LLM call cost."""
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float
    latency_ms: int
    success: bool
    timestamp: float
    query_preview: str = ""


@dataclass
class CostSummary:
    """Summary of costs over period."""
    period_name: str
    start_time: float
    end_time: float
    total_calls: int
    successful_calls: int
    failed_calls: int
    total_tokens: int
    total_cost: float
    avg_latency_ms: float
    provider_breakdown: Dict[str, Any] = field(default_factory=dict)
    model_breakdown: Dict[str, Any] = field(default_factory=dict)


class CostTracker:
    """Track and monitor LLM API costs and usage."""
    
    # Pricing per 1M tokens (approximate)
    PRICING = {
        "gemini-3.5-flash": {
            "input": 0.075,
            "output": 0.3
        },
        "gemini-2.0-flash-exp": {
            "input": 0.1,
            "output": 0.4
        },
        "gemini-2.0-flash-thinking-exp-01-21": {
            "input": 0.6,
            "output": 2.4
        },
        "llama-3.3-70b-versatile": {
            "input": 0.59,
            "output": 0.79
        },
        "openai/gpt-4o-mini": {
            "input": 0.15,
            "output": 0.6
        }
    }
    
    def __init__(self, max_records: int = 10000):
        """
        Initialize cost tracker.
        
        Args:
            max_records: Maximum records to keep in memory
        """
        logger.info("Initializing Cost Tracker")
        self.records: List[CostRecord] = []
        self.max_records = max_records
        self.session_start = time.time()
    
    def record_call(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        success: bool = True,
        query_preview: str = ""
    ) -> CostRecord:
        """
        Record a single LLM API call.
        
        Args:
            provider: Provider name (gemini, groq, openrouter)
            model: Model name
            input_tokens: Input tokens used
            output_tokens: Output tokens used
            latency_ms: Response latency in milliseconds
            success: Whether call was successful
            query_preview: Preview of query (first 100 chars)
            
        Returns:
            CostRecord instance
        """
        total_tokens = input_tokens + output_tokens
        cost = self._calculate_cost(model, input_tokens, output_tokens)
        
        record = CostRecord(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=cost,
            latency_ms=latency_ms,
            success=success,
            timestamp=time.time(),
            query_preview=query_preview[:100] if query_preview else ""
        )
        
        self.records.append(record)
        
        # Limit records in memory
        if len(self.records) > self.max_records:
            self.records = self.records[-self.max_records:]
        
        logger.debug(
            f"Recorded: {provider}/{model} - "
            f"{total_tokens} tokens, ${cost:.4f}"
        )
        
        return record
    
    def _calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Calculate cost for tokens."""
        pricing = self.PRICING.get(model)
        
        if not pricing:
            # Default fallback pricing
            return (input_tokens + output_tokens) * 0.0001 / 1_000_000
        
        input_cost = (input_tokens / 1_000_000) * pricing.get("input", 0.1)
        output_cost = (output_tokens / 1_000_000) * pricing.get("output", 0.4)
        
        return input_cost + output_cost
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary for current session."""
        if not self.records:
            return {
                "session_duration_seconds": int(time.time() - self.session_start),
                "total_calls": 0,
                "total_cost": 0.0
            }
        
        successful = [r for r in self.records if r.success]
        
        return {
            "session_duration_seconds": int(time.time() - self.session_start),
            "total_calls": len(self.records),
            "successful_calls": len(successful),
            "failed_calls": len(self.records) - len(successful),
            "total_tokens": sum(r.total_tokens for r in self.records),
            "total_cost": sum(r.cost for r in self.records),
            "avg_latency_ms": (
                sum(r.latency_ms for r in successful) / len(successful)
                if successful else 0
            ),
            "records_kept": len(self.records),
            "max_records": self.max_records
        }
    
    def get_provider_summary(self) -> Dict[str, Any]:
        """Get breakdown by provider."""
        breakdown = {}
        
        for record in self.records:
            provider = record.provider
            
            if provider not in breakdown:
                breakdown[provider] = {
                    "calls": 0,
                    "successful": 0,
                    "tokens": 0,
                    "cost": 0.0,
                    "avg_latency_ms": 0.0,
                    "total_latency": 0
                }
            
            breakdown[provider]["calls"] += 1
            if record.success:
                breakdown[provider]["successful"] += 1
            breakdown[provider]["tokens"] += record.total_tokens
            breakdown[provider]["cost"] += record.cost
            breakdown[provider]["total_latency"] += record.latency_ms
        
        # Calculate averages
        for provider in breakdown:
            calls = breakdown[provider]["calls"]
            breakdown[provider]["avg_latency_ms"] = (
                breakdown[provider]["total_latency"] / calls
            )
            del breakdown[provider]["total_latency"]
        
        return breakdown
    
    def get_model_summary(self) -> Dict[str, Any]:
        """Get breakdown by model."""
        breakdown = {}
        
        for record in self.records:
            model = record.model
            
            if model not in breakdown:
                breakdown[model] = {
                    "calls": 0,
                    "tokens": 0,
                    "cost": 0.0,
                    "avg_latency_ms": 0.0,
                    "total_latency": 0,
                    "success_rate": 0.0
                }
            
            breakdown[model]["calls"] += 1
            breakdown[model]["tokens"] += record.total_tokens
            breakdown[model]["cost"] += record.cost
            breakdown[model]["total_latency"] += record.latency_ms
        
        # Calculate metrics
        for model in breakdown:
            calls = breakdown[model]["calls"]
            successful = sum(
                1 for r in self.records
                if r.model == model and r.success
            )
            breakdown[model]["avg_latency_ms"] = (
                breakdown[model]["total_latency"] / calls
            )
            breakdown[model]["success_rate"] = successful / calls
            del breakdown[model]["total_latency"]
        
        return breakdown
    
    def get_time_period_summary(
        self,
        minutes: int = 60
    ) -> Dict[str, Any]:
        """Get summary for last N minutes."""
        cutoff_time = time.time() - (minutes * 60)
        recent_records = [r for r in self.records if r.timestamp >= cutoff_time]
        
        if not recent_records:
            return {
                "period_minutes": minutes,
                "records_in_period": 0
            }
        
        successful = [r for r in recent_records if r.success]
        
        return {
            "period_minutes": minutes,
            "records_in_period": len(recent_records),
            "calls": len(recent_records),
            "successful_calls": len(successful),
            "failed_calls": len(recent_records) - len(successful),
            "total_tokens": sum(r.total_tokens for r in recent_records),
            "total_cost": sum(r.cost for r in recent_records),
            "avg_latency_ms": (
                sum(r.latency_ms for r in successful) / len(successful)
                if successful else 0
            )
        }
    
    def get_cost_projection(self) -> Dict[str, Any]:
        """Project costs based on current usage."""
        summary = self.get_session_summary()
        
        if summary["total_calls"] == 0:
            return {
                "daily_projection": 0.0,
                "monthly_projection": 0.0,
                "confidence": "low"
            }
        
        elapsed_seconds = summary["session_duration_seconds"]
        if elapsed_seconds == 0:
            return {
                "daily_projection": 0.0,
                "monthly_projection": 0.0,
                "confidence": "very_low"
            }
        
        cost_per_second = summary["total_cost"] / elapsed_seconds
        daily_cost = cost_per_second * 86400
        monthly_cost = daily_cost * 30
        
        # Confidence based on elapsed time
        if elapsed_seconds < 60:
            confidence = "very_low"
        elif elapsed_seconds < 3600:
            confidence = "low"
        elif elapsed_seconds < 86400:
            confidence = "medium"
        else:
            confidence = "high"
        
        return {
            "daily_projection": daily_cost,
            "monthly_projection": monthly_cost,
            "confidence": confidence,
            "based_on_seconds": elapsed_seconds,
            "cost_per_second": cost_per_second
        }
    
    def get_expensive_queries(self, limit: int = 10) -> List[Dict]:
        """Get most expensive queries."""
        sorted_records = sorted(
            self.records,
            key=lambda r: r.cost,
            reverse=True
        )
        
        return [
            {
                "provider": r.provider,
                "model": r.model,
                "cost": r.cost,
                "tokens": r.total_tokens,
                "preview": r.query_preview,
                "timestamp": datetime.fromtimestamp(r.timestamp).isoformat()
            }
            for r in sorted_records[:limit]
        ]
    
    def get_slow_queries(self, limit: int = 10) -> List[Dict]:
        """Get slowest queries."""
        sorted_records = sorted(
            self.records,
            key=lambda r: r.latency_ms,
            reverse=True
        )
        
        return [
            {
                "provider": r.provider,
                "model": r.model,
                "latency_ms": r.latency_ms,
                "tokens": r.total_tokens,
                "cost": r.cost,
                "preview": r.query_preview,
                "timestamp": datetime.fromtimestamp(r.timestamp).isoformat()
            }
            for r in sorted_records[:limit]
        ]
    
    def get_efficiency_score(self) -> Dict[str, Any]:
        """Get efficiency metrics."""
        summary = self.get_session_summary()
        provider_breakdown = self.get_provider_summary()
        
        if summary["total_calls"] == 0:
            return {"score": 0.0, "rating": "no_data"}
        
        # Calculate efficiency
        success_rate = (
            summary["successful_calls"] / summary["total_calls"]
            if summary["total_calls"] > 0 else 0
        )
        
        # Cost efficiency (tokens per dollar)
        tokens_per_dollar = (
            summary["total_tokens"] / summary["total_cost"]
            if summary["total_cost"] > 0 else 0
        )
        
        # Speed efficiency (avg latency normalized)
        avg_latency = summary["avg_latency_ms"]
        speed_score = 1.0 if avg_latency < 500 else 500 / avg_latency
        
        # Overall score (0-100)
        overall_score = (
            (success_rate * 40) +
            (min(tokens_per_dollar / 10000, 1.0) * 30) +
            (speed_score * 30)
        )
        
        if overall_score > 85:
            rating = "excellent"
        elif overall_score > 70:
            rating = "good"
        elif overall_score > 50:
            rating = "fair"
        else:
            rating = "poor"
        
        return {
            "score": overall_score,
            "rating": rating,
            "success_rate": success_rate,
            "tokens_per_dollar": tokens_per_dollar,
            "avg_latency_ms": avg_latency,
            "components": {
                "success_rate_weight": 40,
                "cost_efficiency_weight": 30,
                "speed_weight": 30
            }
        }
    
    def export_records(self, limit: Optional[int] = None) -> List[Dict]:
        """Export all records as dictionaries."""
        records = self.records
        if limit:
            records = records[-limit:]
        
        return [
            {
                "provider": r.provider,
                "model": r.model,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "total_tokens": r.total_tokens,
                "cost": r.cost,
                "latency_ms": r.latency_ms,
                "success": r.success,
                "timestamp": datetime.fromtimestamp(r.timestamp).isoformat(),
                "query_preview": r.query_preview
            }
            for r in records
        ]


# Singleton instance
_tracker_instance = None


def get_cost_tracker() -> CostTracker:
    """Get or create cost tracker singleton."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = CostTracker()
    return _tracker_instance
