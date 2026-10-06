import time
from typing import Dict, Any


class ExecutionBudget:
    """Execution budget managing hard ceilings (Slide 15, 35, 38)."""

    def __init__(
        self,
        max_steps: int = 10,
        max_tokens: int = 50000,
        timeout_seconds: float = 30.0,
    ):
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds

        self.current_steps = 0
        self.current_tokens = 0
        self.start_time = time.time()

    def record_step(self, tokens_used: int = 0):
        self.current_steps += 1
        self.current_tokens += tokens_used

    def is_exhausted(self) -> Dict[str, Any]:
        elapsed = time.time() - self.start_time

        if self.current_steps >= self.max_steps:
            return {
                "exhausted": True,
                "reason": f"Maximum steps exceeded: {self.current_steps}/{self.max_steps}.",
                "type": "MAX_STEPS_EXCEEDED",
            }

        if self.current_tokens >= self.max_tokens:
            return {
                "exhausted": True,
                "reason": f"Token budget exceeded: {self.current_tokens}/{self.max_tokens}.",
                "type": "TOKEN_LIMIT_EXCEEDED",
            }

        if elapsed >= self.timeout_seconds:
            return {
                "exhausted": True,
                "reason": f"Timeout exceeded: {elapsed:.2f}s/{self.timeout_seconds}s.",
                "type": "TIMEOUT_EXCEEDED",
            }

        return {"exhausted": False}

    def reset(self):
        self.current_steps = 0
        self.current_tokens = 0
        self.start_time = time.time()
