# Kế hoạch Phase 5 — Phân công và phản hồi 360

Ngày lập: 2026-10-20. Trạng thái: đang triển khai theo phê duyệt; chưa nghiệm thu Phase 5.

Yêu cầu giao diện khi bắt đầu: tận dụng các trang hiện có, phân bổ hợp lý trên desktop/mobile. Triển khai dùng chung navigation theo nhóm nghiệp vụ, menu thu gọn trên màn hẹp, bảng cuộn trong khung, form và panel co giãn; nối quản trị/tổng hợp phản hồi ngay từ người tham gia chu kỳ. Không thêm thư viện UI.

Baseline mới trên PostgreSQL riêng `_test`: **570 passed**, không skip, 533,71 giây. Các kiểm tra đầu vào, eligibility, mean/suppression, luồng API/UI và N+1 đã được chạy RED trước khi thêm hoặc sửa phần tương ứng; các ca hồi quy bảo mật tiếp tục được bổ sung trong review.

Full regression local sau triển khai: **657 passed**, không skip, 681,34 giây. Ruff/mypy sạch (77 source files), sole head `20261020_0005`, web 83 test/lint/types/build qua trước ba test UI bổ sung. Các test audit/deadline cuối và race-repeat đang chạy; chưa thay thế nghiệm thu CI tại commit runtime cuối. [Review trực tiếp](../../phase-5-review.md) ghi rõ phương pháp và giới hạn, không nhận là reviewer độc lập.

CI đầu tiên tại runtime `5a9f77565f0d27822e947679233d2ccc75ce46c6`: backend/frontend/docker-smoke đều thành công, [run 39369313123](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39369313123). Sau full local 657, các ca audit bổ sung và deadline sau chờ khóa đã qua; năm lượt cạnh tranh đều **26/26**, lần lượt 46,48 / 41,04 / 44,06 / 40,85 / 42,54 giây. Bộ 26 ca gồm 11 feedback và 15 cycle/KPI, dùng cùng guard/shared evidence version.

Đối chiếu cuối bổ sung IDs pending/blocked chỉ trong HR coverage, test chứng minh không lọt vào summary; PEER/SUBORDINATE mặc định tùy chọn trong form và nhãn quá hạn ở inbox/quản trị. 33 test backend liên quan và 16 test UI feedback đều qua sau chỉnh sửa. Cần CI cuối trước khi đánh dấu hoàn tất toàn phase.

Phân chia commit triển khai: schema/eligibility/administration/submission/summary và các test backend được bàn giao cùng một commit backend có đầy đủ luồng dùng được; UI/layout/cache một commit riêng; smoke/CI/runbook và bằng chứng nghiệm thu riêng. Các task vẫn được đối chiếu theo gate, không tách thành commit trung gian có endpoint hoặc test bị thiếu module phụ thuộc.

Tham chiếu: [kiến trúc](../../architecture.md), [hợp đồng đề xuất Phase 5](../../phase-5-contract.md), [nghiệm thu Phase 4](2026-10-19-phase-4-cycles-kpis.md), [vận hành](../../deployment.md). Không coi các mục chưa đánh dấu là tính năng đã có.

## Cơ sở và kết luận đối chiếu

- [x] Repository clean, main đồng bộ origin/main tại `4ada5f9`; runtime Phase 4 `adcbabe` có CI [39356761739](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39356761739), backend 570/frontend 69/Docker smoke qua theo hồ sơ nghiệm thu.
- [x] Đọc trực tiếp activation, participant snapshots/models, scope queries, shared write authorization, allocation writers, audit allowlist và navigation hiện có. Chưa có module/migration feedback.
- [x] Snapshot đã đủ SELF/MANAGER/direct reports, kể cả người không tham gia. Activation chưa tạo assignment; cần HR tạo và theo dõi coverage, không sửa Phase 4 để giả định đã giao đủ.
- [x] Tách quyền current manager đọc summary với reviewer lịch sử gửi assignment. ADMIN có thể là reviewer, không được cấp HR quyền đọc raw hoặc submit thay người khác.
- [x] Chọn cách giữ UNIQUE(participant,reviewer) khi hủy mềm: phục hồi row đã hủy với version mới, không tạo row trùng. Replacement phải nguyên tử và giữ coverage.
- [x] Chốt đề xuất không tự ủy quyền SELF/MANAGER khi account bị khóa; chỉ tài khoản lịch sử được nhận/gửi. Khôi phục account hoặc thay đổi nghiệp vụ riêng nếu cần delegation.

Chỉ thay đổi tài liệu trong lượt lập kế hoạch. Kiểm tra nhanh local và giới hạn sẽ được ghi ở cuối sau khi chạy; khi bắt đầu code cần baseline PostgreSQL thật, không chỉ unit test hoặc số lượng test collect.

## Luồng nghiệm thu cần đạt

HR mở participant ACTIVE → thấy thiếu SELF/MANAGER → chọn reviewer hợp lệ và giao → reviewer mở inbox riêng → gửi rating/comment một lần → HR thấy tiến độ/raw → nhân viên/current manager xem summary có threshold → chuyển manager và vô hiệu hóa account để xác minh quyền hiện tại/historical assignment. Chu kỳ vẫn ACTIVE; tính điểm/finalize/close thuộc Phase 6.

Các quyết định cụ thể cần giữ xuyên suốt: role không thay eligibility; reviewer không cần có quyền report; assignment và feedback cùng participant version; SELF/MANAGER bắt buộc; group PEER/SUBORDINATE dưới ba người bị che; không hứa ẩn danh. Hợp đồng mô tả payload, deadline, replacement/reopen và giới hạn bị chặn bởi account lịch sử.

## Trình tự triển khai

Task 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8. Viết test thất bại có ý nghĩa trước mỗi nghiệp vụ, xác nhận nguyên nhân rồi triển khai nhỏ và kiểm tra. Test concurrency/authorization/rollback thực hiện ngay trong task liên quan; Task 7 bổ sung review xuyên module. Commit từng task khi gate qua; ghi rõ cách review thực tế, không tự nhận reviewer độc lập.

## Task 1 — Baseline, schema và contract types

File dự kiến: `apps/api/app/modules/feedback/{__init__,models,schemas}.py`; `app/models.py`; migration mới trong `apps/api/alembic/versions/`; integration fixture cleanup; `tests/unit/test_feedback_schemas.py`, `tests/integration/test_feedback_schema.py`.

- [ ] Chạy baseline full PostgreSQL với TEST_DATABASE_URL trỏ DB `_test`, xác minh không skip, ghi head/môi trường/570 test đối chiếu. Không đụng DB đang sử dụng.
- [ ] Test schema trước migration: enum/rating CHECK, FK RESTRICT, object JSONB, versions, UTC timestamps, unique feedback/assignment và partial uniqueness SELF/MANAGER chưa CANCELLED.
- [ ] Thêm đúng hai bảng theo hợp đồng, metadata imports và indexes inbox/participant. Không backfill assignment hoặc feedback từ snapshot khi upgrade.
- [ ] Schema input strict rating/versions, comment bounded/control characters, timezone-aware deadline; extra field/forged identity/empty PATCH bị từ chối. DTO riêng cho inbox, HR raw và summary.
- [ ] Khẳng định hai loại snapshot: quan hệ lúc activation và eligibility lúc assignment; không sửa định dạng/giá trị snapshot Phase 4 hoặc dùng current tree thay thế.
- [ ] Clean install và upgrade từ `20261020_0004`, metadata parity, downgrade/upgrade trên DB dùng riêng bảo toàn cycle/KPI/account. Mở rộng cleanup đúng FK, giữ `_test` guard.

Gate: schema/unit/readiness và schema hồi quy Phase 2–4 qua; Ruff/mypy; sole head. Commit dự kiến `feat(feedback): add assignment and submission schema`.

## Task 2 — Eligibility, reviewer lookup và scope độc lập

File dự kiến: `modules/feedback/{repository,eligibility,policies}.py`; unit/integration eligibility/scope tests; điểm nối `core/domain_writes.py` chỉ khi cần.

- [ ] Test SELF/MANAGER dựa trên user/employee snapshot; SUBORDINATE dựa direct_reports snapshot ACTIVE, kể cả không tham gia; PEER dựa active employee/account tại lúc gán và không giả làm quan hệ lịch sử khác.
- [ ] Case role khác EMPLOYEE/MANAGER vẫn hợp lệ nếu được giao đúng principal. ADMIN assigned có quyền riêng, HR không được submit thay reviewer.
- [ ] Đọc inbox/detail bằng `reviewer_id=current user` ở SQL; quản trị riêng HR; summary reuse live employee scope. List/count và missing/outside UUID thống nhất, không lọc sau phân trang.
- [ ] Kiểm tra quản lý cũ ngoài live scope vẫn đọc/gửi assignment; quản lý mới không tự nhận assignment cũ. Link/role/employment đổi không tự chuyển historical principal; account disabled/session revoked luôn bị từ chối.
- [ ] HR lookup có pagination/q literal, không email, không `/users` privilege; account bị khóa hiện lý do đủ để xử lý, không tự chọn người khác cho SELF/MANAGER.
- [ ] Chuẩn hóa thứ tự khóa trước khi writer dùng: guard/admin/users/family/cycle/participant/assignment. Actor/reviewer user locks theo UUID trước domain rows.

Gate: eligibility matrix và UUID/count/DTO tests qua; auth/organization/KPI scope hồi quy không đổi. Commit `feat(feedback): enforce historical reviewer eligibility and scoped reads`.

## Task 3 — HR phân công, coverage và hủy/thay/phục hồi

File dự kiến: `modules/feedback/{service,router,repository,coverage}.py`; audit allowlist; `app/main.py`; tests assignment CRUD/coverage/concurrency/rollback.

- [ ] HR POST tạo OPEN trong ACTIVE/unfinalized, expected_evidence_version bắt buộc; SELF/MANAGER required=true. Chưa có mandatory assignments thì readiness incomplete, không giả định activation đã tạo.
- [ ] PATCH deadline/required hợp lệ, hủy mềm optional OPEN, phục hồi CANCELLED cùng reviewer/relationship/snapshot; chặn mọi chỉnh SUBMITTED. Validate giới hạn 100 active assignments.
- [ ] Giữ UNIQUE kể cả canceled row; POST trùng trả 409 và UI dẫn tới phục hồi. Partial UNIQUE chặn hai SELF/MANAGER; user không được nhận hai quan hệ cho cùng participant.
- [ ] Required cancellation bị chặn. PEER/SUBORDINATE hạ required chỉ bằng PATCH HR có audit; SELF/MANAGER không hạ được. Readiness luôn kiểm tra hai vai trò bắt buộc, không chỉ các row đang tồn tại.
- [ ] Replacement optional/required PEER/SUBORDINATE nguyên tử: old cancelled + new/reopened eligible, giữ relationship/required; lỗi candidate/unique/audit rollback toàn bộ. Tăng participant version một lần và từng assignment version cần thiết.
- [ ] No-op kiểm tra auth/lifecycle/version nhưng không tăng version/audit. Không sửa cycle.version vì feedback không đổi enrollment/policy.
- [ ] Race cùng version tạo trùng, hai SELF/MANAGER, cancel/reopen/replace và đồng thời KPI mutation; kết quả không lost update/required gap. Test stale form trước cancel/reopen không gửi được sau phục hồi.

Gate: focused assignment/coverage/race tests có PostgreSQL độc lập và audit rollback; Ruff/mypy. Commit `feat(feedback): add versioned assignment administration`.

## Task 4 — Inbox và gửi phản hồi bất biến

File dự kiến: feedback submission service/router; `tests/integration/test_feedback_submission.py`, deadline/replay/concurrency tests; auth regression nếu có sửa helper.

- [ ] POST `/feedback` chỉ nhận assignment ID, hai expected versions, strict rating 1–5 và plain comment. Reviewer/subject/cycle/relationship do server suy ra; forged fields trả 422.
- [ ] Tìm assignment thuộc actor trước lỗi trạng thái/version, khóa cycle → participant → assignment, revalidate account/family và deadline sau chờ khóa. Reviewer ngoài scope report vẫn được gửi đúng assignment.
- [ ] Trong một transaction insert Feedback UNIQUE, đổi SUBMITTED, tăng assignment/participant versions và audit. Lỗi audit/DB rollback mọi thay đổi.
- [ ] Hai submit cùng assignment chỉ một 201; replay 409, không tăng lần hai. Hai assignment cùng participant version và submit-vs-KPI phải cùng lock/version contract.
- [ ] Deadline aware UTC, exact boundary now>=due, naive timestamp bị từ chối; null deadline không tự theo cycle end_date. HR gia hạn OPEN quá hạn hợp lệ, không sửa đã submit.
- [ ] Không PATCH/DELETE feedback, không impersonation HR/ADMIN; CLOSED/finalized/cancelled chặn. Mất response sau commit có thể GET own submission để xác nhận, không tạo bản thứ hai.

Gate: submission/deadline/replay/atomicity/race và session-revocation tests qua. Commit `feat(feedback): add reviewer inbox and one-time submissions`.

## Task 5 — Tổng hợp và ranh giới bảo mật

File dự kiến: `modules/feedback/{summary,presenters,schemas}.py`; `tests/integration/test_feedback_confidentiality.py`; unit aggregate tests với Decimal.

- [ ] Summary HR/self/current manager theo live SQL scope; peer reviewer không tự được xem report. Tách HR raw mode, mine DTO và summary serializer; không bật raw theo query người dùng ngoài HR.
- [ ] Overall sum/count từ mọi feedback đã submit, optional cũng tính như required; empty mean=null. Decimal/ROUND_HALF_UP chỉ để trình bày hai số lẻ; không tạo feedback_score/final_score.
- [ ] Test ngưỡng 0/1/2/3 từng nhóm PEER và SUBORDINATE riêng biệt, ba user khác nhau; dưới ngưỡng không trả count/mean/identity/comment/timestamp/histogram. Không cộng hai nhóm để vượt threshold.
- [ ] Own authored feedback chỉ đúng user; SELF/MANAGER group không lộ comment của người khác. Raw HR không dùng chung cache/DTO với summary employee.
- [ ] Test JSON recursive không có reviewer IDs/comment gốc của người khác, kể cả lỗi/nested objects; không có filter reviewer để suy luận nhóm tùy ý. Public readiness không tiết lộ ai chưa gửi.
- [ ] Có thông báo giới hạn bảo mật nhóm nhỏ vì whole mean vẫn có thể suy luận; không tuyên bố ẩn danh và không tạo sanitized themes giả trước Phase 7.
- [ ] Internal coverage/evidence reader đủ dữ liệu chuẩn cho Phase 6, không dùng aggregate làm tròn và không tạo PerformanceReview/AI table trong task này.

Gate: confidentiality matrix + boundary aggregates/coverage tests qua; raw DTO không tràn vào report. Commit `feat(feedback): add confidentiality-filtered summaries`.

## Task 6 — Giao diện tiếng Việt và hành vi xung đột

File dự kiến: `apps/web/src/features/feedback/`; protected routes `/feedback`, `/feedback/[id]`, `/feedback-administration`, `/employees/[id]/feedback`; navigation, cycle participant links và API types/tests.

- [ ] Inbox xuất hiện cho cả ADMIN/HR/MANAGER/EMPLOYEE, mặc định chỉ mine. HR có màn quản trị riêng, tìm reviewer bằng picker theo relationship/participant, không nhập UUID/email thủ công.
- [ ] HR thấy missing SELF/MANAGER, blocked accounts, required/optional, due/overdue và thao tác cancel/reopen/replace đúng quyền; xác nhận các thao tác, giải thích giới hạn historical account.
- [ ] Form rating 1–5/comment plain text có bộ đếm ký tự, deadline/múi giờ rõ ràng, xác nhận gửi một lần không sửa. Submitted read-only, cancelled/expired không gửi; không render HTML từ comment.
- [ ] Capture versions khi mở form; background refetch không tự thay version dưới nội dung đang gõ. 409 giữ comment/rating, chủ động reload/version acknowledgement rồi xác nhận lại nếu còn OPEN; đã SUBMITTED thì hiện bản đã nhận.
- [ ] Cache tách mine/HR raw/summary và cycle/participant; auth clear cache khi đổi tài khoản. Mutation invalidate inbox/admin/summary/KPI participant version liên quan; không đưa raw vào props trang employee.
- [ ] Loading/error/empty, field errors, bàn phím/mobile, pending chống double-click; reviewer ngoài live employee scope đi qua assignment route và không có link report trái quyền.
- [ ] Behavior tests trước component: role visibility, lookup pagination/selection, deadline, submit confirmation, retained input, stale/replay, suppression message và no unauthorized fetch.

Gate: web tests/lint/typecheck/build; browser thật xác minh HR/admin-reviewer/manager-old/employee ở desktop và màn hẹp. Commit `feat(web): add Vietnamese feedback workflows`.

## Task 7 — Review bảo mật, cạnh tranh và luồng tài khoản thật

File dự kiến: feedback real-account E2E, security/concurrency matrix; bằng chứng review theo cách thực tế.

- [ ] Bootstrap ADMIN → tạo HR/manager/employee/peer/subordinate → link tổ chức → activate cycle → HR phân công → từng account login và gửi → raw HR/summary được lọc. Dùng tài khoản thật, không chỉ token fixture.
- [ ] Transfer manager, unlink/role change/employment inactive: quyền report thay đổi nhưng assigned principal không chuyển. Disable/logout/revoke trong lúc writer chờ khóa phải bị từ chối.
- [ ] Mọi mutation kiểm tra exact Origin/CSRF/family; giả actor/relationship/subject, UUID assignment của người khác, mode=administration và count leakage bị chặn.
- [ ] Review lock order chéo auth/users/organization/KPI/feedback, deadline sau chờ, required replacement gap, version tăng một lần; timeout bắt deadlock và barrier chứng minh có cạnh tranh thật.
- [ ] Chạy race quan trọng ít nhất 5 lượt, ghi từng kịch bản và kết quả. Audit failure rollback submit/replacement/cancel/reopen cùng trạng thái và versions.
- [ ] Review privacy theo response JSON và UI/cache, ngưỡng nhóm nhỏ/own-authored; ghi rõ residual inference được kiến trúc chấp nhận, không coi HR raw là anonymous.

Gate: không còn blocker về quyền, disclosure ngoài policy, double submit, coverage, deadlock hoặc atomicity. Commit `test(feedback): verify privacy and concurrent submissions`.

## Task 8 — Docker/proxy, CI và bàn giao

File dự kiến: `scripts/smoke_auth.py` hoặc feedback smoke được workflow gọi, `.github/workflows/phase1-ci.yml`, container tests; README Việt/Anh, API/database/deployment/architecture và kế hoạch/hợp đồng này.

- [ ] Full backend PostgreSQL không skip + Ruff/mypy; toàn bộ frontend tests/lint/typecheck/build. Giữ dependencies hiện có nếu không có lý do kỹ thuật cụ thể để thay.
- [ ] Smoke mới qua web proxy: tạo các role thật, cycle ACTIVE, HR giao mandatory/optional, reviewer gửi một lần, CSRF/scope/replay và summary suppression. Không chỉ gọi service nội bộ hoặc mock provider.
- [ ] Vì Phase 4 smoke tạo ACTIVE, mở rộng **cùng chu kỳ/participant** cho feedback; không tạo ACTIVE thứ hai, không thêm close/finalize bypass. Dùng project nghiệm thu riêng, không thay stack 3000/8000 đang có dữ liệu.
- [ ] Nâng migration expectations theo head thật; clean install và upgrade Phase 4 giữ KPI/account. Kiểm tra nonroot, image không tooling/.env/secret.
- [ ] Restart PostgreSQL-only rồi đọc revision/count/status/feedback trước khi migrations rerun; giữ assignment đã cancel và feedback đã submit, không cleanup volume người dùng.
- [ ] README có luồng HR/reviewer, hạn chế account lịch sử, bắt buộc SELF/MANAGER, quá hạn, 409 và nhóm nhỏ. Docs chỉ đánh dấu runtime sau bằng chứng, không gọi rating summary là điểm hiệu suất.
- [ ] CI backend/frontend/docker-smoke thành công tại commit runtime cụ thể; ghi URL/test results, đối chiếu diff và git status, commit/push theo ủy quyền repository hiện có. Chỉ sau đó đánh dấu Phase 5 hoàn tất và chuyển Phase 6.

Gate: workflow tái lập được, bằng chứng CI và local/browser chính xác, không có phản hồi giả hay yêu cầu bắt buộc bị lược bỏ. Commit `docs: complete Phase 5 feedback acceptance and runbook`.

## Kiểm tra khi bắt đầu triển khai

Từ `apps/api`, cấp TEST_DATABASE_URL của DB dùng riêng `_test` qua môi trường và chạy `.venv\Scripts\python.exe -m pytest -q`, Ruff, mypy, `alembic heads`. Từ `apps/web` chạy `npm.cmd test -- --run`, lint, typecheck và build. Compose config không cần khởi động stack. Nghiệm thu có ghi dữ liệu chỉ chạy vào project được chọn rõ ràng.

Kế hoạch không yêu cầu thay đổi Windows/WSL hoặc nâng dependency; Docker của máy đã chạy được ở Phase 4. Không chạy lại full suite vì chỉnh tài liệu thuần túy, nhưng bắt đầu code phải đo baseline mới. Chưa có migration, endpoint hoặc màn hình Phase 5 trong lượt lập kế hoạch này.

Kiểm tra nhanh ngày lập kế hoạch: 239 unit backend test qua, Ruff/mypy sạch (69 source files), sole Alembic head `20261020_0004`, frontend typecheck qua. Đây không phải lần chạy lại 570 integration/unit hoặc Docker; bằng chứng đầy đủ của Phase 4 vẫn là CI đã liên kết ở đầu tài liệu.
