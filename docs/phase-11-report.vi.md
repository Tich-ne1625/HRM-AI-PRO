# Báo cáo Phase 11 — Kế hoạch cá nhân và công việc có nghiệm thu

Ngày **25/11/2026**. Trạng thái: **hoàn thành nghiệm thu local, Task 0–6 đạt gate**. Không đồng nghĩa đã hoàn thành toàn bộ quản lý hiệu suất liên tục hoặc nghiệm thu production/cloud.

Hướng dẫn thao tác: [Phase 11 theo từng role](phase-11-huong-dan.vi.md). Đối chiếu [contract](phase-11-contract.vi.md), [kế hoạch](superpowers/plans/2026-11-25-phase-11-work-management.md), [đề xuất tổng thể](nang-cap-quan-ly-hieu-suat-lien-tuc.vi.md).

## Kết quả nghiệp vụ

Luồng đã chạy được từ đầu: **HR lập kỳ và danh sách → quản lý lập kế hoạch → nhân viên yêu cầu làm rõ → quản lý sửa thành revision mới, gửi và duyệt → nhân viên xác nhận đúng revision → HR kích hoạt khi đủ điều kiện → quản lý giao việc → nhân viên cập nhật/vướng mắc/nộp → quản lý trả lại hoặc nghiệm thu**.

| Role | Phạm vi thực hiện |
| --- | --- |
| HR | Tạo/điều phối kỳ, theo dõi kế hoạch và xác nhận, kích hoạt; xem tổng hợp tiến trình, không nghiệm thu hay xem bằng chứng công việc riêng thay quản lý |
| MANAGER | Lập và duyệt kế hoạch của nhân viên trực tiếp, giao việc, hỗ trợ, trả lại/nghiệm thu; không tự duyệt hiệu suất của mình |
| EMPLOYEE | Đọc/làm rõ/xác nhận kế hoạch, đề xuất và sửa việc chưa được giao, cập nhật/báo vướng, nộp/nộp lại bằng chứng của mình |
| ADMIN | Quản trị tài khoản; không hiện menu hoặc có quyền đọc công việc |

Kế hoạch snapshot KPI/baseline/target/trọng số/cách đo/nguồn/chuẩn nghiệm thu. Trọng số tổng đúng 100%; tỷ lệ phải có tử/mẫu, milestone có tỷ trọng tổng 100%. Revision cũ được giữ nguyên; sửa kế hoạch bỏ xác nhận cũ. Lịch được giữ cố định từ khi có kế hoạch đầu tiên.

Công việc có nguồn hồ sơ duy nhất trong kế hoạch, mục tiêu liên quan hoặc nhãn không đo KPI, deadline, mức ưu tiên, một người thực hiện và quản lý duyệt. Đề xuất chưa giao được sửa; sau giao không đổi ngầm deadline, owner hay tiêu chuẩn. Bằng chứng text/URL được lưu thành từng lần nộp bất biến. Cờ vướng mắc không làm mất trạng thái thực hiện. Hủy/mở lại phải có lý do và giữ lịch sử.

**ACCEPTED chưa biến thành actual hoặc điểm.** Đường nhập actual/phân bổ/tính lại/chốt/đóng cũ bị chặn với CONTINUOUS bằng `managed_by_workflow`. Kỳ LEGACY tiếp tục vận hành như trước. Khóa tài khoản bảo mật vẫn được phép; thao tác công việc dừng và hiển thị cần HR kiểm tra.

## Giao diện và thông báo

- Nhân viên có **Công việc của tôi**, quản lý có **Điều phối nhóm**, HR đi từ chu kỳ tới theo dõi kế hoạch. ADMIN không có nhóm Công việc & mục tiêu.
- Chi tiết dùng cửa sổ nổi có X/Escape, focus và bốn tab cố định: **Nội dung / Tiến trình & bằng chứng / Trao đổi / Lịch sử**. Không cần Back để đóng.
- Quyết định gửi/duyệt/xác nhận/nghiệm thu có bước xem lại. Bản nhập giữ khi đổi tab, lỗi mạng hoặc xung đột version; draft của các form được theo dõi riêng. Đóng khi chưa lưu phải xác nhận bỏ bản nhập.
- Dùng lại một SSE connection/tab; có thông báo đúng người nhận, deep link có scope, đồng bộ trạng thái và tình trạng kế hoạch cho HR. Đọc thông báo không hoàn thành hành động.
- Tổng quan của CONTINUOUS hiện số kế hoạch đã nhận, việc mở/chờ nghiệm thu/bị vướng/đã nghiệm thu; không hiển thị biểu đồ điểm giả hoặc yêu cầu nhập actual bằng luồng cũ.

## Bằng chứng kiểm thử

**952 ca backend khác nhau đã được chạy qua các nhóm**; không cộng trùng các lượt kiểm tra lại:

| Nhóm | Số ca |
| --- | ---: |
| Integration cũ trước nhóm collaboration | 156 |
| Integration cũ từ collaboration trở đi | 411 |
| Integration mới Phase 11 (work management + demo + upgrade) | 20 |
| Unit, gồm 12 ca quy tắc mới | 359 |
| Smoke contract Docker/CI | 6 |
| **Tổng duy nhất** | **952** |

Hai lượt chạy rộng bị ngắt bởi môi trường: một lần Alembic không đọc được revision trong lúc phát triển, một lần Argon2 không cấp phát đủ bộ nhớ. Các nhóm/case liên quan đã được chạy lại; 32 ca Phase 11 qua trọn nhóm. Không ghi nhận còn lỗi nghiệp vụ chưa xử lý trong các gate đã chạy. Inventory local nằm ở `.superpowers/phase11/test-inventory.json` và `nodes.json`.

Kiểm tra gồm: quyền/scope/CSRF, đúng revision khi xác nhận/kích hoạt, gửi lặp không trùng dữ liệu, conflict UUID, hai quyết định đồng thời chỉ một có hiệu lực, lỗi audit hoàn tác trạng thái/event/thông báo, account bị khóa, chặn đường API cũ và đổi tổ chức khi kỳ mới đang chạy. Có fresh migration, metadata parity, trigger bất biến, constraint trực tiếp và fingerprint upgrade trên fixture LEGACY.

**193/193 ca web thuộc 27 file đã qua trọn bộ trên bộ dependency cuối.** Có lượt trước bị timeout khi máy chịu tải; sau giảm tải đã kiểm tra lại file liên quan và cả suite. Các ca mới kiểm tra role, thông báo/deep link, filter, draft qua tab/lỗi, xác nhận revision, bàn phím, trọng số kế hoạch và sửa đề xuất chưa giao.

Ruff sạch; mypy sạch **126 source Python**; ESLint và TypeScript sạch. Docker API/web build production thành công. SHA-256 toàn bộ 126 source API trong ảnh đã triển khai khớp source local. Các kiểm chứng này là local; chưa gán kết quả CI từ xa của commit mới.

Kiểm tra dependency phát hiện 10 advisory của bộ thư viện cũ. Đã cập nhật **Next.js / eslint-config-next 16.4.6**, **Zod 4.6.7** và các bản sửa dependency gián tiếp trong dải tương thích; không dùng `audit fix --force`. `npm audit --json` sau cập nhật trả **0 vulnerability** ở mọi mức, gồm cả dependency phát triển. Đây là xử lý cảnh báo xác định được trong lần nghiệm thu, không phải tuyên bố đã kiểm toán toàn bộ ứng dụng. [Advisory từ Next.js](https://github.com/vercel/next.js/security/advisories/GHSA-673q-mjm6-r5xr); bằng chứng trước/sau ở `.superpowers/phase11/npm-audit-verified.json` và `npm-audit-after.json`.

Build web được tối ưu cho Docker VM khoảng 4 GB: dùng Webpack worker riêng và giới hạn heap Node ở 1536 MB trong build stage. TypeScript vẫn chạy trong Docker; cấu hình runtime của web giữ nguyên. Sau một lượt build thiếu tài nguyên, Docker đã phục hồi và fingerprint 19 bảng dữ liệu chính vẫn khớp.

**Browser thật trên stack Docker biệt lập** đã qua, gồm lượt chạy lại đầy đủ trên ảnh Next.js 16.4.6 sau cập nhật dependency:

1. HR tạo CONTINUOUS draft và thêm Huy qua form.
2. Mai Anh lập kế hoạch, Huy yêu cầu làm rõ, Mai Anh sửa thành bản 2, gửi/duyệt; Huy xác nhận bản 2.
3. Màn HR cập nhật trạng thái nhận kế hoạch qua realtime.
4. Mai Anh giao việc gắn mục tiêu đã duyệt; Huy bắt đầu và nộp lần 1.
5. Mai Anh trả lại; Huy bổ sung, nộp lần 2; Mai Anh nghiệm thu. Hai lần nộp vẫn đọc được.
6. Realtime giữa các tài khoản, draft giữ khi đổi tab, đóng không Back, navigation theo role, không có JavaScript exception hoặc gọi AI.

Đã kiểm tra ảnh desktop **1280px** và mobile **390px**, không tràn ngang trang. Script tái lập: `scripts/check_work_management_browser.py`; kết quả và ảnh ở `.superpowers/phase11/browser/`, gồm `result.json` và `employee-evidence-two-submissions-390.png`.

## Triển khai và bảo toàn dữ liệu

Ứng dụng chính **http://localhost:3000** đã chạy ảnh được nghiệm thu, migration head **`20261125_0011`**, API/web/PostgreSQL healthy. `.env` và mật khẩu không được sửa; không nạp seed vào database chính, không gọi Gemini.

Trước nâng cấp có bản `pg_dump -Fc` **162.140 byte** tại `.superpowers/phase11/deployment/before.dump`. Fingerprint so sánh các cột cũ sau nâng cấp xác nhận giữ nguyên bản ghi ở **19 bảng nghiệp vụ/tài khoản/lịch sử**. Hai bảng phiên và login throttle được tách khỏi so sánh vì có hoạt động xác thực bình thường.

Database chính vẫn có **5 kỳ LEGACY**, **1 kỳ ACTIVE**, **0 kỳ CONTINUOUS** và **0 work plan** ngay sau triển khai. Không tự chuyển chế độ, đóng kỳ, tạo điểm hoặc ghi lại lịch sử. Bằng chứng máy đọc được: `.superpowers/phase11/deployment/result.json`.

Demo mới chạy riêng ở **http://localhost:13039**, project `insighthr-phase11-acceptance`, database tmpfs `_test`, không dùng `.env`/volume của ứng dụng chính. Seed `continuous-demo-v1` có hai kỳ mẫu và bốn tình huống công việc; bài thử UI bổ sung kỳ/công việc riêng có nhãn UI DEMO. CLI chống nạp trùng, từ chối database có tài khoản sẵn và hoàn tác toàn bộ nếu lỗi muộn.

## Giới hạn và bước tiếp theo

- Phase 12 mới làm ledger dữ liệu đo được xác minh, tổng hợp actual và check-in/hành động. Phase 13 mới có AI cố vấn theo ngữ cảnh quá trình. Phase 14 mới nối provenance với điểm, giải trình và chốt/đóng CONTINUOUS.
- Phase 15 xử lý thay đổi baseline/lịch giữa kỳ, bàn giao và scheduler. Hiện chuyển tổ chức ảnh hưởng CONTINUOUS ACTIVE bị chặn; nhắc hạn lấy từ danh sách, chưa có job chủ động khi offline.
- Hạn xác nhận kế hoạch là mốc theo dõi chậm nhận; được nhận muộn trước kích hoạt. Hạn nộp/xác minh được kiểm tra thực sự ở API.
- Vẫn một kỳ ACTIVE mỗi database. Dùng demo riêng để thử, không đóng kỳ đang dùng chỉ để chuyển chế độ.
- Bản nghiệm thu local và kết quả audit dependency tại thời điểm này không thay thế kiểm toán bảo mật toàn diện hoặc nghiệm thu production/cloud.

Phase 11 cung cấp quá trình làm việc có trách nhiệm và bằng chứng. Việc nối quá trình đó thành kết quả hiệu suất có thể giải thích được là mục tiêu tiếp theo của Phase 12–14.
