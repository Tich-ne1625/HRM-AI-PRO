# Kế hoạch Phase 3 — Tổ chức và hồ sơ nhân viên

Trạng thái: schema, API và giao diện đã triển khai; đang nghiệm thu CI Linux. Hợp đồng chi tiết tại `docs/phase-3-contract.md`.

Tham chiếu: `docs/architecture.md`, đặc biệt Database ERD, Role and scope policy và REST API map. Nền tảng đầu vào là Phase 2: xác thực cookie, user hiện tại, role policies, ADMIN quản lý tài khoản, audit cùng giao dịch và client API cùng origin.

## Kết quả cần đạt

HR quản lý phòng ban, chức danh và hồ sơ nhân viên. MANAGER chỉ đọc hồ sơ của bản thân và nhân viên báo cáo trực tiếp. EMPLOYEE chỉ đọc bản thân. ADMIN không tự có quyền HR. User có thể liên kết tối đa một employee; `/auth/me` trả `employee_id` thật sau khi được liên kết. Không có KPI, chu kỳ đánh giá, phản hồi, chấm điểm, Gemini, seed hoặc dashboard trong phase này.

## 1. Chốt hợp đồng và kiểm tra điểm nối

- [x] Đọc trạng thái migration, auth context, user policies, audit allowlist, cấu trúc lỗi và UI sau Phase 2; ghi lại baseline test.
- [x] Chốt giới hạn chiều dài mã/tên, enum `employment_status`, quy tắc chuẩn hóa mã và hành vi khi tham chiếu dữ liệu đã nghỉ hoạt động trước khi viết migration. Không suy diễn thêm quy trình nghỉ phép hoặc payroll.
- [x] Mô tả payload, mã lỗi, phân trang, bộ lọc và allowlist sort cho ba nhóm endpoint. Quy định trả 404 khi user ngoài phạm vi đoán UUID hồ sơ, tránh tiết lộ sự tồn tại.
- [x] HR đọc toàn bộ; MANAGER/EMPLOYEE chỉ thấy department/position được tham chiếu bởi hồ sơ trong phạm vi của họ. User chưa liên kết employee nhận danh sách rỗng và không có quyền theo cây báo cáo.
- [x] Xác định thứ tự khóa dùng chung cho cập nhật liên kết user và cây quản lý; mọi writer phải tuân thủ cùng thứ tự.

## 2. Migration và repository

- [x] Viết test PostgreSQL thất bại trước khi tạo migration `20261019_0003_organization`.
- [x] Thêm module `organization` cho Department/Position và `employees` cho Employee; đăng ký metadata trong `app.models`.
- [x] Department: UUID, code duy nhất, name, is_active, timestamp UTC. Position: UUID, code duy nhất, title, is_active, timestamp UTC.
- [x] Employee: UUID, employee_code duy nhất, display_name, department/position FK, manager FK nullable, user FK unique nullable, employment_status và timestamp UTC.
- [x] Thêm CHECK manager khác employee; FK RESTRICT và index phục vụ department/manager/user lookup. Không tạo hard-delete hoặc delete cascade xóa lịch sử.
- [x] Kiểm tra upgrade/downgrade trên database dùng riêng, sole Alembic head và metadata parity. Chỉ cập nhật fixture cleanup cho các bảng đã biết, giữ guard `_test`.

## 3. Phân quyền theo đối tượng và liên kết tài khoản

- [x] Viết test user khác đoán UUID, manager ngoài phạm vi, manager nhìn cấp dưới gián tiếp, ADMIN truy cập endpoint HR và user chưa có employee.
- [x] Dùng user/role hiện tại trong DB; xây policy scope có thể áp dụng trực tiếp vào query danh sách và detail, không lấy toàn bộ dữ liệu rồi lọc ở frontend.
- [x] HR được tạo/sửa; MANAGER đọc self + direct reports; EMPLOYEE đọc self. Không lấy manager_id hoặc user_id từ client làm bằng chứng quyền.
- [x] Liên kết user–employee do HR thực hiện, kiểm tra user tồn tại và ràng buộc một-một bằng UNIQUE. Hai giao dịch cùng liên kết một user chỉ một giao dịch thành công, lỗi còn lại là 409 ổn định.
- [x] Cập nhật `CurrentUser.employee_id` và `/auth/me`, bỏ giả định luôn null trong test/tài liệu. Không đưa hồ sơ nhân viên đầy đủ vào access token hoặc cookie.

## 4. API phòng ban và chức danh

- [x] Viết test CRUD trong phạm vi phase trước mã triển khai: GET/POST `/api/v1/departments`, PATCH `/{id}`; tương tự `/positions`.
- [x] GET phân trang, bộ lọc trạng thái và sort allowlist. POST/PATCH chỉ HR, có exact Origin và CSRF gắn với family còn hoạt động.
- [x] Duplicate code trả 409, UUID không tồn tại trả 404, payload không hợp lệ trả 422. API lỗi không chứa thông tin SQL nội bộ.
- [x] Nghỉ hoạt động reference data thay vì xóa; giữ tham chiếu hiện hữu, quy định rõ việc gán mới vào record đã nghỉ hoạt động.
- [x] Mutation và audit commit cùng transaction; rollback khi audit lỗi. Chỉ thêm metadata tối thiểu theo allowlist cụ thể cho tổ chức, không truyền nguyên request body vào audit.

## 5. API nhân viên và cây quản lý

- [x] Viết test GET/POST `/api/v1/employees`, GET/PATCH `/{id}` cho từng role và từng phạm vi.
- [x] Tạo/cập nhật hồ sơ, lọc department/status và phân trang; trả JSON allowlist, không lộ password hoặc session của user liên kết.
- [x] Kiểm tra self-management và vòng lặp nhiều cấp khi đổi manager; quyền đọc dùng quan hệ hiện tại, không suy diễn lịch sử chu kỳ chưa có.
- [x] Kiểm thử PostgreSQL hai yêu cầu đồng thời A quản lý B và B quản lý A, cùng trường hợp vòng lặp ba node. Khóa một điểm chung cho mọi thay đổi cây (ví dụ advisory transaction lock có khóa cố định) rồi đọc lại quan hệ trong transaction; khóa riêng từng employee chưa đủ ngăn write skew.
- [x] Kiểm thử đồng thời trùng employee_code/user link và thay đổi department/position đang bị retire. Mọi mutation có audit nguyên tử và mã lỗi ổn định.

## 6. Giao diện tiếng Việt

- [x] Viết behavior test trước component: danh sách nhân viên có lọc/phân trang, trang chi tiết, form HR tạo/sửa, quản lý reference data.
- [x] Dùng `apiFetch`, TanStack Query, React Hook Form/Zod hiện có; luôn coi backend là nơi quyết định quyền.
- [x] Dùng loading/error/empty state rõ ràng, label/bàn phím, trạng thái chờ và xác nhận thao tác nghỉ hoạt động. Không hiển thị form HR cho role khác; backend vẫn kiểm tra độc lập.
- [x] Khi thay đổi user–employee link hoặc manager, invalidate query liên quan và identity hiện tại. Không giữ dữ liệu của tài khoản cũ sau logout/login.
- [x] Không vẽ số liệu hiệu suất, biểu đồ hoặc AI giả trước các phase tương ứng.

## 7. Nghiệm thu và bàn giao

- [x] E2E PostgreSQL: bootstrap ADMIN → tạo HR/MANAGER/EMPLOYEE qua API user → HR tạo tổ chức/hồ sơ và liên kết → xác nhận `/me` → kiểm tra scope bằng các tài khoản thật → đổi quan hệ → scope đổi ngay.
- [x] Chạy đầy đủ backend test, Ruff/mypy; frontend test/lint/typecheck/build; Compose config; sole migration head và clean image checks.
- [ ] CI Linux khởi động volume sạch, chạy cả ba migration, kiểm tra luồng tổ chức qua web proxy và dữ liệu còn sau restart.
- [ ] Cập nhật README Việt/Anh, API/database/deployment và trạng thái architecture chỉ cho artifact đã kiểm chứng.
- [ ] Review bảo mật chú trọng UUID ngoài phạm vi, liên kết giả, cycle/write skew, stale permissions và audit rollback. Chỉ chuyển sang Phase 4 sau khi gate Phase 3 sạch.

Thực hiện từng mục nhỏ có test trước, commit riêng và ghi bằng chứng xác minh. Không thêm bảng hoặc tính năng của phase sau trong quá trình triển khai kế hoạch này.
