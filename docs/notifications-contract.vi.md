# Phân công trách nhiệm và thông báo công việc

Phạm vi đã thống nhất: HR tổ chức đợt đánh giá, danh mục KPI, phân công phản hồi, theo dõi, tạo tư vấn và chốt/đóng. Chỉ quản lý trực tiếp được phân bổ KPI, nhập thực tế, tính/tính lại điểm. Nhân viên gửi phiếu được giao và đọc kết quả của mình.

Thông báo bên phải có hai phần: **Thông báo** (lịch sử tương tác có trạng thái chưa đọc/đã đọc) và **Việc cần làm** (tình trạng hiện tại, tự đối chiếu từ hồ sơ và phân công, không phụ thuộc đã đọc thông báo). Đọc thông báo không có nghĩa hoàn thành công việc.

Thông báo được ghi cùng transaction với thay đổi nghiệp vụ, không gửi khi rollback, không nhân đôi khi một yêu cầu được tái sử dụng. PostgreSQL NOTIFY chỉ phát tín hiệu sau commit; SSE gửi tín hiệu cập nhật tới đúng phiên người nhận, rồi trình duyệt đọc danh sách theo quyền hiện tại. Kết nối lại tải lại dữ liệu bền vững để bù sự kiện bị lỡ. Nhiều tab cập nhật cả trạng thái đã đọc. Không cần Redis hoặc dịch vụ bên ngoài.

| Tương tác | Người nhận |
| --- | --- |
| HR kích hoạt kỳ | Quản lý trực tiếp và nhân viên tham gia |
| HR giao/sửa/hủy/khôi phục phiếu | Chính người được giao |
| Quản lý giao KPI/cập nhật thực tế | Nhân viên liên quan và HR |
| Có phản hồi được gửi | HR và quản lý trực tiếp của hồ sơ |
| Quản lý tính điểm | HR kiểm tra/chốt; nhân viên đọc kết quả |
| HR chốt/đóng kỳ | Nhân viên và quản lý liên quan |
| Tạo tư vấn chung thành công | Nhân viên và quản lý liên quan |
| Tạo tư vấn nội bộ thành công | Chỉ HR |

Thông báo không chứa nhận xét gốc, rating theo người, mật khẩu, API key, prompt hoặc nội dung AI. Quyền hiện tại được kiểm tra khi đếm, liệt kê, đánh dấu đã đọc và mở liên kết. Chuyển quản lý/đổi role/khóa tài khoản không giữ quyền đọc dữ liệu cũ. Không tự phát lại toàn bộ lịch sử trước ngày triển khai; công việc đang chờ vẫn có trong **Việc cần làm**.

Đã kiểm tra HR bị từ chối ghi KPI/tính điểm ở API, quản lý sai phạm vi, thông báo đúng người/rollback/replay, cách ly chưa đọc, thay đổi quyền, CSRF/Origin và trạng thái nhiều tab. Migration thêm bảng mới, giữ dữ liệu hiện có.

## Kết quả triển khai ngày 14/11/2026

- **860 test backend** được kiểm tra qua lượt hồi quy và các lượt chạy lại có mục tiêu; hai kỳ vọng cũ về quyền HR/migration đã sửa và chạy lại đạt. Ruff sạch, mypy đạt 110 source file.
- **168 test web / 24 file**, lint, typecheck và production build đạt.
- Edge trên dữ liệu hư cấu riêng: phản hồi phát tin realtime trước chu kỳ polling; đọc đồng bộ hai tab, tải lại vẫn giữ; quản lý tính → HR nhận tin và chốt; bấm tin mở khung chi tiết; hồ sơ chốt khóa sửa; kết nối lại đạt. Đã xem bố cục 1280/390 px. Không gọi AI hoặc ghi nghiệp vụ lên dữ liệu đang dùng trong bài trình duyệt. [Bằng chứng](evidence/notifications-2026-11-14.json).
- Docker hiện tại đã lên head `20261114_0009`, API/web/PostgreSQL healthy. Đã sao lưu trước nâng cấp và đối chiếu 15 bảng nghiệp vụ/tài khoản không đổi; hai bảng xác thực/nhật ký chỉ có vòng refresh phiên bình thường, lịch sử trước đó vẫn được xác minh. Mật khẩu demo hiện có vẫn dùng được.

Lưu ý vận hành: SSE giữ `Cache-Control: no-store, no-transform` để proxy web không nén/giữ tin trong bộ đệm. Khi mất kết nối LISTEN hoặc mạng, trang báo kết nối lại và tạm đọc định kỳ 15 giây. Mỗi tài khoản có tối đa năm kết nối SSE trên một API process; các tab vượt mức dùng cơ chế dự phòng. Tin cũ không được tự tạo lại từ lịch sử trước nâng cấp; **Việc cần làm** vẫn đối chiếu công việc đang chờ.
## Thông báo trao đổi nội bộ

Bảng tin và chat bổ sung các sự kiện `collaboration.post`, `collaboration.comment`, `collaboration.message`, `collaboration.mention`. Chúng dùng liên kết bài viết/tin nhắn riêng, không mượn phạm vi hồ sơ hiệu suất. Tin phòng ban được kiểm tra lại theo phòng hiện tại; chat chỉ thuộc người gửi/người nhận. Phần thông báo chuông không trích nội dung tin nhắn. Mở thông báo dẫn về đúng bài hoặc cuộc trò chuyện. Đánh dấu thông báo đã đọc không giả lập trạng thái đã đọc của chat; khi thực sự xem chat, hệ thống cập nhật cả tin nhắn và thông báo tương ứng. Xem [hướng dẫn và ma trận quyền](bang-tin-va-chat.vi.md).
