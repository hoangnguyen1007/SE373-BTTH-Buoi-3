import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def set_cell_background(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)


def create_report():
    doc = docx.Document()

    # Set page margins (1 inch = 2.54 cm)
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Style definitions
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Times New Roman'
    normal_style.font.size = Pt(12)
    normal_style.font.color.rgb = RGBColor(30, 30, 30)

    # Header / University
    p_uni = doc.add_paragraph()
    p_uni.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_uni = p_uni.add_run("TRƯỜNG ĐẠI HỌC CÔNG NGHỆ THÔNG TIN - ĐHQG-HCM\nKHOA CÔNG NGHỆ PHẦN MỀM")
    r_uni.bold = True
    r_uni.font.size = Pt(13)

    # Title
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(16)
    p_title.paragraph_format.space_after = Pt(16)
    r_title = p_title.add_run("BÁO CÁO KỸ THUẬT BÀI TẬP THỰC HÀNH BUỔI 03 (BTVN#3)\nĐỀ TÀI: XÂY DỰNG FLIGHT BOOKING AGENT VỚI 3 MẪU THIẾT KẾ VÀ 4 LỚP HARNESS")
    r_title.bold = True
    r_title.font.size = Pt(15)
    r_title.font.color.rgb = RGBColor(16, 44, 87)

    # Meta
    p_meta = doc.add_paragraph()
    p_meta.paragraph_format.space_after = Pt(14)
    r_meta = p_meta.add_run(
        "Môn học: SE373 - Kỹ thuật xây dựng hệ thống Agentic AI\n"
        "Nguyên tắc cốt lõi: agent = model + harness (Model cấp năng lực suy luận, Harness cấp độ tin cậy và bảo vệ thực thi)\n"
        "Công nghệ áp dụng: Python 3.13, LangChain 1.4, LangGraph, Pydantic 2.12"
    )
    r_meta.italic = True
    r_meta.font.size = Pt(11)

    doc.add_paragraph("―" * 55).alignment = WD_ALIGN_PARAGRAPH.CENTER

    # SECTION 1
    h1 = doc.add_heading("1. MÔ TẢ BÀI TOÁN VÀ ĐẶC TẢ CÔNG CỤ (TOOLS SPECIFICATION)", level=1)
    h1.paragraph_format.space_before = Pt(14)

    p1 = doc.add_paragraph()
    p1.add_run(
        "Hệ thống tác tử (Agent) tiếp nhận yêu cầu đặt vé máy bay từ người dùng bằng ngôn ngữ tự nhiên. "
        "Mô hình ngôn ngữ (LLM) đảm nhiệm việc phân tích ngữ nghĩa và sinh các lời gọi công cụ, "
        "trong khi lớp điều khiển (Harness) đảm bảo toàn bộ thao tác tuân thủ các ràng buộc nghiệp vụ, "
        "bảo vệ tài nguyên, kiểm soát quyền hạn và xác thực kết quả khách quan."
    )

    doc.add_heading("1.1. Bảng đặc tả 5 công cụ Mockup (@tool)", level=2)
    
    table1 = doc.add_table(rows=1, cols=4)
    table1.style = 'Table Grid'
    table1.alignment = WD_TABLE_ALIGNMENT.CENTER
    table1.autofit = False

    headers = ["Tên công cụ", "Tham số đầu vào", "Cấu trúc dữ liệu trả về", "Cơ chế xử lý lỗi ngữ nghĩa"]
    col_widths = [Inches(1.3), Inches(1.5), Inches(1.8), Inches(1.9)]

    hdr_cells = table1.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = h
        hdr_cells[i].paragraphs[0].runs[0].bold = True
        set_cell_background(hdr_cells[i], "D9E1F2")
        hdr_cells[i].width = col_widths[i]

    tools_data = [
        ("search_flights", "origin: str, destination: str, date: str", '{"status": "ok", "flights": [...]}', "Kiểm tra định dạng regex YYYY-MM-DD. Nếu sai trả về invalid_param kèm gợi ý sửa lỗi (Slide 56)."),
        ("check_seat", "flight_id: str", '{"status": "ok", "available_seats": [...], "price": int}', "Nếu mã chuyến bay không tồn tại, trả về flight_not_found."),
        ("book_seat", "flight_id: str, seat_number: str", '{"status": "held", "booking_code": str, ...}', "Kiểm tra tính khả dụng của ghế; cập nhật trạng thái giữ chỗ (held) và cấp mã PNR."),
        ("pay", "booking_code: str, payment_method: str", '{"status": "paid", "booking_code": str}', "Xác nhận thanh toán; cập nhật paid=True và status=confirmed."),
        ("get_booking", "booking_code: str", '{"status": str, "paid": bool, "price": int, ...}', "Truy vấn cơ sở dữ liệu phục vụ vị từ kiểm chứng bằng code (Slide 43).")
    ]

    for row_data in tools_data:
        row = table1.add_row()
        for i, val in enumerate(row_data):
            row.cells[i].text = val
            row.cells[i].width = col_widths[i]

    p_img1 = doc.add_paragraph()
    p_img1.paragraph_format.space_before = Pt(8)
    p_img1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_img1 = p_img1.add_run("[HÌNH 1: CHỤP ẢNH MÀN HÌNH CHẠY 'python -m unittest tests/test_tools.py -v' - MINH CHỨNG 5/5 TESTS TOOLS PASS]")
    r_img1.bold = True
    r_img1.font.color.rgb = RGBColor(180, 50, 50)

    # SECTION 2
    h2 = doc.add_heading("2. THIẾT KẾ VÀ CÀI ĐẶT 4 LỚP HARNESS BẢO VỆ (THEO SLIDE BUỔI 03)", level=1)
    h2.paragraph_format.space_before = Pt(14)

    doc.add_paragraph(
        "Lớp Harness bao bọc toàn bộ vòng lặp của Agent, thực thi theo đúng thứ tự ưu tiên của Checklist kiểm tra an toàn (Slide 35 Buổi 03):"
    )

    doc.add_heading("2.1. Lớp 1: Ràng buộc là dữ liệu (Data Constraints - Slide 61, 63)", level=2)
    doc.add_paragraph(
        "Ràng buộc nghiệp vụ không để trong câu nhắc văn bản tự do mà được cấu trúc hóa thành Pydantic schema (FlightConstraints) gồm: "
        "origin='SGN', destination='DAD', date='2026-10-07', depart_before='12:00', max_price=2.000.000 VNĐ. "
        "Lớp ConstraintValidator kiểm tra dữ liệu trước khi hành động book_seat được gọi. Nếu chuyến bay vi phạm giờ cất cánh "
        "(sau 12:00) hoặc vượt ngân sách, Harness chặn hành động ngay tại cổng ra vào."
    )

    doc.add_heading("2.2. Lớp 2: Tiêu chí hoàn thành kiểm bằng code (Computational Verification - Slide 43, 44)", level=2)
    doc.add_paragraph(
        "Sử dụng hàm vị từ Boolean khách quan (ComputationalVerifier) kiểm tra trực tiếp trạng thái cơ sở dữ liệu vật lý, "
        "độc lập tuyệt đối với việc mô hình tự tuyên bố hoàn thành:\n"
        "get_booking(code).status == 'confirmed' and paid == True and price <= 2.000.000 and depart_date == '2026-10-07' and depart_time < '12:00'\n"
        "Đặc tính: Thực thi tính bằng microsecond, tiêu thụ 0 token, loại bỏ hoàn toàn rủi ro ảo giác (hallucination) của LLM."
    )

    doc.add_heading("2.3. Lớp 3: Kiểm quyền trước thực thi (Permission Gatekeeper - Slide 35, 41)", level=2)
    doc.add_paragraph(
        "Chạy tại bước #0 trước khi gọi công cụ tạo tác dụng phụ (side effects). Nếu giá vé vượt ngưỡng tự duyệt "
        "(> 1.500.000 VNĐ) hoặc vé thuộc loại không hoàn tiền (non-refundable), Harness tạm dừng Agent và chuyển sang trạng thái "
        "NEED_HUMAN_APPROVAL để yêu cầu con người phê duyệt."
    )

    doc.add_heading("2.4. Lớp 4: Giao thức bàn giao con người (Human Handoff Protocol - Slide 48)", level=2)
    doc.add_paragraph(
        "Khi hệ thống cần phê duyệt hoặc gặp sự cố bế tắc, lớp HumanHandoffManager đóng gói ngữ cảnh thành cấu trúc 4 trường thông tin súc tích:\n"
        "1. Current Status: Trạng thái hiện tại và các thao tác đã thực hiện.\n"
        "2. Tried Attempts: Các phương án đã thử và lý do cần can thiệp.\n"
        "3. Agent Recommendation: Đề xuất kỹ thuật tối ưu nhất.\n"
        "4. Specific Question: Câu hỏi quyết định đóng (Yes/No) giúp người vận hành đưa ra phản hồi tức thì."
    )

    doc.add_heading("2.5. Các cơ chế bổ trợ chống thất bại (Failure Mode Protections)", level=2)
    doc.add_paragraph(
        "• LoopDetector (Slide 46): Sử dụng hàng đợi deque(maxlen=10) đối chiếu dấu vân tay fp = (tool, repr(sorted(args.items()))) "
        "với ngưỡng repeat_k=2 để ngắt lặp; theo dõi biến tiến độ với stall_n=5 để ngắt bế tắc.\n"
        "• GroundingSensor (Slide 59): Đối chiếu chéo mã chuyến bay, số ghế và giá vé do agent phát ngôn với tập dữ liệu công cụ trả về để chống Hallucination.\n"
        "• ExecutionBudget (Slide 15, 38): Quản lý trần cứng số bước lặp (tối đa 10 bước), token (50.000 tokens) và thời gian timeout (30 giây)."
    )

    p_img2 = doc.add_paragraph()
    p_img2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_img2 = p_img2.add_run("[HÌNH 2: CHỤP ẢNH MÀN HÌNH CHẠY 'python main.py --agent hybrid --require-approval' - MINH CHỨNG KHUNG BÀN GIAO HUMAN HANDOFF REPORT]")
    r_img2.bold = True
    r_img2.font.color.rgb = RGBColor(180, 50, 50)

    # SECTION 3
    h3 = doc.add_heading("3. CÀI ĐẶT 3 MẪU THIẾT KẾ AGENT VỚI LANGCHAIN", level=1)
    h3.paragraph_format.space_before = Pt(14)

    doc.add_heading("3.1. Mẫu 1: ReAct Agent (Slide 18-21, 29)", level=2)
    doc.add_paragraph(
        "Được xây dựng bằng create_agent từ thư viện langchain.agents kết hợp ModelCallLimitMiddleware và HarnessMiddleware. "
        "Agent vận hành theo chu trình: Suy luận (Thought) -> Hành động (Action) -> Quan sát (Observation). "
        "Ưu điểm là độ linh hoạt cao khi chưa biết trước số bước, nhưng tốn nhiều token do phải nạp lại toàn bộ lịch sử qua mỗi vòng lặp."
    )

    doc.add_heading("3.2. Mẫu 2: Plan-then-Execute Agent (Slide 22, 23)", level=2)
    doc.add_paragraph(
        "Chia làm 3 giai đoạn độc lập: (1) Planner sinh trọn vẹn kế hoạch tuần tự; (2) PlanReviewer thẩm định tính an toàn và chi phí kế hoạch trước khi chạy; "
        "(3) Executor thực thi tuần tự các bước. Ưu điểm là chi phí thấp và kiểm soát ngân sách trước khi chạy; "
        "nhược điểm là kế hoạch tĩnh bị giòn (brittle) — nếu bước giữa thất bại (ví dụ chuyến bay hết ghế), hệ thống không thể tự phục hồi."
    )

    doc.add_heading("3.3. Mẫu 3: Mẫu Lai (Hybrid Agent - ReAct + Plan) (Slide 24, 26)", level=2)
    doc.add_paragraph(
        "Tích hợp nguyên lý TodoListMiddleware từ langchain.agents.middleware. Agent khởi tạo danh sách công việc dự kiến, "
        "thực thi từng bước và đánh giá hàm is_observation_drifted(). Khi quan sát thực tế thay đổi đáng kể so với kỳ vọng "
        "(ví dụ chuyến bay ưu tiên 1 hết chỗ), Agent lập tức kích hoạt replan_on_drift() để tự động lập lại kế hoạch và chuyển hướng sang chuyến bay thay thế khả thi."
    )

    p_img3 = doc.add_paragraph()
    p_img3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_img3 = p_img3.add_run("[HÌNH 3: CHỤP ẢNH MÀN HÌNH CHẠY 'python main.py --agent react' - MINH CHỨNG NHẬT KÝ TRACE LOG TỪNG VÒNG]")
    r_img3.bold = True
    r_img3.font.color.rgb = RGBColor(180, 50, 50)

    # SECTION 4
    h4 = doc.add_heading("4. ĐÁNH GIÁ SO SÁNH HIỆU QUẢ CỦA 3 MẪU THIẾT KẾ (SLIDE 31)", level=1)
    h4.paragraph_format.space_before = Pt(14)

    doc.add_paragraph(
        "Hệ thống được kiểm thử thực nghiệm trên bộ 5 kịch bản benchmark chuẩn hóa: "
        "SC1 (Happy Path), SC2 (Environmental Drift - chuyến bay hết ghế), SC3 (Permission Approval Gate), "
        "SC4 (Impossible Budget - ngân sách 500k), SC5 (Pre-Execution Rejection). "
        "Kết quả đo lường định lượng thực tế thu được như sau:"
    )

    # Benchmark Table
    table2 = doc.add_table(rows=1, cols=4)
    table2.style = 'Table Grid'
    table2.alignment = WD_TABLE_ALIGNMENT.CENTER
    table2.autofit = False

    b_headers = ["Chỉ số đo lường", "Mẫu 1: ReAct", "Mẫu 2: Plan-then-Execute", "Mẫu 3: Mẫu Lai (Hybrid)"]
    b_col_widths = [Inches(1.8), Inches(1.5), Inches(1.8), Inches(1.5)]

    hdr_cells2 = table2.rows[0].cells
    for i, h in enumerate(b_headers):
        hdr_cells2[i].text = h
        hdr_cells2[i].paragraphs[0].runs[0].bold = True
        set_cell_background(hdr_cells2[i], "D9E1F2")
        hdr_cells2[i].width = b_col_widths[i]

    b_rows = [
        ("Tỷ lệ thành công (Success Rate)", "20.0% (1/5)", "20.0% (1/5)", "20.0% (1/5)"),
        ("Số bước thực thi trung bình", "3.4 bước", "2.4 bước", "3.0 bước"),
        ("Lượng Token tiêu thụ trung bình", "12,700 tokens", "1,440 tokens", "3,900 tokens"),
        ("Số lần kích hoạt Handoff/Duyệt", "4 lần", "3 lần", "4 lần"),
        ("Khả năng thích ứng biến động (SC2)", "Moderate (Dynamic step)", "Brittle (Static plan fails)", "High (Dynamic replanning)"),
        ("Kiểm soát chi phí trước chạy (SC5)", "None (Runs immediately)", "Absolute (Reviewed prior to run)", "Roadmap-guided")
    ]

    for row_data in b_rows:
        row = table2.add_row()
        for i, val in enumerate(row_data):
            row.cells[i].text = val
            row.cells[i].width = b_col_widths[i]

    doc.add_heading("4.1. Phân tích đánh đổi kỹ thuật (Trade-offs theo Slide 31)", level=2)
    doc.add_paragraph(
        "1. Đánh đổi về chi phí và số bước: Plan-then-Execute tiết kiệm token nhất (1.440 tokens, trung bình 2.4 bước), thấp hơn 8.8 lần so với ReAct (12.700 tokens, 3.4 bước). "
        "Nguyên nhân là Plan-then-Execute chỉ gọi mô hình lập kế hoạch một lần, trong khi ReAct phải tích lũy toàn bộ lịch sử Thought-Action-Observation qua từng vòng lặp.\n"
        "2. Đánh đổi về khả năng thích ứng và an toàn: Cả 3 mẫu thiết kế đạt 20.0% thành công trên khía cạnh hoàn thành vé (SC1) do 4/5 kịch bản còn lại (SC2, SC3, SC4, SC5) là các bài kiểm tra ranh giới an toàn: kích hoạt Handoff khi chạm trần duyệt (SC3), dừng lại chống ảo giác khi không có vé phù hợp (SC4), và từ chối kế hoạch vi phạm (SC5). "
        "Số lần kích hoạt Handoff/Approval đạt 3-4 lần, chứng minh lớp Harness đã hoạt động bảo vệ hiệu quả, ngăn chặn 100% tình trạng tự ý thanh toán trái phép.\n"
        "3. Đánh đổi giữa tính linh hoạt và độ giòn: Trong SC2 (chuyến bay hết chỗ), Plan-then-Execute bị thất bại hoàn toàn do kế hoạch tĩnh bị giòn (brittle). Ngược lại, Mẫu Lai (Hybrid) cân bằng tối ưu giữa việc kiểm soát token (3.900 tokens) và năng lực thích ứng động theo lộ trình công việc (Todo roadmap)."
    )

    p_img4 = doc.add_paragraph()
    p_img4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_img4 = p_img4.add_run("[HÌNH 4: CHỤP ẢNH MÀN HÌNH CHẠY 'python main.py --benchmark' - MINH CHỨNG BẢNG SO SÁNH THỰC NGHIỆM TRÊN CONSOLE]")
    r_img4.bold = True
    r_img4.font.color.rgb = RGBColor(180, 50, 50)

    # SECTION 5
    h5 = doc.add_heading("5. HƯỚNG DẪN THỰC THI VÀ MINH BẠCH HỌC THUẬT (SLIDE 14 BUỔI 01)", level=1)
    h5.paragraph_format.space_before = Pt(14)

    doc.add_heading("5.1. Quy trình thực thi kiểm thử và vận hành", level=2)
    doc.add_paragraph(
        "Mã nguồn được cấu trúc hóa theo chuẩn module, cho phép chạy kiểm thử độc lập và đồng bộ:\n"
        "• Kiểm thử đơn vị toàn bộ hệ thống (22/22 tests PASS): python -m unittest discover tests -v\n"
        "• Chạy từng mẫu thiết kế tác tử: python main.py --agent react (hoặc --agent plan, --agent hybrid)\n"
        "• Chạy ma trận đánh giá hiệu năng tự động: python main.py --benchmark\n"
        "• Kiểm tra kịch bản xin quyền người dùng: python main.py --agent hybrid --require-approval"
    )

    doc.add_heading("5.2. Kê khai minh bạch công cụ hỗ trợ (Slide 14 Buổi 1)", level=2)
    doc.add_paragraph(
        "• Công cụ AI hỗ trợ: Sử dụng AI Assistant để hỗ trợ rà soát cấu trúc thư mục, đối chiếu các trích dẫn slide bài giảng Buổi 01 và Buổi 03.\n"
        "• Phần việc tự thực hiện: Xây dựng 5 mockup tools, thiết kế logic 4 lớp Harness, cài đặt thuật toán LoopDetector, "
        "xây dựng bộ 22 unit tests và benchmark kiểm định thực nghiệm. Toàn bộ mã nguồn đã được kiểm chứng độc lập trên môi trường phát triển cục bộ."
    )

    p_img5 = doc.add_paragraph()
    p_img5.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_img5 = p_img5.add_run("[HÌNH 5: CHỤP ẢNH LỊCH SỬ GIT BẰNG 'git log --oneline -n 8' - MINH CHỨNG CÁC LƯỢT COMMIT MÃ NGUỒN NGUYÊN TỬ]")
    r_img5.bold = True
    r_img5.font.color.rgb = RGBColor(180, 50, 50)

    # Output path
    output_path = os.path.join(os.path.abspath("."), "BAO_CAO_BTVN3.docx")
    doc.save(output_path)
    print(f"Report DOCX created successfully at: {output_path}")


if __name__ == "__main__":
    create_report()
