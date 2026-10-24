# Cài đặt và phát triển local chi tiết

Hướng dẫn kỹ thuật; để chạy nhanh và thực hành theo role, xem [README tiếng Việt](../README.vi.md). Các lệnh dưới đây chạy từ `hrm-ai` trừ khi ghi thư mục khác.

## Yêu cầu môi trường

Khi chạy trực tiếp trên máy:

- Git.
- Python 3.12.
- Node.js 24 LTS và npm.
- PostgreSQL 16.

Khi chạy toàn bộ stack:

- Docker Desktop trên Windows/macOS hoặc Docker Engine trên Linux.
- Docker Compose v2 trở lên.
- WSL 2 và virtualization khi dùng Docker Desktop trên Windows.

## Khởi động nhanh bằng Docker Compose

Mở PowerShell tại thư mục gốc `hrm-ai`:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose --env-file .env up --build --wait
```

Trên bash/zsh:

```bash
test -f .env || cp .env.example .env
docker compose --env-file .env up --build --wait
```

Mở http://localhost:3000/login để dùng ứng dụng. Trang trạng thái hệ thống và health endpoints phục vụ chẩn đoán kỹ thuật.

Các endpoint vận hành:

- `http://localhost:8000/health/live`: tiến trình API đang hoạt động.
- `http://localhost:8000/health/ready`: PostgreSQL hoạt động và migration đang ở revision mới nhất.

Dừng hệ thống nhưng giữ dữ liệu PostgreSQL:

```bash
docker compose --env-file .env down
```

Đọc [hướng dẫn triển khai](deployment.md) trước khi xóa volume hoặc xử lý lỗi khởi động.

## Chạy trực tiếp trên máy

Sao chép cấu hình mẫu cho từng ứng dụng:

```powershell
Copy-Item .env.example apps/api/.env
Copy-Item .env.example apps/web/.env.local
```

Tạo role và database PostgreSQL theo phần [Direct-host PostgreSQL](deployment.md#direct-host-postgresql). Thông tin tài khoản phải khớp với `DATABASE_URL` trong `apps/api/.env`.

Trong thư mục `apps/api`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --constraint requirements.lock -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Trên Linux/macOS, tạo và kích hoạt môi trường bằng:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Trong terminal thứ hai, mở thư mục `apps/web`:

```bash
npm ci
npm run dev
```

## Migration cơ sở dữ liệu

Sau khi thêm hoặc sửa SQLAlchemy metadata, chạy từ `apps/api`:

```bash
alembic revision --autogenerate -m "mo ta thay doi schema"
alembic upgrade head
```

Luôn kiểm tra migration được sinh ra trước khi chạy. Head hiện tại là `20261024_0008` (limiter đăng nhập). Chạy `alembic upgrade head` để nâng cấp; xem [schema và lịch sử migration](database.md). Không cần tạo migration mới chỉ để chạy dự án.

## Kiểm thử và kiểm tra chất lượng

Backend cần một database PostgreSQL dành riêng cho kiểm thử. Từ `apps/api` trên PowerShell:

```powershell
$env:TEST_DATABASE_URL="postgresql+psycopg://insighthr_test:insighthr-test-password@127.0.0.1:5432/insighthr_test"
python -m pytest -q
python -m ruff check app tests alembic
python -m mypy app
```

Chỉ dùng database kiểm thử riêng có tên kết thúc bằng `_test`. Fixture sẽ xóa các bảng user/session/audit và `alembic_version`; không dùng database có dữ liệu cần giữ.

Frontend từ `apps/web`:

```bash
npm run test -- --run
npm run lint
npm run typecheck
npm run build
```

## Biến môi trường và bí mật

`.env.example` là hợp đồng cấu hình công khai. Sao chép file này thành `.env` và thay mật khẩu mẫu trước khi dùng trong môi trường dùng chung.

`POSTGRES_PASSWORD_URLENCODED` phải là dạng percent-encoded của `POSTGRES_PASSWORD`. Docker Compose dùng giá trị đã mã hóa khi tạo `DATABASE_URL`. Mọi file `.env` đều bị Git bỏ qua và bị loại khỏi Docker build context.

`AUTH_ACCESS_SECRET` là khóa ký access token, cần giá trị riêng có ít nhất 32 ký tự trong test/production. Giá trị mẫu chỉ dành cho development. `WEB_ORIGIN` phải đúng origin của trình duyệt, ví dụ `http://localhost:3000` (không có dấu `/` ở cuối); đổi cổng web thì phải sửa origin tương ứng. `localhost` và `127.0.0.1` là hai origin khác nhau.

`COOKIE_SECURE=false` chỉ dùng cho HTTP local; production cần HTTPS và `COOKIE_SECURE=true`. `ACCESS_TOKEN_MINUTES=15`, `REFRESH_SESSION_DAYS=7`: refresh giữ nguyên thời hạn tuyệt đối của phiên, không gia hạn thêm bảy ngày mỗi lần. Gemini là tùy chọn; xem [hướng dẫn AI](../README.vi.md#dùng-ai-khi-cần).

## Tạo ADMIN đầu tiên và dùng ứng dụng

Sau khi Compose đã chạy và migration thành công, từ thư mục gốc repository:

```powershell
docker compose --env-file .env exec api python -m app.cli.create_admin --email admin@example.com
```

Lệnh hỏi mật khẩu hai lần và không hiển thị khi gõ. Mật khẩu cần 12–128 ký tự Unicode, không bị tự cắt khoảng trắng. Nếu chạy API trực tiếp, dùng `python -m app.cli.create_admin --email admin@example.com` trong `apps/api` với virtual environment đang hoạt động. Chế độ `--password-stdin` đọc hai dòng trùng nhau cho CI; không đưa mật khẩu vào đối số lệnh, biến môi trường hoặc lịch sử terminal.

1. Mở `http://localhost:3000/login`, nhập email và mật khẩu vừa tạo.
2. Trang `/account` hiển thị email, role, nút đăng xuất và form đổi mật khẩu. Đổi mật khẩu cần mật khẩu hiện tại, mật khẩu mới khác mật khẩu cũ và xác nhận khớp; các phiên khác bị thu hồi.
3. ADMIN mở liên kết **Quản lý tài khoản** hoặc `/admin/users`: xem danh sách/phân trang, tạo tài khoản, đổi role và kích hoạt/vô hiệu hóa. Vô hiệu hóa cần xác nhận và thu hồi mọi phiên của tài khoản đó.
4. Hệ thống không cho hạ quyền hoặc vô hiệu hóa ADMIN đang hoạt động cuối cùng, kể cả hai yêu cầu cùng lúc. ADMIN chỉ quản trị hệ thống, không tự có quyền HR.

Cookie access/refresh là HttpOnly, trình duyệt tự gửi; ứng dụng không lưu token trong localStorage. Cookie CSRF có thể đọc bởi web để gửi `X-CSRF-Token` cho thao tác ghi. Backend kiểm tra cả Origin và CSRF gắn với phiên; không tắt các kiểm tra này khi gặp lỗi 403.

Nếu quên mật khẩu bootstrap: chưa có chức năng reset qua email. Người vận hành có quyền máy chủ có thể tạo ADMIN mới bằng lệnh trên với **email khác**, đăng nhập rồi vô hiệu hóa tài khoản mất quyền truy cập. Lệnh không ghi đè tài khoản trùng email. Không sửa trực tiếp hash trong DB. Xem [runbook vận hành](deployment.md#phase-2-authentication-operations).

Trên PowerShell nếu `npm.ps1` bị chặn, dùng `npm.cmd` thay cho `npm`; không cần thay đổi execution policy toàn máy.
