# Phase 8 — Dashboard và trải nghiệm làm việc

Phạm vi được triển khai tiếp sau Phase 7, dùng lại header, menu trái và các trang nghiệp vụ hiện có. Không thay đổi cách tính điểm hoặc tự động gọi AI.

## Quyền và số liệu

- ADMIN xem số tài khoản theo trạng thái và vai trò; không có số liệu nhân sự/hiệu suất.
- HR xem toàn bộ; MANAGER xem bản thân và nhân viên trực tiếp theo cơ cấu hiện tại; EMPLOYEE chỉ xem bản thân. Dùng lại policy SQL của các trang nghiệp vụ.
- Chu kỳ mặc định: ACTIVE, rồi CLOSED, rồi DRAFT (chỉ HR). Danh sách tối đa 100 chu kỳ mới nhất, có cờ thông báo giới hạn. Chu kỳ được chỉ định ngoài quyền trả 404.
- Nhân viên đang làm việc đếm theo hồ sơ hiện tại trong phạm vi quyền. Các chỉ số còn lại thuộc chu kỳ được chọn.
- Chưa hoàn tất = số người tham gia trừ số người đã chốt. Phân biệt chưa tính, cần tính lại, kết quả hiện hành và đã chốt.
- Trung bình và phân bố chỉ dùng kết quả hiện hành hoặc đã chốt hợp lệ, hiển thị số mẫu; không có mẫu trả null. Khoảng điểm: dưới 65, 65–<80, 80–<90, từ 90 trở lên. Điểm có thể vượt 100 theo cấu hình.
- Tỷ lệ nhập KPI = số KPI có actual / số KPI đã giao, không phải tỷ lệ đạt mục tiêu. Không có KPI trả null.
- So sánh phòng ban dùng snapshot lúc kích hoạt; chu kỳ nháp dùng cơ cấu hiện tại và gắn nhãn xem trước. Chỉ trả tối đa 100 nhóm, có cờ giới hạn.
- Hộp việc phản hồi chỉ đếm assignment OPEN của người đăng nhập, trong chu kỳ ACTIVE và chưa chốt; không lộ trạng thái người khác. Chỉ số này thuộc tất cả chu kỳ, được ghi nhãn riêng.
- Mỗi GET đọc trong một snapshot REPEATABLE READ; tổng hợp bằng SQL, không nạp danh sách nhân viên để tính trong Python; no-store và không ghi DB/gọi Gemini.

## Giao diện và các bước tiếp

Dashboard `/dashboard` nằm trong khung header/menu trái hiện có, có chọn chu kỳ, tải lại, loading/error/empty, thẻ số liệu, biểu đồ kèm số và liên kết tới quy trình cũ. ADMIN có lối vào quản trị riêng. Giao diện tiếng Việt, không tràn ngang trên mobile.

Phase 8 chia thành các phần kiểm chứng riêng:

1. Dashboard, phân quyền và tổng hợp số liệu; sửa lỗi chọn model Gemini đã xác minh.
2. Danh sách tư vấn AI đã lưu trên `/ai-reports`, phân trang và tách PUBLIC/HR_PRIVATE; hoạt động gần đây được lọc và làm sạch.
3. Rà soát UX toàn bộ màn hình, kiểm thử trình duyệt và nghiệm thu tích hợp.

Chỉ đánh dấu hoàn thành Phase 8 khi cả ba phần đạt kiểm tra. Dữ liệu demo hiện có (10 tài khoản, 8 hồ sơ, 2 phòng ban, 3 chu kỳ) được giữ nguyên; không tự đặt lại tiến độ thực hành.

## Danh sách tư vấn đã lưu

`GET /api/v1/ai-reports?audience=PUBLIC&cycle_id=<optional>&page=1&page_size=20` chỉ dành cho HR/MANAGER/EMPLOYEE. ADMIN nhận 403; HR_PRIVATE kiểm tra HR trước mọi truy vấn/count. Dùng quyền nhân viên hiện tại và loại chu kỳ DRAFT ngay trong SQL. Chu kỳ chỉ định ngoài quyền hoặc không tồn tại đều trả 404. Không chỉ định chu kỳ thì tổng là tổng trong phạm vi được phép.

Chỉ liệt kê SUCCEEDED, mỗi dòng là một lần tạo, không phải mỗi người. Sắp xếp `generated_at DESC, id DESC`; page >= 1, page_size 1–100; tổng và trang thuộc cùng snapshot REPEATABLE READ. Projection chỉ có ID tư vấn/báo cáo/nhân viên/chu kỳ, tên snapshot, phạm vi, phiên bản, model, thời điểm và cờ `matches_current_calculation`. Không nạp output, nhận xét, hash, người yêu cầu hoặc mã idempotency vào danh sách. Cờ khớp đòi hỏi đúng lần tính/hash và kết quả hiện hành hoặc đã chốt; nhiều thế hệ cùng bằng chứng có thể cùng khớp, không gọi đó là “mới nhất”.

Mở nội dung dùng lại endpoint chi tiết có phân quyền của Phase 7 và renderer React hiện có. Tư vấn cũ có nhãn lịch sử. Chuyển bộ lọc trả về trang 1 và đóng nội dung; chuyển role tạo lại state phù hợp. Không gọi Gemini từ danh sách, tải lại hoặc mở nội dung. Bộ lọc chu kỳ dùng API hiện có, tối đa 100 lựa chọn với thông báo giới hạn; “tất cả” vẫn truy cập được lịch sử cũ qua phân trang.

## Hoạt động gần đây

- Tối đa 6 sự kiện, sắp xếp `created_at DESC, id DESC`, trong cùng snapshot dashboard.
- ADMIN chỉ nhận `user.created`, `user.role_changed`, `user.status_changed` với entity_type=user; chỉ hành động và thời gian, không tên/tài khoản đích.
- HR/MANAGER/EMPLOYEE chỉ nhận `performance.calculated`, `performance.finalized` với entity_type=performance_review, JOIN báo cáo/nhân viên trong quyền hiện tại và chu kỳ được chọn. Tên lấy snapshot; chuyển quản lý đổi phạm vi đọc sự kiện.
- DTO không có actor, metadata, request_id, nhận xét, sự kiện AI hoặc đăng nhập. So sánh entity_id dạng chuỗi để lịch sử audit có ID không phải UUID không gây lỗi.

## UX và cập nhật dữ liệu

Header/menu trái giữ nhóm chức năng theo role; tư vấn nằm trong nhóm đánh giá. Bảng cuộn được bằng bàn phím, có nhãn; mở/đóng nội dung tư vấn quản lý focus. Form và thẻ dùng lại layout, màu sắc hiện có, có focus-visible và tôn trọng reduced-motion. Loại hướng dẫn “sẽ bổ sung chốt/đóng kỳ” đã lỗi thời.

QueryClient chung vô hiệu hóa cache dashboard và danh sách AI sau khi mutation kết thúc, kể cả phản hồi lỗi có thể đã lưu attempt. Chỉ tải lại GET; không thử lại mutation hoặc tự tạo tư vấn. Cache đăng nhập/đăng xuất tiếp tục được xóa và các query mới gắn user/role/phạm vi vào key. Không thêm thư viện UI, migration hoặc cơ chế reset demo.
