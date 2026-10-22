# Kế hoạch Phase 6 — Tính điểm và chốt đánh giá

Ngày lập: 2026-10-22. Trạng thái: **đã triển khai; đang hoàn tất nghiệm thu hồi quy/CI**.

Tham chiếu: [kiến trúc](../../architecture.md), [hợp đồng đề xuất Phase 6](../../phase-6-contract.md), [nghiệm thu Phase 5](2026-10-20-phase-5-feedback.md), [API](../../api.md), [database](../../database.md), [vận hành](../../deployment.md).

## Cơ sở đối chiếu

- [x] Repository clean, main đồng bộ origin/main khi bắt đầu lập kế hoạch. Phase 5 runtime `bf04fe2` đã qua [CI 39369977157](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39369977157): 661 backend/89 web test; đây là bằng chứng cũ, không phải chạy lại hôm nay.
- [x] Đọc scoring/lifecycle/API của architecture, model KPI/cycle, policy schemas, feedback coverage/summary, SQL employee/participant scope, write authorization và các điểm nối web hiện có.
- [x] Có policy snapshot, definition/organization snapshot, evidence_version, finalized_at và coverage IDs HR. Chưa có performance module, review/revision tables, calculate/finalize/close hoặc plan Phase 6 khác.
- [x] Chốt đề xuất hai bảng để giữ header ổn định + lịch sử bất biến; tính stale bằng evidence version, không sửa mọi writer để tự tính/xóa điểm.
- [x] Không dùng mean đã làm tròn của Phase 5; đề xuất số hữu tỉ nội bộ từ Decimal để giữ chính xác đến bước ROUND_HALF_UP cuối, không thêm thư viện.
- [x] Phân biệt HR/direct manager calculate với HR-only finalize/close; xử lý optional còn OPEN bằng xác nhận số lượng riêng HR, không tự hủy hoặc tạo feedback giả.

Đoạn đối chiếu trên ghi hiện trạng của lượt lập kế hoạch. Lượt triển khai sau đó được người dùng duyệt, bổ sung yêu cầu header/tab phía trên cùng menu trái theo role. Các checkbox chỉ đánh dấu khi có bằng chứng thực chạy. Review bảo mật trong lượt này là review trực tiếp, không tuyên bố reviewer độc lập.

## Luồng nghiệm thu tổng thể

HR/current manager mở người tham gia ACTIVE → xem readiness và xử lý dữ liệu thiếu qua trang KPI/phản hồi cũ → calculate đúng điểm → sửa actual hoặc gửi optional → report STALE, không hiện điểm cũ như current → recalculate, xem được revision trước → HR kiểm tra optional chưa gửi và finalize → mọi KPI/feedback/calculation writer bị khóa → hoàn tất các participant → HR close → đọc lịch sử theo live scope → kích hoạt kỳ DRAFT tiếp theo.

UI luôn tận dụng trang chu kỳ, nhân viên, KPI và feedback hiện có, cùng navigation/layout responsive. Không cần trang chọn context trùng lặp, không thêm dashboard/AI giả.

## Trình tự và nguyên tắc kiểm tra

Task 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8. Viết test thất bại có ý nghĩa cho schema/engine/hành vi trước implementation; concurrency/rollback đi cùng task, Task 7 review xuyên module. Không chạy hai bộ integration trên cùng DB `_test` đồng thời. Gate qua mới commit; tránh commit trung gian thiếu module phụ thuộc hoặc giả vờ endpoint đã hoạt động.

## Task 1 — Baseline, schema và version contracts

File dự kiến: `apps/api/app/modules/performance/{__init__,models,schemas}.py`, `app/models.py`, migration mới sau `20261020_0005`, integration cleanup và schema/input tests.

- [x] Chạy baseline full PostgreSQL riêng `_test`, không skip; ghi môi trường/head/kết quả thực. Kiểm tra 661/89 là baseline đối chiếu, không bắt buộc số test cố định nếu repository đã thay đổi có chủ đích.
- [x] Tests header UNIQUE participant, revision UNIQUE(review,calculation_version), FK RESTRICT, versions/hash/engine/JSON object, finite nonnegative NUMERIC(20,2), UTC timestamps.
- [x] Tạo hai bảng performance_reviews/performance_review_revisions theo hợp đồng; header giữ latest result, revision chứa cả lần đầu; không thêm AI/score cache ở KPI, không backfill review giả.
- [x] Input strict versions, optional acknowledgement nonnegative integer, forbid forged scores/actor/snapshot và empty unsupported changes. Tách public report/revision/readiness với HR finalization context/raw issue DTO.
- [x] Metadata parity, sole head dự kiến `20261022_0006`, clean install và downgrade/upgrade từ Phase 5 bảo toàn accounts/cycle/KPI/assignments/feedback; cập nhật cleanup đúng FK, giữ guard `_test`.

Gate: schema/input/readiness regression Phase 1–5 qua, Ruff/mypy, sole head. Commit `feat(performance): add review and calculation revision schema`.

## Task 2 — Engine tính điểm thuần và canonical evidence

File dự kiến: `performance/{engine,evidence,hashing}.py`, unit tests độc lập DB; ghi chú số học trong architecture khi triển khai.

- [x] Typed input từ Decimal/strict integer; hàm thuần không ORM/HTTP/current clock/global policy. HIGHER/LOWER, actual=0, cap hữu hạn/không cap, weights, ratings và policy snapshot đúng hợp đồng.
- [x] Dùng Fraction từ Decimal chính xác cho tỉ lệ/tổng nội bộ; output cent chính xác HALF_UP. Không round từng thành phần trước khi tính final. Đối chiếu oracle độc lập, không chỉ test lặp lại công thức implementation.
- [x] Golden 89.80, fractions tuần hoàn, sát nửa cent, component rounding khác tổng, target/actual cực trị, cap >100, uncapped score >100, policy 0/100 nhưng vẫn yêu cầu đủ evidence.
- [x] Chứng minh NUMERIC(20,2) đủ theo domain bounds; reject NaN/Infinity/âm/target zero/missing actual, weights thiếu/trùng/quá precision và overflow, không clamp final=100.
- [x] Snapshot schema/hash canonical sorted UUID và decimal chuẩn; cùng input đảo query order có cùng hash, evidence_version/policy/engine/numerical input đổi thì hash đổi. Không comment/email/current manager/status tài khoản hay clock trong hash.

Gate: toàn bộ scoring boundary/oracle/determinism tests qua, không float/dependency mới. Commit `feat(performance): implement exact deterministic scoring engine`.

## Task 3 — Readiness và calculate có lịch sử/nguyên tử

File dự kiến: `performance/{repository,policies,service,router}.py`, audit allowlist, `app/main.py`; integration readiness/calculation/concurrency tests.

- [x] Scoped discovery bằng live employee/participant SQL; HR toàn bộ, manager self/direct reports read nhưng chỉ active direct report đủ điều kiện write. ADMIN/peer reviewer không có report nhờ assignment.
- [x] Readiness kiểm tra complete allocation, mọi actual, required SELF/MANAGER và các required khác; optional SUBMITTED tham gia, optional OPEN không chặn. Zero weight của một thành phần không bỏ validation dữ liệu thành phần đó.
- [x] Đọc rating nguyên và assignment membership từ DB, không reuse mean hai số lẻ; corrupt stored evidence bị chặn. HR issue detail riêng, manager/self không lộ identities/optional group counts.
- [x] Calculate revalidate Origin/CSRF/family/role dưới khóa, cycle ACTIVE/unfinalized và expected evidence version. Dùng frozen policy, ghi header + revision + audit trong một transaction; rollback trên mọi lỗi.
- [x] Same evidence/policy/engine → reused, không version/revision/audit mới. Thay evidence → một calculation_version mới; không đổi evidence_version/cycle.version. Race hai calculate chỉ một revision, compute-vs-KPI/assignment/submit không đọc dữ liệu trộn.
- [x] Các mutation Phase 4–5 vẫn hoạt động trước finalize, tăng shared version như cũ; không tự tính lại hoặc xóa review/history khi thay evidence.

Gate: calculation/authorization/coverage/no-op/audit rollback/race tests qua. Commit `feat(performance): add versioned calculations and readiness`.

## Task 4 — Report/revision theo quyền và phát hiện stale

File dự kiến: `performance/{presenters,schemas,repository}.py`, report/history/privacy integration tests.

- [x] GET không tự calculate/ghi audit/call AI. NOT_CALCULATED/CURRENT/STALE/FINALIZED rõ ràng; stale current_result=null, last result luôn gắn nhãn cũ. Revisions lưu đúng input/labels/policy cũ, không đọc lại default/definition live để tái tạo quá khứ.
- [x] List/count/detail/revision cùng SQL scope trước pagination; outsider/missing cùng 404. Transfer/unlink/role changes đổi report access nhưng không tự đổi historical reviewer principal.
- [x] Presenter chỉ trả KPI breakdown, scores/weights/policy cần giải thích và feedback aggregate theo Phase 5. Không raw evidence JSON/reviewer IDs/individual ratings/comment của người khác/hash phân nhóm.
- [x] Group threshold 0/1/2/3 từng PEER/SUBORDINATE và own-authored dùng đúng feedback set của revision, không trộn submissions mới. HR raw ở màn quản trị riêng; HR-only finalization context không lọt vào public report/cache.
- [x] Aggregate reads có snapshot transaction nhất quán; test reader-vs-writer, bounded query count/no N+1 và pagination history ổn định.

Gate: status/privacy/scope/historical consistency/query-count tests qua. Commit `feat(performance): expose scoped current and historical reports`.

## Task 5 — Finalize và close lifecycle

File dự kiến: `performance/finalization.py`, cycle close service/router hoặc module hiện có, audit metadata, integration lifecycle/race/rollback tests.

- [x] HR finalization-context trả versions, readiness và open_optional_count; non-HR bị chặn trước fetch/serialize dữ liệu riêng.
- [x] Finalize yêu cầu current hash/evidence/calculation versions và acknowledgement count đúng, kể cả 0; kiểm tra lại đủ nguồn evidence dưới khóa. Optional OPEN giữ lịch sử, không auto-cancel, nhưng submit sau chốt bị chặn.
- [x] Finalization atomic: review/participant finalized_at cùng thời điểm, cycle.version +1 và audit; scores/calculation/evidence version giữ nguyên. Replay 409, không mở lại hoặc silent overwrite.
- [x] Kiểm kê tất cả KPI/assignment/feedback/calculation writers đều chặn finalized và CLOSED; race finalize-vs-submit/actual/allocation/replace chỉ kết quả hợp lệ, không lọt evidence sau chốt.
- [x] Close HR expected cycle version, ACTIVE nonempty và mọi participant finalized/current; không auto-finalize. Bounded actionable issues chỉ HR. Cycle lock bảo vệ close-vs-finalize; audit failure rollback state/version.
- [x] CLOSED vẫn đọc được theo live scope, không thay snapshot; replay close/DRAFT close/participant chưa đủ bị chặn. Đóng xong kích hoạt DRAFT tiếp theo không vi phạm unique ACTIVE; kiểm tra cả race close-vs-activate, không xuất hiện hai ACTIVE.

Gate: lifecycle/finalization/close-races và hồi quy mọi evidence writer qua. Commit `feat(performance): finalize reviews and close completed cycles`.

## Task 6 — Web report tiếng Việt, tái sử dụng trang hiện có

File dự kiến: `apps/web/src/features/performance/`, route `/employees/[id]/performance`, links từ cycle/KPI/feedback, API types/cache/test chung.

- [x] Entry từ participant giữ employee/cycle context; header có nhãn lịch sử và trạng thái, desktop overview + breakdown, mobile cards/table trong khung. Không nhân đôi employee/cycle picker hoặc thêm dashboard trống.
- [x] Readiness gợi ý đúng trang xử lý KPI/phản hồi HR, không dẫn peer/manager vào route raw không có quyền. EMPLOYEE read-only; manager không calculate self; ADMIN không fetch report.
- [x] Server scores chuỗi hai số lẻ; UI không tự tính/round lại, không clamp >100. Hiển thị conversion rating 1→20, 5→100 và lý do tổng không cộng từ số đã làm tròn.
- [x] Chưa tính/stale không hiện 0/điểm cũ như current; lịch sử version có nhãn rõ. Không có AI summary/themes/strengths bịa.
- [x] Form capture versions lúc mở, 409 giữ lựa chọn, explicit reload/confirmation; finalize nêu rõ khóa dữ liệu và optional chưa gửi chỉ HR, close explicit confirmation, chống double-click, focus/accessibility/loading/error/empty.
- [x] Cache keys tách user/employee/cycle/current/revision/HR context; KPI/feedback/assignment/cycle mutations invalidate report readiness/current; finalization invalidates mọi quyền/khả năng edit liên quan; auth clear cache giữ nguyên.
- [x] Behavior tests roles, stale/background refetch, calculation reused, history selection, privacy/no unauthorized fetch, optional ack, deadline không liên quan trực tiếp close, pending và lỗi giữ state. Browser thật 390px/1280px và bàn phím, đặc biệt các màn cũ sau đổi lifecycle.

Gate: web tests/lint/typecheck/build và browser thực qua. Commit `feat(web): add performance reports and finalization workflows`.

## Task 7 — Review bảo mật, concurrency và tài khoản thật

File dự kiến: performance real-account E2E, cross-module security/race matrix và review evidence.

- [x] Bootstrap/create/login/link tổ chức thật → allocate/actual/assign/submit → calculate → optional submit/actual change → stale → recalculate → revisions → finalize → evidence block → close → activate kỳ tiếp; không chỉ token fixtures/service calls.
- [x] Revalidate account disable/logout/role/manager transfer trong lúc chờ khóa; guessed IDs/history/count/raw query không bypass scope. Exact Origin/CSRF/family trên mọi mutation.
- [x] Review lock order cùng auth/users/org/KPI/feedback, no review→participant inversion; barrier/event chứng minh tranh chấp và timeout bắt deadlock. Các race quan trọng chạy ít nhất năm lượt, ghi từng lượt, không suy số từ collect.
- [x] Audit failure và DB error rollback first calculate/recalculate/header/revision/finalize/close, không version/audit duplicate. Finalize-vs-optional submit không bỏ sót feedback đã thắng trước khóa.
- [x] Read JSON/UI/cache của current/stale/history/HR context theo từng role, test suppression và own-authored; giữ giới hạn residual inference đã công bố, không tự tuyên bố anonymous.

Gate: không còn blocker về exact score, data loss, stale finalization, authorization/disclosure, deadlock hoặc atomicity. Commit `test(performance): verify scoring privacy and concurrent lifecycle`.

## Task 8 — Docker, CI và bàn giao

File dự kiến: `scripts/smoke_auth.py` hoặc performance smoke được workflow gọi, `.github/workflows/phase1-ci.yml`, README Việt/Anh, API/database/deployment/architecture, contract/plan này.

- [ ] Full backend PostgreSQL không skip, Ruff/mypy; toàn bộ web tests/lint/types/build. Chỉ ghi số test thực chạy và head thực; dependencies hiện có được giữ nếu không có lý do kỹ thuật cụ thể.
- [ ] Smoke qua Next.js proxy mở rộng cùng ACTIVE cycle/participant Phase 4–5: calculate/reused → stale → recalculate → finalize → reject edits → close → activate next. Không xóa feedback/kỳ cũ hoặc bypass điều kiện chốt để làm smoke xanh.
- [ ] Smoke có ít nhất một optional OPEN cần HR acknowledgement; giữ ít nhất hai calculation revisions để chứng minh history. Chốt signature persistence mới từ scenario thực, không giữ cứng assumption một ACTIVE cycle/count chỉ một cycle của Phase 5 sau khi có kỳ kế tiếp.
- [ ] Metadata/head expectations cập nhật migration mới; upgrade từ Phase 5 giữ submitted/cancelled feedback, accounts và KPI. Nonroot, ảnh không app .env/secret/test tooling như gate hiện có.
- [ ] Project/ports/images/volume nghiệm thu riêng, không thay stack người dùng 3000/8000. Restart riêng PostgreSQL, kiểm tra revision/counts/scores/hash/calculation versions/finalized timestamps/cycle statuses và history trước migration rerun. Không xóa volume người dùng.
- [ ] Docs hướng dẫn đầy đủ vai trò, đủ dữ liệu, stale, history, optional chưa gửi lúc chốt, không reopen, close rồi tạo kỳ mới; làm rõ chưa có AI/dashboard. Update architecture note exact rational internal arithmetic, schema/endpoint map thực tế.
- [ ] CI backend/frontend/docker-smoke cùng thành công tại đúng runtime commit; record URL, local/browser/race results và giới hạn. Git diff/status clean, commit/push theo ủy quyền repository. Sau đó mới đánh dấu Phase 6 hoàn tất.

Gate: [hợp đồng](../../phase-6-contract.md) được thực hiện, không score/AI giả hoặc bỏ missing evidence; chỉ chuyển Phase 7 sau nghiệm thu Phase 6. Commit `docs: complete Phase 6 performance acceptance and walkthrough`.

## Bằng chứng của lượt lập kế hoạch

Đã đọc trực tiếp các điểm nối và trạng thái repository như mô tả ở đầu. Đây là thay đổi tài liệu; không chạy lại full integration/Docker, không coi số 661/89 cũ là kết quả mới. Trước Task 1 phải đo baseline mới với TEST_DATABASE_URL `_test`; làm việc trong `apps/api`/`apps/web` đúng thư mục cấu hình. Kiểm tra link tài liệu và sole Alembic head chỉ chứng minh tài liệu/head, không chứng minh Phase 6 đã triển khai.

Kiểm tra lượt lập kế hoạch: source HEAD `00f01c719a7bbda7e744b5b01c9a5f591dba3c08`; `alembic heads` trả duy nhất `20261020_0005`; link nội bộ/UTF-8 hợp lệ, đủ tám task và implementation checklist vẫn chưa đánh dấu. Không đọc/sửa `.env` hoặc dữ liệu ứng dụng đang chạy.
