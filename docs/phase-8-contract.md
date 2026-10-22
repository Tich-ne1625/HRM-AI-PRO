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
