# Menu theo role và cách dùng khung chi tiết

Menu trái được giữ cố định theo tài khoản đang đăng nhập. Đổi tab trên chỉ đổi nội dung và dấu chọn hiện tại; không thêm hoặc bớt mục của cùng một role.

## Mỗi role có những mục nào?

| Nhóm | ADMIN | HR | Quản lý | Nhân viên |
| --- | --- | --- | --- | --- |
| Tổng quan | Thống kê tài khoản | Tổng quan đánh giá toàn phạm vi HR | Tổng quan nhóm trực tiếp | Tổng quan kết quả bản thân |
| Đánh giá hiệu suất | Không hiển thị | Chu kỳ đánh giá; Quản trị phản hồi; Danh mục KPI; Tư vấn AI đã lưu | Chu kỳ đánh giá; Tư vấn AI đã lưu | Chu kỳ đánh giá; Tư vấn AI đã lưu |
| Tổ chức / Nhóm của tôi | Không hiển thị | Nhân viên; Phòng ban; Chức danh | Nhân viên trực tiếp | Không hiển thị danh mục tổ chức |
| Quản trị hệ thống | Quản lý tài khoản; Cấu hình chấm điểm | Không hiển thị | Không hiển thị | Không hiển thị |
| Cá nhân | Phản hồi của tôi; Tài khoản | Phản hồi của tôi; Tài khoản | Phản hồi của tôi; Tài khoản | Phản hồi của tôi; Tài khoản |

“Phản hồi của tôi” là các phiếu chính người đăng nhập được giao, kể cả khi họ có role ADMIN hoặc HR. Nó không cấp thêm quyền quản trị hoặc xem hồ sơ của người khác. Tài khoản có liên kết nhân viên có thể mở **Hồ sơ của tôi** từ trang **Tài khoản**.

Danh mục phòng ban/chức danh/KPI phục vụ quản trị được đưa vào không gian HR. Quản lý và nhân viên xem các thông tin đã gán ngay trong hồ sơ đánh giá, không cần đi qua các danh mục này. Gõ trực tiếp URL quản trị không làm các form và truy vấn của trang đó xuất hiện với role khác; API vẫn kiểm tra quyền và phạm vi độc lập.

## Mở chi tiết mà không rời danh sách

1. Chọn **Chu kỳ đánh giá** rồi bấm tên một kỳ: một khung nổi mở ra trên danh sách.
2. Tại **Người tham gia**, mỗi người có một thao tác **Mở đánh giá**.
3. Hồ sơ mở trong cùng khung với ba tab cố định: **KPI & kết quả thực tế / Phản hồi 360 / Kết quả hiệu suất**.
4. Chuyển giữa ba tab giữ nguyên nhân viên và chu kỳ. Các nút bên trong chỉ xuất hiện khi role, phạm vi và trạng thái hồ sơ cho phép.
5. HR có **Phân công phản hồi** trong phần kết quả hoặc **Quản trị phân công** trong tab phản hồi. Quản lý và nhân viên không thấy các thao tác quản trị này.
6. Bấm **× Đóng** ở góc trên hoặc nhấn **Escape** để đóng toàn bộ khung. Danh sách bên dưới giữ bộ lọc, trang và trạng thái đang xem.

Nút **Về chu kỳ** bên trong hồ sơ mở danh sách người tham gia của kỳ trong cùng khung. Nút **Đóng** luôn kết thúc khung chi tiết và trở về trang phía dưới; không cần bấm Back qua các tab vừa xem.

Trong **Nhân viên**, bấm tên để mở hồ sơ nổi. Trong **Phản hồi của tôi**, bấm phiếu để xem/gửi trong khung nổi. Trong **Tư vấn AI đã lưu**, bấm xem nội dung để mở khung đọc và đóng khi xong.

Các nút **Thêm nhân viên**, **Thêm mới phòng ban/chức danh**, **Thêm định nghĩa KPI**, **Tạo chu kỳ mới** mở form trong khung riêng. Lưu thành công cập nhật danh sách; lưu lỗi giữ dữ liệu đang nhập để sửa. Đóng form chưa lưu sẽ bỏ phần nhập chưa lưu; tránh đóng khi đang cần giữ nội dung đó.

## Nút theo quyền trong hồ sơ đánh giá

| Khu vực | HR | Quản lý trực tiếp | Nhân viên |
| --- | --- | --- | --- |
| KPI | Xem, phân bổ, nhập thực tế khi kỳ/hồ sơ cho phép | Xem, phân bổ, nhập thực tế cho cấp dưới khi được phép | Chỉ xem |
| Phản hồi 360 | Xem tổng hợp, mở quản trị phân công | Xem tổng hợp được phép | Xem tổng hợp được phép |
| Kết quả | Xem, tính, chốt theo điều kiện | Xem, tính theo điều kiện | Chỉ xem |
| Tư vấn AI | Chọn phạm vi, tạo khi đủ điều kiện, đọc lịch sử | Chỉ đọc tư vấn chung trong phạm vi | Chỉ đọc tư vấn chung trong phạm vi |
| Phiếu được giao | Chỉ gửi khi chính mình là người được giao | Như HR | Như HR |

Hồ sơ đã chốt hoặc kỳ đã đóng không còn thao tác sửa bằng chứng. Một nút không xuất hiện vì thiếu quyền khác với nút đang tạm khóa trong khi lưu hoặc chờ xác nhận.

Các liên kết chi tiết vẫn có địa chỉ để mở ở tab mới hoặc truy cập trực tiếp khi cần. Khi mở bằng cách bấm thông thường trong không gian làm việc, chúng dùng khung nổi để giữ ngữ cảnh của danh sách.

## Kiểm tra thay đổi giao diện

Ngày 14/11/2026: **162 test web / 23 file** đạt; lint, typecheck và production build đạt. Kiểm tra Edge thực tế qua bốn role xác nhận menu cố định, phần quản trị đúng role, một khung cho các tab đánh giá, giữ bộ lọc khi đóng và thao tác bàn phím Tab/Escape. Đã kiểm tra bố cục ở 1280/390 px, mở/đóng các form tạo mới HR và phiếu phản hồi. Không ghi dữ liệu nghiệp vụ hoặc gọi AI trong lượt kiểm tra trình duyệt này. [Kết quả kiểm tra](evidence/workspace-ux-2026-11-14.json).
