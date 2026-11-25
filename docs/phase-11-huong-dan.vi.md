# Hướng dẫn Phase 11 — Theo dõi công việc từ đầu

Phase 11 bổ sung **kế hoạch cá nhân → giao việc → theo dõi → nộp bằng chứng → nghiệm thu**. Các kỳ cũ vẫn giữ cách đánh giá hiện tại. Chưa có sổ đo KPI, check-in, AI cố vấn theo công việc hoặc điểm cuối kỳ theo tiến trình; các phần này nối tiếp ở Phase 12–14.

## 1. Chọn đúng nơi thử

- **Ứng dụng hiện tại:** `http://localhost:3000`. Giữ nguyên nhân viên, mật khẩu, kỳ đang hoạt động và lịch sử cũ. Menu Công việc & mục tiêu có thể trống nếu HR chưa tạo kỳ mới theo tiến trình.
- **Demo Phase 11 biệt lập:** `http://localhost:13039` khi stack thử nghiệm được khởi động. Đây là công ty giả lập riêng, không đọc `.env` và không gọi Gemini. Không cần đóng kỳ đang dùng ở cổng 3000.

Ứng dụng hiện chỉ cho **một kỳ ACTIVE**. Không đóng kỳ hiện tại chỉ để thử luồng mới. Dùng stack biệt lập bên dưới.

## 2. Nhập vai trong bộ demo

Ở trang đăng nhập chọn **Dùng tài khoản riêng**. Mật khẩu của bốn tài khoản demo riêng này là **`1`**.

| Thứ tự | Tài khoản | Việc cần nhìn / thực hiện |
| --- | --- | --- |
| 1 | `hr.demo@example.com` | Tổng quan → Chu kỳ đánh giá → theo dõi kế hoạch đã duyệt/đã nhận; HR không nghiệm thu thay quản lý |
| 2 | `care.manager.demo@example.com` — Hoàng Mai Anh | Điều phối nhóm → lập/thống nhất kế hoạch, giao việc, hỗ trợ vướng mắc, xem bản nộp và nghiệm thu/trả lại |
| 3 | `care01.demo@example.com` — Vũ Đức Huy | Công việc của tôi → đọc mục tiêu, yêu cầu làm rõ, xác nhận, làm việc và nộp bằng chứng |
| 4 | `admin.demo@example.com` | Quản trị tài khoản; không có menu hay quyền xem chi tiết công việc |

Nên dùng hai trình duyệt hoặc hai cửa sổ riêng tư để giữ phiên của quản lý và nhân viên. Đăng xuất trước khi đổi người trong cùng cửa sổ.

## 3. Thử thống nhất kế hoạch

1. Quản lý mở **Điều phối nhóm → Kế hoạch & mục tiêu**. Mở kỳ có chữ **Chuẩn bị**. Kế hoạch mẫu đang **Cần bổ sung**, với câu hỏi của Huy trong tab **Trao đổi**.
2. Chọn **Chỉnh sửa kế hoạch**. Mỗi mục tiêu có KPI, giá trị ban đầu, target, trọng số, nguồn đo và tiêu chuẩn nghiệm thu. Tổng trọng số phải đúng 100%. Chọn cách tổng hợp phù hợp; tỷ lệ phải nêu rõ tử và mẫu.
3. Bấm **Xem lại kế hoạch → Lưu bản kế hoạch**. Lần sửa tạo phiên bản mới, giữ nguyên bản cũ và bỏ xác nhận cũ.
4. Trong **Nội dung**, chọn **Gửi để duyệt**, xem lại và xác nhận. Tiếp tục chọn **Duyệt kế hoạch**, xem lại và xác nhận. Quản lý được duyệt bản mình soạn cho nhân viên khác; không được tự duyệt hiệu suất của chính mình.
5. Huy mở đúng kế hoạch. Nếu chưa rõ, chọn **Yêu cầu làm rõ**, nhập câu hỏi; quản lý phải sửa và gửi lại. Nếu đã rõ, chọn **Xác nhận đã nhận kế hoạch → Xem lại → Xác nhận gửi**.
6. HR nhìn thấy kế hoạch đã xác nhận. Khi **mọi người tham gia** đủ điều kiện, HR mới kích hoạt kỳ. Bộ demo đã có kỳ thực hành ACTIVE, nên không kích hoạt thêm kỳ Chuẩn bị; dùng kỳ thực hành để tiếp tục bước 4 bên dưới.

Xem lại baseline cũ ở **Lịch sử → Xem các phiên bản kế hoạch**. Lịch kỳ cố định từ khi có kế hoạch đầu tiên; muốn điều chỉnh baseline/lịch giữa kỳ cần quy trình thay đổi ở giai đoạn sau.

## 4. Thử công việc và nghiệm thu

Bộ demo có bốn tình huống: **chưa bắt đầu**, **đang vướng**, **cần bổ sung**, **đã nghiệm thu**. Dữ liệu được tạo tại lúc nạp demo, không giả làm lịch sử nhiều tuần.

1. Huy mở việc **Đối chiếu hồ sơ khách hàng mới**. Tab **Nội dung** chỉ rõ đầu ra, hạn, mã hồ sơ và ai đang giữ bước.
2. Chuyển **Tiến trình & bằng chứng**, chọn **Bắt đầu thực hiện → Xem lại trước khi gửi → Xác nhận gửi**.
3. Nếu thiếu dữ liệu, chọn **Báo vướng mắc**, nhập lý do. Quản lý nhận thông báo, có thể trao đổi để hỗ trợ. Nhân viên chọn **Đã gỡ vướng** khi đủ dữ liệu. Không nộp bằng chứng khi vẫn đang bị chặn.
4. Chọn **Nộp bằng chứng**, mô tả kết quả và thêm URL HTTP(S) nếu có. Xem lại rồi xác nhận. Hệ thống giữ nguyên bản nộp, chuyển bước sang quản lý.
5. Mai Anh mở thông báo hoặc việc **Chờ nghiệm thu**. Trong **Tiến trình & bằng chứng**, đọc bản nộp rồi chọn **Yêu cầu bổ sung** hoặc **Nghiệm thu**. Cả hai đều cần nhận xét và xác nhận.
6. Nếu bị trả lại, Huy bắt đầu lại, bổ sung và nộp lần tiếp theo. Màn hình giữ cả hai lần nộp; bản đầu không bị ghi đè.
7. Khi được nghiệm thu, trạng thái là **Đã nghiệm thu**. Đây là xác nhận đầu ra, **chưa phải điểm hiệu suất**. Nếu cần mở lại, quản lý phải ghi lý do; lịch sử vẫn được giữ.

Tab **Trao đổi** dùng để hỏi trong phạm vi công việc hoặc gửi **Đề nghị thay đổi**. Gửi đề nghị không tự đổi owner, deadline hoặc tiêu chuẩn đã cam kết. Chat riêng giữa hai người không được tự sao chép vào bằng chứng công việc.

## 5. Cách đọc thông báo và xử lý lỗi

- Chuông thông báo dùng cùng kết nối realtime hiện có. Bấm tin mở đúng kế hoạch hoặc công việc; nội dung chi tiết vẫn được kiểm tra quyền ở API.
- **Việc cần làm** chỉ rõ bước nào của mình và bước nào đang chờ phối hợp. Đọc một tin không đồng nghĩa hoàn thành bước đó.
- Trong cửa sổ chi tiết, bấm **X/Đóng** hoặc Escape để quay về danh sách, giữ bộ lọc. Nếu có bản nhập chưa lưu, chọn tiếp tục sửa hoặc bỏ bản nhập.
- Nếu có người/tab khác vừa cập nhật, hệ thống giữ nội dung nhập và yêu cầu xem phiên bản mới trước khi gửi; không âm thầm ghi đè.
- Tài khoản bị khóa hoặc quản lý mất quyền: thao tác nghiệp vụ dừng, màn hình báo cần HR kiểm tra. Không tự giao quyền nghiệm thu cho ADMIN/HR.
- Quá hạn nộp hoặc xác minh: API chặn bước tương ứng. Mốc nhận kế hoạch dùng để theo dõi chậm xác nhận; nhận muộn vẫn được trước khi HR kích hoạt.

## 6. Khởi động stack demo riêng

Tại thư mục `hrm-ai`, dùng PowerShell:

```powershell
docker compose --project-name insighthr-phase11-acceptance -f infrastructure/docker/phase11-test.compose.yml up -d --build --wait
docker compose --project-name insighthr-phase11-acceptance -f infrastructure/docker/phase11-test.compose.yml exec -T api python -m app.cli.seed_continuous_demo
```

Mở `http://localhost:13039`. Lệnh nạp có marker chống trùng và chỉ chạy với database `_test` biệt lập chưa có tài khoản. Không chạy seed này trên database công ty đang sử dụng.

Dừng và xóa **riêng stack thử nghiệm**:

```powershell
docker compose --project-name insighthr-phase11-acceptance -f infrastructure/docker/phase11-test.compose.yml down
```

PostgreSQL demo dùng bộ nhớ tạm (`tmpfs`): tái tạo container sẽ mất dữ liệu demo. Đây là tính chất của stack thử nghiệm; volume PostgreSQL ứng dụng ở cổng 3000 được giữ riêng.
