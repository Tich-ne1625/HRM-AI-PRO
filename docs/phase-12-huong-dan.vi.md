# Hướng dẫn Phase 12 — Từ công việc đến số đo và hỗ trợ

Tài liệu dùng với mã Phase 12. Sau khi khởi động stack demo bên dưới, mở **http://localhost:13049**. Ứng dụng đang dùng ở cổng **3000** và demo Phase 11 ở **13039** có database riêng; không đóng kỳ hay nạp lại dữ liệu ở hai nơi đó để làm bài thử này.

## 1. Phân biệt bốn việc

| Việc | Ý nghĩa | Ai chịu trách nhiệm |
| --- | --- | --- |
| Nghiệm thu công việc | Đầu ra/bằng chứng đáp ứng cam kết | Quản lý |
| Xác minh số đo | Kiểm tra giá trị định lượng, đơn vị và nguồn; mới được vào tổng KPI | Quản lý, sau khi nhân viên nộp số |
| Check-in | Hai bên rà soát dữ kiện, vướng mắc và hỗ trợ cần thiết | Quản lý tổ chức, nhân viên góp ý |
| Xác nhận hỗ trợ đã xong | Người còn lại kiểm tra hành động của người thực hiện | Nhân viên kiểm tra hỗ trợ của quản lý; quản lý kiểm tra phần của nhân viên |

Nút **Đã nghiệm thu** không tự tạo số hay điểm. Một số **đã xác minh** vẫn chưa phải điểm hiệu suất. AI cố vấn nối tiếp ở Phase 13, điểm/chốt CONTINUOUS nối tiếp ở Phase 14.

## 2. Tài khoản và thứ tự nhập vai

Chọn **Dùng tài khoản riêng** ở trang đăng nhập. Mật khẩu demo của bốn tài khoản là **`1`**.

| Thứ tự | Tài khoản | Màn hình chính |
| --- | --- | --- |
| 1 | `hr.demo@example.com` | Chu kỳ đánh giá → kỳ `[PHASE 12]` → kế hoạch → điều phối số liệu/check-in |
| 2 | `care.manager.demo@example.com` — Hoàng Mai Anh | Điều phối nhóm → Số đo KPI / Check-in |
| 3 | `care01.demo@example.com` — Vũ Đức Huy | Công việc của tôi → Số đo KPI / Check-in |
| 4 | `admin.demo@example.com` | Quản trị tài khoản; không có quyền đọc số đo/bằng chứng/check-in riêng |

Nên giữ quản lý và nhân viên ở hai trình duyệt hoặc hai cửa sổ có phiên riêng. Nếu dùng cùng một cửa sổ, đăng xuất trước khi đổi tài khoản. HR chỉ thấy trạng thái, lượng việc chờ/quá hạn và trường hợp cần kiểm tra tài khoản; không đọc biên bản riêng hoặc xác minh số thay quản lý.

## 3. Đọc bộ dữ liệu trước khi thao tác

Mở **Số đo KPI** và chọn kế hoạch của Huy. Bộ dữ liệu ban đầu có:

| KPI | Số đã xác minh ban đầu | Vì sao |
| --- | --- | --- |
| SUM — Yêu cầu hỗ trợ đã xác minh | **5 yêu cầu** | Một hồ sơ khách hàng có danh sách yêu cầu riêng; nguồn `P12-102` ghi 5 yêu cầu đạt QA. Bản đề nghị sửa xuống 4 đang chờ, chưa thay 5 |
| RATIO — Hồ sơ đúng hạn | **83,33%** | 10/12 hồ sơ có mã riêng đã được xác minh; không lấy trung bình các phần trăm tuần |
| MILESTONE — Bàn giao quy trình | **30%** | Mốc đầu có trọng số 30% đã được xác minh; mốc 70% còn chờ |
| LAST — Snapshot hồ sơ lũy kế | **50 hồ sơ** | Các lần đo 20 → 35 → 50; lấy lần đo mới nhất, không cộng thành 105 |

SUM đo **số yêu cầu bên trong hồ sơ**, không phải số task hoặc số hồ sơ. Người xác minh phải đối chiếu danh sách yêu cầu không trùng giữa các hồ sơ. Đây là kiểm tra nội bộ trên nguồn minh họa, chưa có tích hợp hệ thống ngoài để tự kiểm toán từng mã yêu cầu.

Còn có nguồn cần bổ sung, nguồn đã rút và công việc đã mở lại: chúng không được cộng nhầm vào số hiện hành. Dữ liệu được tạo ở thời điểm nạp demo; không giả là nhật ký công việc đã diễn ra nhiều tuần.

## 4. Thử nộp và xác minh số liệu

1. **Huy:** trong Số đo KPI, chọn KPI SUM → **Xem các nguồn số đo**. Mở `P12-RETURNED` có trạng thái **Cần bổ sung**.
2. Chọn **Sửa bản khai / đề nghị điều chỉnh**. Giữ đúng mã nguồn và thời điểm sự kiện; cập nhật giá trị và mô tả bằng chứng đã bổ sung. URL HTTP(S) là tùy chọn; hệ thống không tự truy cập URL đó.
3. Bấm **Xem lại số đo → Lưu bản khai**. Bản mới được lưu riêng, chưa vào tổng. Trong Nội dung, chọn bước **Nộp để kiểm tra → Xem lại trước khi gửi → Xác nhận gửi**.
4. **Mai Anh:** mở thông báo hoặc Số đo KPI → nguồn vừa nộp. Đọc giá trị, bằng chứng và lịch sử. Chọn **Xác minh số liệu**, **Yêu cầu bổ sung** hoặc **Không chấp nhận**; ghi nhận xét rồi xem lại và xác nhận.
5. **Huy:** theo dõi trạng thái và tổng số cập nhật. Nếu cần bổ sung, thực hiện lại bước 2–3; bản trước vẫn đọc được.

Thử thêm từ đầu: Huy mở một công việc có gắn KPI và đã được nghiệm thu → **Lập số đo từ kết quả này**. Mã nguồn/công việc được điền sẵn, nhưng Huy vẫn phải khai giá trị và nộp để quản lý xác minh. Không nộp thêm dòng cho cùng mã; mở dòng cũ để sửa.

## 5. Thử sửa/rút số đã xác minh

- **Sửa số:** Mai Anh mở nguồn `P12-102` đang chờ điều chỉnh 5 → 4. Đọc bản hiệu lực 5 và bản đề nghị 4. Khi xác minh bản sửa, tổng thay 5 bằng 4, không cộng thành 9. Nếu trả/từ chối bản sửa, 5 vẫn là số hiệu lực.
- **Rút số:** Huy mở nguồn đã xác minh, chọn sửa → loại đề nghị **Rút cả dòng nguồn có lý do**. Quản lý phải xác minh đề nghị rút; sau đó cả dòng bị loại khỏi tổng, không quay về bản cũ.
- **Mở lại công việc:** nguồn `P12-REOPEN` tạm ngừng đóng góp vì công việc cần bổ sung. Huy làm lại/nộp, Mai Anh nghiệm thu lại; số không tự khôi phục. Huy phải lưu và nộp số đo mới tham chiếu lần nghiệm thu mới để Mai Anh xác minh lại.

Một mốc hoặc snapshot chỉ được có một nguồn chưa rút ở cùng vị trí/thời điểm. Nguồn sai đã rút vẫn giữ lịch sử; khi có nguồn thay thế, khôi phục nguồn cũ không được gây tính trùng. Mã nguồn là dữ kiện nghiệp vụ: không đổi mã tùy ý để né kiểm tra trùng.

## 6. Thử check-in và quản lý hỗ trợ nhân viên

1. **Huy:** mở tab Check-in → **Chuẩn bị cuộc rà soát kế tiếp**. Viết đã làm, đang vướng và cần hỗ trợ gì. Mặc định phần chưa chia sẻ là bản riêng. Tick cho người còn lại xem rồi xem lại/lưu nếu muốn chia sẻ.
2. **Mai Anh:** mở cuộc rà soát đó. Ở Chuẩn bị, đọc phần đã chia sẻ, mở buổi rà soát. Phần riêng của Huy không xuất hiện.
3. Chuyển **Biên bản**. Ghi nhận kết luận, điểm chưa thống nhất và hỗ trợ cần làm; chọn **Công bố biên bản**. Hệ thống ghim số liệu đã biết tại thời điểm này. Công bố không tự xác minh những số còn chờ.
4. **Huy:** đọc biên bản. Chọn **Xác nhận đã đọc** hoặc **Yêu cầu làm rõ**. Đã đọc không có nghĩa đồng ý đánh giá. Nếu có câu hỏi, Mai Anh phản hồi bằng **Công bố phụ lục**, Huy đọc đúng bản mới; biên bản gốc không bị sửa.
5. **Mai Anh:** tab Hành động → **Giao hành động hỗ trợ**. Nhập “Liên hệ đối tác lấy kết quả QA”, chọn **Quản lý hỗ trợ · nhân viên xác nhận**, chọn hạn và xem lại/giao.
6. **Mai Anh:** mở hành động của mình, bắt đầu, rồi nộp kết quả hỗ trợ kèm mô tả.
7. **Huy:** mở cùng hành động, kiểm tra kết quả. Chọn **Xác nhận đã hoàn thành** hoặc yêu cầu bổ sung. Mai Anh không tự bấm hoàn thành hỗ trợ của chính mình.

Chiều ngược lại: nếu owner là Huy thì Mai Anh kiểm tra hoàn thành. Muốn đổi owner/nội dung/hạn, quản lý hủy có lý do rồi tạo hành động thay thế có liên kết; không lùi hạn ngầm. Hành động hỗ trợ không tự tạo điểm hoặc đóng góp KPI.

## 7. Đối chiếu theo thời gian và xử lý tình huống

- **Số đo KPI → Xem tiến trình theo khoảng ngày:** SUM/RATIO lấy phát sinh trong khoảng; LAST/MILESTONE là lũy kế đến cuối khoảng. Target vẫn là target cả kỳ, không phải chỉ tiêu tự chia đều cho tuần.
- **Lịch sử số liệu:** chọn một phiên bản, xem nguồn và đúng bản số đo/bằng chứng đã tính. Số hiện hành thay đổi không viết lại các phiên bản cũ hoặc số ghim trong biên bản.
- **Chưa đủ dữ liệu** khác **có số bằng 0**. Tổng mẫu bằng 0 không tự thành 0%/100%. Một SUM/LAST bằng 0 đã được xác minh vẫn là dữ liệu hợp lệ.
- **Xung đột hai phiên:** giữ nội dung nhập, xem trạng thái mới rồi xác nhận lại; không gửi đè. Lỗi mạng có thể thử lại nội dung cũ, request lặp không tạo thêm bản/đóng góp.
- **Quá hạn:** ngừng nộp/sửa sau hạn nộp; quản lý còn xác minh đến hạn xác minh. Bản bị trả sau hạn nộp không được nộp lại qua đường khác; giữ để xử lý cuối kỳ. Chưa có cơ chế tự gia hạn hoặc chốt CONTINUOUS ở Phase 12.
- **Quá lịch check-in/hạn hỗ trợ:** hiện người đang giữ bước để phối hợp, không tự trừ điểm. Thông báo đã đọc không tự hoàn tất việc. Nhắc trong danh sách không phải scheduler chạy khi mọi người offline.

## 8. Tự khởi động demo riêng

Từ thư mục `hrm-ai`, dùng PowerShell:

```powershell
docker compose --project-name insighthr-phase12-acceptance -f infrastructure/docker/phase12-test.compose.yml up -d --build --wait
docker compose --project-name insighthr-phase12-acceptance -f infrastructure/docker/phase12-test.compose.yml exec -T api python -m app.cli.seed_progress_demo
```

Mở **http://localhost:13049**. Marker `continuous-progress-demo-v1` chống nạp trùng; CLI từ chối database đã có tài khoản khác và chỉ chấp nhận database `_test` biệt lập. Gemini bị tắt trong stack này, không dùng key `.env` chính.

Dừng riêng stack demo:

```powershell
docker compose --project-name insighthr-phase12-acceptance -f infrastructure/docker/phase12-test.compose.yml down
```

PostgreSQL demo dùng `tmpfs`: tái tạo container sẽ mất dữ liệu demo. Database chính có volume riêng được giữ nguyên. Xem [contract](phase-12-contract.vi.md) và [kế hoạch](superpowers/plans/2026-11-25-phase-12-measurements-checkins.md) để đối chiếu quy tắc.
