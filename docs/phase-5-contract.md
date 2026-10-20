# Hợp đồng Phase 5 — Phản hồi 360

Ngày lập: 2026-10-20. Trạng thái: đang triển khai theo phê duyệt, chưa nghiệm thu CI. Tham chiếu [kiến trúc](architecture.md), [hợp đồng Phase 4](phase-4-contract.md) và [kế hoạch triển khai](superpowers/plans/2026-10-20-phase-5-feedback.md).

Các quy tắc dưới đây cụ thể hóa thiết kế tổng thể để triển khai và review. Trạng thái nghiệm thu và bằng chứng kiểm tra được cập nhật trong kế hoạch; không coi chức năng đang viết là đã nghiệm thu.

## 1. Điểm nối đã đối chiếu

| Nguồn hiện có | Kết luận cho Phase 5 |
| --- | --- |
| `ParticipantSnapshot` của Phase 4 | Có user/employee ID của SELF, quản lý lúc kích hoạt và danh sách cấp dưới trực tiếp gồm cả người không tham gia; dùng làm bằng chứng quan hệ lịch sử |
| `CycleParticipant.evidence_version` | Dùng chung cho phân công, phản hồi và KPI; không tạo một cơ chế version evidence song song |
| `finalized_at`, cycle status | Chặn mutation nếu participant đã finalized hoặc cycle không ACTIVE; chưa thêm chức năng finalize/close |
| `authorize_domain_write` | Đã nhận tuple allowed roles, khóa guard/admin/user/family và kiểm tra lại quyền. Submit cần cho cả bốn role nếu được giao, không dùng HR-only policy hoặc live employee scope |
| `CycleRepository` và `participant_scope` | Dùng cho quyền xem tổng hợp theo HR/self/direct reports hiện tại. Không dùng để chặn inbox/submit của người đánh giá lịch sử ngoài scope này |
| Activation Phase 4 | Chỉ kiểm tra tài khoản SELF/MANAGER và ghi snapshot, không tạo `FeedbackAssignment`; không backfill phân công tự động khi upgrade |
| Audit allowlist/client API | Bổ sung allowlist feedback riêng; tái sử dụng Origin/CSRF, lỗi chuẩn, structured details và quy tắc giữ form khi lỗi |

Phase 4 đã qua CI tại `adcbabe`, 570 backend/69 frontend tests; tài liệu chốt tại `4ada5f9`. Phase 5 không sửa migration `20261020_0004` hoặc snapshot đã có để khớp dữ liệu tổ chức mới.

## 2. Kết quả và phạm vi

HR chọn người đánh giá; người được giao có hộp việc riêng, gửi rating/comment đúng một lần; HR theo dõi phần còn thiếu và đọc dữ liệu gốc. Nhân viên và quản lý hiện tại xem tổng hợp đã lọc bảo mật. Người đánh giá chỉ có quyền trên assignment của mình, không tự được mở hồ sơ, KPI hoặc báo cáo người được đánh giá.

Không triển khai tính điểm hiệu suất, chốt/đóng chu kỳ, Gemini/themes AI, dashboard, email nhắc việc, queue hoặc seed. Tổng hợp rating là dữ liệu phản hồi, không phải `feedback_score` hay `final_score` của Phase 6. Không tạo phản hồi giả để hoàn tất điều kiện bắt buộc.

## 3. Dữ liệu và vòng đời

Migration mới nối sau sole head `20261020_0004`; chọn mã revision khi bắt đầu code. Hai bảng mới, UUID, timestamp UTC, FK RESTRICT và không cascade xóa lịch sử:

| Bảng | Trường/ràng buộc |
| --- | --- |
| `feedback_assignments` | participant_id FK, reviewer_id User FK, reviewer_employee_id Employee FK ghi nhận danh tính lúc gán, relationship SELF/MANAGER/PEER/SUBORDINATE, required, due_at nullable, status OPEN/SUBMITTED/CANCELLED, version >=1, eligibility_snapshot JSONB object, created_at/updated_at |
| `feedback` | assignment_id FK UNIQUE, rating integer CHECK 1–5, comment VARCHAR(2000) không null mặc định chuỗi rỗng, submitted_at UTC |

Giữ **UNIQUE(participant_id, reviewer_id) trên cả các trạng thái**, đúng kiến trúc. Thêm partial UNIQUE(participant_id, relationship) cho SELF/MANAGER chưa CANCELLED để không có hai phân công cùng vai trò bắt buộc. CHECK SELF/MANAGER luôn required=true. Index phục vụ inbox theo reviewer/status/due_at; partial index không thay thế UNIQUE Feedback.assignment_id.

OPEN → SUBMITTED sau một lần gửi thành công; OPEN → CANCELLED chỉ do HR; CANCELLED → OPEN chỉ do HR phục hồi rõ ràng và kiểm tra lại eligibility. SUBMITTED bất biến: không sửa rating/comment, không hủy, đổi reviewer, relationship, required hoặc deadline.

DELETE assignment là **hủy mềm**, không xóa row. Khi cần giao lại cho cùng user, không tạo row thứ hai: HR phải phục hồi row CANCELLED bằng PATCH có version mới. Reviewer/relationship/eligibility snapshot của row không được đổi. Việc phục hồi kiểm tra người đó còn đủ điều kiện theo chính snapshot ấy; không âm thầm đổi sang hồ sơ khác đang liên kết với account.

PATCH thông thường chỉ áp dụng cho OPEN. CANCELLED chỉ được PATCH như một thao tác phục hồi status=OPEN rõ ràng, kèm các trường deadline/required được phép; không sửa ngầm một assignment đã hủy. Lookup HR phải đánh dấu người đã có assignment và đường phục hồi phù hợp, không chỉ kiểm tra quan hệ.

Eligibility snapshot có `schema_version=1`, rule_version, cycle/participant IDs, relationship, source ACTIVATION hoặc ASSIGNMENT, reviewer employee/user IDs và bằng chứng quan hệ cần thiết. Không ghi email, password/session hoặc toàn bộ cây tổ chức. Nhãn cần cho HR/inbox được lấy từ snapshot đã cho phép, không suy ra lịch sử từ dữ liệu hiện tại.

Tối đa 100 assignment OPEN/SUBMITTED mỗi participant; CANCELLED không tính vào giới hạn nhưng vẫn giữ lịch sử. Reviewer không nhất thiết phải tham gia chu kỳ. Role và employment status không được dùng thay cho quan hệ hợp lệ.

## 4. Chọn người đánh giá và quyền sau khi chuyển công tác

| Relationship | Điều kiện gán |
| --- | --- |
| SELF | Đúng `ParticipantSnapshot.user_id`, gắn reviewer_employee_id theo snapshot employee; luôn required |
| MANAGER | Đúng manager_user_id/manager_id trong snapshot kích hoạt, không dùng manager hiện tại; luôn required |
| SUBORDINATE | Employee/user xuất hiện trong direct_reports snapshot, user_id không null và employment_status ở snapshot là ACTIVE |
| PEER | Một employee hiện đang ACTIVE với account active; khác đối tượng được đánh giá và không thuộc các danh tính SELF/MANAGER/SUBORDINATE đã xác định trong snapshot |

Phân loại có thứ tự SELF → MANAGER → SUBORDINATE → PEER để không gán quản lý/cấp dưới lịch sử thành PEER, gây trùng người hoặc kẹt coverage. PEER không bắt buộc cùng phòng ban/người quản lý. Đây là cách cụ thể hóa đề xuất cho khái niệm “người khác đang hoạt động” trong kiến trúc.

Account được gán phải tồn tại và active. Với SELF/MANAGER/SUBORDINATE, snapshot cố định principal lịch sử; chuyển manager, đổi role, bỏ liên kết hoặc thay employment status sau đó không tự chuyển quyền submit sang user khác. Khi gửi, vẫn bắt buộc account/family hiện tại active và assignment thuộc chính user. Một MANAGER cũ có thể gửi assignment lịch sử dù không còn quyền xem tổng hợp của người đó. User đang mang role ADMIN cũng có thể gửi nếu chính họ được giao; không vì vậy có quyền HR.

Không tự thay SELF/MANAGER bằng quản lý mới hoặc tài khoản bất kỳ khi account lịch sử bị khóa. Trong phạm vi đề xuất này, ADMIN phải khôi phục account hợp lệ để hoàn tất feedback bắt buộc; HR thấy trạng thái bị chặn. Ủy quyền lịch sử hoặc chuyển danh tính SELF/MANAGER cần thay đổi nghiệp vụ riêng, không suy diễn từ form replacement. Đây là giới hạn rõ ràng, không coi missing feedback là zero hoặc bỏ requirement.

HR có lookup có phân trang theo participant/relationship. SELF/MANAGER có lựa chọn cố định; SUBORDINATE dùng snapshot; PEER dùng query employee/account active. DTO chỉ đủ chọn người: ID cần thiết, mã/tên, lý do đủ/thiếu điều kiện; không duyệt tài khoản qua `/users`, không lộ email hay snapshot cho reviewer khác.

## 5. Coverage bắt buộc, hủy và thay thế

Sau kích hoạt có thể chưa có assignment. HR phải chủ động giao SELF và MANAGER; giao diện đánh dấu thiếu từng vai trò, không sửa activation cũ. Readiness chỉ complete khi có **đúng một SELF và MANAGER đã submit**, cùng mọi assignment non-cancelled được HR đánh dấu required đã submit.

PEER/SUBORDINATE mặc định optional; HR có thể đánh dấu required. Không tự hoàn tất coverage khi account bị vô hiệu hóa, deadline qua hoặc reviewer chưa gửi. Mọi feedback đã submit, kể cả optional, đều tham gia mean rating với trọng số bằng nhau theo kiến trúc.

- Hủy một OPEN optional được phép trong ACTIVE/unfinalized; tăng evidence_version và audit.
- Không hủy đơn lẻ assignment required. SELF/MANAGER không được hạ required. Với PEER/SUBORDINATE, HR có thể chủ động PATCH required=false trước khi hủy; cả hai thao tác phải versioned/audited, không tự hạ trong DELETE.
- Thay reviewer của OPEN PEER/SUBORDINATE dùng một thao tác replacement nguyên tử: cùng relationship/required, hủy cũ và tạo hoặc phục hồi row của người mới đủ điều kiện. Một lỗi rollback cả hai; tăng evidence_version đúng một lần.
- Replacement không sửa feedback đã submit, không đổi relationship và không ghi lại snapshot lịch sử của participant. Người mới đã có assignment SUBMITTED/OPEN hoặc có row CANCELLED không tương thích thì trả conflict.
- Readiness nội bộ trả đầy đủ missing/blocked assignments cho HR và Phase 6. DTO công khai không trả reviewer IDs, số lượng optional/required theo nhóm nhỏ hoặc danh sách ai chưa gửi.

## 6. Deadline, nhập liệu và gửi đúng một lần

`due_at` nullable: null không giới hạn thời gian, cycle vẫn phải ACTIVE. Có deadline thì nhận chuỗi ISO timestamp có timezone, chuẩn hóa UTC; từ chối naive timestamp, bool và số Unix timestamp. Khi tạo/phục hồi/sửa hạn, thời điểm phải ở tương lai hoặc null. Deadline không tự theo end_date và không tự hủy assignment. UI hiện múi giờ rõ ràng; input local được chuyển sang ISO có offset/UTC.

Gửi tại `now >= due_at` trả 409 deadline_passed, kiểm tra thời gian lại sau khi lấy khóa. HR có thể gia hạn assignment OPEN đã quá hạn; không sửa hạn của SUBMITTED. Không cần cron, trạng thái overdue được suy ra lúc đọc.

POST feedback chỉ nhận `assignment_id`, `expected_assignment_version`, `expected_evidence_version`, `rating`, `comment`. Server tự suy ra reviewer/employee/cycle/relationship/required; payload thêm các trường này bị 422. Rating StrictInt 1–5, từ chối bool/float/string. Comment là plain text tối đa 2.000 ký tự sau chuẩn hóa CRLF → LF và trim; cho LF/tab, chặn các C0 khác và DEL/NUL. Có thể để trống, không render HTML/Markdown hoặc đưa nội dung vào log/audit.

Mutation xác thực lại user/family, tìm assignment thuộc user ở SQL, khóa cycle → participant → assignment, kiểm tra lifecycle/finalized/status/deadline/versions, insert feedback, đổi SUBMITTED, tăng assignment version và shared evidence_version rồi audit trong một transaction. UNIQUE assignment_id bảo vệ lớp DB. Submit lặp trả 409 feedback_already_submitted khi assignment vẫn trong lifecycle hợp lệ, không tăng version/audit lần hai. Không có PATCH/DELETE feedback.

Nếu response bị mất sau commit, UI tải assignment của mình để kiểm tra đã gửi; không sửa nội dung đã nhận và không tự gửi lại với version mới. Hai assignment khác nhau của cùng participant gửi cùng evidence_version có thể xung đột 409; form giữ nội dung để người dùng chủ động tải version mới và xác nhận gửi lại.

## 7. Bảo mật nội dung và tổng hợp

Tách rõ DTO, không lấy raw response rồi xóa vài field ở frontend:

| Người đọc | Dữ liệu được trả |
| --- | --- |
| Reviewer bất kỳ role | Inbox/detail và feedback của chính assignment; ngữ cảnh tối thiểu người được đánh giá/chu kỳ, deadline và versions. Không danh sách reviewer khác; không cấp quyền employee/KPI/report |
| HR trong chế độ quản trị | Assignment, identity, trạng thái, blocked/required coverage và rating/comment gốc để quản trị |
| HR/self/current direct manager đọc summary | Tổng số đã gửi, mean_rating, readiness đã lọc, relationship summaries theo ngưỡng; authored_feedback chỉ của chính caller |
| ADMIN không được giao | Không có feedback inbox của người khác, không có raw hoặc employee summary |

Overall mean là Decimal(sum rating)/count của mọi feedback đã submit; null nếu count=0. DTO hiển thị hai số lẻ ROUND_HALF_UP dưới dạng string. Phase 6 phải tính lại từ rating nguyên hoặc sum/count, không dùng mean đã làm tròn để tính điểm.

SELF/MANAGER có thể hiện group mean/count, nhưng không tự đưa comment/identity của người khác vào summary. Với PEER và SUBORDINATE, chỉ hiện group mean/count khi có ít nhất **3 user khác nhau đã submit trong chính nhóm đó**. Dưới ngưỡng trả `suppressed=true, mean_rating=null, submitted_count=null`; dùng cùng hình dạng cho 0/1/2. Không trả ID, comment, timestamp, histogram hoặc danh sách riêng lẻ của nhóm. Own authored feedback được trả tách biệt đúng user_id, không phải toàn bộ comment đã “ẩn tên”.

Không tạo themes từ free text trong Phase 5. Tổng bình quân toàn review vẫn được trả theo kiến trúc; nhóm nhỏ và việc so sánh nhiều lần có thể cho phép suy luận. Giao diện nói rõ đây là hạn chế bảo mật của nhóm nhỏ, **không bảo đảm ẩn danh**. Không có filter theo reviewer hoặc endpoint nhóm tùy ý để lách threshold; HR raw là quyền riêng có chủ đích.

## 8. API dự kiến

Prefix `/api/v1`; kế thừa error envelope và no-store. GET không sinh assignment, không tăng version, không gọi AI. POST tạo assignment/feedback trả 201, replacement/PATCH/DELETE mềm trả 200 với versions mới.

| Endpoint | Quyền và payload chính |
| --- | --- |
| GET `/feedback-assignments?view=mine` | Mặc định cho cả 4 role; SQL reviewer_id=current user; filter cycle_id/status/relationship, phân trang |
| GET `/feedback-assignments?view=administration&participant_id=...` | Chỉ HR; raw theo participant/cycle, filter status/relationship; missing/blocked coverage trong DTO quản trị riêng |
| GET `/feedback-assignments/{id}` | Chính reviewer hoặc HR; DTO theo quyền ở server, outsider và missing cùng 404 |
| GET `/feedback-reviewer-options?participant_id=...&relationship=...` | Chỉ HR; lookup eligibility có phân trang/tìm mã hoặc tên literal |
| GET `/feedback-context?participant_id=...` | Chỉ HR; nhãn participant, trạng thái chu kỳ, evidence version và coverage cho form, kể cả khi chưa có assignment; dùng lại participant được chọn từ trang chu kỳ |
| GET `/feedback-coverage?participant_id=...` | Chỉ HR; thiếu SELF/MANAGER đã gửi, số required chưa gửi và account bị khóa |
| POST `/feedback-assignments` | HR `{participant_id,reviewer_id,relationship,required,due_at,expected_evidence_version}`; SELF/MANAGER bắt buộc required=true |
| PATCH `/feedback-assignments/{id}` | HR `{expected_assignment_version,expected_evidence_version,...}`; chỉ required/due_at và phục hồi status=OPEN từ CANCELLED, không đổi identity/relationship |
| DELETE `/feedback-assignments/{id}` | HR JSON versions + reason_code; hủy mềm OPEN optional |
| POST `/feedback-assignments/{id}/replace` | HR versions + reviewer_id mới + due_at/reason_code; replacement OPEN PEER/SUBORDINATE cùng relationship/required, nguyên tử |
| POST `/feedback` | Chính reviewer; payload được giới hạn ở mục 6, gửi một lần |
| GET `/employees/{id}/feedback?cycle_id=...` | HR/self/current direct manager; summary đã lọc, không raw chỉ vì client truyền view=administration |

List `{items,total,page,page_size}`, page >=1, page_size 1–100; sort allowlist due_at/created_at với null last và UUID tie-breaker. Options q tối đa 100, tìm literal, sort employee_code. Scope áp dụng trước count/pagination/detail. Không cho reviewer dùng query parameter để mở admin mode. Inbox context có cycle name/period và subject snapshot label; không dựa vào quyền mở `/review-cycles/{id}`.

Versions là strict positive integer. Mọi thay đổi assignment/submit thành công tăng participant.evidence_version đúng một lần; thay row tăng assignment.version tương ứng, replacement tăng version của cả row cũ/mới. No-op vẫn kiểm tra auth/lifecycle/versions, không tăng version/audit. Không cập nhật cycle.version vì danh sách participant và policy không đổi.

Mã lỗi dự kiến: 404 assignment_not_found/participant_not_found; 409 stale_assignment_version/stale_evidence_version, cycle_not_active, participant_finalized, reviewer_ineligible/reviewer_inactive, assignment_already_exists, required_relationship_exists, required_coverage_conflict, assignment_not_open, feedback_already_submitted, deadline_passed, assignment_limit_reached. Input sai 422, auth 401/403; eligibility details chỉ HR, không echo comments hoặc dữ liệu DB.

## 9. Khóa, audit và giao diện

Giữ thứ tự Phase 4: guard `730031` → active ADMIN UUID → actor/reviewer liên quan theo UUID → family → cycle → participant → assignments theo UUID → feedback. Chỉ đọc ID để chuẩn bị tập khóa sau guard; đọc lại eligibility/permissions sau user locks. Submit cho đủ 4 role qua helper nhưng HR mutation vẫn HR-only. Không khóa assignment rồi mới khóa participant và không refactor toàn bộ auth.

Audit riêng cho assignment.created/updated/cancelled/reopened/replaced và feedback.submitted; metadata allowlist chỉ IDs, relationship, required/status, versions, reason_code enum. Không rating/comment, tên/email, eligibility JSON hoặc nguyên body. Audit failure rollback cả insert feedback, trạng thái, replacement và mọi version. Không tạo bảng review/AI hoặc cơ chế invalidation giả; Phase 6 dùng shared evidence version để phát hiện stale.

UI tiếng Việt: `/feedback` inbox cho mọi role, `/feedback/{assignment_id}` xem/gửi của mình, `/feedback-administration` chỉ HR và `/employees/{id}/feedback?cycle_id=...` cho summary scoped. Menu ADMIN cũng có inbox riêng. Cycle participants dẫn tới quản trị/summary đúng quyền; reviewer ngoài employee scope chỉ dùng assignment route. Form HR chọn người qua lookup, không nhập UUID thủ công; SELF/MANAGER tự hiện lựa chọn lịch sử và giải thích account bị chặn. Có xác nhận submit bất biến, hủy/thay/phục hồi, trạng thái quá hạn, incomplete/empty/loading/error và keyboard/mobile.

Sau 409 không tự retry bằng version mới; giữ rating/comment, chỉ cập nhật versions khi người dùng chủ động tải lại và assignment còn OPEN. Nếu đã SUBMITTED thì chuyển sang bản đã gửi. Cache key chứa mode/cycle/participant/user scope phù hợp, xóa cache khi đổi tài khoản; cache raw HR và summary phải tách biệt. Không dùng chung raw object để render trang employee.
