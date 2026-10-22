# Review Phase 7 — Gemini advisory

Ngày 2026-10-22. Review trực tiếp trên code và kiểm thử; không có reviewer độc lập trong lượt này. Bằng chứng cuối cùng được ghi tại [kế hoạch triển khai](superpowers/plans/2026-10-22-phase-7-gemini.md). Kiểm thử đang được tổng hợp; chưa gọi Gemini thật.

Các ranh giới được đối chiếu:

- PUBLIC xây payload riêng chỉ từ số liệu, alias KPI và aggregate lọc; không lấy comment hay danh tính. HR_PRIVATE truy vấn đúng submitted assignment IDs trong immutable calculation revision, che email/URL/điện thoại/tên/mã đã biết và giới hạn 20×500 ký tự. Không tái dùng private output cho public.
- Reader scope áp dụng trong SQL, bao gồm detail UUID và count/pagination; quyền HR_PRIVATE không suy ra từ ADMIN. GET dùng REPEATABLE READ, no-store và không gọi provider/ghi audit/recover lease.
- Reserve/audit commit trước khi gọi provider; completion lấy lại guard/account/family/cycle/participant/review, kiểm tra evidence/calculation/hash/lease/fence. Test cạnh tranh thực hiện được KPI write và finalize/close khi provider đang chờ; pool không giữ connection ở ranh giới mạng.
- Idempotency gắn với actor và fingerprint của toàn intent. Reuse success không gọi mạng; RUNNING replay trả 202; terminal replay không gọi lại. Partial unique theo review chặn hai audience chạy đồng thời. Lease 60 giây và cooldown 30 giây; phản hồi cũ không ghi đè sau recovery.
- Strict JSON sáu trường, không extra/coercion/duplicate key/NaN/control sai quy định, giới hạn độ dài và 32 KiB. Adapter không tools/function calling/retries, có timeout tổng và đóng cả client sync/async. Lỗi provider chỉ ra mã allowlist, không nội dung exception.
- Giao diện tiếng Việt dùng section trên report hiện có, xác nhận captured versions, mutation không tự retry, giữ request intent trong sessionStorage khi mất response. Storage không chứa output/comment/key. React hiển thị text, không render HTML/Markdown từ provider; đổi role bỏ private DOM.
- Kiểm thử DB phát hiện trường hợp CHECK chấp nhận NULL do logic ba giá trị của PostgreSQL; SUCCEEDED hiện yêu cầu generated_at khác NULL rõ ràng. Migration và model được kiểm tra parity, downgrade/upgrade giữ evidence/scoring cũ, không backfill AI.
- Kiểm thử giao diện phát hiện debounce tìm người đánh giá có thể reset phân trang ngay sau khi mở; chỉ debounce khi search thay đổi, tránh mất trang người dùng vừa chọn.

Giới hạn còn lại: redaction là best effort; tổng hợp vẫn có nguy cơ suy luận từ dữ liệu nền. Schema đúng không bảo đảm nội dung AI đúng. Không cam kết exactly-once chi phí khi tiến trình chết sau khi provider đã nhận request. Không tự động retry ngoài kiểm soát của người dùng. Live model/quota/quyền API thực tế cần người vận hành tự cấu hình và nghiệm thu riêng bằng dữ liệu hư cấu.
