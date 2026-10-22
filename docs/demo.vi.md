# Thực hành InsightHR bằng dữ liệu mẫu

Toàn bộ người, tài khoản, KPI và nhận xét trong bộ `[DEMO]` đều hư cấu. Bộ mẫu có **10 tài khoản, 8 nhân viên, 2 phòng ban, 2 chức danh, 2 KPI và 3 chu kỳ**. Không có đầu ra AI giả; chỉ HR chủ động xác nhận mới gọi Gemini.

## Nạp dữ liệu một lần

Tại thư mục `hrm-ai`, sau khi cập nhật code:

```powershell
docker compose --env-file .env up --build --wait
docker compose --env-file .env exec api python -m app.cli.seed_demo
```

Lệnh tạo mật khẩu ngẫu nhiên dùng chung cho các tài khoản demo và in **một lần** trong terminal. Lưu mật khẩu đó để đăng nhập tại **http://localhost:3000/login**. Mật khẩu không được đưa vào Git/tài liệu hoặc lưu dạng rõ trong database. Tài khoản đang có không đổi mật khẩu hay quyền.

Chạy lại lệnh không nhân bản dữ liệu, không đặt lại mật khẩu và không xóa tiến độ thực hành. Lệnh chỉ dùng khi `APP_ENV=development` hoặc `test`; production bị từ chối. Nếu đã có chu kỳ ACTIVE khác hoặc mã/email demo trùng mà chưa có dấu hoàn tất, lệnh dừng và giữ nguyên dữ liệu. Nếu lỗi giữa chừng, toàn bộ lượt nạp được rollback. Không có lệnh reset/xóa tự động.

Khi chạy API trực tiếp, kích hoạt virtual environment rồi chạy `python -m app.cli.seed_demo` tại `apps/api`. Tùy chọn `--password-stdin` nhận hai dòng mật khẩu giống nhau dành cho công cụ kiểm thử; không đưa mật khẩu vào đối số lệnh.

## Tài khoản và công việc của từng role

Các tài khoản demo dùng chung mật khẩu mà lệnh đã in. Đăng xuất trước khi đổi tài khoản; có thể dùng các profile trình duyệt khác nhau để so sánh quyền.

| Email | Role | Việc nên thử |
| --- | --- | --- |
| `admin.demo@example.com` | ADMIN | Quản trị tài khoản, tạo user, đổi role/khóa tài khoản thử, xem cấu hình tính điểm cho kỳ tương lai |
| `hr.demo@example.com` | HR | Phòng ban/chức danh/nhân viên, kỳ đánh giá, KPI, phân công và nhận xét gốc, tính/chốt điểm, tạo tư vấn AI |
| `manager.demo@example.com` | MANAGER | Nguyễn Lan, quản lý An/Bình/Dũng; nhập KPI, gửi đánh giá quản lý, tính điểm cho nhân viên trực tiếp |
| `sales.manager.demo@example.com` | MANAGER | Trần Huy, quản lý Hà/Linh; thử phạm vi phòng ban khác và tính lại điểm của Linh |
| `an.demo@example.com` | EMPLOYEE | Xem điểm hiện tại và lịch sử hai lần tính; đọc tư vấn chung sau khi HR tạo |
| `binh.demo@example.com` | EMPLOYEE | Gửi tự đánh giá còn thiếu qua **Phản hồi của tôi** |
| `chi.demo@example.com` | EMPLOYEE | Nhân viên trực tiếp của An; xem phản hồi đã gửi với quan hệ SUBORDINATE |
| `dung.demo@example.com` | EMPLOYEE | Xem hồ sơ đã đủ bằng chứng, đang chờ quản lý/HR tính điểm |
| `ha.demo@example.com` | EMPLOYEE | Xem kết quả đã chốt, kiểm tra bằng chứng không còn được sửa |
| `linh.demo@example.com` | EMPLOYEE | Xem điểm cần tính lại; gửi phản hồi PEER còn mở cho An |

ADMIN không tự có quyền HR: đăng nhập ADMIN sẽ không quản lý hồ sơ/đọc báo cáo nhân viên. Quản lý kỹ thuật không xem được Hà/Linh thuộc quản lý kinh doanh. Nhân viên không sửa KPI hay xem nhận xét gốc của người khác.

## Chọn đúng chu kỳ để thực hành

| Chu kỳ | Trạng thái | Mục đích |
| --- | --- | --- |
| `[DEMO] Thực hành đánh giá` | ACTIVE | Thao tác chính với An, Bình, Dũng, Hà, Linh |
| `[DEMO] Lịch sử đã đóng` | CLOSED | Đọc kết quả đã chốt của An/Hà và so với kỳ hiện tại |
| `[DEMO] Kỳ tiếp theo — bản nháp` | DRAFT | Thử thêm người tham gia, sửa ngày/tên; chỉ kích hoạt sau khi đóng kỳ ACTIVE |

Chọn **Chu kỳ đánh giá → Thực hành đánh giá → người tham gia**. Các tab **KPI / Phản hồi / Kết quả** giữ nguyên nhân viên và kỳ đang xem.

## Luồng 1: hoàn thành hồ sơ của Bình

1. Đăng nhập `manager.demo@example.com`, mở Bình trong kỳ thực hành → **KPI**. Một KPI còn thiếu kết quả thực tế; nhập số phù hợp, ví dụ `85`, rồi lưu.
2. Đăng nhập `binh.demo@example.com` → **Phản hồi của tôi** → mở tự đánh giá đang chờ, chọn mức đánh giá 1–5 và nhập nhận xét hư cấu, rồi gửi.
3. Đăng nhập quản lý kỹ thuật → **Phản hồi của tôi** → hoàn thành đánh giá MANAGER cho Bình.
4. Mở **Kết quả** của Bình → **Tính điểm hiệu suất**. Nếu còn thiếu dữ liệu, đọc khối **Việc cần hoàn thành**.
5. Đăng nhập HR, kiểm tra kết quả → **Chốt kết quả** → tích xác nhận và chốt. Từ đó KPI, phân công và gửi phản hồi của Bình trong kỳ bị khóa.

## Luồng 2: xem tính điểm, lịch sử và tư vấn của An

1. HR hoặc quản lý kỹ thuật mở kết quả An. An đã có hai lần tính vì KPI được điều chỉnh sau lần đầu. Với policy mặc định 70/30: điểm trước **87.00**, điểm hiện tại **82.80**; nếu bạn đã sửa policy trước khi nạp thì điểm theo policy của bạn.
2. Mở **Lịch sử tính điểm**, xem từng lần và đối chiếu KPI. Không cần tạo lại dữ liệu để thấy lịch sử.
3. HR mở **Tư vấn AI → Tư vấn chung** hoặc **Nội bộ HR**, đọc phạm vi dữ liệu rồi xác nhận tạo. Dùng API key/model bạn đã cấu hình; thao tác có thể tính phí. Dữ liệu demo không tự gửi đi trong lúc nạp.
4. Đăng nhập An hoặc quản lý kỹ thuật, mở lại kết quả để xem tư vấn chung đã lưu. Nội bộ HR không hiển thị cho hai role này.
5. Phản hồi nhóm PEER của An có ba người đã gửi để thấy thống kê nhóm. SUBORDINATE chỉ có một người nên thống kê nhóm được ẩn. Linh còn một phân công PEER tùy chọn chưa gửi.
6. HR có thể chốt An bằng cách xác nhận số phản hồi tùy chọn còn mở, hoặc để Linh gửi trước. Gửi thêm phản hồi sẽ làm điểm cũ cần tính lại; xem dữ liệu mới trước khi tính/chốt.

## Luồng 3: tính mới, tính lại và xem hồ sơ đã chốt

- **Dũng:** đã đủ KPI và phản hồi bắt buộc, chưa tính điểm. HR/quản lý kỹ thuật bấm tính để thấy luồng tạo kết quả lần đầu.
- **Linh:** đã tính điểm rồi sửa KPI, trạng thái **Cần tính lại**. HR/quản lý kinh doanh tính lại, lịch sử cũ vẫn giữ.
- **Hà:** đã chốt trong kỳ ACTIVE. Xem kết quả hoặc tạo AI bằng HR; các thao tác sửa bằng chứng bị khóa.
- Sau khi mọi người trong kỳ ACTIVE đều đã chốt, HR **Đóng chu kỳ**, rồi có thể kích hoạt kỳ nháp tiếp theo. Một hồ sơ chưa chốt vẫn chặn đóng kỳ.

Mọi lần thử sau đó thay đổi dữ liệu thật trong môi trường local của bạn. Lệnh nạp lại không hoàn tác những thay đổi đó. Nếu quên mật khẩu demo, dùng ADMIN đang có để đặt lại mật khẩu từng tài khoản qua giao diện quản trị.

## Kiểm chứng khi bổ sung bộ demo

[CI 39737007010](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39737007010) tại `33af896` đạt cả backend/frontend/docker-smoke: **816 backend test**, Ruff/mypy sạch (93 source files), frontend và Docker giữ các gate hiện có. Kiểm thử mới xác nhận đăng nhập đủ 10 role/account, phạm vi của hai quản lý, các trạng thái hồ sơ, chạy lại không đổi mật khẩu/tiến độ, từ chối mã trùng/chu kỳ ACTIVE hiện có/production và rollback toàn bộ sau lỗi muộn.

Trên local đã nạp thành công 10 tài khoản demo vào database có sẵn 3 tài khoản; fingerprint của các tài khoản cũ không đổi. Đăng nhập thật đủ 10 tài khoản qua web proxy tại `localhost:3000` đạt; trạng thái An CURRENT 82.80, Bình/Dũng NOT_CALCULATED, Hà FINALIZED 87.00, Linh STALE đúng dự kiến. Chạy lại không tạo trùng. Số AI attempt vẫn bằng 0; không gọi Gemini. Không lưu mật khẩu local vào Git/tài liệu.
