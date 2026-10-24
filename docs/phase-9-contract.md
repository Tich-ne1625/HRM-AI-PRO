# Hợp đồng Phase 9 — Bảo mật và tích hợp

Ngày lập: **24/10/2026**. Trạng thái: **đã triển khai và nghiệm thu** tại runtime `9821e82`; kết quả, CI và giới hạn trong [báo cáo Phase 9](phase-9-report.vi.md).

Đầu vào: runtime Phase 8 `88700d8`, tài liệu `758e93a`, [CI đã đạt](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40086271058) với 830 test backend và 133 test web. Xem [kiến trúc](architecture.md), [báo cáo Phase 8](phase-8-report.vi.md), [kế hoạch thực hiện](superpowers/plans/2026-10-24-phase-9-security-integration.md).

## 1. Mục tiêu và ranh giới

Kiểm chứng luồng xuyên suốt bằng dữ liệu hư cấu, khép các khoảng trống bảo mật có bằng chứng và tạo bộ nghiệm thu có thể chạy lại. Kế thừa các test phân quyền/CSRF/refresh/concurrency/AI hiện có; chỉ bổ sung những đường đi và lỗi chưa được kiểm chứng. Không thay công thức chấm điểm, quyền nghiệp vụ, snapshot lịch sử hoặc cơ chế xác nhận gọi AI.

Phạm vi gồm quyền truy cập, phiên đăng nhập/cache, HTTP/proxy, giới hạn đăng nhập/request, tính nguyên tử/cạnh tranh, AI isolation, API audit đã có trong kiến trúc, kiểm thử tích hợp và đo hiệu năng có giới hạn. Không thêm chấm công/lương/chatbot, SSO/MFA, export dữ liệu, màn hình nghiệp vụ mới, Redis, Kubernetes hay dịch vụ giám sát bên ngoài. Kubernetes thuộc Phase 10.

## 2. Những gì đã có và cần đối chiếu

| Đã có trong code | Phần Phase 9 kiểm tra tiếp |
| --- | --- |
| Role/resource scope trong SQL, 404 ngoài quyền, expected version, guard/row locks | Ma trận phủ toàn bộ router; quyền thay đổi giữa các bước, count/trang/hoạt động và historical reviewer |
| Refresh rotation/replay, CSRF session-bound, exact Origin, thu hồi family | Ranh giới proxy/trình duyệt, refresh đến muộn sau logout/đổi role, request/cache từ phiên trước |
| Transaction domain + audit; fault injection và race theo module | Luồng xuyên module và rollback khi lỗi tại ranh giới; không nhân bản audit/revision/feedback |
| Dashboard/danh sách AI có snapshot, cache refresh; dashboard ẩn cache khi lỗi | Các danh sách, chi tiết và form còn lại có xử lý nhất quán sau 401/403/đổi phạm vi không |
| AI lease/fence, hai audience, JSON chặt, timeout, không retry tự động | Tái kiểm tra sau thay đổi quyền/dữ liệu; provider treo/lỗi trong khi luồng số vẫn hoạt động |
| Next.js proxy cố định; lỗi được làm sạch; image không chứa env/test tooling | Header bảo vệ, cache cả response lỗi, request quá lớn/chunked, cookie qua proxy; không suy ra đã có lỗ hổng khi chưa tái hiện |
| Audit ghi trong các service; hoạt động dashboard là projection nhỏ | `GET /audit-logs` được kiến trúc liệt kê nhưng chưa có router; bổ sung API đọc tối thiểu, không trả raw metadata |
| CI đầy đủ và Docker persistence | E2E thực hiện thao tác qua UI trên stack thử nghiệm, nâng cấp có dữ liệu và baseline hiệu năng |

Rà soát hiện tại chưa thấy cơ chế login throttling dùng chung các worker hoặc bộ security headers tường minh tại Next.js. Đây là hạng mục dự kiến bổ sung, không phải tuyên bố các lớp khác đã được kiểm toán toàn diện.

## 3. Quyền và phiên đăng nhập

- ADMIN chỉ quản trị tài khoản/cấu hình/audit hệ thống; không suy ra quyền HR, nhận xét hay tư vấn nhân sự. ADMIN vẫn có inbox nếu được giao làm reviewer.
- HR quản trị nhân sự và đánh giá; MANAGER xem bản thân/nhân viên trực tiếp hiện tại, chỉ ghi khi đủ điều kiện hiện có; EMPLOYEE xem bản thân. Quyền reviewer theo phân công lịch sử không mở rộng thành quyền đọc báo cáo.
- HR_PRIVATE chỉ HR, kiểm tra trước truy vấn/count; không lộ qua UUID, phân trang, hoạt động hoặc error message. PUBLIC giữ suppression nhóm nhỏ và không nhận xét gốc của người khác.
- Request mới bắt đầu sau khi thu hồi phiên/đổi role đã commit phải dùng quyền mới. Ghi dữ liệu phải xác thực lại dưới lock như hiện tại. GET đang thực hiện được phép hoàn thành theo snapshot của nó; không hứa thu hồi dữ liệu đã tải xuống.
- Khi client biết phiên/role/phạm vi thay đổi, hủy hoặc bỏ qua kết quả request cũ và xóa cache không còn được phép. Không phục hồi nội dung riêng qua back navigation, refetch lỗi, response refresh đến muộn hoặc đổi tài khoản trên cùng tab.
- Các mutation không được retry khi timeout/mất response không rõ đã commit hay chưa. Refresh sau 401 phải có giới hạn và không được chạy lại thao tác của phiên trước sau logout. AI tiếp tục dùng intent riêng và `skipRefresh`, chỉ replay chủ động cùng mã yêu cầu.
- 401 cho không có phiên hợp lệ; 403 cho nhóm chức năng không được phép; UUID tài nguyên ẩn/mất đều 404. Không trả khác biệt count hoặc nội dung lỗi để tiết lộ tài nguyên ngoài quyền.

## 4. HTTP, giới hạn và chống thử đăng nhập hàng loạt

### Boundary và dữ liệu bí mật

Kiểm tra cả API trực tiếp và same-origin proxy: Origin thiếu/sai/null, CSRF thiếu/sai/khác family, method/content-type bất thường, cookie path/SameSite/HttpOnly/Secure và chuyển tiếp Set-Cookie. Cấu hình production tiếp tục yêu cầu HTTPS/secret đúng; local HTTP vẫn có chế độ development rõ ràng.

Thêm `nosniff`, chính sách referrer và chống nhúng trang bằng header. CSP phải tương thích Next.js production và được kiểm tra trên trình duyệt; không bật chính sách làm hỏng hydration hoặc thêm `unsafe-eval` vào production chỉ để test qua. HSTS chỉ cho chế độ HTTPS production. Định nghĩa một nơi sở hữu header, kiểm tra proxy không tạo header mâu thuẫn. Personalized API, kể cả lỗi 401/403/404/429/5xx, phải `no-store`. Không đánh đồng với cache static assets.

Giới hạn body API JSON mặc định **128 KiB**, cấu hình `API_MAX_REQUEST_BYTES`; kiểm tra byte thực tế cả khi thiếu hoặc khai sai Content-Length. Vượt giới hạn trả 413 với lỗi chuẩn, không lưu payload/ghi nghiệp vụ. Không chỉ tin header hoặc buffer body không giới hạn. Giới hạn payload AI 64 KiB/đầu ra 32 KiB hiện có vẫn độc lập và giữ nguyên.

### Login throttling dự kiến

Chọn PostgreSQL để chia sẻ hạn mức giữa worker, không thêm Redis hoặc dùng bộ đếm RAM rồi coi là giới hạn toàn hệ thống. Hạn mức mặc định đề xuất: **10 lần thử / 300 giây / email đã chuẩn hóa**, áp dụng như nhau cho email có/không tồn tại, tính cả thử đúng/sai để hành vi không tiết lộ tài khoản. Các biến `AUTH_LOGIN_MAX_ATTEMPTS` và `AUTH_LOGIN_WINDOW_SECONDS` phải được validate và ghi trong `.env.example`.

Thêm bảng nhỏ `auth_login_limits` qua migration riêng, khóa theo HMAC của email chuẩn hóa, không lưu email/key/token rõ. Dùng `AUTH_ACCESS_SECRET` hiện có với message prefix riêng `login-limit:v1:`; không dùng Gemini key hoặc gửi khóa sang web. Các worker cần cùng cấu hình; đổi secret làm reset các bucket cũ, ghi rõ trong vận hành. Hạn mức được giữ trước bước Argon2 tốn CPU, tăng nguyên tử bằng DB time, không sửa mật khẩu hoặc khóa vĩnh viễn tài khoản. Hết hạn trả lại quyền thử; vượt hạn mức trả 429 generic và Retry-After. Lỗi kho hạn mức trả 503 được làm sạch, không fail-open. Log không ghi khóa HMAC/email/password; không ghi một audit row mới cho mọi request đã bị 429. Dọn bản ghi hết hạn có giới hạn bằng CLI/vận hành; không dùng background job ngầm.

Không tin X-Forwarded-For tùy ý, không thêm hạn mức IP cho đến khi có cấu hình trusted proxy rõ. Giới hạn theo email có thể bị lạm dụng làm một tài khoản phải chờ; ghi rõ tradeoff và không gọi đây là biện pháp chống DDoS. Ngưỡng là cấu hình khởi đầu cho capstone, không phải cam kết bảo vệ production quy mô lớn.

## 5. Tính nguyên tử và cạnh tranh

Giữ lock order hiện có; không lấy lock domain qua ranh giới gọi provider. Race dùng barrier/event và timeout test rõ ràng, không kết luận bằng sleep may rủi. Phải chứng minh chỉ một kết quả hợp lệ khi cùng ghi, version không mất và dữ liệu/audit commit hoặc rollback cùng nhau.

Tái sử dụng các test đã có, bổ sung đường đi xuyên module: sửa cơ cấu/khóa tài khoản với thao tác đang chờ; nhập KPI/gửi phản hồi với tính/chốt; đóng/kích hoạt; hoàn thành AI sau revoke/transfer/recalculate; logout/refresh đến muộn; lỗi ghi audit/flush/commit. Mỗi failure có assertion cho version, trạng thái, số revision/audit/feedback và giá trị cũ, không chỉ HTTP status. GET/count/items phải cùng snapshot ở các aggregate được công bố.

Race trọng yếu chạy **5 lượt liên tiếp**, báo số case thu thập thực tế và kết quả từng lượt; không đặt trước tổng test hoặc nhân bản test đã phủ. Không chạy các bộ test cùng phá/dựng một database song song. Không có deadlock/treo ngoài timeout trong bộ kiểm tra không đồng nghĩa chứng minh hệ thống không bao giờ deadlock.

## 6. API đọc audit tối thiểu

`GET /api/v1/audit-logs?page=1&page_size=20&action=<optional>`; chỉ ADMIN và HR. MANAGER/EMPLOYEE nhận 403. Scope hành động/entity type dùng allowlist chính xác trước count, không lọc theo tiền tố tùy ý. Filter hợp lệ nhưng ngoài phạm vi trả danh sách rỗng; không tồn tại cũng cùng hành vi. Page >= 1, page_size 1–100; sắp xếp `created_at DESC, id DESC`, total/items chung snapshot, `no-store`, không ghi audit cho GET.

ADMIN chỉ user create/role/status và scoring-default change đã được ghi; HR chỉ create/update tổ chức, chu kỳ/KPI/phân công/phản hồi và calculate/finalize trong nghiệp vụ HR đã được ghi. Task 1 phải liệt kê chính xác từng cặp action/entity từ AuditWriter/service hiện tại để đóng băng allowlist; action mới mặc định ẩn. Không đưa sự kiện AI, auth/password hoặc nội dung nhận xét vào endpoint này. Không cấp full database audit access cho HR/ADMIN qua API.

DTO chỉ có `id`, `action`, `entity_type`, `entity_id`, `created_at`. Không raw metadata, actor identity, request_id, prompt/output/hash/token. Không endpoint sửa/xóa audit, export hoặc trang UI audit mới trong Phase 9. Dùng bảng AuditLog hiện có; chỉ thêm index nếu EXPLAIN/đo truy vấn chứng minh cần.

## 7. E2E, AI và dữ liệu kiểm tra

Tạo stack Compose thử nghiệm riêng với volume/cổng riêng, APP_ENV=test và Gemini tắt. Luồng UI cần thực hiện thật: ADMIN cấp tài khoản → HR tạo hồ sơ/chu kỳ/KPI → reviewer gửi → quản lý tính → thay dữ liệu thấy stale → tính lại → HR chốt/đóng → dashboard phản ánh đúng → role khác bị chặn. Kiểm tra lỗi xác nhận/409 giữ input, không tự phát sinh POST khi mở/tải lại trang.

Provider giả/SDK MockTransport chỉ ở test runner hoặc dependency override trong test app, không thêm cờ fake-provider vào runtime. PUBLIC/HR_PRIVATE, timeout, quota, output sai, lease/replay/fence, stale và quyền bị thu hồi đều phải có bằng chứng offline. E2E trình duyệt đọc fixture đã lưu; tương tác tạo AI chỉ thực hiện trong harness thử nghiệm cô lập, có xác nhận. Không bật Gemini thật hoặc gửi dữ liệu người dùng để đạt gate.

Không seed/reset hoặc kiểm thử ghi vào stack người dùng ở 3000/8000. Dữ liệu/ảnh/log test là hư cấu, không chứa secret; stack có guard tên project trước cleanup. Nghiệm thu nâng cấp dùng database có evidence/AI trước Phase 9, so sánh bản ghi trước/sau migration/restart; không sửa nội dung historical scoring/AI. Downgrade chỉ ở database disposable và không xóa dữ liệu nghiệp vụ cũ.

## 8. Đo hiệu năng và điều kiện hoàn thành

Dataset đo riêng: 1.000 hồ sơ, 20 phòng ban, 2 chu kỳ, khoảng 2.000 lượt tham gia, 10.000 KPI được giao, phản hồi/báo cáo/tư vấn giả có số lượng ghi rõ. Không dùng production demo seed để xây dataset này. Đo GET dashboard, AI list và audit list với đủ role, trang đầu/trang sau và scope nhỏ/lớn; thu SQL count và EXPLAIN khi cần. Đo 5 client đồng thời trong 60 giây sau warm-up, báo số request, lỗi, p50/p95/max, máy/CPU/RAM/DB/image/commit và cách chạy lại.

Không đặt SLA p95 tùy ý trước khi có baseline. Gate cứng: kết quả đúng quyền, không 5xx ngoài lỗi được chủ động inject, không leak/timeout/treo, query count không tăng tuyến tính theo số dòng và payload/phân trang giữ giới hạn. Nếu đo cho thấy query chậm, sửa có bằng chứng rồi đo lại; chỉ thêm index/migration liên quan, không thay kiến trúc. CI thông thường dùng assertion đúng dữ liệu/bounded queries; bài đo thời gian tách khỏi runner chia sẻ để tránh gate dao động.

Phase 9 chỉ hoàn thành khi mọi finding được phân loại và đóng/ghi lý do chấp nhận rõ, các thay đổi có test hồi quy, full suite PostgreSQL + chất lượng/build + Docker/E2E/migration đạt, có kết quả 5 lượt race và baseline đo tải, tài liệu vận hành/threat matrix/báo cáo được cập nhật. Không gọi kế hoạch hoặc số lượng test dự kiến là kết quả đã chạy. Kết luận chỉ áp dụng cho phiên bản và môi trường có bằng chứng, không phải chứng nhận bảo mật.
