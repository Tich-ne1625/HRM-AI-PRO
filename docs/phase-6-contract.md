# Hợp đồng Phase 6 — Tính điểm và chốt đánh giá

Ngày: 2026-10-22. Trạng thái: **đã triển khai; đang hoàn tất nghiệm thu hồi quy/CI**. Tham chiếu [kiến trúc](architecture.md), [Phase 4](phase-4-contract.md), [Phase 5](phase-5-contract.md), [kế hoạch Phase 6](superpowers/plans/2026-10-22-phase-6-performance.md).

## 1. Hiện trạng khi lập kế hoạch và phạm vi

| Mã nguồn đã đọc | Điểm nối |
| --- | --- |
| `review_cycles/models.py`, `repository.py` | ACTIVE/CLOSED, snapshot tổ chức/policy, evidence_version và finalized_at; chưa có calculate/finalize/close |
| `kpis/models.py`, `allocations.py` | NUMERIC(14,4), trọng số NUMERIC(5,2), complete allocation, actual=null khác actual=0, định nghĩa đã snapshot |
| `feedback/summary.py`, `schemas.py` | Coverage bắt buộc và IDs pending/blocked chỉ HR; mean hiện tại đã làm tròn, không được dùng làm đầu vào tính điểm |
| `core/domain_writes.py` | Guard 730031, khóa ADMIN/users/family và revalidate quyền/CSRF; dùng lại thay vì tạo đường ghi riêng |
| Web cycle/participant/KPI/feedback | Có đủ đường chọn ngữ cảnh và layout responsive; báo cáo phải nối vào đây |

Baseline tài liệu: Phase 5 nghiệm thu runtime `bf04fe2`, [CI 39369977157](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39369977157), 661 backend/89 web test; sole head `20261020_0005`. Đây là bằng chứng trước đó, không phải lần chạy lại trong lượt lập kế hoạch. Repository clean và đồng bộ origin/main tại lúc đối chiếu; chưa có module performance hoặc migration Phase 6.

Phase 6 gồm bộ tính điểm thuần, lưu tính toán/lịch sử, báo cáo theo quyền, chốt đánh giá và đóng chu kỳ. Không Gemini/AIAnalysis, dashboard tổng thể, xếp hạng nhân viên, email/queue, seed hoặc mở lại đánh giá đã chốt. Không sửa migration/snapshot Phase 4–5 hay backfill điểm giả.

## 2. Công thức và độ chính xác

Nguồn cấu hình duy nhất là `ReviewCycle.scoring_policy_snapshot`, không lấy mặc định ADMIN hiện tại. Target/actual/weight/direction dùng allocation và definition snapshot đã lưu.

```text
HIGHER_IS_BETTER: raw = actual / target * 100
LOWER_IS_BETTER:  raw = target / actual * 100 nếu actual > 0
LOWER_IS_BETTER:  actual = 0 thì normalized = finite cap của chu kỳ
normalized = min(raw, cap) nếu có cap; nếu không thì raw
kpi_score = sum(normalized_i * weight_i / 100)
feedback_score = sum(rating) / submitted_count / 5 * 100
final_score = kpi_score * kpi_weight / 100 + feedback_score * feedback_weight / 100
```

Mọi feedback SUBMITTED đều tính như nhau, kể cả optional; không tự thêm trọng số theo quan hệ. Rating 1 tương ứng 20/100, rating 5 tương ứng 100/100; giải thích trên UI. Không dùng mean hai số lẻ của Phase 5. Ví dụ KPI 90/100 với trọng số 60/40 cho 94, feedback trung bình 4 cho 80, policy 70/30 cho final **89.80**.

Input/output thập phân dùng Decimal/chuỗi, tuyệt đối không float. Chỉ làm tròn kết quả lưu/hiển thị đến hai số lẻ bằng ROUND_HALF_UP; final tính từ các thành phần chưa làm tròn. Các dòng KPI hiển thị đã làm tròn có thể cộng lệch vài phần trăm điểm so với final; UI giải thích ngắn gọn, không cộng lại bằng JavaScript.

Đề xuất cụ thể hóa yêu cầu “không làm tròn trung gian” của kiến trúc: parse Decimal chính xác, dùng `fractions.Fraction` trong thư viện chuẩn cho phép chia/tổng hữu tỉ nội bộ, chuyển chính xác sang số cent theo ROUND_HALF_UP ở biên lưu/DTO. Điều này tránh phụ thuộc precision mặc định 28 khi gặp phân số tuần hoàn và trường hợp sát nửa cent. Không thêm dependency; engine thuần không biết ORM/HTTP. Task engine phải có oracle hữu tỉ độc lập và test biên; cập nhật ghi chú kỹ thuật kiến trúc khi triển khai, không coi lựa chọn này là code đã có.

LOWER_IS_BETTER luôn cần finite cap; thiếu cap trả lỗi policy không tương thích. Cap >100 và HIGHER_IS_BETTER không cap được hỗ trợ; không ép điểm về [0,100]. Điểm không âm, hữu hạn, đề xuất lưu NUMERIC(20,2): 18 chữ số nguyên đủ cho giới hạn actual/target NUMERIC(14,4), kể cả target 0.0001 và actual lớn nhất. Phải chứng minh giới hạn bằng test, từ chối overflow thay vì cắt/round input.

## 3. Điều kiện đủ dữ liệu

Calculation chỉ trong ACTIVE, participant chưa finalized và có snapshot hợp lệ. Bắt buộc:

- Có 1–100 KPI khác nhau; target >0, actual không null và >=0; từng weight >0, tổng đúng 100.00; snapshot/direction/policy hợp lệ.
- Có đúng một SELF và một MANAGER đã SUBMITTED; mọi assignment non-cancelled required đã gửi. Không coi thiếu phản hồi là zero hoặc bỏ/reweight một thành phần khi policy có trọng số 0.
- Feedback SUBMITTED phải có đúng một Feedback hợp lệ; dữ liệu bất nhất không được âm thầm bỏ qua. Các giới hạn assignment hiện có tiếp tục áp dụng.

OPEN optional không chặn tính điểm. Submitted optional vẫn tham gia điểm, kể cả gửi sau một lần tính trước đó; việc gửi làm evidence_version tăng và kết quả cũ trở thành stale. Deadline quá hạn không thay thế phản hồi bắt buộc. Account lịch sử bị khóa không được ngầm ủy quyền; feedback đã gửi vẫn là bằng chứng hợp lệ sau khi tài khoản đổi trạng thái.

Đọc readiness trả nhóm lỗi và tổng số lỗi, tối đa 100 chi tiết. HR được thấy assignment IDs và lý do blocked qua DTO riêng. Manager/self chỉ thấy thiếu KPI nào và trạng thái feedback bắt buộc chưa đủ; không được suy ra danh tính/số optional theo nhóm nhỏ. API hiện hữu của HR vẫn là nơi xem và xử lý phản hồi gốc.

## 4. Schema và lịch sử tính toán

Đề xuất thêm đúng hai bảng trong migration mới sau `20261020_0005` (revision dự kiến `20261022_0006`; xác nhận sole head khi code):

| Bảng | Dữ liệu và ràng buộc |
| --- | --- |
| `performance_reviews` | UUID ổn định, participant_id UNIQUE FK RESTRICT; calculation_version >=1, evidence_version >=1, engine_version, evidence_hash SHA-256, kpi_score/feedback_score/final_score NUMERIC(20,2), evidence_snapshot/policy_snapshot JSONB object, calculated_at UTC, finalized_at nullable, timestamps |
| `performance_review_revisions` | UUID, review_id FK RESTRICT, UNIQUE(review_id,calculation_version); bản sao bất biến của version/evidence/hash/engine/scores/snapshots/calculated_at cho mỗi lần tính thành công |

Header giữ kết quả mới nhất để giữ đường GET/review_id ổn định theo kiến trúc; revision lưu mọi lần tính, không chỉ bản cũ. Insert revision, cập nhật header và audit cùng transaction. Không có PATCH/DELETE lịch sử. CHECK điểm hữu hạn/không âm, versions dương, hash/engine hợp lệ, JSON object; chỉ mục review/revision và truy vấn theo participant/cycle. Không thêm score vào EmployeeKPI làm nguồn sự thật thứ hai; chi tiết score nằm trong calculation snapshot.

Snapshot nội bộ có schema_version, frozen subject labels, policy/source version, KPI IDs/definition snapshots/target/actual/weight, assignment IDs/relationship/required/status cần chứng minh coverage và các rating nguyên được tính. Không sao chép comment, email, credential, role hoặc toàn bộ reporting graph. Dữ liệu nội bộ có identity/rating riêng lẻ không được trả nguyên JSON cho report hoặc dùng làm props web.

Canonical hash: thứ tự UUID ổn định, decimal string chuẩn, schema/engine version, evidence_version, frozen policy và numerical/coverage inputs. Không phụ thuộc query order, thời gian gọi, current names/manager/user role, comment hoặc mean đã làm tròn. Hash là nội bộ/audit cho truy vết; public DTO không lộ hash riêng lẻ của reviewer. Hai lần tính cùng bằng chứng/policy/engine phải ra cùng hash và giá trị.

Chưa tính thì không tạo row giả. Không migration tài khoản, dữ liệu demo, AI hoặc backfill review từ số liệu thiếu.

## 5. Current, stale và tính lại

`is_current` được suy ra từ header.evidence_version so với participant.evidence_version và engine đang được hỗ trợ. Không lưu một cờ stale cần sửa đồng loạt ở mọi writer. Không sửa KPI/feedback để tự gọi calculation hoặc xóa kết quả lịch sử.

Triển khai engine mới sau này không tự sửa hoặc làm mất hiệu lực một kết quả FINALIZED; vẫn đọc scores/snapshot/engine_version đã chốt. Việc nâng engine và chính sách hỗ trợ revision cũ cần migration/quyết định riêng, không tự tính lại lịch sử khi GET.

GET trả trạng thái `NOT_CALCULATED`, `CURRENT`, `STALE` hoặc `FINALIZED`; khả năng ghi còn phụ thuộc cycle/role. `current_result=null` khi chưa tính hoặc stale; có thể trả `last_calculation` an toàn, gắn rõ “Kết quả cũ”, không được trình bày thành điểm hiện tại. Lịch sử là calculation snapshots, không phải tính lại bằng dữ liệu live. Sau thay đổi tổ chức, quyền đọc theo live scope nhưng nhãn lịch sử vẫn theo snapshot.

POST calculate kiểm tra authority/lifecycle/expected_evidence_version dưới khóa, đọc đầy đủ evidence và coverage rồi tính. Chưa có thì 201; tính lại thay đổi thì 200, calculation_version tăng một và thêm revision. Khi bằng chứng/policy/engine không đổi và kết quả current: 200 `reused=true`, không tăng version, không thêm revision/audit. Hai request cùng evidence có thể cùng thành công theo nghĩa một tạo, một reused; chỉ một lần tính được ghi. No-op vẫn kiểm tra quyền/session/CSRF/lifecycle/version. Stale expected evidence trả 409, không tự thử lại bằng version mới.

Calculation không thay participant.evidence_version hoặc cycle.version vì không đổi bằng chứng/lifecycle. Evidence thay đổi rồi quay về cùng giá trị vẫn là một evidence version mới, cần tính lại và giữ lịch sử.

## 6. Chốt đánh giá và đóng chu kỳ

Chỉ HR finalize. Body chứa expected_calculation_version, expected_evidence_version và `acknowledge_open_optional_count` là strict integer >=0, bắt buộc kể cả 0. Trước khi chốt phải có review current, đủ evidence/coverage, ACTIVE và chưa finalized. Kiểm tra lại hash từ nguồn dưới khóa; không tin điểm do client gửi.

OPEN optional được phép còn tồn tại khi chốt, nhưng HR phải xác nhận đúng số lượng hiện tại trong DTO HR riêng. UI nêu rõ họ sẽ không gửi thêm được sau chốt. Count sai trả 409; concurrent assignment/submit đổi evidence version cũng làm form stale. Không tự đổi OPEN thành CANCELLED, không tạo feedback zero, không làm lộ optional count cho manager/self. HR có thể xử lý các phân công trước rồi chốt với count=0.

Thành công: cùng timestamp UTC cho Review.finalized_at và Participant.finalized_at, tăng cycle.version một lần để form đóng chu kỳ phát hiện thay đổi, audit nguyên tử. Không đổi điểm/calculation_version/evidence_version. KPI/feedback writers hiện có phải tiếp tục chặn finalized; form “Tính lại” cũng bị chặn. Replay finalize trả 409 review_already_finalized, không thêm audit/version. Không mở lại trong Phase 6.

Khóa chốt áp dụng bằng chứng đánh giá của participant trong kỳ, không khóa hồ sơ tổ chức hiện tại. HR vẫn có thể chuyển quản lý/đổi liên kết hồ sơ theo Phase 3; việc này thay live report scope nhưng không thay calculation snapshots hoặc điểm đã chốt.

HR close chỉ với ACTIVE và expected_version của cycle. Cần nonempty participant list và tất cả participant có review finalized/current hợp lệ; không tự finalize hàng loạt. Giữ cycle lock khi kiểm tra để không đua với finalize/evidence; writers khác đều khóa cycle trước participant. Nếu cần khóa nhiều participant thì UUID tăng dần. Lỗi chưa đủ trả count và tối đa 100 employee/participant issues chỉ HR. Thành công status=CLOSED, cycle.version tăng một, audit cùng transaction; không thêm CLOSED timestamp nếu không có nhu cầu cụ thể trong implementation.

Replay close trả 409 cycle_already_closed. CLOSED đọc lịch sử được trong live scope, chặn mọi calculate/evidence mutation; không mở lại hoặc sửa người tham gia. Sau khi đóng có thể kích hoạt DRAFT tiếp theo theo unique ACTIVE index hiện có. End_date không tự đóng.

Đối với review đã finalized, điều kiện current khi close là evidence/hash/version nhất quán với calculation/engine đã chốt; không bắt review cũ tự đổi engine chỉ vì ứng dụng được nâng cấp. Chính sách này không cho phép sửa bằng chứng sau chốt.

## 7. Quyền và API đề xuất

| Người dùng | Đọc | Ghi |
| --- | --- | --- |
| HR | Mọi participant/report/revisions; readiness đầy đủ và context chốt riêng | Calculate, finalize, close |
| MANAGER | Self và direct reports hiện tại qua SQL scope | Calculate chỉ direct report đang làm việc với actor profile active, cùng nguyên tắc can_write_kpis; không tự calculate self |
| EMPLOYEE | Self qua liên kết hiện tại | Không calculate/finalize/close |
| ADMIN | Không mặc định quyền report hoặc HR raw, kể cả từng là reviewer | Không ghi performance qua quyền hệ thống |
| Reviewer ngoài live scope | Assignment/feedback của mình như Phase 5 | Không được quyền report nhờ assignment |

Mọi list/count/detail/revision/readiness dùng cùng SQL live scope trước phân trang. Outside/missing cùng 404. Quản lý cũ mất report nhưng vẫn giữ assignment lịch sử; quản lý mới có thể calculate direct report hiện tại, không nhận thay assignment MANAGER cũ. Không cấp scope lịch sử ngầm cho người đã unlink chỉ vì có snapshot user_id.

| Endpoint `/api/v1` | Payload/kết quả |
| --- | --- |
| GET `/performance/{employee_id}?cycle_id=...` | Scoped report kể cả chưa tính; labels, lifecycle, versions, trạng thái, current_result/last_calculation, KPI breakdown, feedback tổng hợp đã lọc, can_calculate/can_finalize; không tự calculate |
| GET `/performance/{employee_id}/readiness?cycle_id=...` | Scoped prerequisite issues, DTO HR riêng; không tính hay ghi |
| POST `/performance/{employee_id}/calculate` | `{cycle_id,expected_evidence_version}`; 201 lần đầu, 200 recomputed/reused |
| GET `/reviews/{review_id}/revisions` | Scoped paginated version summaries, page >=1/page_size <=100, newest calculation_version trước |
| GET `/reviews/{review_id}/revisions/{calculation_version}` | Scoped snapshot report qua presenter an toàn, không raw evidence JSON |
| GET `/reviews/{review_id}/finalization-context` | Chỉ HR: versions, readiness và open_optional_count để xác nhận |
| POST `/reviews/{review_id}/finalize` | Versions + acknowledge_open_optional_count; HR, 200 |
| POST `/review-cycles/{cycle_id}/close` | `{expected_version}`; HR, 200 |

Phân biệt employee_id/review_id/cycle_id trong OpenAPI/client, không dùng một UUID cho hai loại. Versions strict positive int, unknown fields/forged scores/actor/employee identity 422. Mọi response no-store, mutation exact Origin + family CSRF + revalidate status/role/session sau chờ khóa.

Lỗi dự kiến: 404 participant_not_found/review_not_found/revision_not_found; 403 forbidden; 409 stale_evidence_version/stale_calculation_version/stale_version, cycle_not_active, cycle_already_closed, participant_finalized/review_already_finalized, review_not_calculated/review_stale, evidence_incomplete, optional_feedback_acknowledgement_required, cycle_reviews_incomplete, scoring_policy_incompatible. Corrupt stored evidence trả 409 evidence_inconsistent với chi tiết được lọc, overflow hữu hạn trả 409 score_out_of_range; không echo comment/request/DB exception. 422 input, 401 auth theo hiện hữu.

## 8. Bảo mật report, khóa và audit

Report/revision không trả raw ratings theo người, reviewer identity, eligibility snapshot hoặc comment của người khác. Tổng count/mean và group suppression giữ chính sách Phase 5; revision dùng đúng tập feedback của revision, không trộn số liệu mới. Own-authored feedback chỉ exact author và chỉ nếu có trong tập snapshot đang xem; đọc comment từ feedback gốc trong scope membership, không sao chép vào revision. HR raw vẫn đi màn quản trị Phase 5 riêng. Không trả full finalization context cho người ngoài HR.

Giữ guard → sorted active ADMIN → sorted actor/related users → active family → cycle → participant → child evidence nếu cần khóa → review → revisions. Tìm scoped IDs trước khi khóa domain; không khóa review rồi quay lại participant. All evidence writers phải được kiểm kê lại, không chỉ tin timestamp/version. Manager transfer/disable/logout trong lúc chờ phải bị kiểm tra lại. Reads không giữ global write guard; readiness/report lấy snapshot đọc nhất quán trong một transaction (REPEATABLE READ cho read aggregate hoặc một query snapshot tương đương), không ghép versions/evidence từ hai thời điểm.

Audit `performance.calculated`, `performance.finalized`, `review_cycle.closed`; allowlist riêng chỉ IDs, versions, engine_version/hash, status/count cần thiết. Không điểm riêng lẻ, rating, comment, tên/email, numerical/full snapshots hoặc request body. Audit lỗi rollback header/revision/finalization/cycle transition và mọi version. Reused không audit lần hai. Không cập nhật AI rows chưa có; Phase 7 phải liên kết review_id + calculation_version + evidence_hash khi triển khai.

## 9. Giao diện và ranh giới nghiệm thu

Route đề xuất `/employees/{id}/performance?cycle_id=...`, thêm link từ cycle participant, KPI và feedback summary; tận dụng context chọn sẵn. Chưa thêm một màn chọn nhân viên/chu kỳ trùng. Header có tên/mã, kỳ, trạng thái; score cards và breakdown theo trọng số, readiness để xử lý thiếu, badge “Cần tính lại”, lịch sử version, HR confirmation chốt/đóng ở đúng ngữ cảnh.

Desktop dùng không gian hiện có cho overview + bảng; mobile xếp cards, bảng cuộn trong khung, keyboard focus tới confirmation/validation. Score >100 hiển thị đúng; chưa tính/stale không hiển thị 0/điểm cũ như current. Không bịa AI summary/strengths/themes hoặc score distribution trước phase tương ứng.

Form giữ expected versions khi mở; background refetch không đổi version ngầm, 409 giữ lựa chọn và yêu cầu tải/xác nhận lại. Chốt/đóng pending chống double-click, explicit irreversible confirmation nêu rõ dữ liệu bị khóa và số optional chỉ HR. Cache tách report/current/revision/finalization context, user/cycle/employee; invalidation dùng chung với KPI/feedback/cycle/auth, không đưa HR raw vào report cache.

Nghiệm thu bằng tài khoản thật và PostgreSQL: đủ dữ liệu → calculate → đổi actual/optional submit → stale → recalculate có history → HR finalize → mọi writer bị chặn → finalize tất cả → close → kích hoạt kỳ kế tiếp. Test privacy, exact arithmetic, overflow, last-cent rounding, scope/CSRF/revocation, calculate-vs-evidence, finalize-vs-submit/KPI, close-vs-finalize và rollback audit. Docker project riêng, migration preserve Phase 5, proxy smoke, restart trước rerun migrations, CI đúng runtime commit. Kết quả test chỉ ghi khi thực chạy.
