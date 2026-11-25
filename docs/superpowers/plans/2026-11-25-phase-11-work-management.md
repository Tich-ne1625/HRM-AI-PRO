# Kế hoạch Phase 11 — Kế hoạch hiệu suất và công việc có nghiệm thu

Ngày: **25/11/2026**. Trạng thái: **hoàn thành nghiệm thu local — Task 0–6 đạt gate**. Xem [báo cáo và bằng chứng](../../phase-11-report.vi.md), [hướng dẫn theo role](../../phase-11-huong-dan.vi.md). Chưa tuyên bố nghiệm thu production hoặc hoàn thành các Phase 12–15.

| Task | Gate đã kiểm chứng |
| --- | --- |
| 0 | Contract, quyền/trạng thái, nguồn số và đường tương thích LEGACY |
| 1 | Migration `20261125_0011`, fresh upgrade, metadata/constraint/immutability, fingerprint dữ liệu cũ |
| 2 | Hai tài khoản thống nhất kế hoạch, sửa revision, xác nhận đúng bản, điều kiện activation |
| 3 | Giao/đề xuất/sửa draft, tiến trình, vướng mắc, nộp/trả/nộp lại/nghiệm thu, replay/race/rollback |
| 4 | Thông báo/SSE/readiness/deep link theo scope, chặn API cũ và chuyển tổ chức khi ACTIVE |
| 5 | UI theo role, tab cố định/modal/draft/error/focus, browser desktop 1280px và mobile 390px |
| 6 | Demo riêng qua domain services, browser đầu–cuối, tài liệu, deploy và bảo toàn dữ liệu chính |

Đọc trước: [đề xuất quản lý hiệu suất liên tục](../../nang-cap-quan-ly-hieu-suat-lien-tuc.vi.md), [kiến trúc hiện tại](../../architecture.md), [vai trò](../../vai-tro-va-quy-trinh.vi.md), [cách dùng bộ dữ liệu mở rộng](../../du-lieu-mo-rong.vi.md).

## Đầu ra và giới hạn của phase

Một quản lý tạo kế hoạch cho nhân viên, hai bên làm rõ tiêu chuẩn, quản lý duyệt, nhân viên xác nhận đã nhận. Sau khi HR kích hoạt kỳ CONTINUOUS, quản lý giao việc; nhân viên cập nhật, báo vướng mắc, nộp bằng chứng; quản lý nghiệm thu hoặc trả lại. Người dùng thấy lịch sử và việc cần làm tiếp theo.

Phase này **chưa** tạo điểm cuối kỳ CONTINUOUS, hội thoại AI cố vấn, sổ đo KPI hay lịch check-in hoàn chỉnh. Các nút nhập actual/tính điểm cũ phải bị chặn trong chế độ mới để không công bố dữ liệu chưa có nguồn. Kỳ LEGACY và tính năng AI báo cáo cũ tiếp tục hoạt động.

Không thay `.env`, mật khẩu, dữ liệu thực hành hoặc tự kích hoạt/đóng kỳ đang dùng. Không gọi Gemini thật. Thử nghiệm luồng mới trong database/stack biệt lập vì ứng dụng hiện chỉ cho một kỳ ACTIVE.

## Task 0 — Chốt hợp đồng nghiệp vụ và đường tương thích

**Tệp dự kiến:** `docs/phase-11-contract.vi.md`, cập nhật tài liệu kiến trúc/API/quyền khi contract được duyệt.

- Chốt chế độ `LEGACY`/`CONTINUOUS`, quyền, vòng đời WorkPlan/acknowledgement/WorkItem/EvidenceSubmission và điều kiện kích hoạt.
- Chốt lịch kỳ: ngày bắt đầu/kết thúc đo, hạn nhận kế hoạch, hạn nộp dữ liệu, hạn xác minh, hạn giải trình. Múi giờ là thuộc tính kỳ, UTC là cách lưu timestamp.
- Một kế hoạch hiện hành cho mỗi participant; revision chứa baseline KPI/target/weight/source/acceptance/milestone. Danh mục KPI dùng lại; định nghĩa đo và baseline được snapshot.
- Quản lý có thể duyệt kế hoạch do mình soạn cho nhân viên khác; chặn tự duyệt hồ sơ của mình. Nhân viên đề xuất nội dung và yêu cầu làm rõ, không tự duyệt baseline.
- Giữ giới hạn MVP: không tự chuyển kế hoạch giữa quản lý khi đang chạy, không đổi baseline giữa kỳ, không sửa kết quả đã chốt. Chuyển người/phòng ảnh hưởng CONTINUOUS ACTIVE phải bị chặn rõ; khóa bảo mật vẫn được phép và sinh trạng thái cần HR xử lý.
- Nhận diện mọi đường ghi cũ có thể vượt workflow: allocation replace, actual update, calculate/recalculate, finalize/close, seed helper. Định nghĩa lỗi `managed_by_workflow`/readiness cho mode mới; không chỉ ẩn nút.
- Chốt hợp đồng đóng góp dữ liệu cho Phase 12 ngay ở đây: WorkItem có owner, goal, tiêu chuẩn đầu ra và nguồn duy nhất; `ACCEPTED` không tự biến thành điểm.

**Gate:** ma trận actor × đối tượng × trạng thái × hành động; bảng chuyển trạng thái; ví dụ hợp lệ/không hợp lệ; wireframe theo role và ít nhất một kịch bản đầu–cuối được đọc hiểu. Nếu chưa chốt nguồn số KPI thì chưa viết migration áp dụng runtime.

## Task 1 — Schema và migration bổ sung

**Phụ thuộc:** Task 0. **Vị trí:** `apps/api/app/modules/work_management/`, migration tiếp theo sau head thực tế, model registry.

- Thêm `workflow_mode` cho kỳ, default LEGACY; metadata lịch riêng của CONTINUOUS. Không gán mode theo tên kỳ hoặc dựa vào dữ liệu demo.
- Thêm kế hoạch/revision, mục tiêu, công việc, lịch sử và bản gửi bằng chứng. Draft có version; approved revision bất biến. Bằng chứng đính kèm đầu tiên là text/URL, không tải tệp hay fetch URL.
- FK/unique/check/index cho participant-plan, revision-goal, owner, reviewer, due date, loại event, version dương và cùng cycle/participant. Ràng buộc bằng composite key hoặc kiểm tra giao dịch, tránh trộn UUID của hai nhân viên.
- Có trường `client_request_id` chống nộp/giao trùng. Định nghĩa paged-list, thứ tự timestamp + ID ổn định; không tải toàn bộ người/công việc.
- Không sửa bảng/tính lại kết quả lịch sử. Nếu gắn nguồn kế hoạch mới vào EmployeeKPI, trường mới nullable cho LEGACY và có ràng buộc rõ theo mode.
- Bổ sung liên kết target thông báo phù hợp, không nhét work ID vào employee/assignment ID hoặc bỏ qua scope hiện tại.

**Gate:** fresh upgrade, metadata parity, upgrade trên fixture có dữ liệu hiện tại; fingerprint các bản ghi cũ giữ nguyên; kiểm tra constraint vượt API. Không downgrade tự động trên database người dùng.

## Task 2 — Dịch vụ lập và thống nhất kế hoạch

**Phụ thuộc:** Task 1. **Vị trí:** work management schemas/service/repository/router; review cycle activation.

- Quản lý đọc nhân viên trực tiếp, soạn baseline cho participant DRAFT; nhân viên đề xuất/yêu cầu làm rõ/xác nhận nhận bản cụ thể. HR đọc và điều phối, không sửa nội dung kỹ thuật thay quản lý.
- Duyệt khi KPI có nguồn đo, target hợp lệ, trọng số tổng 100%, chuẩn nghiệm thu, lịch và người xác minh. Không chấp nhận tỷ lệ chỉ có một số phần trăm nhưng không định nghĩa tử/mẫu.
- Kế hoạch đổi sau khi nhân viên đọc thì xác nhận cũ không còn giá trị với bản mới. Sự xác nhận luôn gắn revision ID.
- CONTINUOUS activation đòi hỏi baseline và acknowledgement đầy đủ ngoài các điều kiện tài khoản/quan hệ/policy hiện có. Phản hồi lỗi nêu đúng người và việc cần bổ sung, không tự tạo phiếu 360 hoặc ký nhận hộ.
- Khi kỳ mới hoạt động, adapter chỉ cung cấp target/weight đã được duyệt. Mọi đường PUT phân bổ cũ cho mode này trả lỗi; LEGACY giữ contract cũ.
- Với draft chưa có dữ liệu tiến trình, không hiện bảng biểu như đang có actual hoặc báo cáo chấm điểm hợp lệ.

**Gate:** hai tài khoản soạn → đề nghị làm rõ → sửa → duyệt → xác nhận đúng revision → HR kích hoạt; race giữa sửa/xác nhận/kích hoạt không chấp nhận bản cũ. LEGACY activation và allocation tests vẫn qua.

## Task 3 — Giao việc, cập nhật và nghiệm thu

**Phụ thuộc:** Task 2.

- Một người chịu trách nhiệm chính và người duyệt đủ quyền; kiểm tra người thực hiện đang hoạt động, thuộc phạm vi quản lý và participant tương ứng. Nhân viên chỉ tự tạo đề xuất, không giao việc chính thức cho người khác.
- Giao việc có goal, đầu ra/checklist, thời hạn trong cửa sổ công việc của kỳ và ưu tiên. Một việc không đo KPI vẫn hiển thị bình thường, nhãn rõ; không tự cho điểm vì có task.
- Nhân viên bắt đầu, cập nhật mô tả, báo cờ blocked có lý do, nộp bằng chứng. Quản lý accept/return có nhận xét. Không tự nghiệm thu đầu ra do chính mình thực hiện.
- Sửa bản nháp được; đã gửi thì tạo lần nộp tiếp theo thay vì sửa lịch sử. ACCEPTED giữ nội dung nguồn và người quyết định; hủy/reopen có lý do và điều kiện, không xóa event đã xảy ra.
- Deadline/acceptance/owner đã cam kết không sửa ngầm sau giao việc. MVP ghi đề nghị thay đổi, chưa áp dụng thay đổi giữa kỳ; UI nói rõ giới hạn.
- Lưu sự kiện, audit, trạng thái và thông báo trong một giao dịch. Khóa/ủy quyền theo thứ tự đã có; không lấy khóa user/ADMIN sau khóa work item.

**Gate:** giao → cập nhật → blocked → được hỗ trợ → submit → return → resubmit → accept; lặp request không lặp event/thông báo; hai người/tab cùng xử lý chỉ một quyết định có hiệu lực; lỗi audit hoàn tác.

## Task 4 — Tích hợp thông báo, readiness và chặn đường tắt

**Phụ thuộc:** Task 2–3.

- Thông báo nhận kế hoạch/việc, yêu cầu làm rõ, nhận bản nộp, yêu cầu bổ sung và nghiệm thu. Đúng recipient, không phát nội dung bằng chứng hay mô tả riêng tư ra SSE.
- Mở đúng plan/work item trong khung chi tiết. Danh sách Việc cần làm thể hiện người đang giữ bước; read notice không hoàn tất action.
- Tái sử dụng một SSE connection/tab, coalescing và fallback; thêm query domains có phân quyền. Không tạo socket thứ hai chỉ để cập nhật task.
- Không gửi thông báo mỗi lần lưu nháp hay báo tiến độ nhỏ. Nhắc hạn đọc-derived là MVP; thông báo deadline chủ động phải có task scheduler/lease/idempotency riêng trước khi quảng cáo là chạy khi offline.
- `calculate/finalize/close` với CONTINUOUS trả trạng thái chưa có nguồn/phase chưa sẵn sàng. Khi Phase 14 hoàn thành mới mở readiness mới; không ghi tạm actual rồi gọi engine cũ để giả lập luồng.
- Chặn chuyển phòng/quản lý ảnh hưởng active CONTINUOUS ở đúng đường organization write, không chặn nhầm nghiệp vụ LEGACY. Thay đổi/thu hồi quyền phải làm cache và khả năng thao tác cập nhật ngay.

**Gate:** deep link không lộ đối tượng khác; thông báo tới đúng role; GET không gây mutation; mất quyền/đổi role giữa mở màn hình và submit bị từ chối; đường API cũ không vượt được mode.

## Task 5 — Giao diện theo công việc của từng role

**Phụ thuộc:** Task 2–4. **Vị trí dự kiến:** `apps/web/src/features/work-management/`, protected routes, navigation/dashboard/dialog dùng chung.

- Thêm một nhóm **Công việc & mục tiêu**, với nhãn “Công việc của tôi”/“Điều phối nhóm” theo role. ADMIN không hiện nhóm này; HR xem tổng hợp điều phối qua chu kỳ thay vì một bảng task toàn công ty dày đặc.
- Giao diện nhân viên ưu tiên việc cần bắt đầu, cần bổ sung, bị chặn và kế hoạch chờ đọc. Quản lý ưu tiên bản nộp chờ xác minh và việc cần hỗ trợ.
- Kế hoạch rõ mục tiêu, KPI, cách đo, chuẩn đạt và người duyệt; dùng bước “xem lại trước gửi”, không đặt các nút duyệt cạnh nút lưu nháp thiếu phân biệt.
- Khung chi tiết nhất quán: Nội dung / Tiến trình & bằng chứng / Trao đổi / Lịch sử. Bảng trao đổi công việc là dữ liệu được chia sẻ trong scope, không tự sao chép chat riêng người–người.
- X/Escape, focus khi mở/đóng, thao tác bàn phím, modal gần toàn màn hình trên mobile, giữ filter và không mất draft khi chuyển tab nội bộ. Cảnh báo khi đóng draft chưa lưu.
- Ẩn action sai quyền/trạng thái nhưng vẫn giải thích hợp lý các bước đang chờ. Không render nút AI cố vấn giả ở Phase 11; nhãn roadmap ở tài liệu, không làm người dùng tưởng đã có tính năng.

**Gate:** người thử theo đúng role hoàn tất luồng; thử desktop 1280px/mobile 390px, keyboard, error/retry/empty, hai tab xung đột, giữ bản nhập khi server trả lỗi. Test hành vi thật, không chỉ snapshot class CSS.

## Task 6 — Demo có câu chuyện và bằng chứng nghiệm thu

**Phụ thuộc:** Task 1–5.

- Tạo seed riêng `continuous-demo-v1` trong stack/database test; mượn nhân vật CSKH Huy/Hoàng Mai Anh từ bộ 60 người nhưng không sửa seed/bản ghi đang dùng.
- Có một kỳ DRAFT cần làm rõ kế hoạch và một luồng ACTIVE với việc TODO, blocked, bị trả lại, ACCEPTED. Tạo dữ liệu có thời gian hợp lý; demo mới chỉ khẳng định các bước Phase 11 đã làm.
- Dùng domain services và outer transaction; marker chống nạp trùng, kiểm tra namespace, hoàn tác khi lỗi muộn. Không “hoàn thiện” trạng thái bằng UPDATE trực tiếp để vượt duyệt.
- Ghi bằng chứng migration, role/scope, concurrency, browser, bảo toàn dữ liệu; ghi giới hạn Phase 11 và đường tiếp theo sang ledger/check-in.
- Cập nhật README, hướng dẫn role, API/database/architecture và báo cáo phase dựa trên kết quả thật. Không lấy số test phase cũ làm kết quả lần này.

**Gate cuối phase:** deploy được trong stack biệt lập, dữ liệu cũ không đổi, một người dùng mới hiểu được ai giao → ai làm → ai duyệt → việc nào đang chờ. Chưa tuyên bố nghiệm thu quản lý hiệu suất liên tục toàn phần; phải tiếp tục 12–14 để có quá trình dẫn tới điểm cuối.

## Điểm nối bắt buộc sang Phase 12–15

| Phase sau | Task nghiệp vụ cần đặc tả | Fixture minh chứng tối thiểu |
| --- | --- | --- |
| 12 | Ledger, rule revision, verified measurements, sửa số trước cutoff, aggregate snapshots, check-in/actions | Không cộng snapshot lũy kế; ratio 30/40 rồi 90/100 cuối kỳ đúng; mẫu số 0; duplicate source; return/verify race; check-in sinh hành động có người nhận |
| 13 | Thread owner/scope, context builder, evidence refs, provider turns, share excerpt, preview action | Hỏi khi chưa có review; dữ liệu thiếu; quyền đổi; prompt injection trong mô tả việc; HR_PRIVATE không sang nhân viên; mất provider; replay không tạo hai turn thành công |
| 14 | Cutoff/reconciliation, evidence bundle adapter, scoring/version, employee response/clarification, HR finalize | Click từ score → actual → measurement revision → bằng chứng; bundle đổi làm điểm cũ STALE; có giải trình thì không chốt sớm; LEGACY không đổi |
| 15 | Baseline changes theo ngày hiệu lực, handover, scheduler vận hành, mở rộng mẫu và pilot | Không áp mục tiêu mới hồi tố; chuyển quản lý không mở dữ liệu riêng trước bàn giao; nhắc hạn không nhân bản giữa replica; người dùng làm được luồng mà không được người phát triển chỉ từng nút |

Mỗi phase sau có contract và kế hoạch task riêng khi đến lượt. Bảng này giữ các quyết định phụ thuộc ngay từ đầu; chưa thay cho bản đặc tả triển khai đã duyệt của các phase đó.

Đã lập bước tiếp theo: [kế hoạch Phase 12](2026-11-25-phase-12-measurements-checkins.md) và [dự thảo contract](../../phase-12-contract.vi.md), trạng thái chưa triển khai. Đối chiếu hai tài liệu này trước khi bổ sung ledger/check-in; không thay đổi trạng thái nghiệm thu Phase 11.
