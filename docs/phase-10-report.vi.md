# Báo cáo Phase 10 — Kubernetes local và tinh gọn giao diện


Ngày bàn giao: **25/10/2026** (Asia/Bangkok). **Hoàn thành 8/8 task và nghiệm thu CI/local.** Runtime giao diện `559e74a`; tooling triển khai cuối `d4a78bc`. Không triển khai cloud/production hoặc thay dữ liệu người dùng.

## Kết quả nghiệm thu

| Phạm vi | Kết quả và bằng chứng |
| --- | --- |
| Backend/web/build/Docker | [Full CI](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40118504207): **843 backend, 141 web tests / 21 files**, Ruff sạch, mypy 103 source files, lint/typecheck/build và Docker smoke/persistence đạt |
| Kubernetes | [Workflow nghiệm thu cuối](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40118509036): cluster mới, schema validation, migration, browser, failure/recovery/restore, TLS và cleanup |
| Browser thật | 4 role, **32 thao tác gửi từ form**, **18 ảnh ở 1280/390 px**; không runtime exception hoặc tràn ngang trang |
| Numeric workflow | Actual 90/rating 4 → **87.00**; sửa actual 80 → stale → tính lại **80.00**; HR chốt/đóng, dashboard CLOSED average 80.00/sample 1 |
| HTTP/quyền/AI | Đóng sớm 409, private UUID 404, đổi role áp dụng quyền mới, khóa tài khoản kết thúc phiên; fake AI 2 success + quota 503 giữ success cũ; **không Gemini thật** |
| Migration/deployment | Job thành công trước rollout; config migration sai làm Job lỗi và không rollout; Lease/CAS chặn runner thứ hai, kể cả Lease hết hạn khi Job trước vẫn active |
| Dependency outage | PostgreSQL ngắt: API `/health/live` **200**, `/health/ready` **503**; hồi phục và đọc dữ liệu lại thành công |
| Persistence | Thay pod PG, rollout API/web và cluster stop/start giữ fingerprint; đọc lại trước khi chạy migration lần nữa |
| Backup/restore | `pg_dump -Fc` binary-safe, restore DB/PVC/namespace mới, so **toàn bộ cột của 17 bảng ORM và head**; phiên đã cấp trước backup dùng được sau restore |
| TLS | Client verify CA và hostname `insighthr.test`; Secure/HttpOnly/SameSite cookies, CSRF/Origin, CSP nonce/HSTS; body 131.073 byte thường/chunked đều 413 qua ingress HTTPS |
| Compose người dùng | Đã cập nhật UI; API/web/PG healthy, `.env` giữ nguyên, domain fingerprint trước/sau bằng nhau |

[Bằng chứng JSON trong repository](evidence/phase-10-acceptance.json) giữ count/hash/versions và browser report. CI chỉ upload report/ảnh hư cấu, không Secret, password, cookie, cert private key, dump, kubeconfig hoặc browser profile. Artifact CI giữ 14 ngày; các số backend/web/browser là các loại nghiệm thu riêng, không cộng thành một số test tổng.

[Artifact nghiệm thu cuối](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40118509036/artifacts/12569358891) chứa các report và 18 ảnh hư cấu; JSON trong repository giữ bằng chứng sau khi artifact hết hạn. CI cuối dùng kubectl v1.36.1 với server v1.35.5+k3s1.

Local Windows cũng đã chạy browser Edge **156.0.4314.42**, restore và HTTPS có xác minh. Local bổ sung thử dump hỏng bị từ chối, target `insighthr` bị guard từ chối và head tạm sai trả ready503/live200, sau đó khôi phục và so fingerprint bằng nhau. Không mô tả các phép thử local bổ sung này như một bước có sẵn trong workflow CI.

## Đã triển khai 8 task

1. Preflight/tooling: k3d portable có SHA256 kiểm chứng, một server K3s, cổng loopback 13010/13443/16443, kubeconfig riêng; không đổi current-context hay dừng Compose.
2. Manifests: Kustomize HTTP/HTTPS, API/web Deployment, PG StatefulSet/PVC, ClusterIP Services, ConfigMap/Secret theo workload; **8 resource/overlay**, strict server-side validation.
3. Runner: image theo release/source commit, khóa Lease renewable/CAS và active-Job fence, Job Alembic độc lập, timeout/retry hữu hạn, rollout sau migration; giữ secret khi redeploy.
4. Ingress/TLS: chỉ mở web, giữ Next same-origin proxy; HTTPS dùng hostname/CA riêng, không sửa hosts/trust store và không tắt verify. Đợi endpoint được cập nhật trước khi kết luận TLS ready.
5. Storage/recovery: fingerprint toàn cột gồm session/password hashes trong hash/audit/limiter, backup binary, restore namespace mới; không export records hay restore đè nguồn.
6. E2E/failure: form thật xuyên 4 role, numeric/AI scope/revoke, outage/rollout/restart. Harness AI chỉ mount vào namespace acceptance rồi trả API về command keyless bình thường.
7. CI riêng: pin k3d/K3s/PostgreSQL và **kubectl 1.36.1**, có timeout/concurrency, artifact allowlist, cleanup cluster có receipt/UID guard. Pin kubectl vì runner từng cung cấp 1.37.1 ngoài khoảng lệch minor được hỗ trợ với server 1.35; [chính sách chính thức](https://kubernetes.io/releases/version-skew-policy/) là căn cứ lựa chọn.
8. Tài liệu/bàn giao: [hướng dẫn Kubernetes](kubernetes.vi.md), [cài local chi tiết](local-development.vi.md), README Việt rút gọn và trạng thái kiến trúc/kế hoạch. Compose vẫn là cách chạy hằng ngày.

Các lỗi phát hiện trong bài nghiệm thu đã được sửa trước bàn giao: dùng config thực sự không hợp lệ để thử migration failure; probe body trên đúng HTTPS route và đợi API qua ingress trả 401 hợp lệ trước POST; PostgreSQL readiness qua TCP thay vì socket tạm trong initdb; lưu chẩn đoán Job/pod chỉ gồm reason/exit code/exception class; khóa kubectl thay vì dùng công cụ mặc định thay đổi theo runner. Không hạ yêu cầu xác minh TLS hay bỏ failure gate để làm CI xanh.

## Giao diện đã tinh gọn

| Màn hình/chức năng | Thay đổi |
| --- | --- |
| Menu chung | Giữ tab nhóm trên header; menu trái tập trung nhóm đang mở, kèm tổng quan/cá nhân. Các nhóm còn lại truy cập bằng header |
| Dashboard | Bỏ đường dẫn lặp với menu; EMPLOYEE tập trung kết quả cá nhân, bớt chỉ số tổ chức; chi tiết phòng ban mở khi cần |
| Phòng ban/chức danh/KPI/chu kỳ | Form tạo mới thu gọn dưới tiêu đề có thể mở bằng bàn phím; sửa bản ghi tự mở form, lỗi giữ nội dung đã nhập |
| Danh sách nhân viên | Bộ lọc phòng ban nâng cao có thể mở khi cần; tìm mã/tên và trạng thái vẫn trực tiếp |
| Báo cáo hiệu suất | Điểm, trạng thái, việc thiếu và thao tác chính rõ trước; chi tiết KPI/phản hồi của lần tính thu gọn để giảm độ dài trang |
| Mobile/accessibility | Giữ Mở menu, focus ring, summary/details native và vùng bảng cuộn ngang; không ép cả trang tràn ngang |
| README Việt | Tách hướng dẫn chạy hằng ngày và thực hành role khỏi hướng dẫn kỹ thuật, hạn chế lặp lịch sử phase và sửa thông tin migration/AI đã cũ |

Quy tắc chấm điểm, phân quyền, xác nhận thao tác nhạy cảm và nội dung lịch sử giữ nguyên. Phase 10 không thêm API/domain schema; head vẫn **`20261024_0008`**. Bộ web tăng từ 140 lên 141 test nhờ regression menu theo nhóm; browser kiểm chứng thêm các form thu gọn khi thực hiện luồng thật. Không tuyên bố cải thiện p95 backend vì không có thay đổi/đo tải backend mới trong phase này.

## Cấu hình và phạm vi đo

| Thành phần | Bản đã dùng |
| --- | --- |
| Cluster | k3d 5.8.3, K3s v1.35.5-k3s1, một server/không agent |
| Kubectl | Windows và CI pin v1.36.1; schema được API server 1.35 kiểm tra |
| Database | PostgreSQL 16.15-bookworm, digest `d81f7b51697014367236d07ec58b54153fc28f828b72bf247fe5c7487520bcb0` |
| Python test tools | PyYAML 6.0.3, cryptography 50.0.2, websockets 16.0 |
| Application | Một API/web mỗi namespace; same-origin web → Service `api:8000`; UID/GID 10001, read-only root với tmp giới hạn |
| PG storage | UID/fsGroup 999, PVC local-path 2 GiB, PGDATA trong PVC; không emptyDir database |
| Requests/limits | API 100m/192Mi → 1 CPU/512Mi; web 100m/128Mi → 1 CPU/384Mi; PG 100m/192Mi → 1 CPU/512Mi |
| Local host | Windows 11 build 26200, Docker Engine 29.8.1, 8 CPU/4.063.952.896 byte RAM được cấp |

Database acceptance không rỗng: 2 nhân viên, 1 chu kỳ đã đóng, 1 KPI, 2 phản hồi, 1 report/2 revisions và 3 AI attempts; có thêm tài khoản/phiên/audit do test setup. Counts đầy đủ và digest từng bảng trong JSON; fingerprint recovery và restore là hai thời điểm khác nhau vì restore setup tạo thêm một tài khoản test và login trước backup. Không suy diễn mọi snapshot phải có cùng count khi có thao tác setup hợp lệ ở giữa.

Backup local nghiệm thu **60.424 byte**; CI ghi kích thước thực tế trong JSON. Đạt restore dựa trên hash và phiên thực tế, không dựa vào kích thước file. Chỉ thử single-node/fixture nhỏ; không có benchmark Kubernetes tải lớn hoặc HA trong phase này.

## Bảo toàn dữ liệu và trạng thái local

Compose vẫn dùng project/volume `insighthr`, cổng 3000/8000. Không nạp lại seed hoặc gọi Gemini. Fingerprint domain trước/sau cập nhật UI:

`26e60bf40a5fb09f4b2561f671b5f2ae3ca4bab9d82ae785681dd9d995c45cf6`

Phạm vi: user id/email/role/active và toàn bộ cột của organization/cycle/KPI/feedback/report/revision/AI/config, với 13 users/8 employees/3 cycles/9 participants/14 KPI/19 assignments/16 feedback/5 reports/6 revisions/3 AI attempts. Phép so demo này không bao gồm password hash/session/audit; cluster test fingerprint toàn bộ các bảng đó riêng. Không gọi hai phạm vi này là cùng một phép bảo toàn toàn database.

Sau nghiệm thu, cluster test có thể stop để trả tài nguyên, storage còn trong node container; hướng dẫn start/delete có guard nằm trong tài liệu. Bản Compose để người dùng tiếp tục mở **http://localhost:3000**.

## Giới hạn bàn giao

- Kubernetes local một node/PG không HA, chưa production/cloud/public hosting, không tự bật NetworkPolicy chưa kiểm chứng hoặc thêm operator/Redis/Helm.
- Local-path PVC không bảo đảm sống sót khi xóa cluster/volume; restore cần backup ngoài cluster và gây gián đoạn nếu áp dụng vào môi trường thật. Tool restore hiện bảo vệ namespace nghiệm thu cố định.
- TLS được kiểm tra bằng client tin CA riêng, **chưa cài/test browser trust local CA**. Không tự đổi trust store/hosts và dùng hostname riêng để tránh ảnh hưởng localhost/HSTS của Compose.
- Gemini chỉ fake/transport offline trong nghiệm thu; chưa đánh giá chất lượng AI thật hoặc toàn bộ private-generation live. Numeric và saved reads tiếp tục độc lập provider.
- Báo cáo là review trực tiếp và test có thể chạy lại, không phải pentest độc lập hoặc chứng nhận bảo mật.

Đã thực hiện công đoạn cuối trong lộ trình 10 phase của kiến trúc. Các yêu cầu sản phẩm mới hoặc đưa lên Internet cần phạm vi/kế hoạch riêng; không tự coi production đã sẵn sàng hoặc có một Phase 11 mặc định.
