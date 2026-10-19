# Hợp đồng Phase 3: tổ chức và hồ sơ nhân viên

Triển khai theo kế hoạch `superpowers/plans/2026-10-19-phase-3-organization.md`. Giữ nguyên modular monolith, auth cookie/CSRF và các ranh giới role của Phase 2.

## Dữ liệu và quy tắc

- Department: UUID, `code`, `name`, `is_active`, timestamp UTC. Position: tương tự với `title`.
- Mã department/position/employee: trim, viết hoa ASCII, regex `[A-Z0-9][A-Z0-9_-]{1,31}`; unique theo từng loại và CHECK chuẩn hóa trong DB. Tên/display name được trim, 1–200 ký tự không trắng.
- Employee: `employee_code`, `display_name`, department/position FK bắt buộc, manager FK nullable, user FK unique nullable, `employment_status` enum `ACTIVE|INACTIVE`, timestamp UTC. Không có trường payroll/nghỉ phép hoặc thông tin cá nhân bổ sung.
- Không xóa cứng; FK RESTRICT. Nghỉ hoạt động reference data hoặc manager vẫn giữ các liên kết hiện hữu. Tạo mới/đổi liên kết chỉ được chọn department/position và manager đang hoạt động; cập nhật trường khác không bắt buộc thay liên kết cũ.
- Trạng thái việc làm độc lập với `users.is_active`; đổi employment status không tự khóa tài khoản. Quyền vẫn dựa trên role/user đang hoạt động và quan hệ hiện tại.
- HR có thể liên kết/bỏ liên kết tài khoản tồn tại; một user gắn tối đa một employee. Liên kết không thay role, mật khẩu hay trạng thái user. `/auth/me`, login/refresh và user JSON trả employee_id thực tế, không có hồ sơ đầy đủ trong JWT.

## API và quyền

| Endpoint `/api/v1` | Quyền/hành vi |
| --- | --- |
| GET/POST `/departments`, PATCH `/departments/{id}` | HR đọc/ghi tất cả; MANAGER/EMPLOYEE chỉ đọc danh sách reference data thuộc employee trong phạm vi |
| GET/POST `/positions`, PATCH `/positions/{id}` | Tương tự phòng ban |
| GET/POST `/employees`, GET/PATCH `/employees/{id}` | HR đọc/ghi tất cả; MANAGER đọc self + direct reports; EMPLOYEE đọc self |
| GET `/employees/linkable-users?email=...` | Chỉ HR, tra cứu **đúng email** để liên kết tài khoản; trả id/email/is_active/employee_id. Không cho HR truy cập API quản trị users hoặc duyệt toàn bộ tài khoản |

ADMIN không tự có quyền HR. User chưa liên kết employee nhận danh sách scoped rỗng. Không tin manager_id/user_id từ client làm bằng chứng quyền. Detail ngoài phạm vi trả `404 employee_not_found`; query danh sách và count cùng áp dụng scope ở SQL.

Danh sách trả `{items,total,page,page_size}`, page >=1, page_size 1–100, sort tăng dần có UUID tie-breaker. Department sort code/name/created_at/is_active; position code/title/created_at/is_active. Employee sort employee_code/display_name/created_at/employment_status, lọc department_id/position_id/employment_status và tìm q tối đa 100 ký tự. Chuỗi tìm kiếm không được biến thành SQL hoặc sort tùy ý. PATCH từ chối field lạ, payload rỗng hoặc null cho field bắt buộc; manager_id/user_id cho phép null để bỏ liên kết.

Mọi POST/PATCH có exact Origin và CSRF gắn family đang hoạt động. Service đọc lại user/role/family dưới khóa trước mutation; audit và mutation cùng transaction. Lỗi chuẩn: 409 duplicate_code/employee_code_already_exists/user_already_linked; 409 reference_inactive/manager_inactive/reporting_cycle; 404 reference_not_found/user_not_found/employee_not_found; 422 validation_error; lỗi auth giữ contract Phase 2. Không có DELETE.

## Khóa và audit

Mọi writer tổ chức dùng PostgreSQL advisory transaction lock cố định `730031`, rồi khóa active ADMIN theo UUID (cùng thứ tự với user management), rồi các user tham gia theo UUID, cuối cùng các record tổ chức cần sửa. Auth mutation chỉ khóa user của nó rồi session. Không có writer giữ user lock rồi chờ organization guard; việc này tránh chu trình khóa chéo module. Guard serialize số ít mutation tổ chức trong đồ án để ngăn write skew A→B/B→A và cuộc đua reference retirement/user-link. Đọc không dùng guard và luôn scope bằng SQL.

Sau guard, đọc lại toàn bộ cây manager cần kiểm tra trong transaction. Không cho self manager hoặc bất kỳ chu trình nhiều cấp nào. Chứng minh bằng test PostgreSQL với hai session độc lập, không chỉ test tuần tự. Unique constraint là hàng rào cuối cho code và user link.

Audit action: department.created/updated, position.created/updated, employee.created/updated. Metadata chỉ chứa allowlist field thay đổi (`code`, `name`, `title`, `is_active`, `employee_code`, `display_name`, `department_id`, `position_id`, `manager_id`, `user_id`, `employment_status`) với giá trị tối thiểu; UUID chuyển thành chuỗi. Không ghi nguyên payload, email tra cứu, token, cookie, mật khẩu hoặc hash. Test rollback khi audit thất bại.

Giao diện tiếng Việt cho danh sách/chi tiết và form HR, loading/error/empty states, xác nhận nghỉ hoạt động, tìm tài khoản đúng email để liên kết và invalidation cache/identity khi cập nhật. Không tạo seed, KPI, review, dashboard hoặc Gemini trong phase này.
