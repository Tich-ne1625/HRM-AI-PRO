# Chạy InsightHR bằng Kubernetes local

**Chạy hằng ngày:** mở Docker Desktop, dùng `docker compose --env-file .env up --build --wait`, rồi vào http://localhost:3000. Kubernetes dành cho học cách triển khai, kiểm tra migration và phục hồi dữ liệu; dùng các trang và nghiệp vụ giống bản Compose.

## Bắt đầu trên Windows

Chạy tại thư mục `hrm-ai`, dùng PowerShell trong VS Code. Docker Desktop phải đang chạy Linux containers/WSL2; cần `kubectl` và Python virtualenv của API. K3d được tải portable vào dự án, không cài toàn máy, không sửa PATH hoặc kubeconfig mặc định.

```powershell
apps/api/.venv/Scripts/python.exe -m pip install -r scripts/kubernetes/requirements.txt
apps/api/.venv/Scripts/python.exe scripts/kubernetes/install_tools.py
apps/api/.venv/Scripts/python.exe scripts/kubernetes/cluster.py create
apps/api/.venv/Scripts/python.exe scripts/kubernetes/validate.py
$release = 'phase10-' + (git rev-parse --short HEAD)
apps/api/.venv/Scripts/python.exe scripts/kubernetes/deploy.py --release $release --build --namespace insighthr-local
```

Mở **http://localhost:13010/login**. Namespace `insighthr-local` là dữ liệu thực hành riêng, chưa có tài khoản người dùng Compose. Không nạp dữ liệu từ `.env` hay database cũ tự động. Chỉ chạy một namespace HTTP được publish tại một thời điểm: không triển khai `insighthr-local` và `insighthr-phase10-acceptance` cùng ingress host `localhost`.

Khi cluster đã có, dùng `cluster.py status` để kiểm tra; dùng lại cùng `$release` nếu chỉ rollout lại image đã build. Khi source thay đổi và đã commit, tạo tag theo commit mới và chạy lại deploy với `--build`. API/migration cùng image; web build trỏ Service `api`, nên chỉ đổi `API_INTERNAL_URL` runtime không thay rewrite đã build.

Trên Linux, thay đường dẫn Python bằng virtualenv Linux hoặc `python` đã cài requirements. Baseline tooling: k3d **5.8.3**, K3s **1.35.5-k3s1**, PostgreSQL **16.15** pin digest; xem [versions.json](../infrastructure/kubernetes/versions.json). Chưa hỗ trợ kiểm chứng macOS/ARM trong bộ lệnh này.

## Tài khoản và demo thực hành

Không có mật khẩu mặc định. Dùng CLI tương tác trong namespace thực hành; mật khẩu nhập vào prompt, không đặt trên command line hoặc chia sẻ screenshot:

```powershell
kubectl --kubeconfig .superpowers/sdd/phase-10/kubeconfig --context k3d-insighthr-phase10 -n insighthr-local exec -it deployment/api -- python -m app.cli.create_admin --email admin.practice@example.com
```

Muốn bộ demo đủ role trong **namespace thực hành mới**, chạy:

```powershell
kubectl --kubeconfig .superpowers/sdd/phase-10/kubeconfig --context k3d-insighthr-phase10 -n insighthr-local exec -it deployment/api -- python -m app.cli.seed_demo
```

Seed in password ngẫu nhiên một lần, giữ dữ liệu khi chạy lại và không gọi Gemini. Xem [bài thực hành theo role](demo.vi.md). Không chạy bộ nghiệm thu tự động vào namespace thực hành; nó dùng namespace acceptance riêng và bootstrap tài khoản hư cấu.

## Những gì runner làm

Runner kiểm tra context/namespace, giữ secret hiện có khi redeploy và khóa namespace bằng Lease. Sau đó chuẩn bị PostgreSQL/PVC, chạy một Job Alembic, đợi thành công rồi rollout API/web. Nếu migration lỗi hoặc có Job migration khác còn active, runner dừng; không tự downgrade hay đặt lại database.

Mỗi namespace có database/Secret/PVC riêng. API và PostgreSQL dùng ClusterIP; ingress chỉ mở web và giữ proxy `/api/v1` cùng origin. Key Gemini không được đưa vào web hay Job migration. Cấu hình mẫu mặc định tắt AI. Không cần copy `.env` vào cluster để chạy.

Kubeconfig, key, dump, browser profile và báo cáo local nằm trong `.superpowers/` bị Git bỏ qua. Không upload cả thư mục đó. Chỉ JSON/ảnh giả được allowlist mới đi vào CI artifacts. Secret Kubernetes vẫn cần bảo vệ ở cluster; base64 không phải mã hóa bảo mật.

## Kiểm tra khi có lỗi

```powershell
apps/api/.venv/Scripts/python.exe scripts/kubernetes/cluster.py status
kubectl --kubeconfig .superpowers/sdd/phase-10/kubeconfig --context k3d-insighthr-phase10 -n insighthr-local get pods,jobs,pvc,ingress
```

- **Pending/ContainerCreating:** kiểm tra CPU/RAM, image pull và PVC. Không tự xóa PVC để sửa startup.
- **Job migration Error:** giữ status/log cho chẩn đoán, sửa config rồi deploy lại; không bỏ qua Job để chạy API. Tránh đưa log chứa connection string/Secret vào báo cáo công khai.
- **API unready, process vẫn sống:** `/health/ready` kiểm tra DB/head; `/health/live` chỉ kiểm tra process. Khôi phục DB hoặc migration; việc restart API liên tục không sửa được thiếu schema.
- **Ingress chưa truy cập ngay sau Ready:** controller có thể cần thêm thời gian cập nhật endpoint; kiểm tra Service/pod và host/port đúng. Runner TLS đợi endpoint với timeout, vẫn xác minh certificate ở mỗi lần thử.
- **Thiếu RAM khi chạy song song Compose:** kiểm tra `docker stats`; người dùng quyết định dừng bớt stack hoặc cấp thêm RAM. Tool không tự dừng Compose hoặc đổi thiết lập WSL2/Docker Desktop.

Máy nghiệm thu Windows đã chạy được Compose cùng cluster với Docker được cấp khoảng **3,8 GiB RAM**. Đây là quan sát một máy/dữ liệu giả nhỏ, không phải bảo đảm cho mọi máy hoặc workload; lúc build cần thêm tài nguyên host.

## Backup và phục hồi

Lệnh `backup.py` hiện phục vụ **namespace nghiệm thu cố định**, không nhận một database tùy ý để ghi đè. `pg_dump -Fc` được truyền bằng binary stream trong Python, tránh pipeline PowerShell đổi bytes thành text. File được lưu ở `.superpowers/sdd/phase-10/backups/`; nó chứa dữ liệu nhạy cảm dù là bản test, không commit/upload.

```powershell
apps/api/.venv/Scripts/python.exe scripts/kubernetes/backup.py backup
apps/api/.venv/Scripts/python.exe scripts/kubernetes/backup.py restore-test --release $release
```

`restore-test` yêu cầu namespace `insighthr-phase10-restore` chưa tồn tại. Nó tạo DB/PVC mới, giữ signing key để kiểm tra session cũ sau restore, so toàn bộ bảng/cột bằng hash rồi kiểm tra phiên thực tế. Không restore đè nguồn. Không chạy lại restore-test trên namespace đã chứa dữ liệu; đọc kết quả lần trước hoặc dùng một cluster test mới có chủ đích.

PG pod replacement giữ cùng PVC; cluster **stop/start** giữ storage của node container. **Xóa cluster hoặc volume có thể làm mất local-path data**. Backup file nằm ngoài cluster cũng cần được giữ và thử restore; PVC không thay thế backup. Bộ công cụ không tự migration dữ liệu Compose sang Kubernetes.

## Chạy bộ nghiệm thu riêng

Chỉ làm trong cluster mới dành cho test, không có namespace thực hành đang publish cùng host. Các bước tạo cluster/build/validate giống phần đầu nhưng deploy namespace mặc định `insighthr-phase10-acceptance`:

```powershell
apps/api/.venv/Scripts/python.exe scripts/kubernetes/deploy.py --release $release --build
apps/api/.venv/Scripts/python.exe scripts/kubernetes/acceptance.py --with-offline-provider
apps/api/.venv/Scripts/python.exe scripts/kubernetes/check_failures.py --release $release
apps/api/.venv/Scripts/python.exe scripts/kubernetes/check_recovery.py --release $release
apps/api/.venv/Scripts/python.exe scripts/kubernetes/check_http.py --release $release
apps/api/.venv/Scripts/python.exe scripts/kubernetes/status_report.py
```

Browser nhập/submit form thật cho 4 role, không chạy API fixture rồi gọi đó là UI test. Provider giả được mount chỉ trong namespace acceptance; test xong trả API về command keyless bình thường. Các tư vấn lưu có nhãn OFFLINE. Numeric workflow và quyền giữ nguyên, không gọi Gemini thật.

Recovery thử database ngắt, thay PG pod, rollout ứng dụng, cluster stop/start và restore mới. Failure test cố tình tạo một Job lỗi, nên thấy một pod migration Error sau test là dự kiến; report phải xác nhận runner dừng trước rollout. Không dùng script lỗi này trên namespace thực hành.

TLS test đổi **namespace acceptance** sang production config để kiểm tra secure-cookie/HSTS; dùng hostname riêng `insighthr.test:13443` và CA riêng trong client. Script resolve về loopback với Host/SNI đúng, không tắt verify, sửa hosts hoặc cài CA toàn máy. `localhost:13010` không còn là địa chỉ để thực hành namespace đó sau khi chuyển HTTPS. Nghiệm thu TLS bằng HTTP client có verify; chưa tuyên bố browser đã tin local CA.

Workflow **Phase 10 Kubernetes acceptance** chạy thủ công trên GitHub, tạo cluster disposable rồi upload JSON và ảnh giả, giữ 14 ngày. Báo cáo/giới hạn nằm ở [báo cáo Phase 10](phase-10-report.vi.md).

## Dừng và dọn cluster

```powershell
apps/api/.venv/Scripts/python.exe scripts/kubernetes/cluster.py stop
apps/api/.venv/Scripts/python.exe scripts/kubernetes/cluster.py start
```

Dùng stop để giải phóng tài nguyên khi không thực hành, dữ liệu vẫn nằm trong node container. Nếu muốn xóa hoàn toàn **cluster test và dữ liệu của nó**, kiểm tra backup trước rồi tự chạy:

```powershell
apps/api/.venv/Scripts/python.exe scripts/kubernetes/cluster.py delete --confirm-delete insighthr-phase10
```

Cluster cần đang chạy để xác minh identity trước khi xóa; nếu đã stop, chạy start trước. Lệnh không đụng project Compose `insighthr`, Docker context hoặc kubeconfig mặc định. Không dùng `docker system prune` hay xóa các volume khác để dọn thử nghiệm.

## Giới hạn triển khai

Đây là một node local với một PostgreSQL, chưa HA, autoscaling, cloud hosting hay hệ thống backup production. API nghiệp vụ/giao diện không chứa khái niệm Kubernetes. Người dùng văn phòng tiếp tục dùng header, menu theo role và các trang đánh giá hiện có. Các quyết định TLS/secret/backup thực tế khi public Internet cần đánh giá riêng theo môi trường đích.
