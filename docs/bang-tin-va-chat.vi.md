# Bảng tin và chat nội bộ

Hai khu vực này phục vụ trao đổi công việc hằng ngày. Dữ liệu đánh giá, phản hồi 360 và tư vấn AI vẫn được xử lý theo các màn hình nghiệp vụ và quyền hiện có.

## Sử dụng bảng tin

1. Đăng nhập và chọn **Tổng quan → Bảng tin nội bộ** ở menu trái, hoặc mở `/news`.
2. Chọn **Tất cả**, **Toàn công ty** hoặc **Phòng ban của tôi** để lọc bài viết.
3. Bấm **+ Viết bài**, chọn người được xem, nhập tiêu đề và nội dung.
4. Nếu cần một người chú ý, bấm **@ Nhắc người liên quan**, tìm tên hoặc email rồi tích chọn. Có thể chọn tối đa 10 người. Những người đã chọn được hiển thị thành thẻ @tên trong bài/trao đổi đã gửi. Gõ một tên vào nội dung đơn thuần không tạo lượt @nhắc.
5. Bấm **Đăng bài**. Người thuộc phạm vi bài nhận thông báo; tác giả không nhận thông báo của chính mình.
6. Chọn **Xem bài viết và trao đổi** để mở cửa sổ nổi. Mọi người có quyền xem bài đều có thể trao đổi và @nhắc người cùng phạm vi.
7. Bấm **Đóng** hoặc Escape để về danh sách; bộ lọc vẫn được giữ.

| Vai trò | Đăng bài toàn công ty | Đăng bài phòng ban | Xem/trao đổi |
| --- | --- | --- | --- |
| HR, ADMIN | Có | Chọn một phòng ban đang hoạt động | Toàn công ty và mọi phòng ban |
| MANAGER, EMPLOYEE có hồ sơ đang hoạt động | Không | Phòng ban hiện tại của mình | Tin toàn công ty và phòng ban hiện tại |
| Tài khoản khác chưa gắn hồ sơ nhân viên | Không, trừ HR/ADMIN | Không | Tin toàn công ty |

Quyền tổ chức, phân công, tính điểm hay chốt đánh giá không thay đổi bởi quyền đăng bài. Khi nhân viên chuyển phòng, hệ thống kiểm tra lại phạm vi bài và thông báo cũ; đường dẫn được chia sẻ không vượt được phân quyền.

Trao đổi mới chỉ gửi thông báo cho tác giả bài và người được @nhắc, tránh gửi mọi bình luận cho cả công ty. Người nhận bấm thông báo để mở đúng bài viết.

## Sử dụng chat cửa sổ nhỏ

1. Bấm **Chat nội bộ** ở góc phải dưới màn hình.
2. Chọn **Tìm đồng nghiệp**, tìm theo tên/email và chọn người muốn nhắn. Có thể liên lạc khác phòng ban; danh bạ chỉ cung cấp thông tin liên hệ cơ bản, không mở quyền xem hồ sơ đánh giá của họ.
3. Nhập nội dung và bấm **Gửi**. Bấm **@ Nhắc** nếu muốn đánh dấu nhắc trực tiếp người nhận.
4. Người nhận thấy số tin chưa đọc trên nút chat và có thông báo ở biểu tượng chuông. Danh sách **Gần đây** giúp mở lại cuộc trò chuyện.
5. Khi người nhận mở cuộc trò chuyện và xem phần tin mới, người gửi thấy **Đã đọc**. Xem tin cũ, thu gọn chat hoặc chuyển sang tab trình duyệt ẩn không tự đánh dấu tin mới đã đọc.
6. Bấm **×** hoặc Escape khi đang thao tác trong khung để thu gọn; trang công việc vẫn ở nguyên vị trí. Nội dung đã gửi lưu trong cơ sở dữ liệu và xem lại được sau khi đăng nhập lại. Hãy gửi bản nháp trước khi đóng cửa sổ.

Đây là chat **1–1**. Chỉ người gửi và người nhận được xem nội dung, kể cả HR/ADMIN cũng không có API đọc cuộc trò chuyện của hai người khác. Chat riêng chỉ @nhắc được người nhận; muốn nhắc nhiều người cùng trao đổi, dùng bài viết theo phạm vi phù hợp.

**Đã đọc thông báo** tại chuông và **đã đọc tin nhắn** là hai trạng thái riêng: đánh dấu tất cả thông báo đã đọc không giả lập việc đã xem chat.

## Cập nhật trực tiếp và giới hạn

- Bảng tin, thông báo và chat dùng chung luồng SSE đã xác thực. Tín hiệu chỉ yêu cầu trình duyệt tải lại dữ liệu theo quyền, không phát nội dung chat hay nhận xét đánh giá ra kênh chung.
- Có kiểm tra định kỳ 15 giây để phục hồi khi mất kết nối. Mọi thao tác gửi/đọc đều cần phiên hợp lệ, cùng nguồn và CSRF.
- Mỗi lượt gửi có UUID để thử lại không tạo trùng nội dung/thông báo. Lưu nội dung, nhật ký và thông báo trong cùng giao dịch; lỗi thì hoàn tác.
- Bài viết tối đa 10.000 ký tự; tiêu đề 200; trao đổi/tin nhắn 2.000. Phân trang bài/trao đổi 20, tin nhắn 30; không tải toàn bộ lịch sử cùng lúc.
- Nội dung hiển thị dạng văn bản thuần, không chạy HTML. Nhật ký kiểm toán chỉ chứa định danh sự kiện, không chứa nội dung tin nhắn.
- Bản này chưa có chat nhóm, tệp đính kèm, gọi thoại, sửa/xóa bài hoặc tin nhắn. Không có thao tác nào tự gọi Gemini.

## Thử nhanh với hai tài khoản demo

1. Cửa sổ thường: đăng nhập HR, mở **Bảng tin nội bộ**, đăng một thông báo toàn công ty.
2. Cửa sổ ẩn danh hoặc trình duyệt khác: đăng nhập Nhân viên An. Bài viết và thông báo tự cập nhật.
3. An mở bài, viết trao đổi và dùng nút @nhắc HR. HR mở thông báo để xem đúng bài.
4. HR mở chat, tìm An và gửi tin. An thấy số chưa đọc, mở chat; HR thấy trạng thái **Đã đọc**.
5. HR đăng bài cho phòng Kỹ thuật. Tài khoản phòng Kinh doanh không thấy bài đó và không mở được bằng đường dẫn trực tiếp.

Không cần nạp lại dữ liệu demo để có tính năng này. Cập nhật Docker bằng lệnh trong README sẽ chạy migration `20261114_0010`, bổ sung ba bảng mới và liên kết thông báo, không đặt lại tài khoản hoặc dữ liệu đánh giá.
