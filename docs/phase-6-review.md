# Review triển khai Phase 6

Ngày: 2026-10-22. Đây là review trực tiếp của người triển khai, không phải reviewer độc lập. Đối chiếu với [hợp đồng](phase-6-contract.md) và [kế hoạch](superpowers/plans/2026-10-22-phase-6-performance.md).

| Ranh giới | Kiểm chứng |
| --- | --- |
| Số học | Decimal đầu vào → Fraction chính xác, không float; HALF_UP ở đầu ra cent. Final dùng thành phần chưa làm tròn. Golden 89.80, oracle Decimal precision cao, context precision khác nhau, số cực trị, cap >100/không cap, LOWER actual=0, dữ liệu lỗi |
| Tính tái lập | Đóng băng policy/definition/subject; hash canonical sorted UUID, số đúng scale, evidence/engine versions. Không dùng clock, comment, email, quản lý hiện tại. Cùng hash không tạo revision/audit; mọi lần tính mới có history kể cả lần đầu |
| Phạm vi SQL | Report/revision/count/detail cùng live employee scope; ADMIN không có HR access. Chuyển manager thu hồi cả history; inbox historical reviewer vẫn độc lập. Quản lý đọc nhưng không tự calculate cho mình |
| Riêng tư | Presenter allowlist thay vì trả snapshot JSON; threshold 0/1/2/3 riêng PEER/SUBORDINATE, cả report/revision. Own comment chỉ exact author thuộc submitted membership của revision; bài gửi sau không lọt vào revision trước |
| Đọc nhất quán | REPEATABLE READ trước SELECT đầu tiên của aggregate. Event test tạm dừng reader, commit writer rồi tiếp tục: không trộn evidence mới và version cũ. Query-count tests bảo vệ report và paginated history |
| Origin/CSRF/account | Calculate/finalize/close đều exact Origin, family-bound CSRF, revalidate role/account/family dưới khóa. Event tests disable/logout/đổi role/chuyển manager trước khi calculator lấy guard |
| Thứ tự khóa | Guard 730031 → active ADMIN/users theo thứ tự → family → cycle → participant → review/revision; discovery không khóa review trước participant. Dùng cùng guard/cycle/participant với KPI và feedback; không thêm guard vào GET |
| Cạnh tranh | Calculate/calculate chỉ một revision; calculate/actual không mất version. Finalize đua submit/actual/allocation/replacement chỉ một kết quả hợp lệ. Finalize/close cần version mới chủ động; close/activate không tạo hai ACTIVE. Barrier/Event và lock/future timeouts kiểm tra tranh chấp thật |
| Tính nguyên tử | Transaction bao header/revision/audit; audit failure thử first calculate/recalculate/finalize/close. Lỗi CHECK khi flush revision bảo vệ rollback cả header/audit. Replay không tăng calculation/evidence/cycle version lần hai |
| Chốt và đóng kỳ | HR recheck current hash + cả hai versions + optional count; chốt participant/header cùng UTC, tăng cycle.version một lần. Optional OPEN giữ nguyên, gửi muộn bị chặn. Close không auto-finalize, giữ lịch sử, không reopen |
| UI/cache | Top header/tab nhóm + menu trái theo role, tab theo employee/cycle trên trang cũ. Stale không có current totals; history có nhãn rõ. Xác nhận reset khi context thay đổi, 409 yêu cầu tải lại. Cache tách user/current/history/HR context; writer invalidate các nhóm liên quan |

Edge trên project/ports/volume riêng đã thực hiện calculate bằng MANAGER, xem STALE bằng EMPLOYEE, recalculate/history/finalize/close bằng HR, menu ADMIN và các màn cũ ở 390/1280px. Đã xem ảnh để sửa tab mobile bị khuất và trạng thái menu trái. Không dùng Figma làm nguồn màu đã xác minh vì file chưa truy cập được. Không thêm dependency, service hoặc biến môi trường.

Giới hạn: tổng thống kê vẫn có khả năng suy luận nhóm nhỏ như Phase 5; HR có màn dữ liệu gốc riêng. Không có delegation/reset mật khẩu cho historical SELF/MANAGER, mở lại kỳ đã chốt, AI hoặc dashboard trong scope này. Cần có đủ người và tài khoản hoạt động để hoàn tất phản hồi bắt buộc trước khi chốt. Kiểm tra HTTPS/Secure cookie còn phụ thuộc môi trường triển khai thực tế.

Quy trình thực tế: engine được viết theo RED/GREEN; schema/service và các kiểm thử PostgreSQL được phát triển cùng nhau, không tuyên bố mọi test đều viết trước implementation. Lượt full local đầu có 748 đạt và hai kỳ vọng Phase 4 cũ thất bại (close chưa tồn tại/head 0005); đã sửa kỳ vọng theo API/schema mới và chạy lại cùng các ca privacy mới. Kết quả CI đầy đủ cuối cùng và năm lượt cạnh tranh được ghi trong kế hoạch nghiệm thu khi hoàn thành.
