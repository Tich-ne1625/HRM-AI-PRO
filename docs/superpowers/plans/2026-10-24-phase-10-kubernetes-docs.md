# Kế hoạch Phase 10 — Kubernetes và tài liệu triển khai

Ngày lập: **24/10/2026**, nghiệm thu **25/10/2026**. Trạng thái: **đã triển khai 8/8 task**; [báo cáo](../../phase-10-report.vi.md) ghi từng gate, CI và giới hạn. Runtime UI `559e74a`, tooling cuối `d4a78bc`. Runtime đầu vào `9821e82`, docs `845676a`; 843 backend/140 web tests là baseline Phase 9, không phải kết quả Kubernetes.

Đọc [hợp đồng Phase 10](../../phase-10-contract.md), [báo cáo Phase 9](../../phase-9-report.vi.md), [kiến trúc](../../architecture.md), Dockerfile/Compose, Next rewrite và health/config hiện có trước khi thực hiện. Giữ nguyên `.env`, dữ liệu và stack Compose của người dùng; không gọi Gemini thật.

## Task 1 — Preflight và đóng băng topology/version

**Mục đích:** chứng minh môi trường có thể chạy một cluster local nhỏ, chọn/pin công cụ đã kiểm tra.

**Tệp dự kiến:** `infrastructure/kubernetes/README.md`, cluster config và file version matrix; khung `scripts/kubernetes/`.

- Kiểm tra Docker/WSL2, kubectl client, k3d, cổng 13010/13443, CPU/RAM/disk thực tế. Lúc lập kế hoạch chỉ thấy kubectl, chưa thấy k3d/kind; không coi Docker Desktop là đã bật Kubernetes.
- Kiểm tra tài liệu chính thức; pin k3d/K3s, ingress và schema tool tương thích, image digest cần dùng. Không cài Docker Desktop Kubernetes đồng thời chỉ để chạy k3d.
- Chọn cluster `insighthr-phase10`, namespace `insighthr-local` và namespace acceptance riêng; bind cổng ra loopback khi cấu hình cho phép và kiểm tra thực tế. Một server, không agent, không mở API/PG ra host.
- Chốt inventory env/secret theo workload. Đảm bảo web image build trỏ `http://api:8000`; k8s API Service tên `api`. Kiểm tra hostname public origin/port của hai overlay.
- Đặt ngân sách request/limit ban đầu vừa với cluster nhỏ; đo lại khi chạy. Nếu Docker khoảng 4 GiB không đủ cho cluster cộng Compose, nêu nhu cầu thực tế, không tự tắt Compose/chỉnh RAM hệ thống.

**Gate:** version/topology/env matrix có lý do, preflight read-only rõ thiếu gì; không thay context/dữ liệu hiện có. Bản kế hoạch được cập nhật nếu bằng chứng buộc đổi topology trước Task 2.

## Task 2 — Base manifests, secret boundary và kiểm tra tĩnh

**Phụ thuộc:** Task 1. **Tệp dự kiến:** `infrastructure/kubernetes/base/`, `overlays/local-http/`, `overlays/local-https/`, schema-validation script/test.

- Namespace/labels riêng, Services ClusterIP, API/web Deployments một replica, PostgreSQL StatefulSet một replica và PVC; tên Service `api` giữ rewrite build hợp lệ.
- ConfigMap/Secret reference tường minh theo nhu cầu: web chỉ nonsecret; migrate không có Gemini key; API keyless mặc định; không copy `.env` vào manifest hoặc build context.
- Security context API/web nonroot 10001, capabilities drop, seccomp, không service-account token; xác minh thư mục ghi/cache trước readOnlyRootFilesystem. PostgreSQL UID/fsGroup theo image, volume có quyền đúng.
- CPU/memory requests/limits, emptyDir có giới hạn nếu cần; storage request và reclaim policy rõ. Không dùng quota/limit khiến Job/PG không thể khởi động rồi gọi đó là hardening.
- API startup/liveness dùng health/live; readiness dùng health/ready. Web dùng HTTP /login phù hợp startup; không dùng DB làm liveness. PG có probe hữu hạn hợp lý.
- Render/schema check hai overlay, phát hiện secret giá trị thật, image placeholder/latest và sai URL build. Kiểm tra manifest behavior có ý nghĩa, không tạo test chỉ so toàn bộ YAML snapshot.

**Gate:** render/schema đạt, không có secret thật/hostPath người dùng/mount Docker socket; resource inventory và khác biệt hai overlay được review trực tiếp.

## Task 3 — Runner triển khai, migration Job và release repeatability

**Phụ thuộc:** Task 2. **Tệp dự kiến:** `scripts/kubernetes/deploy.py`, `preflight.py`, tài nguyên Job riêng và helper PowerShell mỏng khi cần.

- Build API/web một lần theo commit, import image vào đúng k3d cluster; không dùng tag `insighthr-*:local` của Compose để tránh ghi đè bản người dùng. Ghi digest/source revision.
- Mọi kubectl truyền context/namespace; preflight kiểm tra identity/ownership/DB name. Không đổi current-context; từ chối target lạ và thao tác xóa không có guard.
- Tạo secret ngẫu nhiên trong memory hoặc input/file ngoài Git, stdin không echo; đảm bảo password raw/encoded tương đương. Không log `kubectl ... --from-literal=<secret>` hoặc upload rendered Secret. Cho phép giữ secret qua redeploy, không đổi signing key mỗi lần chạy.
- Apply DB/config → đợi PG → tạo Job Alembic với release/run ID → đợi Complete/deadline → rollout API/web → ready. Không nhét Job vào bundle apply mỗi lần; không Alembic trong từng replica.
- Serialize deployment cùng namespace bằng Lease có holder/run ID, renewal và resourceVersion CAS; kiểm tra Job migration active trước khi tạo Job mới kể cả Lease cũ hết hạn. Workload không được quyền quản lý Lease. Kiểm tra hai runner đồng thời và runner chết/mất Lease; CI concurrency chỉ bổ sung, không thay guard. Giữ/sanitize log trước TTL cleanup.
- Test migration failure, timeout, head mismatch, wrong credentials, apply lại cùng release và rollback image tương thích. Không downgrade DB tự động; nếu runtime guard nhỏ cần sửa, bổ sung regression trước khi tiếp tục.

**Gate:** fresh namespace lên được head 0008 và healthy; lỗi migration dừng rollout; redeploy không reset secret/domain hoặc chạy nhiều migration đồng thời; command provenance có thể xem lại.

## Task 4 — Ingress HTTP/TLS và ranh giới trình duyệt

**Phụ thuộc:** Task 3. **Tệp dự kiến:** overlays ingress/TLS references, `scripts/kubernetes/check_http.py`, tài liệu certificate local.

- Dùng ingress controller/version đã pin; route `/` về web, không route trực tiếp API/health/admin riêng. Kiểm tra `/api/v1/*` đi qua Next và đúng upstream Service.
- HTTP local APP_ENV=test, exact localhost origin, insecure-cookie chỉ trong profile này. Kiểm tra login/refresh/logout, CSRF/Origin sai và 413 body thường/chunked qua ingress + web.
- HTTPS profile dùng production config và COOKIE_SECURE=true; host `insighthr.test:13443`, CA/cert có SAN đúng host, trust bundle và loopback resolution riêng cho client, giữ đúng Host/SNI. Tách host khỏi localhost để HSTS không tác động Compose HTTP. Không sửa validator, tắt TLS verify, tự chỉnh hosts hoặc cài CA toàn máy.
- Kiểm tra cookie Secure/HttpOnly/SameSite, CSRF cookie behavior, nonce CSP/no-store/HSTS, redirect/origin có cổng đúng. Liveness probe bên trong vẫn không phụ thuộc external TLS/Google.
- Xác nhận ingress timeout/body handling phù hợp API 128 KiB/Gemini deadline; không để ingress trả response lớn/HTML lỗi làm client mất xử lý mà không ghi nhận giới hạn.

**Gate:** truy cập thực qua hai public origin đạt, HTTPS chain/hostname được verify; CSRF/origin không bị nới và secret không tới browser. Phân biệt browser HTTP acceptance với HTTPS API-client acceptance nếu chưa cấu hình browser trust riêng.

## Task 5 — PostgreSQL persistence, backup và restore độc lập

**Phụ thuộc:** Task 3–4. **Tệp dự kiến:** `scripts/kubernetes/backup.py`, `restore_test.py`, fingerprint helper, `docs/kubernetes.vi.md` phần phục hồi.

- Seed fictional data explicit trong namespace acceptance; không chạy seed startup/production hoặc seed vào Compose. Phải có report/revision finalized và AI fixture có nhãn, không chỉ các bảng trống.
- Fingerprint mọi cột/bảng liên quan, bao gồm user/password hashes/session/audit trong hash nhưng không in records; ghi rõ limiter/head nằm trong/ngoài từng phép so sánh. Tạm ngưng background traffic trước snapshot để tránh login/audit thay đổi hợp lệ.
- Rollout API/web, thay PG pod trên cùng PVC, đợi Ready rồi đọc **trước migration chạy lại**; dữ liệu/phiên/history giữ nguyên. Cluster stop/start không delete được thử riêng.
- Backup pg_dump custom bằng binary stream an toàn trên Windows/Linux; lưu ngoài cluster/Git, không ra log/artifact. Restore namespace/DB/PVC mới có guard; không overwrite DB nguồn.
- So fingerprint/counts/head và xác nhận đăng nhập/báo cáo sau restore. Có đường xử lý wrong DB, dump hỏng, restore fail mà không sửa nguồn. Phân biệt backup logical DB với snapshot PV và xóa cluster.

**Gate:** pod replacement + cluster restart + restore độc lập đều có evidence. Dump tạo thành công chưa đủ; thử restore mới đóng task. Không cleanup nguồn khi restore chưa đạt.

## Task 6 — E2E qua ingress và test failure/recovery

**Phụ thuộc:** Task 4–5. **Tệp dự kiến:** `scripts/kubernetes/acceptance.py`, browser harness/helper, fixture test-only nếu cần.

- Kế thừa assertions Phase 9 nhưng thay transport/target guards có chủ đích; scripts hardcode Compose/project/cổng cũ không được chạy vào cluster nguyên trạng.
- Browser form ADMIN → HR tạo tổ chức/kỳ/KPI → reviewer submit → manager calculate/recalculate → HR finalize/close; score/stale/409/dashboard đúng. Role demotion/inactive và private UUID vẫn chặn.
- UI giữ top tabs/menu trái/context tabs, desktop/mobile, không thêm Kubernetes/config vào trải nghiệm nhân viên. Không tính API fixture writes thành UI interactions.
- Saved AI PUBLIC/HR_PRIVATE đọc đúng với Gemini disabled; nếu test nút tạo AI thì chỉ bind/mount harness vào namespace test được guard, không đưa fake runtime flag vào image/app. Không live Gemini.
- PG tạm unavailable: readiness fail nhưng liveness không restart vì DB; hồi phục xong kết quả/phiên còn đúng. API/web rollout không làm nhân bản domain/audit. Nếu kiểm tra hai replica, reserve/login/refresh phải chia sẻ PG và báo cáo đúng phạm vi đã thử; một replica là gate bắt buộc ban đầu.

**Gate:** E2E thực qua ingress, failure/recovery và UX checks đạt với dữ liệu giả; sanitized JSON/screens có commit/target/actual counts. Không dùng số test Phase 9 thay cho nghiệm thu cluster.

## Task 7 — CI cluster riêng và tái lập trên máy sạch

**Phụ thuộc:** Task 6. **Tệp dự kiến:** `.github/workflows/phase10-kubernetes-acceptance.yml`, validation step phù hợp trong CI hiện có.

- Workflow manual hoặc path-filtered có timeout/concurrency; pin tool/image versions, build/import đúng tag, tạo cluster disposable mới. Không cần registry credential hoặc kubeconfig production.
- Chạy render/schema, server-side dry-run khi phù hợp, Job/rollout, ingress/TLS, E2E, restart/restore. Gate restore không bị bỏ qua để làm CI xanh.
- Artifacts chỉ report/ảnh hư cấu, phiên bản/resource/status/log đã lọc; loại Secret, cert key, kubeconfig, dump, cookie/password/browser profile. Không `kubectl get secret -o yaml` hoặc `kubectl describe` env nhạy cảm vào report.
- Cleanup trong finally/always chỉ tài nguyên cluster/namespace được tạo bởi run có ownership proof; lưu evidence trước cleanup. Không prune Docker hoặc xóa cluster/volume khác.
- Full backend/web/quality/build khi runtime code thay đổi; chạy integration tuần tự trên mỗi DB `_test`. Với deployment-only diff, dùng CI nền và cluster gates phù hợp, không gọi số regression cũ là test cluster mới.
- Chạy lại theo hướng dẫn trên Windows/WSL2; ghi khác biệt shell/path/binary backup và tài nguyên tối thiểu quan sát được. Linux CI không thay cho bằng chứng người dùng Windows.

**Gate:** workflow xanh tại đúng commit và artifacts có thể mở; hướng dẫn chạy từ repo sạch, tạo/khôi phục/xóa đúng target đã được đối chiếu thực tế.

## Task 8 — Tổng nghiệm thu, tài liệu và bàn giao

**Phụ thuộc:** Task 1–7. **Tệp dự kiến:** `docs/phase-10-report.vi.md`, `docs/kubernetes.vi.md`, README Việt/Anh, architecture/deployment/database/API khi thực sự có tác động.

- Báo cáo exact runtime/docs commit, CI links, tool/image/K3s versions, migration head, resources, actual counts, phạm vi fingerprints, backup/restore/TLS verification và giới hạn.
- Hướng dẫn ngắn: lúc nào dùng Compose, lúc nào dùng Kubernetes; preflight → create → secrets → migrate → deploy → demo → test → backup/restore → cleanup. Không yêu cầu người mới dùng K8s để chạy đồ án hằng ngày.
- Ghi limitation: local single-node/PG, local-path lifecycle, downtime khi restore, chưa HA/production/cloud; secret/TLS/backup production cần kế hoạch riêng. Không tuyên bố security/compliance certification.
- Xác nhận Compose hiện có vẫn chạy, dữ liệu không thay đổi, `.env` không bị sửa; không tự di chuyển dữ liệu hoặc bật Gemini. Chỉ đánh dấu phase hoàn tất khi toàn bộ gate có bằng chứng.
- Commit/push thay đổi đã kiểm tra; tách báo cáo planning và report kết quả. Không viết số test hoặc thời gian hoàn thành dự kiến thành kết quả thực tế.

**Gate bàn giao:** người dùng tái lập được cluster local và restore thử, bản Compose còn nguyên; toàn bộ 10 phase trong kiến trúc có trạng thái đúng. Nhu cầu sản phẩm/production sau đó được đánh giá riêng, không tự phát sinh một Phase 11 đã được “duyệt”.

## Phụ thuộc và cách triển khai từng phần

`1 → 2 → 3 → 4 → 5 → 6 → 7 → 8`. Mỗi task đóng bằng gate trước khi chuyển bước; lỗi hạ tầng phải được tái hiện/giải quyết trong target disposable. Các đường dẫn ở từng task ghi phạm vi dự kiến lúc lập kế hoạch; triển khai thực tế dùng `cluster.py` cho preflight/create, `validate.py` cho strict server schema và các runner trong `scripts/kubernetes/`. Lệnh đã thử nằm trong [hướng dẫn Kubernetes](../../kubernetes.vi.md). UI/README được tinh gọn theo yêu cầu bổ sung của người dùng; chi tiết kiểm chứng trong báo cáo.

Nguồn chính thức và quyết định topology/security nằm trong [hợp đồng](../../phase-10-contract.md#nguồn-kỹ-thuật). Không cần thêm app/plugin ngoài để lập hoặc thực hiện kế hoạch này.
