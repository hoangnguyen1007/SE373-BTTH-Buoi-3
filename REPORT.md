# TRƯỜNG ĐẠI HỌC CÔNG NGHỆ THÔNG TIN - ĐHQG-HCM
## KHOA CÔNG NGHỆ PHẦN MỀM

---

# BÁO CÁO KỸ THUẬT BÀI TẬP THỰC HÀNH BUỔI 03 (BTVN#3)
## ĐỀ TÀI: XÂY DỰNG FLIGHT BOOKING AGENT VỚI 3 MẪU THIẾT KẾ VÀ 4 LỚP HARNESS

* **Môn học:** SE373 - Kỹ thuật xây dựng hệ thống Agentic AI
* **Nguyên tắc cốt lõi:** `agent = model + harness` (Model cấp năng lực suy luận ngôn ngữ, Harness cấp độ tin cậy và bảo vệ thực thi)
* **Công nghệ áp dụng:** Python 3.13, LangChain 1.4, LangGraph, Pydantic 2.12

---

## 1. MÔ TẢ BÀI TOÁN VÀ ĐẶC TẢ CÔNG CỤ (TOOLS SPECIFICATION)

### 1.1. Khái quát bài toán
Hệ thống tác tử (Agent) tiếp nhận yêu cầu đặt vé máy bay từ người dùng bằng ngôn ngữ tự nhiên. Mô hình ngôn ngữ (LLM) đảm nhiệm việc phân tích ngữ nghĩa và sinh các lời gọi công cụ, trong khi lớp điều khiển (Harness) đảm bảo toàn bộ thao tác tuân thủ các ràng buộc nghiệp vụ, bảo vệ tài nguyên, kiểm soát quyền hạn và xác thực kết quả khách quan.

### 1.2. Bảng đặc tả 5 công cụ Mockup (`@tool`)

| Tên công cụ | Tham số đầu vào | Cấu trúc dữ liệu trả về | Cơ chế xử lý lỗi ngữ nghĩa (Semantic Hints) |
| :--- | :--- | :--- | :--- |
| `search_flights` | `origin: str, destination: str, date: str` | `{"status": "ok", "flights": [...]}` | Kiểm tra định dạng regex `YYYY-MM-DD`. Nếu sai trả về `invalid_param` kèm gợi ý sửa lỗi (Slide 56). |
| `check_seat` | `flight_id: str` | `{"status": "ok", "available_seats": [...], "price": int}` | Kiểm tra mã chuyến bay. Nếu không tìm thấy, trả về lỗi `flight_not_found`. |
| `book_seat` | `flight_id: str, seat_number: str` | `{"status": "held", "booking_code": str, ...}` | Kiểm tra tính khả dụng của ghế; cập nhật trạng thái giữ chỗ (`held`) và cấp mã PNR. |
| `pay` | `booking_code: str, payment_method: str` | `{"status": "paid", "booking_code": str}` | Xác nhận thanh toán; cập nhật `paid=True` và `status=confirmed`. |
| `get_booking` | `booking_code: str` | `{"status": str, "paid": bool, "price": int, ...}` | Truy vấn cơ sở dữ liệu phục vụ vị từ kiểm chứng bằng code (Slide 43). |

```
[HÌNH 1: CHỤP ẢNH MÀN HÌNH CHẠY 'python -m unittest tests/test_tools.py -v' - MINH CHỨNG 5/5 TESTS TOOLS PASS]
```

---

## 2. THIẾT KẾ VÀ CÀI ĐẶT 4 LỚP HARNESS BẢO VỆ (THEO SLIDE BUỔI 03)

Lớp Harness bao bọc toàn bộ vòng lặp của Agent, thực thi theo đúng thứ tự ưu tiên của Checklist kiểm tra an toàn (Slide 35 Buổi 03):

### 2.1. Lớp 1: Ràng buộc là dữ liệu (Data Constraints - Slide 61, 63)
Ràng buộc nghiệp vụ không để trong câu nhắc văn bản tự do mà được cấu trúc hóa thành Pydantic schema (`FlightConstraints`) gồm:
* Hành trình: `SGN` $\rightarrow$ `DAD`, Ngày bay: `2026-10-07`.
* Giờ cất cánh: trước `12:00` (buổi sáng).
* Ngân sách trần: `2.000.000 VNĐ`.

Lớp `ConstraintValidator` kiểm tra dữ liệu trước khi hành động `book_seat` được gọi. Nếu chuyến bay vi phạm giờ cất cánh (sau 12:00) hoặc vượt ngân sách, Harness chặn hành động ngay tại cổng ra vào.

### 2.2. Lớp 2: Tiêu chí hoàn thành kiểm bằng code (Computational Verification - Slide 43, 44)
Sử dụng hàm vị từ Boolean khách quan (`ComputationalVerifier`) kiểm tra trực tiếp trạng thái cơ sở dữ liệu vật lý, độc lập tuyệt đối với việc mô hình tự tuyên bố hoàn thành:
$$\text{Predicate} = (\text{status} == \text{'confirmed'}) \land (\text{paid} == \text{True}) \land (\text{price} \le \text{budget}) \land (\text{depart} < \text{12:00})$$
*Đặc tính:* Thực thi tính bằng microsecond, tiêu thụ 0 token, loại bỏ hoàn toàn rủi ro ảo giác (hallucination) của LLM.

### 2.3. Lớp 3: Kiểm quyền trước thực thi (Permission Gatekeeper - Slide 35, 41)
Chạy tại bước #0 trước khi gọi công cụ tạo tác dụng phụ (side effects). Nếu giá vé vượt ngưỡng tự duyệt (> 1.500.000 VNĐ) hoặc vé thuộc loại không hoàn tiền (`refundable == False`), Harness tạm dừng Agent và chuyển sang trạng thái `NEED_HUMAN_APPROVAL` để yêu cầu con người phê duyệt.

### 2.4. Lớp 4: Giao thức bàn giao con người (Human Handoff Protocol - Slide 48)
Khi hệ thống cần phê duyệt hoặc gặp sự cố bế tắc, lớp `HumanHandoffManager` đóng gói ngữ cảnh thành cấu trúc 4 trường thông tin súc tích:
1. **Current Status:** Trạng thái hiện tại và các thao tác đã thực hiện.
2. **Tried Attempts:** Các phương án đã thử và lý do cần can thiệp.
3. **Agent Recommendation:** Đề xuất kỹ thuật tối ưu nhất.
4. **Specific Question:** Câu hỏi quyết định đóng (Yes/No) giúp người vận hành đưa ra phản hồi tức thì.

### 2.5. Các cơ chế bổ trợ chống thất bại (Failure Mode Protections)
* **LoopDetector (Slide 46):** Sử dụng hàng đợi `deque(maxlen=10)` đối chiếu dấu vân tay $fp = (\text{tool}, \text{repr(sorted(args))})$ với ngưỡng $repeat \ge 2$ để ngắt lặp; theo dõi biến tiến độ với ngưỡng $stall\_n = 5$ để ngắt bế tắc.
* **GroundingSensor (Slide 59):** Đối chiếu chéo mã chuyến bay, số ghế và giá vé do agent phát ngôn với tập dữ liệu công cụ trả về để chống Hallucination.
* **ExecutionBudget (Slide 15, 38):** Quản lý trần cứng số bước lặp (tối đa 10 bước), token (50.000 tokens) và thời gian timeout (30 giây).

```
[HÌNH 2: CHỤP ẢNH MÀN HÌNH CHẠY 'python main.py --agent hybrid --require-approval' - MINH CHỨNG KHUNG BÀN GIAO HUMAN HANDOFF REPORT]
```

---

## 3. CÀI ĐẶT 3 MẪU THIẾT KẾ AGENT VỚI LANGCHAIN

### 3.1. Mẫu 1: ReAct Agent (Slide 18-21, 29)
Được xây dựng bằng `create_agent` từ thư viện `langchain.agents` kết hợp `ModelCallLimitMiddleware` và `HarnessMiddleware`. Agent vận hành theo chu trình: *Suy luận (Thought) $\rightarrow$ Hành động (Action) $\rightarrow$ Quan sát (Observation)*. Ưu điểm là độ linh hoạt cao khi chưa biết trước số bước, nhưng tốn nhiều token do phải nạp lại toàn bộ lịch sử qua mỗi vòng lặp.

### 3.2. Mẫu 2: Plan-then-Execute Agent (Slide 22, 23)
Chia làm 3 giai đoạn độc lập:
1. *Planner:* Sinh trọn vẹn kế hoạch tuần tự từ đầu.
2. *PlanReviewer:* Thẩm định tính an toàn và chi phí kế hoạch trước khi chạy (Slide 23).
3. *Executor:* Thực thi tuần tự các bước.

*Ưu điểm:* Tiết kiệm token và kiểm soát ngân sách trước khi chạy; *nhược điểm:* kế hoạch tĩnh bị giòn (brittle) — nếu bước giữa thất bại (ví dụ chuyến bay hết ghế), hệ thống không thể tự phục hồi.

### 3.3. Mẫu 3: Mẫu Lai (Hybrid Agent - ReAct + Plan) (Slide 24, 26)
Tích hợp nguyên lý `TodoListMiddleware` từ `langchain.agents.middleware`. Agent khởi tạo danh sách công việc dự kiến, thực thi từng bước và đánh giá hàm `is_observation_drifted()`. Khi quan sát thực tế thay đổi đáng kể so với kỳ vọng (chuyến bay ưu tiên 1 hết chỗ), Agent lập tức kích hoạt `replan_on_drift()` để tự động lập lại kế hoạch và chuyển hướng sang chuyến bay thay thế khả thi.

```
[HÌNH 3: CHỤP ẢNH MÀN HÌNH CHẠY 'python main.py --agent react' - MINH CHỨNG NHẬT KÝ TRACE LOG TỪNG VÒNG]
```

---

## 4. ĐÁNH GIÁ SO SÁNH HIỆU QUẢ CỦA 3 MẪU THIẾT KẾ (SLIDE 31)

Hệ thống được kiểm thử thực nghiệm trên bộ 5 kịch bản benchmark chuẩn hóa:
* **SC1 (Happy Path):** Kịch bản lý tưởng, chuyến bay và ghế trống đầy đủ.
* **SC2 (Environmental Drift):** Chuyến bay ưu tiên hết chỗ, đòi hỏi khả năng thích ứng runtime.
* **SC3 (Permission Gate):** Giá vé vượt hạn mức duyệt tự động.
* **SC4 (Impossible Budget):** Ngân sách 500.000 VNĐ (không có chuyến bay thỏa mãn).
* **SC5 (Pre-Execution Rejection):** Kế hoạch vi phạm chính sách bị từ chối ngay khâu thẩm định.

### 4.1. Bảng ma trận so sánh định lượng thực tế

| Chỉ số đo lường | Mẫu 1: ReAct | Mẫu 2: Plan-then-Execute | Mẫu 3: Mẫu Lai (Hybrid) |
| :--- | :---: | :---: | :---: |
| **Tỷ lệ thành công (Success Rate)** | **20.0%** (1/5) | **20.0%** (1/5) | **20.0%** (1/5) |
| **Số bước thực thi trung bình** | 3.4 bước | 2.4 bước | 3.0 bước |
| **Lượng Token tiêu thụ trung bình** | 12,700 tokens | 1,440 tokens | 3,900 tokens |
| **Số lần kích hoạt Handoff/Duyệt** | 4 lần | 3 lần | 4 lần |
| **Khả năng thích ứng biến động (SC2)** | Moderate (Dynamic step) | Brittle (Static plan fails) | **High (Dynamic replanning)** |
| **Kiểm soát chi phí trước chạy (SC5)** | None (Runs immediately) | **Absolute (Reviewed prior to run)** | Roadmap-guided |

### 4.2. Phân tích đánh đổi kỹ thuật (Trade-offs theo Slide 31)
1. **Đánh đổi về chi phí và số bước:** Plan-then-Execute tiết kiệm token nhất (1.440 tokens, trung bình 2.4 bước), thấp hơn 8.8 lần so với ReAct (12.700 tokens, 3.4 bước). Nguyên nhân là Plan-then-Execute chỉ gọi mô hình lập kế hoạch một lần, trong khi ReAct phải tích lũy toàn bộ lịch sử Thought-Action-Observation qua từng vòng lặp.
2. **Đánh đổi về khả năng thích ứng và an toàn:** Cả 3 mẫu thiết kế đạt 20.0% thành công trên khía cạnh hoàn thành vé (SC1) do 4/5 kịch bản còn lại (SC2, SC3, SC4, SC5) là các bài kiểm tra ranh giới an toàn: kích hoạt Handoff khi chạm trần duyệt (SC3), dừng lại chống ảo giác khi không có vé phù hợp (SC4), và từ chối kế hoạch vi phạm (SC5). Số lần kích hoạt Handoff/Approval đạt 3-4 lần, chứng minh lớp Harness đã hoạt động bảo vệ hiệu quả, ngăn chặn 100% tình trạng tự ý thanh toán trái phép.
3. **Đánh đổi giữa tính linh hoạt và độ giòn:** Trong SC2 (chuyến bay hết chỗ), Plan-then-Execute bị thất bại hoàn toàn do kế hoạch tĩnh bị giòn (brittle). Ngược lại, Mẫu Lai (Hybrid) cân bằng tối ưu giữa việc kiểm soát token (3.900 tokens) và năng lực thích ứng động theo lộ trình công việc (Todo roadmap).

```
[HÌNH 4: CHỤP ẢNH MÀN HÌNH CHẠY 'python main.py --benchmark' - MINH CHỨNG BẢNG SO SÁNH THỰC NGHIỆM TRÊN CONSOLE]
```

---

## 5. HƯỚNG DẪN THỰC THI VÀ MINH BẠCH HỌC THUẬT (SLIDE 14 BUỔI 01)

### 5.1. Quy trình thực thi kiểm thử và vận hành
Mã nguồn được cấu trúc hóa theo chuẩn module, cho phép chạy kiểm thử độc lập và đồng bộ:
* **Kiểm thử đơn vị toàn bộ hệ thống (22/22 tests PASS):** `python -m unittest discover tests -v`
* **Chạy từng mẫu thiết kế tác tử:** `python main.py --agent react` (hoặc `--agent plan`, `--agent hybrid`)
* **Chạy ma trận đánh giá hiệu năng tự động:** `python main.py --benchmark`
* **Kiểm tra kịch bản xin quyền người dùng:** `python main.py --agent hybrid --require-approval`

### 5.2. Kê khai minh bạch công cụ hỗ trợ (Slide 14 Buổi 1)
* **Công cụ AI hỗ trợ:** Sử dụng AI Assistant để hỗ trợ rà soát cấu trúc thư mục, đối chiếu các trích dẫn slide bài giảng Buổi 01 và Buổi 03.
* **Phần việc tự thực hiện:** Xây dựng 5 mockup tools, thiết kế logic 4 lớp Harness, cài đặt thuật toán LoopDetector, xây dựng bộ 22 unit tests và benchmark kiểm định thực nghiệm. Toàn bộ mã nguồn đã được kiểm chứng độc lập trên môi trường phát triển cục bộ.

```
[HÌNH 5: CHỤP ẢNH LỊCH SỬ GIT BẰNG 'git log --oneline -n 8' - MINH CHỨNG CÁC LƯỢT COMMIT MÃ NGUỒN NGUYÊN TỬ]
```
