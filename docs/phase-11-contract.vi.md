# Hợp đồng Phase 11 — Kế hoạch và công việc

Ngày 25/11/2026. Triển khai theo kế hoạch Phase 11 đã được chấp thuận.

## Phạm vi và nguồn số

Kỳ cũ mặc định `LEGACY`, giữ nguyên dữ liệu và cách vận hành. Kỳ mới chọn chế độ khi tạo; không chuyển chế độ sau đó. `CONTINUOUS` thu thập quá trình làm việc; Phase 11 chưa tạo actual, điểm hay AI cố vấn. Nghiệm thu một công việc **không** tự cộng điểm KPI.

Lịch CONTINUOUS gồm múi giờ IANA, hạn xác nhận kế hoạch, hạn nộp, hạn xác minh và hạn giải trình. Hạn xác nhận không sau ngày bắt đầu; hạn nộp không trước cuối ngày kết thúc; xác minh không trước hạn nộp; giải trình không trước xác minh. Timestamp lưu UTC; ngày làm việc diễn giải trong múi giờ kỳ.

Trong MVP, lịch kỳ cố định khi đã có kế hoạch cá nhân đầu tiên, tránh HR thay thời hạn sau khi hai bên đã thống nhất. Có thể đổi tên kỳ. Hạn xác nhận là mốc theo dõi quá hạn; nhân viên vẫn được xác nhận muộn trước khi HR kích hoạt. Hạn nộp/xác minh là giới hạn ghi thực sự ở API. Thay đổi lịch/baseline và bàn giao đang hoạt động thuộc Phase 15.

Mỗi participant có một kế hoạch với các revision bất biến. Mỗi mục tiêu tham chiếu danh mục KPI, snapshot định nghĩa, baseline, target dương, trọng số, nguồn đo, cách tổng hợp và chuẩn nghiệm thu. Tổng trọng số đúng 100. Ratio phải nêu tử và mẫu; milestone phải có mốc và tỷ trọng tổng 100. Phase 12 mới ghi sổ đo và tính actual: SUM dùng delta, LAST dùng snapshot, RATIO cộng tử/mẫu, MILESTONE dùng mốc cố định. Không dùng số tin nhắn, số task hoặc thời gian online làm điểm mặc định.

## Quyền và trạng thái

| Người | Đối tượng | Hành động |
| --- | --- | --- |
| HR | Kỳ và tổng hợp kế hoạch | Tạo kỳ, thêm người, xem tình trạng, kích hoạt khi đủ điều kiện; không soạn/duyệt kỹ thuật hay nghiệm thu thay quản lý |
| Quản lý | Nhân viên trực tiếp đang hoạt động | Soạn/gửi/duyệt kế hoạch của người khác; giao việc, phản hồi, trả lại/nghiệm thu |
| Nhân viên | Kế hoạch và công việc của mình | Đề xuất/làm rõ, xác nhận đúng revision; đề xuất việc, bắt đầu, cập nhật, báo vướng, nộp và nộp lại bằng chứng |
| ADMIN | Tài khoản | Không có quyền nghiệp vụ kế hoạch/công việc do vai trò ADMIN |

Kế hoạch: `DRAFT → SUBMITTED → APPROVED`; nhân viên/quản lý yêu cầu làm rõ `SUBMITTED/APPROVED → CHANGES_REQUESTED`; quản lý sửa tạo revision mới về `DRAFT`, hủy xác nhận cũ. Nhân viên xác nhận chỉ bản APPROVED hiện hành, không ký thay. Không sửa baseline khi kỳ đã ACTIVE. HR kích hoạt khi tất cả kế hoạch APPROVED, đã xác nhận đúng revision, người và quản lý còn đủ quyền.

Công việc: `PROPOSED → TODO → IN_PROGRESS → SUBMITTED → ACCEPTED`; quản lý trả bản nộp về `CHANGES_REQUESTED`, nhân viên bắt đầu lại rồi nộp revision bằng chứng mới. `blocked` là cờ kèm lý do, không thay trạng thái; chỉ nhân viên cập nhật ở TODO/IN_PROGRESS/CHANGES_REQUESTED. Quản lý có thể hủy việc chưa ACCEPTED, hoặc mở lại ACCEPTED; phải có lý do, giữ lịch sử. Việc đã giao không sửa owner/deadline/tiêu chuẩn ngầm. Đề nghị thay đổi ghi thành trao đổi; áp dụng đổi baseline/bàn giao thuộc Phase 15.

Mỗi việc thuộc đúng participant và revision mục tiêu đã duyệt, có một người thực hiện, một quản lý hiện hành, đầu ra, ưu tiên và hạn trong ngày làm việc của kỳ. Có thể không gắn KPI và ghi rõ không đo KPI. Bằng chứng chỉ text/URL HTTP(S), không upload hoặc truy xuất URL. Bản nộp bất biến; nhận xét và sự kiện lưu riêng.

## Giao dịch, phạm vi và tương thích

Mọi mutation kiểm tra lại tài khoản, phiên, CSRF và quyền trong giao dịch; khóa tổ chức → ADMIN → user → phiên → cycle → participant → plan/work. Version chống ghi đè. `client_request_id` cùng actor và nội dung cho phép retry, nội dung khác trả 409; event, audit, thông báo và trạng thái cùng commit hoặc cùng rollback. Danh sách phân trang, thứ tự timestamp/ID, lọc phạm vi trong SQL trước phân trang; đối tượng ngoài phạm vi trả 404.

Thông báo có target plan/work riêng; SSE chỉ tín hiệu làm mới, không phát bằng chứng. Đánh dấu đã đọc không hoàn thành công việc. Nhắc hạn ở Phase 11 lấy trực tiếp từ danh sách, chưa có scheduler chạy offline.

CONTINUOUS chặn API phân bổ/actual/tính lại/chốt/đóng cũ bằng `managed_by_workflow`. Không tự sinh feedback 360 hoặc kết quả giả. Chặn chuyển quản lý/phòng, đổi liên kết nhân viên và trạng thái tổ chức ảnh hưởng kỳ CONTINUOUS ACTIVE; khóa tài khoản bảo mật vẫn được phép, người còn lại thấy cần HR xử lý. LEGACY không chịu các hạn chế mới.

## Giao diện và ví dụ nghiệm thu

Nhân viên: **Công việc của tôi** → kế hoạch cần xác nhận, việc cần làm, việc cần bổ sung. Quản lý: **Điều phối nhóm** → kế hoạch cần chuẩn bị, bản nộp chờ duyệt, việc bị vướng. HR theo dõi qua chu kỳ. ADMIN không hiện mục này. Chi tiết mở cửa sổ nổi, có X/Escape và các tab cố định **Nội dung / Tiến trình & bằng chứng / Trao đổi / Lịch sử**; giữ bộ lọc và nội dung nhập khi lỗi/chuyển tab.

Ví dụ: Mai Anh lập kế hoạch CSKH cho Huy → Huy yêu cầu giải thích nguồn tỷ lệ xử lý đúng hạn → Mai Anh sửa tử/mẫu, gửi và duyệt → Huy xác nhận bản mới → HR kích hoạt → Mai Anh giao xử lý hồ sơ → Huy báo thiếu dữ liệu, cập nhật, nộp bằng chứng → Mai Anh trả lại thiếu kiểm tra → Huy nộp bản thứ hai → Mai Anh nghiệm thu. Màn hình thể hiện hai lần nộp và quyết định, chưa có điểm.

Không hợp lệ: Huy xác nhận revision cũ, quản lý khác nghiệm thu, ADMIN xem bằng chứng, HR nhập actual cho kỳ mới, cùng request tạo hai việc hoặc hai tab ghi đè quyết định. Các trường hợp này phải bị từ chối và không phát thông báo thành công.
