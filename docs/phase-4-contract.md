# Hợp đồng Phase 4 — Chu kỳ đánh giá và KPI

Ngày lập: 2026-10-19. Trạng thái: schema, API, giao diện và nghiệm thu CI đã hoàn tất ngày 2026-10-20. Chi tiết công việc và bằng chứng tại [kế hoạch Phase 4](superpowers/plans/2026-10-19-phase-4-cycles-kpis.md).

Tài liệu cụ thể hóa Phase 4 trong [kiến trúc tổng thể](architecture.md), giữ nguyên modular monolith, cookie/CSRF, phân quyền theo dữ liệu và audit cùng giao dịch. Các quy tắc dưới đây đã được triển khai và kiểm chứng theo kế hoạch.

## 1. Kết quả và ranh giới

HR tạo chu kỳ nháp, chọn nhân viên tham gia, kiểm tra điều kiện và kích hoạt. Sau đó HR hoặc quản lý trực tiếp hiện tại phân bổ trọn bộ KPI và nhập kết quả thực tế. Nhân viên xem KPI của mình. ADMIN quản lý cấu hình chấm điểm mặc định; không kế thừa quyền HR.

Phase này không tính điểm KPI hoặc điểm tổng, không nhận phản hồi 360, không chốt đánh giá, không gọi Gemini và không tạo dashboard/seed. Cột dữ liệu phục vụ lịch sử không đồng nghĩa đã có nghiệp vụ của phase sau.

Kiến trúc quy định chu kỳ chỉ CLOSED khi mọi đánh giá đã finalized. Vì finalization thuộc Phase 6, Phase 4 **không cung cấp thao tác đóng chu kỳ**, cũng không thêm lối tắt đóng cưỡng bức để demo. Hệ thống ban đầu chỉ có tối đa một chu kỳ ACTIVE; việc mở chu kỳ ACTIVE thứ hai phải đợi luồng đóng hợp lệ ở Phase 6. Ngày kết thúc không tự đóng chu kỳ.

## 2. Dữ liệu đã triển khai

Migration `20261020_0004` nối sau `20261019_0003` và là sole head hiện tại. UUID, timestamp UTC, FK RESTRICT, không xóa lịch sử đã kích hoạt.

| Bảng | Trường và ràng buộc chính |
| --- | --- |
| `system_config` | Singleton có CHECK khóa cố định; `version >= 1`; `scoring_policy` JSON đã được service kiểm tra; timestamp. Migration khởi tạo duy nhất cấu hình mặc định, không tạo tài khoản hoặc dữ liệu demo |
| `review_cycles` | UUID, `name` 1–200 ký tự, `start_date`, `end_date`, `status` DRAFT/ACTIVE/CLOSED, `version >= 1`, `scoring_policy_snapshot` và `policy_source_version` nullable khi DRAFT, `activated_at` nullable, timestamp; CHECK start <= end và tính nhất quán trạng thái/snapshot; partial unique index đảm bảo chỉ một ACTIVE |
| `cycle_participants` | UUID, cycle/employee FK, UNIQUE(cycle_id, employee_id), `evidence_version >= 1`, snapshot nullable khi DRAFT, `finalized_at` nullable để làm hàng rào bất biến; không có API ghi finalized_at trong Phase 4 |
| `kpi_definitions` | UUID, code unique, name, description, unit, direction HIGHER_IS_BETTER/LOWER_IS_BETTER, is_active, version, timestamp |
| `employee_kpis` | UUID, participant/definition FK, UNIQUE(participant_id, definition_id), snapshot định nghĩa, target, actual nullable, weight, timestamp; CHECK target > 0, actual >= 0 nếu có, 0 < weight <= 100 |

Snapshot participant lưu mã/tên nhân viên, UUID/mã/tên phòng ban và chức danh, employee/user ID của bản thân và quản lý, cùng các quan hệ cấp dưới trực tiếp tại lúc kích hoạt. Quan hệ cấp dưới lưu employee/user ID, kể cả người không tham gia chu kỳ; không suy ra quan hệ lịch sử từ cây hiện tại ở Phase 5. Không lưu email, password hoặc session trong snapshot. Snapshot là dữ liệu nội bộ; DTO phải có allowlist, không trả toàn bộ JSON quan hệ cho người đọc scoped.

Khi nháp, participant chỉ chọn employee; preview dùng dữ liệu hiện tại và được ghi rõ chưa đóng băng. Kích hoạt mới ghi snapshot chính thức. Dữ liệu tổ chức chuyển phòng/đổi tên/đổi quản lý sau đó không sửa snapshot.

Code dùng chuẩn Phase 3: trim, uppercase ASCII, `[A-Z0-9][A-Z0-9_-]{1,31}`. Name/unit không rỗng sau trim, tối đa 200/50 ký tự; description tối đa 2.000 ký tự, có thể rỗng. Chặn NUL/C0/DEL ở các trường văn bản một dòng; description chỉ cho phép xuống dòng/tab trong nhóm điều khiển. Không có hard-delete định nghĩa KPI; dùng is_active.

Target/actual dùng NUMERIC(14,4); weight dùng NUMERIC(5,2). API gửi/nhận các số nghiệp vụ dưới dạng chuỗi thập phân; xử lý bằng Decimal, từ chối bool, NaN, Infinity, vượt precision/scale và không âm thầm làm tròn đầu vào. Không dùng float để cộng trọng số. Tổng weight của một allocation phải đúng `100.00`.

## 3. Cấu hình mặc định và policy đóng băng

Policy schema v1 gồm `schema_version: 1`, `kpi_weight: "70.00"`, `feedback_weight: "30.00"`, `kpi_cap: "100.00"`. Hai trọng số thành phần trong [0,100], tối đa hai chữ số thập phân, cộng đúng 100.00. Cap là null hoặc số dương hữu hạn NUMERIC(7,2). null biểu thị không giới hạn; không gán KPI LOWER_IS_BETTER vào chu kỳ có cap null. Cách chuyển rating và làm tròn theo kiến trúc, chưa mở thành tùy chọn mới.

ADMIN đọc/sửa mặc định qua `/settings/scoring`, gửi expected_version. HR chỉ nhận preview policy cho chu kỳ nháp và policy đã đóng băng cho chu kỳ đang xem; không được sửa system defaults. Kích hoạt đọc cấu hình mới nhất **trong cùng transaction**, sao chép policy và version nguồn vào chu kỳ. Đổi mặc định sau đó chỉ tác động các lần kích hoạt tiếp theo.

Chỉ lưu/kiểm tra policy trong Phase 4. Hàm chấm điểm và báo cáo ở Phase 6; không trả score giả bằng 0.00 khi actual chưa có.

## 4. Vòng đời chu kỳ và participant

1. HR tạo DRAFT với name/start_date/end_date; không yêu cầu ngày hiện tại nằm trong kỳ. Ngày là nhãn kỳ đánh giá; quyền ghi do status quyết định, không có cron tự kích hoạt/đóng.
2. HR sửa metadata, thêm/xóa participant chỉ khi DRAFT. Mọi sửa dùng expected_version của cycle. Thêm một batch 1–100 employee UUID duy nhất; toàn batch thành công hoặc rollback. Nhân viên phải ACTIVE; không tự thêm toàn bộ tổ chức. Dùng phân trang để chọn nhiều batch, không giới hạn tổng participant theo page_size.
3. Xóa participant chỉ trong DRAFT, khi chưa có evidence; đây là chỉnh danh sách nháp, không xóa hồ sơ nhân viên/lịch sử. ACTIVE/CLOSED không thêm/xóa participant.
4. Kích hoạt yêu cầu expected_version, có ít nhất một participant và không có ACTIVE khác. Đọc lại điều kiện: participant đang làm việc, department/position còn hoạt động; tài khoản SELF tồn tại và active; quản lý hiện tại khác bản thân, đang làm việc và có tài khoản active khác SELF. Các account không bắt buộc có role EMPLOYEE/MANAGER để được nhận feedback sau này: quyền submit dựa trên assignment và account active.
5. Gốc tổ chức không có quản lý hoặc người chưa liên kết tài khoản chưa đủ điều kiện tham gia với chính sách SELF + MANAGER bắt buộc. Trả danh sách vấn đề có giới hạn và tổng số cho HR; không tự bỏ họ khỏi chu kỳ hoặc tự tạo tài khoản/quản lý.
6. Trong một transaction, đóng băng policy + snapshot nhân viên/quan hệ, tăng cycle version và evidence_version của các participant được snapshot, đổi ACTIVE và ghi audit. Một lỗi ở bất kỳ participant/audit nào rollback toàn bộ. Không tạo FeedbackAssignment trong Phase 4.

Sau kích hoạt, account bị vô hiệu hóa hoặc bỏ liên kết không được tự sửa snapshot. Phase 5 phải kiểm tra tài khoản reviewer hiện tại và có quy trình HR thay assignment có audit; snapshot không cấp quyền đăng nhập. Không đưa ra cam kết rằng eligibility tại kích hoạt bảo đảm mọi tài khoản sẽ còn active mãi.

## 5. Quyền đọc và ghi

| Dữ liệu/thao tác | ADMIN | HR | MANAGER | EMPLOYEE |
| --- | --- | --- | --- | --- |
| System scoring defaults | Đọc/sửa | Không; chỉ xem preview/snapshot cycle được phép | Không | Không |
| Tạo/sửa/kích hoạt chu kỳ, danh sách nháp | Không | Có | Không | Không |
| Danh sách/chi tiết chu kỳ | Không | Tất cả, kể cả DRAFT | ACTIVE/CLOSED có self hoặc direct report hiện tại tham gia | ACTIVE/CLOSED có bản thân tham gia |
| Participant và allocation | Không | Tất cả | Bản thân + direct reports hiện tại | Bản thân |
| Tạo/sửa/ngừng dùng định nghĩa KPI | Không | Có | Không | Không |
| Đọc định nghĩa KPI | Không | Toàn bộ | Chỉ định nghĩa đã gán trong phạm vi | Chỉ định nghĩa đã gán cho bản thân |
| Gán KPI/nhập actual | Không | Participant chưa finalized trong ACTIVE | Direct report hiện tại đang làm việc, actor có hồ sơ ACTIVE, trong ACTIVE và chưa finalized | Không |

MANAGER đọc self nhưng không tự ghi KPI của mình. HR có thể hoàn tất actual của nhân viên đã nghỉ việc trong kỳ; không tự hủy participant khi employment_status thay đổi. HR không cần có employee profile để quản trị.

Scope theo quan hệ hiện tại, không lấy manager snapshot làm quyền đọc/ghi. Snapshot chỉ phục vụ lịch sử và assignment về sau. Mọi list/count/detail áp dụng SQL scope trước phân trang; manager mới nhận quyền với direct report hiện tại, manager cũ mất quyền ngay ở request kế tiếp. User chưa liên kết employee có danh sách rỗng. UUID ngoài phạm vi và UUID không tồn tại có cùng lỗi 404; không tiết lộ tồn tại qua version/error details hoặc lookup.

Manager cần tra cứu định nghĩa chưa từng được gán để phân bổ. Cung cấp lookup riêng `/employees/{id}/kpi-options?cycle_id=...` chỉ cho HR/người quản lý được phép ghi participant đó, gồm định nghĩa active. Đây là quyền chọn KPI cho một công việc cụ thể, không mở toàn bộ `/kpis` cho mọi manager.

## 6. Allocation, actual và version

- Chỉ ghi trong ACTIVE, participant chưa finalized; mỗi writer khóa cùng participant, kiểm tra expected_evidence_version rồi mới ghi. Version bắt đầu 1, tăng mỗi mutation evidence thành công, kể cả kích hoạt snapshot; không tăng khi lỗi hoặc payload không làm đổi dữ liệu. No-op vẫn phải xác thực, kiểm tra version/lifecycle/scope.
- PUT allocation gửi **toàn bộ** danh sách không rỗng, tối đa 100 KPI, không trùng definition_id, target > 0, từng weight > 0, tổng đúng 100.00. Không lưu một allocation dở dang trên server; giao diện giữ nháp cục bộ đến khi hợp lệ.
- Allocation chưa được tạo có thể rỗng khi vừa ACTIVE. PUT rỗng không dùng để xóa một allocation hiện có. Chưa có allocation được hiển thị là “Chưa phân bổ KPI”.
- Định nghĩa mới gán phải active, hợp policy cap của cycle. Snapshot gồm code/name/description/unit/direction và version định nghĩa; sửa định nghĩa không đổi assignment đã có. KPI đang giữ lại dùng snapshot cũ; bỏ rồi gán lại dùng snapshot mới.
- Full replacement reconcile theo definition_id trong transaction, giữ UUID của dòng còn lại. Dòng giữ nguyên target giữ actual; thay target xóa actual về null để nhập lại. Đổi weight không tự xóa actual. Dòng mới có actual null; PUT không nhận actual từ client. Dòng đã bỏ không xuất hiện ở allocation hiện hành; audit ghi ID/version thay đổi, không tạo lời hứa lưu lịch sử chấm điểm trước Phase 6.
- Định nghĩa retired có thể giữ trong allocation hiện hữu và nhập actual; không gán mới hoặc đưa trở lại sau khi đã bỏ. Không refresh snapshot khi giữ dòng. Không cho đổi snapshot/direction bằng PATCH assignment.
- PATCH actual nhận duy nhất `actual` và expected_evidence_version; actual null có nghĩa xóa kết quả để nhập lại. Không sửa target/weight bằng endpoint này. Mỗi thay đổi làm tăng evidence_version của participant, không chỉ version của dòng KPI.
- Khi hai người sửa cùng participant, chỉ một request với version cũ thắng; request còn lại trả 409 `stale_evidence_version`. UI giữ dữ liệu đang nhập, báo xung đột, cho tải bản mới và nhập lại; không tự retry mutation bằng version mới.
- Phase 5–7 phải dùng cùng participant lock/version cho feedback, tính điểm và kiểm tra stale. Chưa tạo bảng PerformanceReview/AI hoặc logic invalidation giả trong Phase 4.

## 7. API đã triển khai

Tất cả prefix `/api/v1`, cùng envelope lỗi Phase 2/3. GET/POST/PATCH/PUT/DELETE thành công trả no-store; POST tạo resource trả 201, thao tác còn lại trả 200 (xóa participant nháp trả cycle version mới). Mutation yêu cầu exact Origin, CSRF gắn family còn active và kiểm tra lại quyền trong transaction.

| Endpoint | Payload/kết quả chính |
| --- | --- |
| GET, PATCH `/settings/scoring` | ADMIN; PATCH `{expected_version, policy}`; trả policy/version |
| GET, POST `/review-cycles` | GET phân trang scoped; POST `{name,start_date,end_date}` tạo DRAFT |
| GET, PATCH `/review-cycles/{id}` | Detail có version, policy preview/snapshot, quyền thao tác do server suy ra; PATCH metadata + expected_version, DRAFT only |
| GET, POST `/review-cycles/{id}/participants` | GET phân trang scoped; POST `{expected_version,employee_ids:[...]}`; trả cycle version và số thêm |
| DELETE `/review-cycles/{id}/participants/{participant_id}` | HR, DRAFT; JSON `{expected_version}`; trả cycle version mới |
| POST `/review-cycles/{id}/activate` | `{expected_version}`; trả cycle đã ACTIVE/version; lỗi validation không ghi một phần |
| GET, POST `/kpis`; PATCH `/kpis/{id}` | List scoped, HR tạo/sửa/retire; PATCH expected_version + field thay đổi |
| GET `/employees/{id}/kpi-options?cycle_id=...` | Lookup phân trang định nghĩa active, kiểm tra quyền ghi participant; không lộ catalog qua employee ngoài phạm vi |
| GET `/employees/{id}/kpis?cycle_id=...` | Participant/cycle status, evidence_version, quyền thao tác và allocation snapshots; không có điểm |
| PUT `/employees/{id}/kpis?cycle_id=...` | `{expected_evidence_version,items:[{definition_id,target,weight}]}`; trả allocation/version mới |
| PATCH `/employee-kpis/{id}` | `{expected_evidence_version,actual}`; resolve participant ở server; trả allocation/version mới |

`GET allocation` là một aggregate có tối đa 100 dòng, không phải catalog phân trang. Danh sách cycle/participant/definition/options dùng `{items,total,page,page_size}`, page >= 1, page_size 1–100. Filter cycle: status, q tối đa 100; sort start_date/name/created_at. Participant: q/department snapshot khi ACTIVE, dữ liệu hiện tại khi DRAFT, sort employee_code. Definition/options: q/is_active/direction, sort code/name/created_at; options luôn active. Sort allowlist tăng dần + UUID tie-breaker, tìm kiếm literal. Không nhận role, scope, snapshot hoặc status tùy ý từ client.

Cycle response/count cho MANAGER/EMPLOYEE chỉ phản ánh participant trong phạm vi, không lộ tổng số toàn chu kỳ. Preview activation lỗi chi tiết chỉ HR. DTO account/relationship không lộ email hoặc danh sách reviewer tương lai.

Các lỗi dự kiến: 422 validation_error; 404 cycle_not_found/participant_not_found/kpi_not_found/employee_kpi_not_found; 409 duplicate_code/participant_already_enrolled/cycle_not_draft/cycle_not_active/active_cycle_exists/activation_requirements_not_met/kpi_definition_inactive/kpi_policy_incompatible/participant_finalized/stale_version/stale_evidence_version. 401/403 giữ auth contract. Trường hợp sai tổng weight/duplicate items là 422 có field details; lỗi điều kiện DB không trả SQL hoặc tên constraint nội bộ.

Ví dụ PUT allocation, không đưa ID nhân viên hay quyền vào body:

```json
{
  "expected_evidence_version": 2,
  "items": [
    {"definition_id": "<uuid-doanh-so>", "target": "100.0000", "weight": "60.00"},
    {"definition_id": "<uuid-chat-luong>", "target": "95.0000", "weight": "40.00"}
  ]
}
```

## 8. Giao dịch, khóa và audit

Với quy mô đồ án, mọi writer Phase 4 dùng lại organization advisory transaction lock `730031` để nhất quán với cập nhật manager/user link của Phase 3. Không thêm guard ngược thứ tự hoặc refactor khóa Phase 2/3 diện rộng để tối ưu trước khi có số đo.

Thứ tự: guard → active ADMIN rows theo UUID → actor/các user liên quan theo UUID → kiểm tra family/CSRF → config nếu cần → cycle → participant theo UUID → definition/assignment theo UUID. Đọc lấy ID phục vụ lập tập khóa được phép nhưng phải đọc lại dữ liệu/quyền sau khi đã giữ khóa. Không lấy user/participant lock rồi mới chờ guard. Writer system defaults cũng tuân thủ thứ tự này. Không giữ transaction giữa hai request hoặc lúc người dùng nhập form.

Không gọi thẳng `OrganizationRepository.authorize_write` cho MANAGER/ADMIN vì hàm hiện tại chỉ cho HR. Thêm helper authorization dùng chung có allowed roles rõ ràng, bảo toàn quy tắc HR-only của endpoint cũ và kiểm thử hồi quy. Revalidate role/is_active/family và direct-report scope sau khi đợi khóa. Không dùng context đã đọc trước khi chờ để quyết định mutation.

Partial unique ACTIVE và UNIQUE participant/definition/code là hàng rào DB cuối cùng. Validate dưới khóa, map IntegrityError sang 409 ổn định. Race activation với đổi manager/link hoặc sửa defaults phải tạo một snapshot nhất quán theo thứ tự commit; không có tổ hợp dữ liệu nửa cũ/nửa mới. Sau activation, tổ chức vẫn có thể thay đổi theo Phase 3.

Audit tối thiểu: `scoring_defaults.updated`, `review_cycle.created/updated/activated`, `cycle_participant.enrolled/removed`, `kpi_definition.created/updated`, `kpi_allocation.replaced`, `employee_kpi.actual_updated`. Allowlist riêng; metadata chỉ UUID, code, field names, version trước/sau, trạng thái và số lượng. Không copy name/description, snapshot, email, request body hoặc credential. Ghi audit và dữ liệu/version trong cùng transaction; lỗi audit rollback cả deletion/replacement/snapshot.

## 9. Giao diện và bàn giao

Các route đã triển khai: `/review-cycles`, `/review-cycles/{id}`, `/kpis`, `/employees/{id}/kpis?cycle_id=...`, `/settings/scoring`. Giao diện tiếng Việt, dùng API client/TanStack Query/RHF/Zod hiện có. Không thêm dependency hoặc UI framework chỉ để làm phase này.

HR có màn hình nháp, selector nhân viên tìm kiếm/phân trang, xác nhận activation nêu rõ các trường sẽ đóng băng. Không tự nhập UUID. Manager chọn KPI qua options có scope, chỉnh toàn bộ tỷ trọng với tổng hiện tại, chỉ lưu khi đủ 100.00; đổi target cảnh báo xóa actual. Actual chưa có hiển thị “Chưa nhập”, 0.0000 là kết quả hợp lệ. Người chỉ có quyền đọc không thấy form ghi.

Hiển thị rõ kỳ đánh giá đang chọn; không tự dùng một cycle lịch sử mơ hồ. Dùng server capabilities để hỗ trợ UI, backend vẫn kiểm tra độc lập. Có loading/error/empty, field errors, keyboard labels, pending, xác nhận retirement và xung đột version. Giữ form khi lỗi; invalidate cycle/participant/KPI/options liên quan sau ghi thành công và xóa cache khi đổi tài khoản theo cơ chế auth hiện có.

Nghiệm thu đã chứng minh luồng HR + manager + employee thật, scope sau transfer, stale version, race PostgreSQL, audit rollback, migration và Docker/proxy/persistence. Phase 1–4 đã hoàn thành và nghiệm thu CI; feedback và scoring thuộc các phase tiếp theo.
