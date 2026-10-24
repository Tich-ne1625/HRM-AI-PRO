# Ma trận bảo mật Phase 9

Mốc kiểm kê 24/10/2026, baseline `88700d8`. Đây là review trực tiếp, không phải review độc lập hoặc chứng nhận. [Danh sách HTTP operations](phase-9-route-inventory.json) ghi method/path/policy alias/source để đối chiếu toàn bộ router; scope nghiệp vụ và test tham chiếu bên dưới. Các finding chỉ đóng khi có test/evidence, không suy ra an toàn từ menu ẩn.

## Quyền và boundary

| Nhóm route | Quyền đọc | Quyền ghi / kiểm tra thêm | Test kế thừa |
| --- | --- | --- | --- |
| health/live, ready | Public; ready chỉ DB/migration, không Gemini | Không ghi | unit health, integration readiness, container contract |
| auth/login | Public; Origin đúng, limiter trước Argon2 | Login tạo family/audit nguyên tử; không token JSON | auth_login, auth_mutations, auth_end_to_end |
| auth/me, refresh/logout/password | Phiên còn hiệu lực, role/status hiện tại | Origin + CSRF family-bound; rotation/replay/revoke, absolute expiry | auth_me, auth_refresh, auth_mutations |
| users GET/POST/PATCH | ADMIN; DTO user an toàn | ADMIN dưới lock, giữ ADMIN cuối; role/status revoke sessions | users_api, last_admin_concurrency |
| departments/positions GET | HR toàn bộ; manager/self scope từ nhân viên hiện tại | HR create/update; reference active và mã duy nhất | organization_api/end_to_end/concurrency |
| employees GET/detail | HR toàn bộ; MGR bản thân/direct reports; EMP bản thân | HR create/update/link; guard reporting tree và tài khoản liên quan | employees_api, organization_concurrency |
| account lookup | HR; chỉ match được phép cho liên kết | Không ghi; không mở user listing cho HR | employees_api |
| settings/scoring GET/PATCH | ADMIN | ADMIN expected version; chỉ tác động kỳ tương lai | scoring_settings |
| kpis definitions GET/POST/PATCH | HR toàn bộ; scope definitions qua KPI được giao cho người đọc | HR, expected version, retire thay vì xóa | kpi_definitions, kpi_scope |
| review cycles GET/detail/participants | HR toàn bộ; MGR/EMP có người tham gia thuộc scope, không DRAFT | HR draft/enroll/remove/activate; close khi mọi người đã chốt | cycle_scope, cycle_activation, review_security |
| allocation/options/actual | Employee + cycle scope trong SQL, snapshot sau activation | HR/eligible direct manager; không sửa mình; ACTIVE/chưa chốt, evidence version | employee_kpis, kpi_concurrency |
| feedback inbox/detail | Chính reviewer lịch sử; HR administration theo tham số đã kiểm tra | HR create/change/cancel/reopen/replace; chỉ reviewer gửi, một lần, deadline/version | feedback_security/workflows/concurrency |
| feedback context/options/coverage/admin | HR | Không suy ra từ quyền reviewer hoặc ADMIN | feedback_security/confidentiality |
| feedback summary | HR/MGR/EMP cùng employee/cycle scope | Suppression nhóm nhỏ; chỉ nhận xét mình gửi; không tự tính missing=0 | feedback_confidentiality, performance_privacy |
| performance/readiness/revisions | HR/MGR/EMP resource scope, version history | Calculate HR/eligible MGR; finalize/close chỉ HR; đủ evidence + CAS + lock | performance_security/concurrency/privacy |
| AI state/history/detail/directory | PUBLIC theo report scope; HR_PRIVATE chỉ HR trước count | HR generate, explicit intent/version, lease/fence/cooldown; không lock khi gọi mạng | ai_workflows, ai_contracts/provider, ai_reports |
| dashboard/activity | ADMIN account DTO; HR/MGR/EMP scoped aggregate | GET snapshot/no-store, không provider/audit/write | dashboard, ai_reports |
| audit-logs (Phase 9) | ADMIN/HR action/type allowlist riêng | Read-only, metadata projection tối thiểu, no-store | test_audit_reader mới |

Mọi domain mutation giữ exact Origin và CSRF/session revalidation dưới lock; malformed input không được ghi một phần. Kiểm tra UUID ngoài scope và không tồn tại có cùng 404; 403 dành cho chức năng không được cấp. GET đang chạy có snapshot semantics, request mới sau revoke dùng quyền mới.

## Allowlist audit đọc đã đóng băng

ADMIN: `(user.created,user)`, `(user.role_changed,user)`, `(user.status_changed,user)`, `(scoring_defaults.updated,system_config)`.

HR: create/update cho `department`, `position`, `employee`, `kpi_definition`, `review_cycle`; `review_cycle.activated/closed` → review_cycle; `cycle_participant.enrolled/removed` và `kpi_allocation.replaced` → cycle_participant; `employee_kpi.actual_updated` → employee_kpi; `assignment.created/updated/cancelled/reopened/replaced` và `feedback.submitted` → feedback_assignment; `performance.calculated/finalized` → performance_review.

Đối chiếu action/type từ services hiện tại; action mới mặc định ẩn. Không user.bootstrap/demo/password, auth, AI; DTO không actor/request/metadata/hash/comment. Source chính xác là allowlist trong `modules/audit/router.py`; test phải kiểm tra cả sai cặp entity để không lọt event chỉ vì action giống.

## Finding ledger

| ID | Bằng chứng / ảnh hưởng | Sửa và regression dự kiến | Trạng thái |
| --- | --- | --- | --- |
| P9-01 | API client chỉ có refresh generation, không chặn response của tài khoản cũ sau transition; nghi ngờ cross-session cache | Session epoch/abort và test deferred response/late refresh/logout | Đang kiểm chứng |
| P9-02 | Nhiều list render query.data dù refetch lỗi; dữ liệu cũ/form có thể còn trên DOM sau mất quyền | Hide cached data on error; AuthProvider bỏ query/state khi identity/role đổi; tests revoked refetch | Đang kiểm chứng |
| P9-03 | Error handler không đặt no-store trên mọi response lỗi | API boundary + error handler headers; test 401/403/404/422/429/500 | Đang kiểm chứng |
| P9-04 | Không có body cap trước JSON parse/domain work | ASGI byte cap 128 KiB, chunked/missing header/forged length tests, 413 không ghi | Đang kiểm chứng |
| P9-05 | Login không có hạn mức chung worker trước verify | PostgreSQL HMAC buckets + migration/cleanup; atomic reservation/expiry/503/no secret tests | Đang kiểm chứng |
| P9-06 | Web chưa có CSP nonce/security headers tường minh | Per-request nonce, dynamic HTML, no unsafe-eval production; thực kiểm tra hydration qua browser | Đang kiểm chứng |
| P9-07 | Kiến trúc có audit read API nhưng chưa có router ở baseline | Scoped projection API + count/UUID/action/entity/snapshot tests | Đang kiểm chứng |
| P9-08 | Chưa có baseline đo tải 1.000 hồ sơ; UI Phase 8 chủ yếu đọc | Isolated E2E có ghi + upgrade/persistence + 5 race rounds + benchmark có cấu hình/counts | Chưa nghiệm thu |

## Thay đổi vận hành được chọn

Migration `20261024_0008` chỉ thêm auth_login_limits, không thay family/scoring/evidence/AI. Config: body 131072 bytes, login 10 lượt/300 giây; HMAC dùng signing key và domain prefix, DB statement time ổn định trong một reservation. Cleanup TTL bằng CLI bounded; không tin forwarded IP hoặc gọi đây là chống DDoS. CSP theo [Next.js nonce](https://nextjs.org/docs/app/guides/content-security-policy); inline styles vẫn cần cho layout/runtime, script dùng nonce, unsafe-eval chỉ development. Proxy không cấp quyền, API tiếp tục là nơi quyết định quyền.
