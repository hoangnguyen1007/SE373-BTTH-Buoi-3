"""
Ngân sách vòng lặp (Execution Budget).
Slide 15, 35, 38 Buổi 03:
- Giới hạn cứng: Bước (vòng), Token, Thời gian (giây), Chi phí (tiền).
- Ngân sách luôn được kiểm tra CUỐI CÙNG trong chu trình Harness (Slide 35):
  "Đặt nó lên đầu thì mọi lỗi đều báo về là hết ngân sách, và bạn mất chẩn đoán."
- Dừng bất thường khi hết ngân sách: Phải log và trả kết quả dở dang cho con người.
"""
import time
from typing import Optional, Dict, Any


class ExecutionBudget:
    """
    Quản lý và thực thi giới hạn cứng (Hard Limits) cho Agent Loop.
    """
    def __init__(
        self,
        max_steps: int = 10,
        max_tokens: int = 50000,
        timeout_seconds: float = 30.0,
        cost_limit_vnd: int = 2_500_000
    ):
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.cost_limit_vnd = cost_limit_vnd

        self.current_steps = 0
        self.current_tokens = 0
        self.start_time = time.time()

    def record_step(self, tokens_used: int = 0):
        """Cập nhật chi phí mỗi vòng lặp."""
        self.current_steps += 1
        self.current_tokens += tokens_used

    def is_exhausted(self) -> Dict[str, Any]:
        """
        Kiểm tra xem đã chạm bất kỳ trần ngân sách nào hay chưa.
        """
        elapsed = time.time() - self.start_time

        if self.current_steps >= self.max_steps:
            return {
                "exhausted": True,
                "reason": f"Chạm trần số bước cho phép: {self.current_steps}/{self.max_steps} vòng.",
                "type": "MAX_STEPS_EXCEEDED"
            }

        if self.current_tokens >= self.max_tokens:
            return {
                "exhausted": True,
                "reason": f"Chạm trần token phiên làm việc: {self.current_tokens}/{self.max_tokens} tokens.",
                "type": "TOKEN_LIMIT_EXCEEDED"
            }

        if elapsed >= self.timeout_seconds:
            return {
                "exhausted": True,
                "reason": f"Hết thời gian tối đa: {elapsed:.2f}s/{self.timeout_seconds}s.",
                "type": "TIMEOUT_EXCEEDED"
            }

        return {"exhausted": False}

    def reset(self):
        """Khởi động lại đồng hồ và bộ đếm."""
        self.current_steps = 0
        self.current_tokens = 0
        self.start_time = time.time()
