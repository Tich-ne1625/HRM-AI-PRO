# Kế hoạch Phase 12 — KPI theo tiến trình và check-in

Ngày **25/11/2026**. **Đã triển khai; kết quả nghiệm thu local theo [báo cáo Phase 12](../../phase-12-report.vi.md).** Baseline **`13fd9e3`**: Phase 11 đã hoàn thành local; migration Phase 12 **`20261125_0012`**. [Contract](../../phase-12-contract.vi.md), [hướng dẫn theo role](../../phase-12-huong-dan.vi.md), [lộ trình mở rộng](../../nang-cap-quan-ly-hieu-suat-lien-tuc.vi.md).

## 1. Mục tiêu sử dụng được

Nhân viên không chỉ nộp “đã làm xong”, mà còn khai số đo có nguồn; quản lý xác minh và xem tiến trình thật; hai bên check-in, chốt hỗ trợ rồi kiểm tra việc hỗ trợ đã xong chưa. HR thấy khâu đang tắc để điều phối. **Không làm AI hoặc điểm cuối kỳ trong Phase 12.**

Ví dụ: Huy xử lý hồ sơ → Mai Anh nghiệm thu → Huy lập số đo từ hồ sơ → Mai Anh xác minh → tổng KPI cập nhật → check-in ghi nhận còn thiếu dữ liệu từ đối tác → giao Mai Anh hỗ trợ với hạn cụ thể → Mai Anh báo đã hỗ trợ → Huy xác nhận → lần check-in sau thấy hành động đã xong và số liệu thay đổi từ nguồn nào.

## 2. Kết quả đối chiếu code và quyết định thiết kế

| Hiện có | Điểm cần làm tiếp |
| --- | --- |
| `work_management/models.py`: goal snapshot, source_key, submission/event bất biến | Không tạo lại hệ thống giao việc; thêm sổ đo nối đúng goal/revision/bằng chứng |
| `GoalInput`: SUM/LAST/RATIO/MILESTONE, baseline/target/weight/source | Chốt cách nhập và tổng hợp từng loại; không thêm DISTINCT_COUNT chỉ qua tên gọi |
| `AllocationService.view`: CONTINUOUS trả actual=None; API ghi/tính/chốt cũ bị chặn | API tiến trình riêng; không mở đường nhập actual hoặc tính điểm cũ |
| Work `accept` và `reopen` giữ lịch sử, dùng version và giao dịch | ACCEPTED không tự tạo số; reopen phải treo đóng góp trong cùng giao dịch |
| `overview.py`/`tasks.py`: số việc, người giữ bước | Thêm backlog số đo/check-in/hành động; thiếu dữ liệu không hiện thành điểm 0 |
| Workspace theo role, modal và SSE chung | Dùng lại layout và connection; cố định vị trí chức năng, không thêm một hệ điều hướng khác |
| Demo biệt lập cổng 13039, một ACTIVE mỗi DB | Demo Phase 12 riêng; không đóng kỳ hiện tại hoặc seed vào DB chính |

Các quyết định chi tiết nằm trong contract: nguồn theo từng đối tượng, sửa bằng revision thay thế, VOID không quay lại số cũ, snapshot ghim thời điểm biết dữ liệu, check-in hai người có hành động và phản hồi. Giữ cách đo/baseline đã duyệt; không tự lấp dữ liệu cũ.

## 3. Phạm vi và thứ tự

| Task | Phụ thuộc | Đầu ra review được | Trạng thái |
| --- | --- | --- | --- |
| 0 | Phase 11 | Chốt contract, ma trận quyền/chuyển trạng thái, ví dụ số và wireframe | Đã hiện thực và đối chiếu bằng kiểm thử |
| 1 | 0 | Migration và constraints cho rule/ledger/snapshot/check-in/actions | Đã triển khai; fresh/upgrade, parity, triggers |
| 2 | 1 | Nộp/duyệt/trả/sửa/rút số, nguồn và bất biến | Đã triển khai; quyền, replay, race, rollback |
| 3 | 2 | Tổng hợp chính xác, snapshot, xử lý reopen/treo nguồn | Đã triển khai; bốn phép đo và lịch sử có nguồn |
| 4 | 1, 3 | Check-in hai chiều và hành động hỗ trợ | Đã triển khai; riêng tư, công bố, phụ lục, kiểm tra chéo |
| 5 | 2–4 | Quyền, tasks/dashboard, thông báo và SSE tích hợp | Đã tích hợp vào hạ tầng hiện có |
| 6 | 2–5 | Web theo role, form số đo và check-in, modal/responsive | Đã triển khai; kiểm thử component và trình duyệt |
| 7 | 0–6 | Demo đầu–cuối, hồi quy, tài liệu/báo cáo, deploy có bảo toàn | Đạt local; 989 backend / 202 web theo các lượt ghi trong báo cáo; main 0012 giữ dữ liệu cũ |

Thực hiện lần lượt, gate task trước đạt mới chuyển phần phụ thuộc. Không triển khai một lượt rồi mới kiểm tra quyền/tính nguyên tử. Không ước lượng ngày hoàn thành hoặc số test thành công trước khi có kết quả.

## Task 0 — Khóa hợp đồng nghiệp vụ

**Tệp:** `docs/phase-12-contract.vi.md`, tài liệu vai trò/UI hiện có khi cần.

- Rà soát ma trận actor × đối tượng × trạng thái × hành động, gồm HR metadata và quản lý là owner của hành động hỗ trợ.
- Chốt đơn vị RATIO/MILESTONE, giới hạn số, source key, LAST cùng timestamp, mốc bất biến, thiếu dữ liệu/0, thời gian xảy ra so với thời gian biết.
- Chốt không nhận lô thời gian chồng lấn trong v1; nội dung tự do của source không đủ để tuyên bố tự động kiểm chứng hệ thống ngoài.
- Chốt số VERIFIED cũ vẫn hiệu lực khi bản sửa đang chờ; VOID loại cả dòng; work reopen treo cả dòng và phải xác minh lại sau nghiệm thu mới.
- Wireframe trang và modal cho ba role nghiệp vụ; kiểm tra tránh nút trùng/tab lồng nhau; đọc hiểu ví dụ đầu–cuối không cần đọc schema.

**Gate:** có các ví dụ hợp lệ và bị chặn với đáp án định lượng; không còn quyết định tác động tới unique/FK/nguồn dữ liệu bị để “xử lý sau” trong Task 1. Contract được đối chiếu với schema, service và các ca kiểm thử, kể cả vị trí LAST/MILESTONE sau VOID.

## Task 1 — Schema và migration bổ sung

**Vị trí dự kiến:** `apps/api/app/modules/progress/`, mở rộng `work_management`, registry, migration tiếp sau head thực tế `20261125_0011`. Không ghi số head mới vào CI trước khi migration tồn tại.

- Rule snapshot bất biến theo goal/revision và algorithm version; stream Measurement có khóa nguồn, projection version/current effective/pending; revisions chứa payload/source/bằng chứng, quyết định/event append-only.
- Plan có measurement version riêng; aggregate snapshots giữ dữ liệu chính xác, provenance và hash. Chốt lưu danh sách nguồn có phân trang/chi tiết thay vì nhét không giới hạn vào response dashboard.
- Check-in/chuẩn bị/phần chia sẻ, bản công bố/phụ lục/acknowledgement, action và lịch sử. Tách draft riêng với nội dung đã chia sẻ; không chỉ dựa vào việc frontend giấu trường.
- Notifications thêm FK target cụ thể cho measurement/check-in/action; không dùng nhầm `work_item_id` để mang UUID loại khác.
- Ràng buộc cùng plan/goal/rule/work/submission bằng composite FK hoặc kiểm tra giao dịch rõ, unique source/milestone/LAST timestamp/pending revision/idempotency, check trạng thái/giá trị/version. Triggers bảo vệ payload đã gửi và event/revision/snapshot đã đóng băng, không vô tình cấm cập nhật nháp/projection.
- Index hỗ trợ scope trước pagination, inbox trạng thái/hạn, lịch sử theo ID/time, snapshot version và source lookup. Không thêm message broker/worker/provider mới.

**Gate:** fresh migration, metadata parity, trực tiếp thử FK/unique/check/immutability; upgrade fixture gồm LEGACY và CONTINUOUS Phase 11, fingerprint cột cũ giữ nguyên. Không tạo bản ghi số đo/check-in từ dữ liệu cũ, không downgrade DB người dùng.

## Task 2 — Dịch vụ số đo và xác minh

**Vị trí dự kiến:** `progress/models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`; dùng authorization/CSRF/transaction helper hiện có.

- Danh sách KPI/rule/dòng nguồn theo scope; tạo nháp, sửa nháp, submit/return/reject/verify; đề nghị correction/VOID có lý do và expected version.
- WORK điền nguồn có sẵn, nộp chỉ khi ACCEPTED và tham chiếu đúng lần; EXTERNAL_REFERENCE hiển thị là xác minh nội bộ. Không fetch URL.
- Một nguồn chỉ một revision pending; bản gửi bất biến, sửa/nộp lại thành revision mới. Kiểm tra key chuẩn hóa và hai loại nguồn không tạo hai đóng góp của cùng mã.
- Chặn tự duyệt, giả goal/work/submission UUID, role đổi, account khóa, hạn sai và nhập lô không hỗ trợ. Version/idempotency giống quy ước của hệ thống; không phát thông báo thành công khi rollback.

**Gate:** hai tài khoản nộp → trả → nộp lại → verify → correction → verify → VOID; giữ đủ lịch sử và chỉ đúng một bản hiệu lực. Cạnh tranh verify/return/correction và replay có đáp án xác định; thử lỗi audit/notice rollback toàn bộ. Task này chưa được tuyên bố actual hoạt động khi Task 3 chưa đạt.

## Task 3 — Tổng hợp và nguồn hiệu lực

**Vị trí dự kiến:** `progress/aggregation.py`, `snapshots.py`; hook `work_management/service.py` ở reopen và quyết định nguồn liên quan.

- Hàm thuần SUM/LAST/RATIO/MILESTONE, số chính xác, không cộng baseline hay snapshot lũy kế. Rule revision đóng băng, aggregate không đọc định nghĩa hiện hành.
- Cập nhật hiệu lực và snapshot đồng bộ khi verify/VOID/treo nguồn, tăng measurement version đúng một lần. GET không tạo dữ liệu hoặc tự sửa snapshot thiếu.
- Treo mọi revision của nguồn WORK khi reopen trong cùng giao dịch work/audit/notice/aggregate. Nghiệm thu lại cần nộp và verify số mới; không tự khôi phục.
- Cung cấp hiện hành/theo khoảng thời gian và snapshot tại version; provenance cho phép mở tới đúng revision/bằng chứng/decision. Check-in có thể ghim snapshot không có dữ liệu.
- Chốt canonical hash và thứ tự nguồn ổn định; rebuild từ ledger phải bằng snapshot đã lưu. Đọc nhiều bảng dùng transaction snapshot nhất quán, không trộn hai version trong response.

**Gate số học:** SUM delta 20/35/50 → 105; LAST cùng dữ liệu → 50, duyệt muộn không thắng ngày đo mới hơn; RATIO 9/10 + 1/2 → 83,3333… và 30/40 + 90/100 → 85,714285…; 0 mẫu/không dữ liệu → null; giá trị 0 có xác minh → 0; MILESTONE 30/70 không trùng mốc. Correction 10→8 tính 8, không phải 18; correction chờ không loại 10; VOID bỏ dòng; reopen bỏ nguồn nhưng snapshot cũ nguyên vẹn. Có overflow, DST/múi giờ, biên cutoff, race verify/reopen và lỗi lưu snapshot.

## Task 4 — Check-in và hành động hỗ trợ

**Vị trí dự kiến:** `apps/api/app/modules/checkins/`, dùng chung nguồn số từ progress, không sao chép hàm aggregate.

- Quản lý lên lịch và khoảng rà soát, gợi ý lần sau 7/14 ngày qua thao tác xác nhận. Nhân viên/quản lý chuẩn bị riêng, chia sẻ rõ, mở buổi rà soát.
- Công bố biên bản với snapshot đã ghim, nhận xét/vướng mắc/điểm chưa thống nhất và hành động. Không công bố thay phần draft chưa chia sẻ; không mặc định không xác nhận là đồng ý.
- Nhân viên đọc hoặc yêu cầu làm rõ; quản lý phản hồi bằng phụ lục, acknowledgement tham chiếu đúng bản/phụ lục. Câu hỏi chưa xử lý vẫn hiện, không sửa hoặc xóa biên bản đã công bố.
- Action một owner, reviewer còn lại; bắt đầu/nộp/trả/bổ sung/xác nhận; hủy/thay thế có lý do và lịch sử, không tự đóng việc hỗ trợ của mình. Link work item nếu có nhưng không tự sinh đóng góp KPI.
- Hạn action không sau hạn xác minh; overdue/readiness lấy từ đồng hồ server. HR metadata riêng, không nhận nội dung riêng trong payload.

**Gate:** nhân viên cần hỗ trợ → quản lý nhận hành động → báo xong → nhân viên xác nhận; chiều ngược lại manager kiểm tra action của nhân viên. Draft riêng không lộ, biên bản giữ snapshot cũ sau sửa số, phụ lục có xác nhận đúng bản. Race công bố/hủy hoặc submit/return không tạo hai kết quả, lỗi audit/notice rollback.

## Task 5 — Tích hợp tasks, dashboard, thông báo và tương thích

- `work_management/tasks.py`: ai đang cần nộp/xác minh/bổ sung/đọc biên bản/xử lý hành động; tránh thêm cùng bước dưới nhiều nhãn và không biến chậm duyệt của quản lý thành lỗi nhân viên.
- Dashboard nhân viên/quản lý có số xác minh/thiếu dữ liệu/backlog, HR có aggregate điều phối. Không hiện score/AI coaching hoặc mức đạt theo tiến độ tuyến tính chưa cam kết.
- Deep link mới và SSE invalidation theo query domains; reuse kết nối duy nhất, polling fallback và session/cache fencing. Shared event không chứa text, số đo riêng hay draft.
- Giữ `managed_by_workflow` ở allocation/actual/calculate/finalize/close CONTINUOUS; không thay engine/EmployeeKPI lịch sử. Thông điệp giải thích đúng phần chờ Phase 14.

**Gate:** bốn role thử GET/POST/deep link giả UUID; chuyển phiên/role không còn cache người cũ; notify chỉ sau commit và đúng recipient, đọc notice không hoàn tất action. Bộ hồi quy LEGACY/Phase 11 không đổi hành vi, kể cả reopen không có measurement.

## Task 6 — Web theo role, không tăng độ rối

**Vị trí dự kiến:** `features/work-management/`, `features/progress/`, `features/checkins/`; dùng `WorkspaceDialog`, form, pagination và query hooks hiện có.

- Cố định bốn tab của khu vực hiện có: Công việc / Kế hoạch & mục tiêu / Số đo KPI / Check-in; header/sidebar giữ nguyên. HR đi qua chu kỳ, ADMIN không có menu hoặc fetch dữ liệu mới.
- Số đo: chọn KPI → nguồn → form đúng phương pháp → xem lại → gửi. Quản lý thấy nguồn, giá trị cũ/đề nghị mới và quyết định; lịch sử/bằng chứng đọc được, số chờ không trộn tổng xác minh.
- Check-in: lịch, chuẩn bị riêng/chia sẻ, biên bản ghim số, hành động có người nhận và hạn. Dùng từ tiếng Việt chỉ đúng bước, phân biệt “đã đọc” và “đồng ý”.
- Chuyển công việc sang số đo bằng ngữ cảnh rõ và một lớp modal; giữ bộ lọc và draft. Không chồng modal có nhiều cấp tab, không bắt Back của browser.
- Không sửa nút để lách quyền; actions do server cho biết và API kiểm tra lại. Review trước verify/VOID/công bố, không gửi khi pending; lỗi/version conflict giữ nội dung, retry giữ UUID.

**Gate:** component tests cho permission, form, null/0/ratio, correction/VOID, private draft, acknowledgement và keyboard; browser forms bằng manager/employee/HR/admin ở 1280px/390px. Không tràn ngang hoặc mất draft khi chuyển tab/lỗi, focus trở về vị trí hợp lý.

## Task 7 — Demo, hồi quy và báo cáo

- Thêm dataset có marker **`continuous-progress-demo-v1`**, CLI riêng chỉ DB `_test` rỗng/đúng marker; dùng domain services và giao dịch có rollback, không chạm main hoặc sửa dataset Phase 11 đã có.
- Tái dùng Mai Anh–Huy để dễ hiểu nhưng trong stack Phase 12 biệt lập, chọn cổng không xung đột 3000/13039. Có bốn phương pháp trong fixture, còn câu chuyện UI tập trung ba KPI: hồ sơ xác minh SUM, tỷ lệ đúng hạn RATIO và mốc bàn giao MILESTONE; LAST trình bày riêng như snapshot lũy kế.
- Tình huống cần thấy: số chưa nộp, chờ duyệt, trả lại, đã xác minh, correction chờ/đã duyệt, VOID, nguồn treo do reopen, check-in cần đọc/làm rõ và hỗ trợ quá hạn. Không giả timestamp hệ thống nhiều tuần; fixture lịch sử nằm DB test và ghi rõ hư cấu.
- Browser thao tác form từ công việc → nộp số → trả/nộp lại → verify → snapshot → check-in → quản lý hỗ trợ → nhân viên xác nhận. Chụp desktop/mobile, ghi không gọi AI. Không chỉ seed trạng thái cuối rồi gọi là đầu–cuối.
- Chạy unit/integration/race/schema/upgrade/quality, full web tests/typecheck/lint/build và Docker smoke phù hợp. Chạy có kiểm soát tài nguyên, ghi số test thực tế, phân biệt local và CI.
- Đo query count/độ trễ ở danh sách và tổng hợp với 60 người cùng fixture nhiều nguồn số đo trong DB test; kiểm tra không N+1, không tải toàn bộ công ty hoặc bằng chứng vào dashboard. Phân trang chi tiết nguồn, giới hạn page size theo quy ước hiện có; ghi cấu hình máy và số bản ghi thay vì suy ra sẵn sàng production từ dữ liệu nhỏ.
- Backup/fingerprint trước migration thực tế; so sánh cột cũ ở cả LEGACY/CONTINUOUS và hash mật khẩu, không xuất giá trị nhạy cảm. Bảo toàn `.env`/khóa/cycle đang ACTIVE. Sau các gate mới triển khai ảnh đã kiểm chứng; không reseed main để làm demo.
- Cập nhật README, API/database/architecture, hướng dẫn theo role/demo và `phase-12-report.vi.md` **bằng kết quả thật sau khi code**, không tạo báo cáo hoàn thành trước.

**Gate cuối phase:** người thử theo được ai cung cấp → ai xác minh → con số nào đổi → bằng chứng ở đâu → check-in quyết định gì → ai hỗ trợ → ai xác nhận. Snapshot trước sửa vẫn đọc được, không có đóng góp trùng hoặc lộ nội dung cho HR/ADMIN; LEGACY hoạt động; không có lời khẳng định Phase 13/14 đã xong.

## 4. API dự kiến và cách review từng lát cắt

Tên dưới đây là thiết kế, **chưa phải endpoint đang có**; chốt schema/request/error cụ thể trong Task 0–2.

| Nhóm | Dự kiến |
| --- | --- |
| Tiến trình | `/api/v1/progress/plans/{id}/goals`, `/goals/{id}/measurements`, `/measurements/{id}`, `/measurements/{id}/draft`, `/measurements/{id}/actions` |
| Truy xuất | `/api/v1/progress/plans/{id}/snapshots`, `/snapshots/{id}`, `/snapshots/{id}/sources`, lịch sử dòng số đo có pagination |
| Check-in | `/api/v1/checkins`, `/{id}`, `/{id}/preparation`, `/{id}/actions`, `/{id}/history`, `/{id}/follow-ups` |
| Hành động | `/api/v1/checkin-actions/{id}`, `/{id}/actions`, `/{id}/history` |
| HR | API metadata/tổng hợp riêng theo cycle; không tái dùng response chi tiết rồi giấu trường ở UI |

Mỗi lát cắt giao gồm service + API + UI nhỏ + fixture + test gate; schema triển khai trước, không chờ cuối phase mới có thứ để xem. Bắt đầu bằng một SUM và cặp Mai Anh–Huy, sau đó phủ RATIO/LAST/MILESTONE, correction/VOID/reopen và check-in. Chưa mở đa nguồn phức tạp khi lát cắt này chưa đúng.

## 5. Điều kiện bàn giao sang phase sau

| Phase | Đầu vào Phase 12 phải cung cấp | Không làm sớm ở đây |
| --- | --- | --- |
| 13 — AI cố vấn | Query scoped nguồn xác minh/chờ, work/check-in/hành động đã chia sẻ, snapshot/version có nguồn | Không đưa draft riêng/HR_PRIVATE/chat riêng vào context; không gọi Gemini lúc test phase này |
| 14 — Kết quả có nguồn | Aggregate chính xác, rule/version/provenance, thiếu dữ liệu và backlog quá hạn phân biệt rõ | Chưa gán actual vào engine v1 hoặc mở chốt/đóng CONTINUOUS |
| 15 — Thay đổi/bàn giao | Bản bất biến và event để đối chiếu trước/sau, người giữ bước và nguồn treo rõ ràng | Không đổi baseline giữa kỳ, chuyển reviewer hay chạy nhắc hạn offline |

Điều chỉnh lộ trình chỉ dựa vào gate thực tế. Phase 12 hoàn thành sẽ cho quá trình định lượng và hỗ trợ có kiểm chứng; để trình bày trọn vòng tới AI và điểm cuối vẫn phải tiếp tục Phase 13–14.
