# InsightHR

Hệ thống quản lý hiệu suất nhân viên: hồ sơ, KPI, phản hồi 360, tính điểm và tư vấn AI theo quyền. [English](README.md).

## Chạy và xem ngay

1. Mở **Docker Desktop**.
2. Mở terminal tại thư mục **`hrm-ai`** và chạy:

```powershell
docker compose --env-file .env up --build --wait
```

3. Vào **http://localhost:3000/login** và đăng nhập.

Nếu cài lần đầu, tạo file cấu hình trước khi chạy:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Khi code thay đổi, chạy lại lệnh có `--build`. Khi code không đổi, có thể bỏ `--build`. Tài khoản và dữ liệu cũ được giữ; không cần nạp lại demo.

Muốn dừng và giữ dữ liệu: `docker compose --env-file .env down`. [Cài đặt/terminal/kiểm thử chi tiết](docs/local-development.vi.md).

## Có dữ liệu để thực hành chưa?

Nếu đã nạp demo trước đó, dùng lại tài khoản hiện có. Với bộ cài mới, nạp dữ liệu hư cấu:

```powershell
docker compose --env-file .env exec api python -m app.cli.seed_demo
```

Lệnh tạo **10 tài khoản, 8 nhân viên, 3 chu kỳ**, in mật khẩu ngẫu nhiên một lần. Chạy lại giữ tiến độ và mật khẩu cũ. Xem [danh sách tài khoản và bài thực hành](docs/demo.vi.md).

Nếu muốn tạo ADMIN riêng:

```powershell
docker compose --env-file .env exec api python -m app.cli.create_admin --email admin@example.com
```

Nhập mật khẩu khi được hỏi; không đặt mật khẩu hoặc API key trong lệnh/Git.

## Dùng chức năng theo role

| Role | Công việc chính |
| --- | --- |
| ADMIN | Tạo/khóa tài khoản, đổi role, cấu hình trọng số tính điểm |
| HR | Hồ sơ/tổ chức, chu kỳ/KPI, giao phản hồi, chốt kết quả, đóng kỳ, yêu cầu AI |
| Quản lý | Theo dõi nhân viên trực tiếp, nhập kết quả KPI/tính điểm khi có quyền, gửi phản hồi được giao |
| Nhân viên | Xem KPI/kết quả của mình, gửi phản hồi được giao, đọc tư vấn chung đã lưu |

**Tab trên** chọn nhóm chức năng; **menu trái** hiện các việc của nhóm đang mở. Trên điện thoại, bấm **Mở menu**. Form tạo mới và chi tiết tính điểm được thu gọn, bấm tiêu đề để mở khi cần.

Luồng đánh giá: **HR lập kỳ/giao KPI → nhập thực tế → reviewer gửi phản hồi → quản lý/HR tính điểm → HR chốt từng người và đóng kỳ**. Nếu sửa KPI/phản hồi, kết quả chuyển “Cần tính lại”. Từ chu kỳ, chọn nhân viên rồi dùng các tab **KPI / Phản hồi 360 / Kết quả hiệu suất** để làm việc cùng ngữ cảnh.

## Dùng AI khi cần

Điểm số và nghiệp vụ chạy được khi AI tắt. HR mở báo cáo kết quả, chọn **Tư vấn chung** hoặc **Nội bộ HR**, đọc phạm vi dữ liệu rồi xác nhận tạo. Chỉ thao tác xác nhận mới gửi yêu cầu tới Gemini; mở/tải lại trang không gọi AI.

Muốn bật, tự điền `.env` trên máy của bạn:

```dotenv
GEMINI_ENABLED=true
GEMINI_API_KEY=<key của bạn>
GEMINI_MODEL=<model bạn được quyền sử dụng, hỗ trợ structured JSON>
```

Chạy lại lệnh Compose có `--build`. Không đưa key vào biến `NEXT_PUBLIC_` hoặc Git. Nội dung AI là tư vấn, không thay đổi điểm; private chỉ HR được đọc. Xem [cấu hình và xử lý lỗi AI](docs/deployment.md#phase-7-optional-gemini-operations).

## Kubernetes và tài liệu

**Compose** phù hợp để chạy hằng ngày. **Kubernetes local** dùng cho học triển khai, migration, ingress/TLS và phục hồi backup. Hai môi trường có dữ liệu riêng. Xem [hướng dẫn Kubernetes tiếng Việt](docs/kubernetes.vi.md).

- [Báo cáo Phase 10 và bằng chứng kiểm thử](docs/phase-10-report.vi.md).
- [Kiến trúc và lộ trình 10 phase](docs/architecture.md).
- [Database](docs/database.md), [API](docs/api.md), [triển khai](docs/deployment.md).
- [Bảo mật và cấu hình vận hành](docs/phase-9-operations.vi.md).

Web dùng Next.js, API FastAPI và PostgreSQL. Gemini là thành phần tùy chọn. Tài liệu báo cáo từng phase ghi rõ phạm vi đã nghiệm thu và các giới hạn còn lại.
