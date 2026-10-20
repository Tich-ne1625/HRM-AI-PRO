# Kế hoạch Phase 4 — Chu kỳ đánh giá và KPI

Ngày lập: 2026-10-19. Trạng thái: hoàn tất Task 1–8 và nghiệm thu CI Linux ngày 2026-10-20. Runtime được xác minh tại `adcbabe1a77e73042aea7e67552ea510ae450832`.

Nguồn: [kiến trúc](../../architecture.md), [hợp đồng Phase 4](../../phase-4-contract.md), [nghiệm thu Phase 3](2026-10-19-phase-3-organization.md), [vận hành và bằng chứng CI](../../deployment.md). Hợp đồng Phase 4 là nơi quy định nghiệp vụ/API; kế hoạch này quy định trình tự, file dự kiến và gate. Nếu phát hiện mâu thuẫn, sửa tài liệu và test trước khi viết tiếp thay vì tự bỏ điều kiện kiến trúc.

## Đầu vào đã kiểm tra

- [x] Repository clean tại `f1c8021`, main đồng bộ origin/main trước khi lập kế hoạch; runtime gần nhất `8f193b3`.
- [x] Phase 3 đã nghiệm thu CI run [39221690393](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39221690393): 467 backend tests được collect, 49 frontend tests, backend/frontend/docker-smoke thành công theo hồ sơ bàn giao.
- [x] Đọc model/repository/service organization/employees, auth policies, audit allowlist, cấu trúc router và cơ chế khóa chéo user management. Phase 4 chưa có module hoặc migration.
- [x] Kiểm tra nhanh ngày lập kế hoạch: 209 unit backend tests qua; sole Alembic head `20261019_0003`; Ruff và mypy sạch (45 source files); frontend typecheck qua. Không coi đây là chạy lại toàn bộ integration/Docker hoặc kiểm chứng production.
- [x] Xác định phụ thuộc Phase 6: Phase 4 không đóng chu kỳ khi chưa có finalization. Không triển khai feedback/scoring/Gemini/dashboard để làm cho demo có số liệu.

Các kiểm tra trên đủ cơ sở lập kế hoạch tiếp theo; khi bắt đầu code phải chạy baseline có PostgreSQL để phát hiện thay đổi môi trường. Không yêu cầu chạy lại full suite chỉ vì sửa tài liệu.

## Kết quả người dùng có thể nghiệm thu

1. ADMIN xem/sửa scoring defaults cho các lần kích hoạt sau, không truy cập dữ liệu HR.
2. HR tạo chu kỳ nháp, chọn danh sách tham gia, sửa nháp, thấy lý do chưa thể kích hoạt, sau đó kích hoạt nguyên tử và xem snapshot.
3. HR tạo/retire định nghĩa KPI; HR/manager hiện tại phân bổ đầy đủ target/weight và nhập actual đúng phạm vi.
4. EMPLOYEE chỉ xem KPI của bản thân trong chu kỳ chỉ định; manager không tự ghi KPI của mình hoặc cấp dưới gián tiếp.
5. Hai người sửa cùng participant không ghi đè âm thầm; transfer đổi quyền hiện tại nhưng giữ nguyên lịch sử snapshot.

## Trình tự và điểm dừng

Thực hiện Task 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8. Task 7 bổ sung review/race liên module; kiểm thử phân quyền, concurrency và rollback phải được viết ngay trong task có nghiệp vụ tương ứng. Mỗi task có commit riêng khi kiểm tra liên quan qua; không dùng số lượng test cố định làm mục tiêu chất lượng. Ghi rõ người và cách review thực tế trong bằng chứng nghiệm thu.

## Task 1 — Baseline và schema

File dự kiến: `apps/api/app/modules/settings/{models,schemas}.py`, `modules/review_cycles/{models,schemas}.py`, `modules/kpis/{models,schemas}.py`; `app/models.py`; một file mới trong `apps/api/alembic/versions/`; `apps/api/tests/integration/test_review_cycle_schema.py`; fixture cleanup hiện có.

- [x] Chạy full backend với PostgreSQL test riêng trước sửa; xác minh test không bị skip do thiếu TEST_DATABASE_URL, ghi baseline và revision đang chạy. Không sử dụng DB làm việc làm test DB.
- [x] Viết test schema thất bại trước: singleton config; enum/CHECK; FK RESTRICT; unique employee/cycle và participant/definition; partial unique một ACTIVE; precision; sole migration chain; metadata parity.
- [x] Tạo năm bảng trong hợp đồng và CHECK/index cần thiết, initial policy 70/30 cap 100.00. Không tạo PerformanceReview, FeedbackAssignment hoặc dữ liệu demo.
- [x] Chốt DTO snapshot có version schema, UUID serialized rõ ràng; snapshot private tách DTO công khai. DRAFT chưa có snapshot chính thức.
- [x] Validation Decimal string, bounds/scale, control characters, extra fields, expected versions dương; không round/float ngầm.
- [x] Kiểm tra upgrade từ Phase 3 giữ nguyên users/employees/audits; upgrade từ DB sạch; downgrade/upgrade chỉ trong DB dùng riêng, `_test` guard vẫn hoạt động.
- [x] Xác minh tất cả model được import vào metadata; cập nhật fixture cleanup theo FK, không tắt constraint hoặc drop bảng tùy ý.

Gate: schema tests + readiness/auth smoke có PostgreSQL, Ruff/mypy; Alembic một head, không drift. Commit dự kiến `feat(cycles): add cycle and KPI schema`.

## Task 2 — Scoring defaults và catalog KPI

File dự kiến: `modules/settings/{repository,service,router}.py`, `modules/kpis/{repository,service,router}.py`; authorization helper gần `app/core/policies.py`; `modules/audit/service.py`; `app/main.py`; `tests/integration/test_scoring_settings.py`, `test_kpi_definitions.py` và unit schema tests.

- [x] Viết test trước cho ADMIN-only settings, HR-only definition mutations, role denied, unlinked account, SQL-scoped list/count, inactive definitions, code normalization/uniqueness.
- [x] Settings GET/PATCH dùng expected_version, validate exact component sum/cap, optimistic conflict; GET không làm thay đổi DB.
- [x] KPI GET/POST/PATCH có q/status/direction, sort allowlist và phân trang; lỗi 404/409/422 ổn định, không DELETE.
- [x] Catalog của manager/employee chỉ thấy định nghĩa được gán trong scope; chưa được gán thì empty. Chuẩn bị query options riêng theo participant ở Task 5.
- [x] Tạo helper khóa/revalidate dùng allowed roles rõ ràng theo hợp đồng. Kiểm thử endpoint HR cũ vẫn HR-only; không tái sử dụng cứng hàm chỉ cho HR rồi vô tình mở quyền.
- [x] Audit allowlist riêng cho settings/KPI, version và mutation atomic; inject audit failure để chứng minh rollback.
- [x] Race cùng expected_version của defaults/definition chỉ một writer thắng; duplicate code có một 201 và một 409, không 500.

Gate: focused tests + auth/organization authorization regression, Ruff/mypy. Commit dự kiến `feat(kpis): add definitions and scoring defaults`.

## Task 3 — Chu kỳ nháp, enrollment và scope

File dự kiến: `modules/review_cycles/{repository,service,router}.py`; `app/main.py`; `tests/integration/test_review_cycles.py`, `test_cycle_scope.py`.

- [x] Test HR tạo/sửa DRAFT, start <= end, version conflict, batch enrollment atomic, duplicate trong payload/DB, employee inactive, batch size 1–100 và pagination nhiều batch.
- [x] Thêm GET/POST cycles, GET/PATCH detail, GET/POST participants, DELETE participant DRAFT theo contract. Client không tự đặt status hoặc snapshots.
- [x] DRAFT chỉ HR; ACTIVE/CLOSED manager/employee chỉ thấy cycle có participant trong phạm vi. Count cũng scope; không lộ danh sách quan hệ/user IDs từ JSON snapshot.
- [x] Test self/direct report/indirect report, UUID ngoài scope, unlinked account, ADMIN và chuyển manager. Phân biệt cycle_id/participant_id/employee_id trong operation ID và client types.
- [x] Cycle version tăng khi sửa metadata/enroll/remove thành công; no-op không tăng; error không để lại participant/audit/version dở dang.
- [x] Viết race enrollment/removal/update cùng version, test rollback audit khi xóa participant nháp. ACTIVE/CLOSED từ chối mọi chỉnh danh sách.

Gate: cycle/scope tests + Phase 3 regression, Ruff/mypy. Commit dự kiến `feat(cycles): add draft enrollment and scoped reads`.

## Task 4 — Kích hoạt và đóng băng lịch sử

File dự kiến: service/repository/schema review_cycles, settings policy reader, employee relationship snapshot query; `tests/integration/test_cycle_activation.py`, `test_cycle_concurrency.py`.

- [x] Test activation thiếu participant, inactive employee/reference, thiếu SELF hoặc manager account, inactive account, manager không hợp lệ; trả issue list có giới hạn và tổng số cho HR.
- [x] Implement POST activate với expected_version, đọc lại policy/account/cây hiện tại dưới khóa; snapshot cả cấp dưới không tham gia chu kỳ; không tạo feedback assignment.
- [x] Snapshot/policy/status/version/audit commit cùng transaction. Test lỗi participant cuối và audit failure không để lại snapshot hoặc ACTIVE một phần.
- [x] DB partial unique đảm bảo một ACTIVE; hai chu kỳ cùng kích hoạt chỉ một thành công, bên còn lại 409. Kích hoạt lặp không tạo thêm snapshot/audit thành công.
- [x] Race activation với scoring-default update, đổi manager, user link, reference retirement và account deactivation: kết quả tương ứng một thứ tự commit hợp lệ, không deadlock hoặc dữ liệu trộn.
- [x] Sau activation sửa tổ chức/defaults, chứng minh snapshot cũ giữ nguyên còn quyền đọc dùng quan hệ hiện tại. Account bị khóa sau activation không còn quyền authenticated.
- [x] DRAFT metadata không sửa sau ACTIVE; không đăng ký `/close` hoặc cơ chế hạ ACTIVE về DRAFT. UI giải thích giới hạn đến Phase 6.

Gate: activation/atomicity/concurrency tests có hai session PostgreSQL độc lập, timeout bắt deadlock; Ruff/mypy. Commit dự kiến `feat(cycles): freeze policy and relationships on activation`.

## Task 5 — Phân bổ đầy đủ KPI và nhập actual

File dự kiến: kpis repository/service/router/schemas, participant-lock helper; `tests/integration/test_employee_kpis.py`, `test_kpi_scope.py`, `test_kpi_concurrency.py`.

- [x] Test GET allocation, options lookup scoped và current manager writer; manager chỉ đọc self, không ghi self/indirect/outside scope; HR không cần employee profile.
- [x] Test allocation trống ban đầu; PUT rỗng/duplicate/weight sai tổng, zero/negative target, overprecision, bool/NaN/Infinity và quá 100 items đều bị từ chối.
- [x] PUT reconcile full allocation trong một transaction dưới participant lock/version; snapshot định nghĩa mới, giữ snapshot cũ; map retired/missing definition và cap incompatibility đúng lỗi.
- [x] Chứng minh giữ target giữ actual, đổi target clear actual, đổi weight giữ actual, bỏ/gán lại lấy snapshot mới. Audit failure khôi phục cả dòng bị xóa và evidence_version.
- [x] PATCH chỉ nhận actual + expected_evidence_version, actual 0 hợp lệ và null để clear; không nhận target/weight/snapshot/cycle_id tùy ý trong body.
- [x] Mọi evidence mutation tăng chung participant version một lần; stale version không cập nhật dữ liệu. No-op vẫn check quyền/version/status, không tăng version.
- [x] Race PUT/PUT, PUT/PATCH actual, hai actual trên hai dòng của cùng participant: chỉ một request cùng expected version thắng. Race khác participant không tạo deadlock; chấp nhận serialize guard ở quy mô đồ án.
- [x] Test transfer/deactivation trong lúc chờ guard; revalidate current actor/family/direct-report trước mutation. Chứng minh không có đường nhận scope từ body.
- [x] DRAFT/CLOSED/finalized participant không ghi được; retirement định nghĩa không phá actual của dòng đã gán. Không trả score hoặc gọi calculator.

Gate: KPI/schema/scope/concurrency tests + auth/organization regressions, Ruff/mypy. Commit dự kiến `feat(kpis): add atomic allocations and actual entry`.

## Task 6 — Giao diện tiếng Việt

File dự kiến: `apps/web/src/features/cycles/`, `features/kpis/`, `features/settings/`; routes dưới `src/app/(protected)/review-cycles/`, `kpis/`, `employees/[id]/kpis/`, `settings/scoring/`; navigation hiện có và feature behavior tests.

- [x] Tạo typed client cho cycle/participant/definition/allocation/policy, số Decimal là string; query key luôn có cycle/employee/filter/page phù hợp.
- [x] HR list/detail/create/edit DRAFT, employee selector tìm kiếm/phân trang, add/remove, activation confirmation + actionable server errors, policy preview/snapshot phân biệt rõ.
- [x] HR catalog định nghĩa tạo/sửa/retire; ADMIN settings form versioned. Không mở route HR chỉ vì role ADMIN hoặc ghi mặc định từ form HR.
- [x] Allocation editor chọn từ options scoped; tổng weight tính chính xác bằng đơn vị phần trăm nhỏ nhất hoặc Decimal string helper, không cộng float; cho chỉnh nháp chưa đủ 100 nhưng không gửi PUT đến khi hợp lệ.
- [x] Actual editor phân biệt null/0; cảnh báo đổi target xóa actual. Employee/manager-self chỉ đọc, cycle ID hiển thị rõ, không nút đóng chu kỳ hoặc điểm giả.
- [x] Loading/error/empty, labels/keyboard, pending, giữ form khi API lỗi; 409 không tự retry bằng version mới. Invalidate các query bị ảnh hưởng khi thành công; giữ auth cache isolation.
- [x] Behavior tests: vai trò, chọn nhiều trang không mất lựa chọn, thiếu điều kiện activation, tổng weight, version conflict giữ input, mutation error giữ form và query invalidation sau thành công.

Gate: frontend tests, ESLint, TypeScript, production build; rà luồng trên màn hình hẹp và bàn phím. Commit dự kiến `feat(web): add Vietnamese cycle and KPI workflows`.

## Task 7 — Review bảo mật và tích hợp

File dự kiến: integration tests luồng tài khoản thật và concurrency; tài liệu bằng chứng review. Sửa code tại module gây lỗi nếu phát hiện, có regression test chứng minh.

- [x] E2E: bootstrap ADMIN → tạo HR/manager/employee accounts → HR lập tổ chức/liên kết → ADMIN sửa defaults → HR tạo cycle/enroll/activate → manager phân bổ/nhập actual → employee đọc; thử UUID ngoài scope bằng các session thật.
- [x] Transfer nhân viên: manager cũ mất quyền, manager mới nhận quyền, snapshot vẫn cũ; thay link/inactive/role và dùng access token trước đó để kiểm tra DB authority hiện tại.
- [x] Review mọi writer cùng lock order, không deadlock với user management/auth/organization; scoped counts và errors không lộ resource.
- [x] Mutation thiếu/sai Origin/CSRF, family revoked, payload extra/forged scope đều từ chối; audit không có body/snapshot/free-text/credential.
- [x] Chạy các race quan trọng ít nhất 5 lượt bằng PostgreSQL với barrier và giới hạn timeout; ghi từng kịch bản/kết quả thay vì chỉ tổng số pass.
- [x] Kiểm tra audit rollback của activation, allocation replacement, actual và config; snapshot private không xuất hiện trong scoped DTO ngoài allowlist.
- [x] Ghi rõ review trực tiếp hay reviewer độc lập thực tế; xử lý phát hiện nghiêm trọng trước Task 8, không tự nhận đã có independent review.

Gate: không còn lỗi phân quyền, lost update, snapshot không nhất quán, deadlock hoặc atomicity chưa giải quyết. Commit dự kiến `test(cycles): verify authorization and concurrent evidence updates`.

## Task 8 — Nghiệm thu, tài liệu và CI

File dự kiến: `scripts/smoke_auth.py` (hoặc script domain riêng được gọi từ cùng workflow), `.github/workflows/phase1-ci.yml`, container-contract tests, README Việt/Anh, `docs/{api,database,deployment,architecture}.md`, kế hoạch/hợp đồng này.

- [x] Full backend suite với TEST_DATABASE_URL đúng DB test, không skip integration; Ruff/mypy. Frontend toàn bộ tests/lint/typecheck/build. Không nâng dependency nếu không có lý do gắn với task.
- [x] Docker Compose config + Linux CI clean stack áp migration mới, API ready theo head mới, proxy HTTP thật cho role/scoped cycle/allocation/actual flow; không chỉ mock route.
- [x] Update container migration expectations theo sole head thực tế; images vẫn nonroot, runtime không chứa tooling/secrets. Password tạo trong memory/stdin theo smoke hiện tại.
- [x] Restart PostgreSQL, đọc revision và persisted cycle/participant/allocation/actual trước khi migration chạy lại; không xóa volume chứa dữ liệu làm việc. Kiểm tra fresh install và upgrade từ Phase 3 bằng môi trường dùng riêng.
- [x] Nếu local Docker/WSL vẫn unavailable, ghi đúng giới hạn và dùng CI Linux làm bằng chứng; không tự thay đổi cấu hình Windows để chạy Docker.
- [x] README có walkthrough HR/manager/employee/ADMIN, URL, trạng thái “chưa phân bổ/chưa nhập”, xử lý 409 và giới hạn một ACTIVE chưa đóng được đến Phase 6. API/database mô tả artifact đã triển khai, không đưa plan vào phần implemented.
- [x] Ghi commit + URL CI + kết quả thật, review diff và git status. Chỉ đánh dấu Phase 4 hoàn thành sau các gate trên; không suy ra Phase 5 đã làm vì đã có snapshot.

Gate cuối: backend/frontend/docker-smoke thành công và walkthrough tái lập được; không test nào bị skip ngoài lý do được ghi rõ. Commit dự kiến `docs: complete Phase 4 acceptance and runbook`.

## Lệnh kiểm tra dự kiến khi triển khai

PowerShell, từ repository root; TEST_DATABASE_URL chỉ trỏ database dùng riêng có tên kết thúc `_test`, không sao chép URL chứa credential thật vào tài liệu hoặc lịch sử shell.

```powershell
Set-Location apps/api
# Cấp TEST_DATABASE_URL từ môi trường local/test đã cấu hình.
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check app tests
.venv\Scripts\python.exe -m mypy app
.venv\Scripts\python.exe -m alembic heads
Set-Location ../web
npm.cmd test -- --run
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
Set-Location ../..
docker compose --env-file .env.example config --quiet
```

Lệnh upgrade/downgrade và smoke tạo dữ liệu phải chọn rõ môi trường dùng riêng; không thêm lệnh xóa volume hàng loạt vào quy trình bình thường. Baseline Phase 3 vẫn là điểm đối chiếu hồi quy cho auth, role và tổ chức.

## Bằng chứng nghiệm thu ngày 2026-10-20

- Task 1, commit `025b0b6`: baseline PostgreSQL 467/467 qua; 47 test schema/validation và hồi quy schema auth/organization/readiness qua. Sole head `20261020_0004`; metadata parity và downgrade/upgrade bảo toàn dữ liệu Phase 3.
- Task 2, commit `d3623c8`: 14 test settings/catalog mới và 76 test concurrency/hồi quy users/organization/auth/policies qua. Kiểm tra Origin/CSRF, audit rollback, scoped empty lists, no-op và stale version.
- Task 3, commit `8a080dd`: 5 test draft/enrollment/audit rollback và 4 test SQL scope/transfer/concurrency qua. Hai writer cùng version có một 200 và một 409; count và DTO không lộ snapshot riêng tư.
- Task 4, commit `edc459e`: 17 test activation/concurrency qua, gồm hai chu kỳ tranh ACTIVE, defaults/manager/link/reference thay đổi khi activation và account deactivation chéo module. Audit failure rollback toàn bộ participant/policy/status.
- Task 5, commit `93300a0`: 14 test allocation/actual, 7 test KPI concurrency và 6 test scope qua. Request đang chờ bị từ chối sau logout, disable, chuyển manager hoặc đổi role. Audit failure khôi phục dòng và version.
- Task 6, commit `641094d`: 69 frontend test, ESLint/TypeScript và production build qua. Edge headless xác nhận login bằng Enter, HR desktop/390px, điều hướng bàn phím, MANAGER lưu actual qua giao diện, EMPLOYEE chỉ đọc và ADMIN settings; không tràn viewport. Vitest giới hạn 2 worker để tránh quá tải jsdom.
- Task 7, commit `cd559d6`: review trực tiếp, không tự nhận reviewer độc lập. 15 race PostgreSQL qua đủ 5 lượt (22.04s/30.25s/20.79s/31.10s/22.44s). Full suite local trước bổ sung security: 566 qua; 5 test security/real-account bổ sung qua, final collection 570. Kiểm tra cả 10 mutation path với Origin/CSRF/revoked family, SQL scope, audit allowlist và lock order.
- Task 8, runtime commit `adcbabe1a77e73042aea7e67552ea510ae450832`: [InsightHR CI 39356761739](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39356761739) thành công cả **backend (570 test), frontend (69 test) và docker-smoke**. Local Docker cũng qua build/nonroot/runtime inspection, proxy HTTP, Edge và PostgreSQL-only restart/persistence trước khi migration chạy lại. Stack nghiệm thu dùng cổng 13004/18004, không thay stack người dùng 3000/8000, và đã được dừng sau kiểm tra.

README Việt/Anh, API/database/deployment/architecture đã cập nhật. Phase 5 feedback chưa triển khai; đóng chu kỳ vẫn chờ finalization Phase 6.
