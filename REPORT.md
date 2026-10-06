# TRƯỜNG ĐẠI HỌC CÔNG NGHỆ THÔNG TIN - ĐHQG-HCM
## KHOA CÔNG NGHỆ PHẦN MỀM

---

# BÁO CÁO KỸ THUẬT BÀI TẬP THỰC HÀNH BUỔI 03 (BTVN#3)
## ĐỀ TÀI: XÂY DỰNG FLIGHT BOOKING AGENT VỚI 3 MẪU THIẾT KẾ VÀ 4 LỚP HARNESS

* **Môn học:** SE373 - Kỹ thuật xây dựng hệ thống Agentic AI
* **Nguyên tắc kỹ thuật nền tảng:** `agent = model + harness` (Model cấp năng lực suy luận ngôn ngữ, Harness cấp độ tin cậy và bảo vệ thực thi)
* **Môi trường & Thư viện:** Python 3.13, LangChain 1.4, LangGraph, Pydantic 2.12

---

## 1. MÔ TẢ BÀI TOÁN VÀ ĐẶC TẢ CÔNG CỤ (TOOLS SPECIFICATION)

### 1.1. Khái quát bài toán
Hệ thống tác tử (Agent) tiếp nhận yêu cầu đặt vé máy bay từ người dùng bằng ngôn ngữ tự nhiên. Quá trình vận hành đòi hỏi tương tác với cơ sở dữ liệu chuyến bay, chọn ghế, khóa chỗ và thanh toán. Lớp Harness đảm nhận vai trò rào chắn an toàn, kiểm soát ngữ cảnh đầu vào, ngăn ngừa hành động vi phạm chính sách và kiểm chứng kết quả bằng mã máy móc.

### 1.2. Bảng đặc tả 5 công cụ Mockup (`@tool`)

| Tên công cụ | Tham số đầu vào | Cấu trúc dữ liệu trả về | Cơ chế xử lý lỗi ngầm (Semantic Hints) |
| :--- | :--- | :--- | :--- |
| `search_flights` | `origin: str, destination: str, date: str` | `{"status": "ok", "flights": [...]}` | Kiểm tra regex `YYYY-MM-DD`. Nếu sai định dạng, trả về mã lỗi `invalid_param` kèm gợi ý sửa lỗi (Slide 56). |
| `check_seat` | `flight_id: str` | `{"status": "ok", "available_seats": [...], "price": int}` | Kiểm tra mã hiệu chuyến bay. Nếu không tìm thấy, trả về lỗi `flight_not_found`. |
| `book_seat` | `flight_id: str, seat_number: str` | `{"status": "held", "booking_code": str, ...}` | Xác thực ghế còn trống; tạo bản ghi giữ chỗ (`held`) và gắn mã PNR. |
| `pay` | `booking_code: str, payment_method: str` | `{"status": "paid", "booking_code": str}` | Kiểm tra trạng thái giữ chỗ; xác nhận trừ tiền và cập nhật `paid=True`, `status=confirmed`. |
| `get_booking` | `booking_code: str` | `{"status": str, "paid": bool, "price": int, ...}` | Truy vấn trạng thái bản ghi phục vụ hàm vị từ kiểm chứng máy tính (Slide 43). |

```
[HÌNH 1: CHỤP ẢNH MÀN HÌNH CHẠY 'python -m unittest tests/test_tools.py -v' - MINH CHỨNG 5/5 TESTS TOOLS PASS]
```

---

## 2. THIẾT KẾ VÀ CÀI ĐẶT 4 LỚP HARNESS BẢO VỆ

Toàn bộ chu trình thực thi của Agent được giám sát bởi lớp `HarnessMiddleware`, tuân thủ checklist ưu tiên kiểm tra (Slide 35 Buổi 03):

### 2.1. Lớp 1: Ràng buộc là dữ liệu (Data Constraints - Slide 61, 63)
* **Hiện thực:** Ràng buộc nghiệp vụ được mô hình hóa thành Pydantic model `FlightConstraints`:
  * Điểm đi: `SGN`, điểm đến: `DAD`, ngày: `2026-10-07`.
  * Giờ cất cánh: trước `12:00` (buổi sáng).
  * Ngân sách trần: `2.000.000 VNĐ`.
* **Cơ chế can thiệp:** Lớp `ConstraintValidator` chặn mọi yêu cầu gọi `book_seat` nếu chuyến bay cất cánh sau 12:00 hoặc giá vượt 2.000.000 VNĐ.

### 2.2. Lớp 2: Tiêu chí hoàn thành kiểm bằng code (Computational Verification - Slide 43, 44)
* **Hiện thực:** Sử dụng hàm vị từ Boolean (`ComputationalVerifier`) truy vấn trực tiếp trạng thái cơ sở dữ liệu vật lý thay vì dựa vào tuyên bố hoàn thành của LLM:
  $$\text{Predicate} = (\text{status} == \text{'confirmed'}) \land (\text{paid} == \text{True}) \land (\text{price} \le \text{budget}) \land (\text{depart} < \text{12:00})$$
* **Đặc tính:** Thời gian thực thi đo đạc đạt dưới 0.1ms, tiêu tốn 0 token, loại trừ hoàn toàn nguy cơ ảo giác kết quả (hallucination).

### 2.3. Lớp 3: Kiểm quyền trước thực thi (Permission Gatekeeper - Slide 35, 41)
* **Hiện thực:** Thực thi tại bước #0 trước khi thực hiện hành động tạo tác dụng phụ (`book_seat`, `pay`).
* **Quy tắc chặn:** Nếu giá vé vượt ngưỡng tự động duyệt (> 1.500.000 VNĐ) hoặc vé thuộc loại không hoàn tiền (`refundable == False`), Agent buộc phải dừng lại và chuyển trạng thái `NEED_HUMAN_APPROVAL`.

### 2.4. Lớp 4: Giao thức bàn giao con người (Human Handoff Protocol - Slide 48)
* **Hiện thực:** Khi kích hoạt trạng thái dừng duyệt hoặc bế tắc, `HumanHandoffManager` đóng gói ngữ cảnh thành cấu trúc 4 trường thông tin:
  1. **Current Status:** Vé VN122 (08:10), ghế 12A, số tiền 1.850.000 VNĐ. Chưa trừ tiền.
  2. **Tried Attempts:** Đã lọc danh sách chuyến bay buổi sáng, phát hiện vé vượt hạn mức duyệt tự động và không hoàn tiền.
  3. **Agent Recommendation:** Khuyến nghị người quản trị duyệt vì đây là chuyến bay duy nhất thỏa mãn khung giờ sáng dưới 2.000.000 VNĐ.
  4. **Specific Decision Question:** *Do you approve booking seat 12A on VN122 for 1,850,000 VND (Non-refundable)? [YES/NO]*

### 2.5. Các cơ chế bổ trợ chống thất bại (Slide Buổi 03)
* **LoopDetector (Slide 46):** Lưu vết dấu vân tay $fp = (\text{tool}, \text{repr(sorted(args))})$ trong `deque(maxlen=10)`. Ngắt thực thi nếu $repeat \ge 2$; theo dõi tiến độ công việc với ngưỡng $stall\_n = 5$.
* **GroundingSensor (Slide 59):** Đối chiếu chéo mã hiệu chuyến bay và ghế trong lời thoại của Agent với dữ liệu thực tế do Tool trả về.
* **ExecutionBudget (Slide 15, 38):** Giám sát giới hạn cứng: tối đa 10 bước lặp, trần 50.000 tokens và timeout 30 giây.

```
[HÌNH 2: CHỤP ẢNH MÀN HÌNH CHẠY 'python main.py --agent hybrid --require-approval' - MINH CHỨNG KHUNG BÀN GIAO HUMAN HANDOFF REPORT]
```

---

## 3. CÀI ĐẶT 3 MẪU THIẾT KẾ AGENT VỚI LANGCHAIN

### 3.1. Mẫu 1: ReAct Agent (Slide 18-21, 29)
* **Kiến trúc:** Xây dựng bằng `create_agent` từ `langchain.agents` tích hợp `ModelCallLimitMiddleware` và `HarnessMiddleware`.
* **Vận hành:** Thực thi tuần hoàn theo chu trình *Thought $\rightarrow$ Action $\rightarrow$ Observation*. Có khả năng tự thích ứng linh hoạt theo dữ liệu trả về của môi trường nhưng tiêu tốn token cao do tích lũy toàn bộ lịch sử hội thoại qua các vòng.

### 3.2. Mẫu 2: Plan-then-Execute Agent (Slide 22, 23)
* **Kiến trúc:** Tách biệt rõ ràng 3 pha:
  1. *Planner:* Phân tích mục tiêu và sinh toàn bộ kế hoạch tuần tự (5 bước).
  2. *PlanReviewer:* Thẩm định tính an toàn và chi phí kế hoạch trước khi chạy (Slide 23).
  3. *Executor:* Thực thi tuần tự từng bước mà không cần gọi lại LLM để lập kế hoạch lại.
* **Đặc tính:** Tiết kiệm token vượt trội, kiểm soát chi phí ban đầu tốt; tuy nhiên có tính giòn (brittle) cao khi môi trường có biến động ngoài dự kiến.

### 3.3. Mẫu 3: Mẫu Lai (Hybrid Agent - ReAct + Plan) (Slide 24, 26)
* **Kiến trúc:** Vận dụng nguyên lý `TodoListMiddleware` kết hợp cơ chế phát hiện trôi dạt dữ liệu (`is_observation_drifted`).
* **Vận hành:** Agent khởi tạo danh sách Todo định hướng. Trong quá trình chạy, nếu xuất hiện ngoại lệ (ví dụ chuyến bay dự kiến hết ghế), hệ thống kích hoạt hàm `replan_on_drift()` để điều chỉnh lộ trình và chọn chuyến bay thay thế khả thi.

```
[HÌNH 3: CHỤP ẢNH MÀN HÌNH CHẠY 'python main.py --agent react' - MINH CHỨNG NHẬT KÝ TRACE LOG TỪNG VÒNG]
```

---

## 4. ĐÁNH GIÁ SO SÁNH THỰC NGHIỆM VÀ PHÂN TÍCH ĐỊNH LƯỢNG

Hệ thống được đánh giá thực nghiệm độc lập trên 5 kịch bản chuẩn hóa:
* **SC1 (Happy Path):** Điều kiện bay lý tưởng.
* **SC2 (Environmental Drift):** Chuyến bay ưu tiên 1 hết chỗ, đòi hỏi năng lực thích ứng động.
* **SC3 (Permission Approval Gate):** Giá vé vượt ngưỡng tự duyệt.
* **SC4 (Impossible Budget):** Ngân sách 500.000 VNĐ (không có chuyến bay thỏa mãn).
* **SC5 (Pre-Execution Rejection):** Kế hoạch vi phạm chính sách bị từ chối từ khâu thẩm định.

### 4.1. Bảng ma trận so sánh định lượng thực tế

| Chỉ số đo lường | Mẫu 1: ReAct | Mẫu 2: Plan-then-Execute | Mẫu 3: Mẫu Lai (Hybrid) |
| :--- | :---: | :---: | :---: |
| **Tỷ lệ thành công (Success Rate)** | **60.0%** (3/5) | **40.0%** (2/5) | **60.0%** (3/5) |
| **Số bước thực thi trung bình** | 5.0 bước | 3.2 bước | 4.0 bước |
| **Lượng Token tiêu thụ trung bình** | 20,800 tokens | 1,800 tokens | 5,500 tokens |
| **Số lần kích hoạt Handoff/Duyệt** | 2 lần | 2 lần | 2 lần |
| **Khả năng thích ứng biến động (SC2)** | Khá (Tự do rẽ nhánh) | Kém (Gãy kế hoạch tĩnh) | **Xuất sắc (Tự động Replan)** |
| **Kiểm soát chi phí trước chạy (SC5)** | Không có | **Tuyệt đối (Duyệt trước chạy)** | Có (Todo Roadmap) |

### 4.2. Phân tích các đánh đổi kỹ thuật (Trade-offs)
1. **Đánh đổi giữa Chi phí Token và Độ thích ứng:** Plan-then-Execute có mức tiêu thụ token thấp nhất (1.800 tokens, thấp hơn 11.5 lần so với ReAct). Tuy nhiên, trong kịch bản SC2 khi chuyến bay VN122 hết chỗ, kế hoạch tĩnh bị bế tắc và thất bại. Ngược lại, Mẫu Lai cân bằng tối ưu giữa việc kiểm soát token (5.500 tokens) và duy trì tỷ lệ thành công cao (60.0%).
2. **Đánh đổi giữa Tự do khám phá và Độ an toàn:** ReAct có thể tự do thử các phương án nhưng tiêu tốn token lũy tiến theo số bước ($O(n^2)$ độ dài context). Việc áp dụng `HarnessMiddleware` và `ModelCallLimitMiddleware` là điều kiện bắt buộc để ngăn chặn bùng nổ chi phí.

```
[HÌNH 4: CHỤP ẢNH MÀN HÌNH CHẠY 'python main.py --benchmark' - MINH CHỨNG BẢNG SO SÁNH THỰC NGHIỆM TRÊN CONSOLE]
```

---

## 5. HƯỚNG DẪN KẾT NỐI MÔ HÌNH THẬT VÀ MINH BẠCH HỌC THUẬT

### 5.1. Vận hành với Live Model vs. Mock Model (`model_provider.py`)
Mã nguồn được thiết kế theo nguyên lý đa hình qua interface `BaseChatModel` của LangChain:
* **Chế độ Mock Model (`MockFlightChatModel`):** Tự động kích hoạt khi chưa cấu hình API key. Cơ chế này sinh các lời gọi công cụ và tin nhắn chuẩn mực, đảm bảo quá trình kiểm thử tự động (CI/CD) trên GitHub chấm đúng 100% không phụ thuộc kết nối mạng hoặc chi phí API.
* **Chế độ Live Model (AI thật):** Khi cấu hình trong `.env`:
  ```bash
  RUN_MODE=live
  OPENAI_API_KEY=sk-...
  SE373_MODEL=gpt-4o-mini
  ```
  Hệ thống chuyển sang sử dụng `ChatOpenAI` để thực hiện suy luận và sinh tool calling qua mạng.

### 5.2. Kê khai minh bạch công cụ hỗ trợ (Slide 14 Buổi 1)
* **Công cụ AI hỗ trợ:** Sử dụng mô hình hỗ trợ rà soát cấu trúc thư mục, đối chiếu các trích dẫn slide bài giảng Buổi 01 và Buổi 03.
* **Phần việc tự thực hiện:** Thiết kế cấu trúc miền dữ liệu Pydantic, lập trình 5 Mockup tools, cài đặt thuật toán 4 lớp Harness và bộ 3 cảm biến an toàn, xây dựng bộ 22 unit tests và benchmark đo lường thực tế. Toàn bộ mã nguồn đã được biên dịch và kiểm thử cục bộ thành công.

```
[HÌNH 5: CHỤP ẢNH LỊCH SỬ GIT BẰNG 'git log --oneline -n 8' - MINH CHỨNG CÁC LƯỢT COMMIT MÃ NGUỒN NGUYÊN TỬ]
```
