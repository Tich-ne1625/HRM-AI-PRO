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

Phases 1–6 đã hoàn tất và qua [CI nghiệm thu Phase 6](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39715137000): **767 test backend, 104 test web**, kiểm tra chất lượng, build và Docker smoke/persistence đều đạt. Phase 6 có tính điểm, báo cáo/lịch sử, chốt đánh giá và đóng chu kỳ. Giao diện chung có **tab nhóm chức năng phía trên và menu trái theo quyền**, cùng tab KPI/phản hồi/kết quả giữ nguyên nhân viên và kỳ đang xem. Xem bằng chứng trong [kế hoạch Phase 6](docs/superpowers/plans/2026-10-22-phase-6-performance.md). Dashboard tổng thể chưa triển khai; Phase 7 được cập nhật bên dưới.

**Phase 7 — tư vấn Gemini** đã qua [CI nghiệm thu](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39728715722): **811 test backend, 117 test web**, quality/build và Docker persistence đạt. Đã triển khai trên trang kết quả: tư vấn chung từ số liệu và phân tích nhận xét riêng HR, có xác nhận trước khi gửi. Mặc định AI tắt, không cần API key để chạy dự án. Xem [kế hoạch và bằng chứng nghiệm thu](docs/superpowers/plans/2026-10-22-phase-7-gemini.md), [hợp đồng](docs/phase-7-contract.md) và [review](docs/phase-7-review.md). Dashboard tổng thể chưa triển khai; kiểm thử Gemini thật được ghi riêng với kiểm thử offline.

## Chạy và xem nhanh

Nếu đã có `.env`, mở Docker Desktop, rồi chạy tại thư mục `hrm-ai`:

```powershell
docker compose --env-file .env up --build --wait
```

Mở **http://localhost:3000/login** để đăng nhập. Lệnh trên build lại code và tự nâng database, giữ tài khoản/dữ liệu cũ. Những lần chạy sau khi code không đổi có thể bỏ `--build`. Các bước tạo ADMIN lần đầu nằm ở phần bên dưới.

Để xem kết quả: **Chu kỳ đánh giá → mở kỳ → người tham gia → Kết quả**. HR và quản lý hiện tại tính điểm; nhân viên xem kết quả của mình. Hướng dẫn chốt/đóng kỳ ở [phần Phase 6](#dùng-báo-cáo-hiệu-suất-và-chốt-kỳ-phase-6).

## Dữ liệu mẫu để thực hành từng role

Đã có lệnh nạp bộ demo với **10 tài khoản, 8 nhân viên và 3 chu kỳ** ở các trạng thái khác nhau. Sau khi cập nhật image, chạy:

```powershell
docker compose --env-file .env exec api python -m app.cli.seed_demo
```

Lệnh in mật khẩu ngẫu nhiên một lần. Chạy lại không nhân bản, không đổi mật khẩu hay đặt lại tiến độ. Bộ demo giữ nguyên dữ liệu hiện có, chỉ chạy trong development/test và không tự gọi Gemini. Xem [tài khoản và bài thực hành ADMIN / HR / quản lý / nhân viên](docs/demo.vi.md).

## Dùng tư vấn AI (Phase 7)

1. Mở **Chu kỳ đánh giá → người tham gia → Kết quả**. Khối **Tư vấn AI** nằm ngay dưới điểm số, dùng chung header, menu trái và nhân viên/kỳ đang xem.
2. **HR** chọn **Tư vấn chung** hoặc **Nội bộ HR**. Tư vấn chung chỉ gửi số liệu KPI/điểm và thống kê phản hồi đã lọc; nội bộ HR gửi thêm tối đa 20 nhận xét đã che thông tin của đúng lần tính. Che thông tin là biện pháp giảm rủi ro, không bảo đảm ẩn danh tuyệt đối.
3. Bấm **Tạo tư vấn AI**, đọc phạm vi dữ liệu, tích đồng ý và xác nhận. Chỉ thao tác này mới gửi dữ liệu tới Gemini và có thể phát sinh phí. Mở trang, làm mới, tính điểm và chốt kỳ không tự gọi AI.
4. Nhân viên và quản lý trực tiếp hiện tại chỉ đọc tư vấn chung đã lưu; ADMIN không có quyền HR mặc định. HR xem riêng nội bộ và lịch sử. Đầu ra chỉ mang tính tư vấn, không sửa điểm số.
5. Nếu mất kết nối, dùng **Kiểm tra yêu cầu vừa gửi** để tra lại cùng mã yêu cầu. Muốn tạo bản khác phải chủ động xác nhận lại; chờ ít nhất 30 giây giữa hai lượt của cùng hồ sơ. Tạo lại lỗi vẫn giữ bản thành công trước đó.
6. Khi KPI/phản hồi thay đổi, tính lại điểm trước khi tạo tư vấn mới. Tư vấn cũ được giữ trong lịch sử. Kết quả đã chốt và kỳ đã đóng vẫn có thể được phân tích nếu có quyền.

Nếu thấy **Gemini chưa được cấu hình**, dự án vẫn chạy bình thường. Khi muốn bật, tự điền trong `.env` phía máy chủ:

```dotenv
GEMINI_ENABLED=true
GEMINI_API_KEY=<API key của bạn>
GEMINI_MODEL=<model hỗ trợ structured JSON mà bạn được quyền dùng>
GEMINI_TIMEOUT_SECONDS=20
GEMINI_MAX_OUTPUT_TOKENS=2048
```

Sau đó chạy `docker compose --env-file .env up --build --wait`. Key chỉ chuyển vào API, không đưa vào biến `NEXT_PUBLIC_`, Git hay ảnh chụp. Khi chưa cần, giữ `GEMINI_ENABLED=false` và để key/model trống. Kiểm thử tự động dùng provider giả có nhãn; **chưa nghiệm thu lời gọi Gemini thật**. Hướng dẫn kiểm thử thật với dữ liệu hư cấu nằm trong [vận hành Phase 7](docs/deployment.md#phase-7-optional-gemini-operations).

## Dùng báo cáo hiệu suất và chốt kỳ (Phase 6)

1. Mở **Chu kỳ đánh giá → người tham gia → Kết quả**. Các tab phía trên báo cáo chuyển giữa KPI, phản hồi và kết quả của cùng nhân viên/kỳ; không cần chọn lại.
2. Nếu chưa đủ dữ liệu, làm theo **Việc cần hoàn thành**: phân bổ KPI đúng 100%, nhập thực tế cho mọi KPI, hoàn thành tự đánh giá, đánh giá của quản lý và mọi phân công bắt buộc. Phân công không bắt buộc chưa gửi không chặn tính điểm.
3. **HR hoặc quản lý trực tiếp hiện tại** bấm **Tính điểm hiệu suất**. Điểm lấy cấu hình đã đóng băng khi kích hoạt kỳ; không phụ thuộc AI. Ví dụ KPI 90 và phản hồi 80, trọng số 70/30, cho điểm hiệu suất **87.00**.
4. Khi sửa KPI/phân công hoặc có thêm phản hồi, báo cáo hiện **Cần tính lại**. Điểm cũ được giữ trong **Lịch sử tính điểm**; bấm **Tính lại điểm** để có kết quả mới. Không thay dữ liệu thì tính lại sẽ dùng kết quả hiện có, không tạo lịch sử trùng.
5. **HR** bấm **Chốt kết quả**, kiểm tra số phân công không bắt buộc chưa gửi, tích xác nhận rồi **Xác nhận chốt kết quả**. Chốt sẽ khóa KPI, phân công, gửi phản hồi và tính lại của nhân viên trong kỳ đó. Các phân công chưa gửi được giữ trong lịch sử. Không mở lại kết quả đã chốt.
6. Sau khi mọi người tham gia đã chốt, **HR** mở chi tiết chu kỳ → **Đóng chu kỳ** → xác nhận. Sau đó có thể kích hoạt kỳ nháp tiếp theo. Kỳ đã đóng vẫn xem được theo quyền hiện tại.

Nhân viên chỉ xem của mình; quản lý xem bản thân/nhân viên trực tiếp nhưng không tự tính điểm cho mình. ADMIN không có quyền HR. Khi chuyển quản lý, quyền đọc báo cáo/lịch sử đổi theo quan hệ hiện tại. Nhóm phản hồi nhỏ vẫn được ẩn thống kê; báo cáo chỉ hiện nhận xét do chính người xem viết. Nếu báo xung đột dữ liệu, chọn **Tải bản mới** và kiểm tra lại trước khi xác nhận.

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

Luôn kiểm tra migration được sinh ra trước khi chạy. Head hiện tại là `20261022_0006`, thêm kết quả và lịch sử tính điểm; nối sau feedback `20261020_0005`, chu kỳ/KPI `20261020_0004`, organization `20261019_0003`, auth `20261003_0002` và baseline `20261003_0001`. Nâng cấp database hiện hữu bằng `alembic upgrade head`; sao lưu dữ liệu cần giữ trước khi migration.

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

`COOKIE_SECURE=false` chỉ dùng cho HTTP local; production cần HTTPS và `COOKIE_SECURE=true`. `ACCESS_TOKEN_MINUTES=15`, `REFRESH_SESSION_DAYS=7`: refresh giữ nguyên thời hạn tuyệt đối của phiên, không gia hạn thêm bảy ngày mỗi lần. Chưa có cấu hình Gemini ở phase này.

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

Nếu quên mật khẩu bootstrap: chưa có chức năng reset qua email. Người vận hành có quyền máy chủ có thể tạo ADMIN mới bằng lệnh trên với **email khác**, đăng nhập rồi vô hiệu hóa tài khoản mất quyền truy cập. Lệnh không ghi đè tài khoản trùng email. Không sửa trực tiếp hash trong DB. Xem [runbook vận hành](docs/deployment.md#phase-2-authentication-operations).

Trên PowerShell nếu `npm.ps1` bị chặn, dùng `npm.cmd` thay cho `npm`; không cần thay đổi execution policy toàn máy.

## Dùng phần tổ chức và nhân viên (Phase 3)

1. Đăng nhập ADMIN, mở `/admin/users` và tạo ít nhất một tài khoản role **HR**. Tạo thêm MANAGER/EMPLOYEE để thử phân quyền. ADMIN không tự có quyền quản lý hồ sơ nhân sự.
2. Đăng xuất ADMIN rồi đăng nhập HR. Menu sẽ có **Nhân viên**, **Phòng ban**, **Chức danh**. Trên database mới, danh sách rỗng là bình thường; chưa có seed tự động.
3. Mở `/departments` và `/positions`, tạo mã/tên phòng ban và chức danh. Mã gồm 2–32 ký tự chữ ASCII, số, `_` hoặc `-`; hệ thống chuẩn hóa viết hoa. Tên tối đa 200 ký tự.
4. Mở `/employees`, bấm **Thêm nhân viên**, nhập mã/họ tên và chọn phòng ban/chức danh đang hoạt động. Có thể tìm và phân trang các lựa chọn. Tạo hồ sơ người quản lý trước rồi chọn người này cho nhân viên cấp dưới.
5. Trong form hồ sơ, nhập **đúng email** tài khoản đã được ADMIN tạo, bấm **Tìm tài khoản**, chọn **Liên kết tài khoản này**, rồi **Lưu hồ sơ**. Một tài khoản chỉ liên kết một hồ sơ. HR không thể tạo hay đổi quyền tài khoản qua form này.
6. Bấm tên nhân viên để mở `/employees/{id}`. HR có thể sửa hồ sơ, đổi/bỏ người quản lý, thay/bỏ liên kết tài khoản và đổi trạng thái làm việc. Hệ thống chặn tự quản lý và vòng lặp nhiều cấp, kể cả hai yêu cầu đồng thời.
7. Đăng nhập MANAGER đã liên kết: chỉ thấy bản thân và nhân viên báo cáo trực tiếp, không thấy cấp dưới gián tiếp. EMPLOYEE chỉ thấy chính mình. Tài khoản chưa liên kết hồ sơ sẽ thấy danh sách rỗng. Quyền đổi ngay khi HR chuyển manager hoặc thay liên kết, không cần phát hành lại JWT.

Ngừng hoạt động phòng ban/chức danh cần xác nhận và không xóa hồ sơ cũ. Các hồ sơ đang tham chiếu vẫn đọc/sửa được; không được gán mới reference đã ngừng hoạt động. Trạng thái nhân viên `ACTIVE`/`INACTIVE` độc lập với trạng thái đăng nhập của user: HR đổi trạng thái làm việc **không** tự khóa tài khoản; ADMIN quản lý quyền đăng nhập.

## Dùng chu kỳ đánh giá và KPI (Phase 4)

Nếu đang chạy bản cũ bằng Docker, từ thư mục `hrm-ai` chạy:

```powershell
docker compose --env-file .env up --build --wait
```

Lệnh build lại và áp head hiện tại `20261022_0006`; chức năng chu kỳ/KPI được thêm từ `20261020_0004`. Không cần tạo lại ADMIN hoặc xóa volume.

1. **ADMIN** mở **Cấu hình chấm điểm** (`/settings/scoring`): mặc định KPI 70%, phản hồi 30%, cap 100.00. Chỉ sửa nếu cần; tổng hai trọng số phải đúng 100.00%. Sửa mặc định không đổi chu kỳ đã kích hoạt. ADMIN không có quyền HR.
2. **HR** mở **Danh mục KPI** (`/kpis`), thêm mã/tên/đơn vị và chọn “Càng cao càng tốt” hoặc “Càng thấp càng tốt”. Ngừng sử dụng không xóa KPI đã gán; định nghĩa đã ngừng không được gán mới.
3. **HR** mở **Chu kỳ đánh giá** (`/review-cycles`), tạo nháp với tên/ngày, mở chi tiết rồi tìm/chọn người tham gia. Lựa chọn giữ khi đổi trang; mỗi lượt thêm tối đa 100 người. Nhân viên phải đang làm việc, có phòng ban/chức danh hoạt động, có tài khoản đang hoạt động và có người quản lý đang làm việc với tài khoản active. Người chưa có quản lý chưa đủ điều kiện theo chính sách SELF + MANAGER bắt buộc.
4. Bấm **Kích hoạt chu kỳ** rồi xác nhận. Lỗi chỉ rõ hồ sơ cần kiểm tra nếu thiếu điều kiện. Kích hoạt đóng băng danh sách, thông tin tổ chức, quan hệ lịch sử và policy; không sửa danh sách sau đó. Chỉ có một ACTIVE. HR đóng kỳ sau khi mọi người tham gia đã chốt kết quả; ngày kết thúc không tự đóng.
5. Từ danh sách người tham gia, **HR hoặc quản lý trực tiếp hiện tại** mở **Quản lý KPI**. Bấm **Chỉnh phân bổ KPI**, tìm/chọn KPI, nhập target dương và từng trọng số dương, tổng đúng **100.00%**, rồi **Lưu toàn bộ phân bổ**. Danh sách chưa đủ 100% chỉ là nháp trên màn hình. Tối đa 100 KPI/người/chu kỳ.
6. Bấm **Nhập thực tế** ở từng KPI để nhập actual không âm. `0.0000` là kết quả hợp lệ; để trống để xóa. Đổi target của KPI đã có actual cần xác nhận và xóa actual liên quan để nhập lại. Đổi weight giữ actual; sửa danh mục không đổi snapshot của KPI đã gán.
7. **EMPLOYEE** mở chu kỳ của mình rồi **Xem KPI**, không sửa được. MANAGER đọc self/direct reports hiện tại nhưng chỉ ghi cho direct report đang làm việc, không tự ghi KPI của mình. Chuyển quản lý đổi quyền hiện tại và giữ nguyên lịch sử tổ chức của kỳ.
8. Nếu báo **dữ liệu đã thay đổi**, thông tin đang nhập được giữ khi lỗi. Chọn **Tải bản mới**, kiểm tra rồi nhập lại thay đổi; không tự gửi lại bằng version mới. Chưa có allocation/actual sẽ hiện “Chưa phân bổ KPI”/“Chưa nhập”; không có điểm hiệu suất hoặc AI giả.

## Tài liệu liên quan

- [Kiến trúc hệ thống](docs/architecture.md).
- [Triển khai và vận hành](docs/deployment.md).
- [Thiết kế database](docs/database.md).
- [Hợp đồng API](docs/api.md).
- [Ranh giới thiết kế AI](docs/ai-design.md).
- [Kế hoạch triển khai Phase 1](docs/superpowers/plans/2026-10-03-phase-1-foundation.md).
- [Kế hoạch triển khai Phase 2](docs/superpowers/plans/2026-10-03-phase-2-authentication.md).

## Các phase tiếp theo

Phase 4 đã hoàn tất theo [kế hoạch chi tiết](docs/superpowers/plans/2026-10-19-phase-4-cycles-kpis.md) và [hợp đồng nghiệp vụ](docs/phase-4-contract.md), nghiệm thu CI ngày 2026-10-20. Phase 5 phản hồi cũng đã nghiệm thu. Gemini, dashboard, seed và Kubernetes là các công đoạn tiếp theo.

Phase 5 hoàn tất theo [kế hoạch 8 task](docs/superpowers/plans/2026-10-20-phase-5-feedback.md) và [hợp đồng](docs/phase-5-contract.md); runtime `bf04fe2` đã qua đầy đủ CI. Năm lượt test cạnh tranh đều đạt 26/26. Giới hạn bảo mật và account lịch sử được mô tả trong hướng dẫn dưới đây.

Phase 6 có [kế hoạch 8 task](docs/superpowers/plans/2026-10-22-phase-6-performance.md) và [hợp đồng](docs/phase-6-contract.md). Tính điểm và lịch sử hoạt động độc lập với AI; AI thuộc Phase 7.

## Dùng phản hồi 360 (Phase 5)

Xem báo cáo đã tính bằng tab **Kết quả hiệu suất** trong trang KPI hoặc tổng hợp phản hồi. Mức phản hồi trung bình /5 khác với điểm phản hồi /100 dùng trong báo cáo.

Sau khi cập nhật code, tại thư mục `hrm-ai` chạy `docker compose --env-file .env up --build --wait` để nâng schema lên `20261022_0006`, giữ nguyên tài khoản và dữ liệu. Trên màn hình hẹp, bấm **Mở menu** để chọn trang; màn hình lớn có điều hướng bên trái.

1. **HR** vào **Chu kỳ đánh giá**, mở chu kỳ ACTIVE, chọn **Phân công phản hồi** ở dòng người tham gia. Trang này dùng lại nhân viên và chu kỳ vừa chọn.
2. Trong **Thêm phân công**, chọn quan hệ và người đánh giá hợp lệ, đặt hạn nếu cần rồi **Giao phản hồi**. Cần giao cả **Tự đánh giá** và **Quản lý**; kích hoạt chu kỳ chưa tự tạo hai phân công này. Hai quan hệ luôn bắt buộc và dùng tài khoản đã ghi nhận lúc kích hoạt. Nếu tài khoản bị khóa, ADMIN cần khôi phục đúng tài khoản, không tự giao cho quản lý mới.
3. **Người được giao**, gồm cả ADMIN nếu có phân công, mở **Phản hồi của tôi**, chọn phân công, nhập mức 1–5 và nhận xét tối đa 2.000 ký tự. Bấm **Kiểm tra và gửi**, xem lại rồi **Xác nhận gửi một lần**. Nội dung đã gửi không sửa/xóa được. HR có quyền đọc nhận xét gốc.
4. Nếu quá hạn, liên hệ HR gia hạn. Không đặt hạn riêng vẫn chỉ gửi được khi chu kỳ ACTIVE và hồ sơ chưa chốt. Nếu báo dữ liệu đã thay đổi, bấm **Tải phiên bản mới, giữ nội dung**, kiểm tra lại rồi xác nhận; ứng dụng không tự gửi lại bằng phiên bản mới.
5. **HR** dùng **Mở phân công** để xem nội dung đã gửi hoặc sửa deadline/tính bắt buộc của phân công OPEN. Hủy chỉ áp dụng OPEN tùy chọn; muốn hủy một PEER/SUBORDINATE bắt buộc phải chủ động bỏ bắt buộc trước. **Thay người đánh giá** giữ quan hệ và tính bắt buộc trong một thao tác nguyên tử. Phân công đã hủy được khôi phục cùng người, không tạo dòng trùng. SELF/MANAGER không được thay người.
6. **Nhân viên và quản lý trực tiếp hiện tại** mở **Tổng hợp phản hồi** từ chu kỳ. Nhóm đồng nghiệp/cấp dưới dưới ba người gửi sẽ ẩn thống kê riêng. Chỉ nhận xét do chính bạn viết được hiện lại cho bạn; nhận xét của người khác không xuất hiện. HR có trang dữ liệu gốc riêng; thống kê không cam kết ẩn danh tuyệt đối và mức trung bình chưa phải điểm hiệu suất.

Sau khi đổi quản lý, người quản lý cũ mất quyền xem tổng hợp nhưng vẫn có thể xem/gửi phân công được giao cho chính tài khoản của họ. Quyền không chuyển sang tài khoản liên kết mới.
