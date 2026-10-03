# InsightHR

[Read this guide in English](README.md)

InsightHR là hệ thống quản lý hiệu suất nhân viên có hỗ trợ AI, được xây dựng như một đồ án capstone. Hệ thống hướng tới quản lý hồ sơ nhân viên, chu kỳ đánh giá, KPI, phản hồi 360 độ có phân quyền, tính điểm có thể tái lập và phân tích tư vấn bằng Gemini khi người dùng yêu cầu.

Dự án sử dụng kiến trúc modular monolith gồm ứng dụng web Next.js, API FastAPI và PostgreSQL. Xem [bản thiết kế kiến trúc](docs/architecture.md) để hiểu đầy đủ các quyết định kỹ thuật và quy tắc nghiệp vụ.

## Trạng thái hiện tại

Phase 1 đã hoàn thành:

- Quy ước repository và hợp đồng biến môi trường.
- FastAPI với cấu hình được kiểm tra, định dạng lỗi ổn định và request ID.
- Endpoint liveness và readiness có kiểm tra PostgreSQL cùng Alembic revision.
- Trang trạng thái hệ thống bằng Next.js.
- Docker image chạy bằng người dùng không phải root.
- Docker Compose thực hiện migration trước khi khởi động API và web.
- GitHub Actions kiểm tra backend, frontend, image, migration và khả năng giữ dữ liệu sau khi khởi động lại.

Authentication và RBAC thuộc Phase 2. Các chức năng nghiệp vụ như nhân viên, phòng ban, chu kỳ đánh giá, KPI, phản hồi, tính điểm, Gemini và dashboard chưa được triển khai.

## Công nghệ

- Web: Next.js 16, React 19, TypeScript strict, Tailwind CSS.
- API: Python 3.12, FastAPI, SQLAlchemy 2, Pydantic Settings, Alembic, psycopg 3.
- Cơ sở dữ liệu: PostgreSQL 16.
- Triển khai: Docker, Docker Compose, GitHub Actions.
- Chất lượng: pytest, Ruff, mypy, Vitest, ESLint và TypeScript compiler.

## Cấu trúc repository

```text
apps/
  api/               FastAPI, migration và kiểm thử backend
  web/               Next.js và kiểm thử frontend
docs/                Kiến trúc, API và hướng dẫn vận hành
infrastructure/
  docker/            Dockerfile production cho API và web
docker-compose.yml   Toàn bộ stack chạy cục bộ
```

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
Copy-Item .env.example .env
docker compose --env-file .env up --build --wait
```

Trên bash/zsh:

```bash
cp .env.example .env
docker compose --env-file .env up --build --wait
```

Mở `http://localhost:3000`. Trang chủ phải hiển thị `API connected`.

Các endpoint vận hành:

- `http://localhost:8000/health/live`: tiến trình API đang hoạt động.
- `http://localhost:8000/health/ready`: PostgreSQL hoạt động và migration đang ở revision mới nhất.

Dừng hệ thống nhưng giữ dữ liệu PostgreSQL:

```bash
docker compose --env-file .env down
```

Đọc [hướng dẫn triển khai](docs/deployment.md) trước khi xóa volume hoặc xử lý lỗi khởi động.

## Chạy trực tiếp trên máy

Sao chép cấu hình mẫu cho từng ứng dụng:

```powershell
Copy-Item .env.example apps/api/.env
Copy-Item .env.example apps/web/.env.local
```

Tạo role và database PostgreSQL theo phần [Direct-host PostgreSQL](docs/deployment.md#direct-host-postgresql). Thông tin tài khoản phải khớp với `DATABASE_URL` trong `apps/api/.env`.

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

Luôn kiểm tra migration được sinh ra trước khi chạy. Phase 1 chỉ có baseline rỗng `20261003_0001`; các bảng nghiệp vụ được bổ sung trong những phase sau.

## Kiểm thử và kiểm tra chất lượng

Backend cần một database PostgreSQL dành riêng cho kiểm thử. Từ `apps/api` trên PowerShell:

```powershell
$env:TEST_DATABASE_URL="postgresql+psycopg://insighthr_test:insighthr-test-password@127.0.0.1:5432/insighthr_test"
python -m pytest -q
python -m ruff check app tests alembic
python -m mypy app
```

Không trỏ `TEST_DATABASE_URL` vào database development, staging hoặc production vì fixture integration sẽ xóa bảng `alembic_version`.

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

Phase 1 chưa chứa secret xác thực hoặc Gemini. Các biến đó chỉ được thêm ở phase sở hữu chức năng tương ứng.

## Tài liệu liên quan

- [Kiến trúc hệ thống](docs/architecture.md).
- [Triển khai và vận hành](docs/deployment.md).
- [Thiết kế database](docs/database.md).
- [Hợp đồng API](docs/api.md).
- [Ranh giới thiết kế AI](docs/ai-design.md).
- [Kế hoạch triển khai Phase 1](docs/superpowers/plans/2026-10-03-phase-1-foundation.md).
- [Kế hoạch triển khai Phase 2](docs/superpowers/plans/2026-10-03-phase-2-authentication.md).

## Các phase tiếp theo

Phase 2 triển khai đăng nhập, refresh token rotation, logout, RBAC, quản trị tài khoản ADMIN và chính sách bảo mật dùng chung. Các phase sau lần lượt bổ sung tổ chức và nhân viên, chu kỳ/KPI, phản hồi, tính điểm, Gemini, dashboard, kiểm thử tích hợp bảo mật và Kubernetes.
