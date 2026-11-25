# Báo cáo Phase 12 — Số đo có xác minh và check-in

Ngày **25/11/2026**. Baseline triển khai: Phase 11 `13fd9e3`; kế hoạch `fa18ba4`. Migration mới **`20261125_0012`**, nối tiếp `20261125_0011`. Báo cáo này ghi nhận kiểm chứng local; không thay cho CI từ xa hay nghiệm thu production.

## 1. Kết quả nghiệp vụ

Quy trình hiện có: **thống nhất kế hoạch → giao việc → nhân viên thực hiện/nộp bằng chứng → quản lý nghiệm thu → nhân viên khai số có nguồn → quản lý xác minh → xem KPI có truy xuất nguồn → check-in → giao hỗ trợ → người còn lại xác nhận kết quả hỗ trợ**.

| Vai trò | Việc thực hiện |
| --- | --- |
| Nhân viên | Khai/nộp/sửa/rút số của mình; chuẩn bị check-in; xác nhận đã đọc, yêu cầu làm rõ; thực hiện hành động hoặc xác nhận hỗ trợ của quản lý |
| Quản lý trực tiếp | Kiểm tra nguồn và quyết định số đo; tổ chức/công bố/bổ sung check-in; giao hỗ trợ cho cả hai phía; kiểm tra phần nhân viên thực hiện |
| HR | Xem lượng chờ, quá hạn và trạng thái cần điều phối; không nhập số, đọc bằng chứng hay biên bản riêng |
| ADMIN | Quản trị tài khoản; không đọc nội dung số đo/check-in riêng |

Giao diện dùng lại trang công việc với bốn tab cố định, khung chi tiết có nút đóng, phân quyền theo API và trạng thái thực tế. Thông báo cá nhân/SSE cập nhật giữa các phiên; không mở thêm một kết nối realtime riêng. Phần chuẩn bị chưa chia sẻ chỉ chủ nội dung thấy; bản đang gõ được giữ khi cuộc họp chuyển sang đã công bố.

## 2. Tính đúng và truy vết

- SUM cộng phát sinh; LAST chọn thời điểm đo mới nhất; RATIO chia tổng tử cho tổng mẫu; MILESTONE cộng trọng số mốc đã thống nhất. Tính bằng phân số chính xác, chỉ làm tròn khi hiển thị; không cộng baseline, không lấy trung bình tỷ lệ, không biến thiếu dữ liệu thành 0.
- Mỗi nguồn có định danh chuẩn hóa ổn định và các revision bất biến. Sửa số đang chờ giữ số đã xác minh trước đó; xác minh bản mới thay thế số cũ. VOID loại cả dòng, không quay lại phiên bản cũ. Timestamp/mốc đang được nguồn khác sử dụng không được tái kích hoạt trùng.
- Nghiệm thu công việc không tự sinh số. Mở lại việc tạm loại đóng góp liên quan trong cùng giao dịch; nghiệm thu lại vẫn phải xác minh số. Snapshot cũ và biên bản đã công bố giữ nguyên nguồn/giá trị tại thời điểm đó.
- Khóa theo thứ tự miền dùng chung; kiểm tra tài khoản/phiên, quyền, CSRF, version và UUID chống lặp. Lỗi audit/snapshot/thông báo phải rollback cả trạng thái và lịch sử. UUID nội bộ khi treo nguồn tách khỏi UUID lệnh công khai; replay công việc do receipt công việc kiểm soát.
- Biên bản, phụ lục và chuẩn bị đã chia sẻ tại lúc công bố được lưu cố định. “Đã đọc” gắn đúng phiên bản, không coi là đồng ý kết quả. Hành động chỉ có một người thực hiện; người còn lại xác nhận, không tự đánh dấu phần mình hoàn thành.

## 3. Phạm vi kiểm chứng

Các gate bao gồm phép tính chính xác/overflow/null và 0, quyền riêng tư, Origin/CSRF, replay/version conflict, quyết định cạnh tranh, verify/reopen, rollback khi audit lỗi, cutoff/múi giờ, revision/snapshot bất biến, khóa nguồn trùng, chuẩn bị riêng, phụ lục/đã đọc, kiểm tra chéo hỗ trợ, migration fresh/upgrade và tính idempotent của demo.

| Kiểm tra | Kết quả local |
| --- | --- |
| Backend | 989 ca khác nhau đạt: 526 ca ở lượt đầu và 463 ca trong lượt hồi quy tiếp nối sau sửa fixture migration |
| Web | 202 ca khác nhau đạt sau chạy lại các file lỗi thời gian và bổ sung ca tải chậm; xem diễn giải bên dưới |
| Chất lượng | Ruff sạch; mypy sạch 135 tệp; TypeScript và ESLint đạt |
| Đóng gói | Build production API/web đạt; 135 tệp Python trong image API khớp hash mã nguồn |
| Trình duyệt trên bản build cuối | Luồng form bốn role, realtime, quyền riêng, sửa số và biên bản ghim, hỗ trợ kiểm tra chéo; cả 1280/390 px, không lỗi JavaScript hoặc gọi AI |

Lượt web đầy đủ đầu tiên sau bổ sung ca hồi quy có 192 ca đạt, tám timeout 5 giây khi đang build Docker và một lỗi nhập liệu tiếp nối sau timeout. Các file liên quan được chạy lại với một worker và timeout 15 giây, đều đạt; hợp nhất theo tên file/ca cho 201 ca đạt. Không thay assertion hay tăng timeout trong cấu hình dự án. Các lượt trước đó có 200 ca đạt trước khi bổ sung ca chặn giao hỗ trợ sau công bố. Lỗi chức năng thực tế này được sửa bằng quyền `create_followup`, tách khỏi quyền sửa phần chuẩn bị, và đã có ca hồi quy riêng.

Lượt kiểm tra cuối bổ sung ca mở số đo qua deep link khi mục tiêu tải chậm: nút sửa chỉ bật sau khi có đúng goal của số đo. Cả chín ca trong file progress đạt; tổng số ca web khác nhau đã đạt là **202**. Lượt này chạy lại TypeScript và ESLint, không thay dữ liệu hoặc assertion của các ca cũ.

Lượt backend local từng bị ngưng tại `psycopg.connect` trong setup fixture, trước khi có truy vấn vào PostgreSQL. Container test chỉ bind `127.0.0.1:15480`; chuyển URL test từ `localhost` sang IPv4 cụ thể, thêm `connect_timeout=5` đã xác nhận kết nối được. Không sửa thuật toán hoặc nới kiểm tra nghiệp vụ để xử lý vấn đề kết nối này.

Kiểm tra tải đọc dùng fixture tổng hợp **60 người, 1.000 nguồn đã xác minh**, trang 20 dòng: danh sách người cần **7 truy vấn**, tổng KPI **9**, trang nguồn **11**. Các lần đo local chịu tải build/test đồng thời; đây là kiểm tra giới hạn truy vấn và dữ liệu trả về, không phải cam kết độ trễ production. Fixture này không được trình bày thành lịch sử thực hiện công việc thật.

Trong hồi quy, test round-trip schema Phase 9 được sửa để so dấu vân tay đúng 16 bảng có tại schema 0007. Các bảng được bổ sung sau đó bị downgrade chủ động không phải mất dữ liệu cũ. Gate upgrade 0011 → 0012 riêng vẫn kiểm tra nguyên vẹn dữ liệu/cột cũ của LEGACY và CONTINUOUS.

Lượt backend tiếp nối thu thập đủ 989 ca, bỏ chọn đúng 526 ca đã đạt và chạy 463 ca còn lại: **463 passed, 526 deselected**, 349,16 giây, một cảnh báo về quyền ghi cache pytest trên Windows. XML xác nhận không có failure, error hay skipped; cảnh báo không thuộc dữ liệu/kiểm tra nghiệp vụ. Không trình bày đây là một lượt chạy liền mạch 989 ca; các ca sửa mới nằm trong phần chạy lại. Các kết quả XML/log local được lưu dưới `.superpowers/phase12/`, không đưa dữ liệu thử vào Git.

## 4. Chạy thử và bảo toàn

Xem [hướng dẫn chi tiết theo role](phase-12-huong-dan.vi.md). Demo tách biệt ở **http://localhost:13049**, API **18049**, bốn tài khoản thử mật khẩu `1`. Database demo nằm trên tmpfs, không dùng volume chính và không nạp `.env`. Sau nghiệm thu, đã tái tạo riêng demo này về bộ mẫu ban đầu và xác nhận lại SUM **5**, RATIO **83,33%**, MILESTONE **30%**, LAST **50**, cùng các trường hợp chờ/trả/rút/treo nguồn. Nạp lần hai trả `Progress demo already exists`, không nhân đôi dữ liệu.

Trước nâng cấp hệ thống chính, đã tạo bản dump PostgreSQL **185.208 byte** và dấu vân tay **27 bảng** tại `.superpowers/phase12/deployment-release/` (bị Git bỏ qua), đồng thời giữ các bản sao lưu trước đó. So sánh giữ cột cũ, tài khoản/mật khẩu/role và bản ghi nghiệp vụ; session/login-limit là dữ liệu vận hành có thể thay đổi khi sử dụng. Không nạp lại demo, đóng kỳ đang chạy, đổi `.env` hay gọi Gemini để nghiệm thu Phase 12.

Đã triển khai image nghiệm thu lên stack chính, API/web healthy, head **`20261125_0012`**. Dấu vân tay **25 bảng nghiệp vụ/cột cũ** khớp toàn bộ bản ghi trước nâng cấp, bao gồm password hash/role, kế hoạch, công việc, chat/bảng tin, feedback, điểm và lịch sử AI. Volume PostgreSQL chính được giữ nguyên. Bản chạy chính tiếp tục ở **3000/8000**; các kỳ LEGACY hiện có không tự chuyển sang CONTINUOUS. Xem luồng mới trong demo **13049** theo hướng dẫn riêng.

## 5. Giới hạn và bước sau

Đây là xác minh nghiệp vụ nội bộ, chưa kết nối đối soát CRM. Khóa nguồn chống trùng trong từng goal/rule, chưa chứng minh phân chia công sức của cùng đầu ra giữa nhiều nhân viên. API không hỗ trợ nhập lô khoảng thời gian chồng lấn. Trạng thái quá hạn được tính khi đọc/ghi; chưa có scheduler nhắc hạn khi người dùng offline.

Phase 13 tiếp nối cố vấn AI theo ngữ cảnh của quá trình. Phase 14 mới nối dữ kiện đã xác minh sang điểm/giải trình/chốt CONTINUOUS; Phase 15 xử lý thay đổi baseline, bàn giao và pilot vận hành. Các phần này chưa được coi là đã hoàn thành trong Phase 12.
