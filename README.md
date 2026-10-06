# BTVN#3: Flight Booking Agent & Harness Architecture

Hệ thống tác tử đặt vé máy bay tự động dựa trên mô hình ngôn ngữ và lớp bảo vệ thực thi (Harness), xây dựng theo nguyên tắc:
$$\text{Agent} = \text{Model} + \text{Harness}$$

---

## 1. Cấu trúc dự án

```text
SE373-BTTH-Buoi-3/
├── src/
│   ├── domain/          # Pydantic models (Flight, Booking, FlightConstraints)
│   ├── tools/           # 5 công cụ mockup (@tool với semantic error handling)
│   ├── harness/         # 4 lớp Harness bảo vệ và các cảm biến an toàn
│   │   ├── constraints.py   # Lớp 1: Ràng buộc là dữ liệu
│   │   ├── verification.py  # Lớp 2: Tiêu chí hoàn thành kiểm bằng code
│   │   ├── permission.py    # Lớp 3: Kiểm quyền trước thực thi
│   │   ├── handoff.py       # Lớp 4: Giao thức bàn giao con người (30s protocol)
│   │   ├── detectors.py     # LoopDetector & GroundingSensor
│   │   ├── budget.py        # ExecutionBudget (steps, tokens, timeout)
│   │   └── middleware.py    # HarnessMiddleware tích hợp LangChain
│   ├── agents/          # 3 mẫu thiết kế tác tử
│   │   ├── react_agent.py        # Mẫu 1: ReAct Agent (create_agent)
│   │   ├── plan_execute_agent.py # Mẫu 2: Plan-then-Execute (Reviewer trước chạy)
│   │   ├── hybrid_agent.py       # Mẫu 3: Mẫu Lai (TodoList + Replan on drift)
│   │   └── model_provider.py     # Tích hợp LLM (Gemini / OpenAI / Offline Fallback)
│   └── benchmark/       # Bộ 5 kịch bản đánh giá định lượng
│       ├── scenarios.py     # Kịch bản SC1 đến SC5
│       └── evaluator.py     # Trình chạy và bảng so sánh hiệu năng
├── tests/               # 22 unit tests độc lập
├── main.py              # CLI thực thi hệ thống
├── requirements.txt     # Danh sách thư viện phụ thuộc
├── .env.example         # Mẫu biến môi trường
└── 24521182_LeVuHoangNguyen_BTTH3.pdf # Báo cáo kỹ thuật chính thức
```

---

## 2. Cài đặt

Yêu cầu môi trường: **Python 3.10+**.

```bash
# Cài đặt thư viện phụ thuộc
pip install -r requirements.txt
```

*(Tùy chọn)* Kết nối mô hình LLM trực tiếp:
Tạo file `.env` từ `.env.example` và điền khóa API (hỗ trợ Google Gemini hoặc OpenAI):
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-flash-latest
```
*Lưu ý: Nếu không cấu hình API key, hệ thống tự động sử dụng bộ mô phỏng ngoại tuyến để đảm bảo mọi lệnh chạy kiểm thử không bị gián đoạn.*

---

## 3. Hướng dẫn chạy

### 3.1. Chạy toàn bộ Unit Tests (22/22 tests)
```bash
python -m unittest discover tests -v
```

### 3.2. Chạy từng mẫu thiết kế Agent
```bash
# Mẫu 1: ReAct Agent
python main.py --agent react

# Mẫu 2: Plan-then-Execute Agent
python main.py --agent plan

# Mẫu 3: Mẫu Lai (Hybrid Agent)
python main.py --agent hybrid
```

### 3.3. Chạy kịch bản kiểm quyền con người (Human Gate & Handoff)
```bash
python main.py --agent hybrid --require-approval
```

### 3.4. Chạy ma trận đánh giá hiệu năng (Benchmark 3 mẫu trên 5 kịch bản)
```bash
python main.py --benchmark
```

---

## 4. Tóm tắt kết quả thực nghiệm

Kết quả đo lường định lượng trên 5 kịch bản chuẩn hóa (Happy Path, Data Drift, Permission Gate, Impossible Budget, Pre-Execution Rejection):

| Chỉ số đo lường | ReAct | Plan-then-Execute | Mẫu Lai (Hybrid) |
| :--- | :---: | :---: | :---: |
| **Tỷ lệ hoàn thành vé** | 20.0% (1/5) | 20.0% (1/5) | 20.0% (1/5) |
| **Số bước trung bình** | 3.4 bước | 2.4 bước | 3.0 bước |
| **Lượng token trung bình** | 12,700 tokens | 1,440 tokens | 3,900 tokens |
| **Kích hoạt duyệt / Handoff** | 4 lần | 3 lần | 4 lần |
| **Khả năng thích ứng (SC2)** | Moderate | Brittle (Kế hoạch tĩnh) | **High (Tự động Replan)** |
| **Kiểm soát chi phí (SC5)** | None | **Absolute (Duyệt trước chạy)** | Roadmap-guided |

Chi tiết phân tích kỹ thuật và hình ảnh minh chứng được trình bày đầy đủ trong file `24521182_LeVuHoangNguyen_BTTH3.pdf`.
