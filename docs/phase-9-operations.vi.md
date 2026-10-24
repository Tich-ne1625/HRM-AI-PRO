# Vận hành và chạy lại nghiệm thu Phase 9

## Chạy dự án thường ngày

Tại thư mục `hrm-ai`, giữ Docker Desktop đang mở và chạy:

```powershell
docker compose --env-file .env up --build --wait
```

Mở http://localhost:3000/login. Migration `20261024_0008` thêm bảng hạn mức đăng nhập; không đặt lại tài khoản, KPI, điểm hoặc tư vấn đã lưu. Không cần nạp lại demo và không cần thay Gemini key. Header và menu theo role tiếp tục dùng bố cục hiện tại.

## Cấu hình bảo mật

Các biến có mặc định trong `.env.example`; không bắt buộc thêm vào `.env` đang dùng:

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `API_MAX_REQUEST_BYTES` | `131072` | Tối đa 128 KiB body API thực tế, kể cả chunked; vượt ngưỡng trả 413 trước xử lý nghiệp vụ |
| `AUTH_LOGIN_MAX_ATTEMPTS` | `10` | Số lượt đăng nhập cho một email chuẩn hóa trong cửa sổ; tính cả thành công và thất bại |
| `AUTH_LOGIN_WINDOW_SECONDS` | `300` | Cửa sổ 5 phút theo thời gian PostgreSQL |

Vượt hạn mức trả 429 và `Retry-After`; chờ đủ thời gian rồi thử lại. Database lỗi trả 503, không bỏ qua limiter. Bảng lưu HMAC của email bằng signing key, không lưu email thô. Đây là hạn mức theo email, có thể gây chờ tạm thời cho chủ tài khoản; chưa phải giải pháp chống DDoS hay thay thế rate limit tại ingress. Đổi signing key cũng đổi bucket; không dùng việc đổi key để giải quyết một tài khoản bị chờ.

Dọn bucket **đã hết hạn**, mỗi lượt tối đa 1.000 dòng mặc định, không xóa session hoặc dữ liệu nghiệp vụ:

```powershell
docker compose --env-file .env exec api python -m app.cli.cleanup_login_limits --limit 1000
```

Lệnh không chạy ngầm; người vận hành có thể lên lịch phù hợp. Các worker chia sẻ PostgreSQL nên dùng chung hạn mức.

Web dùng CSP nonce cho script trên HTML động; API và lỗi có `no-store`, `nosniff`, chống nhúng iframe và referrer policy. `unsafe-eval` chỉ ở development. Inline style vẫn được cho phép để tương thích layout/runtime. HSTS chỉ bật khi `APP_ENV=production` và `WEB_ORIGIN` là HTTPS; local HTTP vẫn chạy. API tiếp tục kiểm tra quyền, Origin và CSRF; header không thay thế các kiểm tra đó.

Đổi role áp dụng quyền mới ở request tiếp theo; tài khoản vẫn có thể đăng nhập với role mới. Vô hiệu hóa tài khoản thu hồi mọi family. Giao diện bỏ response phiên cũ, cache và form khi nhận diện thay đổi; request 401/403 kiểm tra lại danh tính. Request đọc đã bắt đầu có snapshot semantics; không thể thu hồi nội dung người dùng đã tải hay chụp trước đó.

## API đọc audit

`GET /api/v1/audit-logs?page=1&page_size=20&action=...` chỉ dành cho ADMIN/HR. ADMIN đọc sự kiện tài khoản/cấu hình; HR đọc sự kiện HR-domain theo [allowlist](phase-9-security-matrix.md). Action ngoài phạm vi hoặc không tồn tại trả danh sách rỗng. EMPLOYEE/MANAGER nhận 403. DTO chỉ có `id`, `action`, `entity_type`, `entity_id`, `created_at`; không có actor, request ID hay metadata. Chưa có màn hình audit riêng hoặc export trong Phase 9.

## Nghiệm thu cô lập

Chạy từ repository root. Đây là **stack dữ liệu giả riêng**, không dùng project `insighthr` đang chạy hằng ngày. Yêu cầu Python có `websockets` và Edge/Chrome; API virtualenv của dự án đã có transport này. Có thể đặt `PHASE9_BROWSER` thành đường dẫn Chrome nếu cần.

```powershell
docker compose --project-name insighthr-phase9-acceptance --env-file infrastructure/docker/phase9.env.example -f docker-compose.yml -f infrastructure/docker/phase9-test.compose.yml up --build --detach --wait
apps/api/.venv/Scripts/python.exe scripts/phase9_browser.py
apps/api/.venv/Scripts/python.exe scripts/phase9_persistence.py
apps/api/.venv/Scripts/python.exe scripts/phase9_http.py
```

Script browser yêu cầu database mới, bootstrap bằng password ngẫu nhiên qua stdin rồi nhập/submit form thật cho 4 role. Provider giả được bind mount từ `tests/acceptance/phase9_app.py`, chỉ chấp nhận APP_ENV=test, project và database cố định. Nó không được đóng gói trong runtime image. Hai lần đầu trả nội dung có nhãn OFFLINE, lần thứ ba lỗi quota để kiểm tra giữ success cũ. Không có lời gọi Google hoặc đánh giá chất lượng Gemini thật.

Script persistence fingerprint toàn bộ cột/bảng ORM có trước Phase 9, bao gồm user/session/audit, rồi downgrade 0007 → upgrade 0008 và chỉ restart PostgreSQL. Đọc lại trước khi chạy migrate container khác; chỉ ghi count/digest, không xuất bản ghi. `auth_login_limits` được loại khỏi phép so sánh vì đây chính là bảng mới bị xóa/tạo trong roundtrip. HTTP probe kiểm tra 131.073 byte cả Content-Length và chunked qua web proxy.

Artifacts nằm trong `.superpowers/sdd/phase-9/` bị Git bỏ qua. Workflow **Phase 9 isolated acceptance** có thể chạy thủ công trong GitHub Actions và upload report/ảnh giả đã làm sạch; không upload browser profile, password hay cookie. Sau khi xem kết quả, chỉ xóa stack thử nghiệm bằng đúng project/config này:

```powershell
docker compose --project-name insighthr-phase9-acceptance --env-file infrastructure/docker/phase9.env.example -f docker-compose.yml -f infrastructure/docker/phase9-test.compose.yml down --volumes
```

Lệnh trên xóa **volume dữ liệu giả Phase 9**, vì vậy chạy lại sẽ bắt đầu sạch. Không đổi tên project thành `insighthr`, không dùng `docker system prune` hoặc xóa volume demo.

## Race và baseline tải

Tại root, đặt `TEST_DATABASE_URL` tới database disposable có tên kết thúc `_test`, dùng API virtualenv chạy `scripts/phase9_races.py`. Script chạy tuần tự 5 lượt, mỗi lượt 10 file kiểm tra race/fault. Không chạy các integration khác cùng database trong thời gian này.

Benchmark chỉ nhận database có tên **`phase9_benchmark_test`**. Tạo database rỗng đó trong PostgreSQL test, đặt `TEST_DATABASE_URL`, rồi chạy:

```powershell
apps/api/.venv/Scripts/python.exe scripts/phase9_benchmark.py --seed --seed-only
apps/api/.venv/Scripts/python.exe scripts/phase9_benchmark.py --seconds 60 --clients 5
```

Fixture dùng ORM create_all và dữ liệu hư cấu; đây không phải kiểm tra migration. Nó tạo 1.000 nhân viên, 20 phòng, 2 kỳ, 1.998 người-kỳ, 9.990 KPI, 5.994 phản hồi và 3.996 tư vấn giả. Setup/password hashing/warm-up nằm ngoài giai đoạn đo; điểm được tính bằng engine thật và evidence collector. Đo API trong process qua TestClient với PostgreSQL thật, không bao gồm proxy, mạng hoặc browser. Kiểm tra count/scope/điểm và SQL count cùng latency; không suy diễn thành SLA production. Không chạy build hoặc race nặng cùng lúc với lượt đo.

Xem [báo cáo nghiệm thu](phase-9-report.vi.md) để biết commit, kết quả thực tế và giới hạn.
