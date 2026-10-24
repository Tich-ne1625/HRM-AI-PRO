# Phase 8 — kế hoạch thực hiện

**Đã hoàn thành cả ba phần ngày 24/10/2026.** Runtime cuối `88700d8` qua [CI 40086271058](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40086271058): 830 backend/133 web tests, Ruff/mypy 99 file, lint/types/build và Docker smoke/persistence. Xem [báo cáo đầy đủ](../../phase-8-report.vi.md). Các mục bên dưới giữ lại kế hoạch và bằng chứng theo mốc; phần 1 riêng không đại diện cho nghiệm thu cuối.

Đối chiếu: `docs/architecture.md`, `docs/phase-8-contract.md`, các module performance/AI hiện có và dữ liệu thực hành trong `docs/demo.vi.md`.

## Phần 1: Dashboard

1. Xác minh Gemini đang chạy, sửa phân loại lỗi 400/404 an toàn và đổi model local đã được Google hỗ trợ. Không ghi key vào repository.
2. Thêm GET `/api/v1/dashboard` với aggregate SQL và policy hiện có, snapshot nhất quán, không phát sinh ghi dữ liệu.
3. Thêm trang tổng quan tiếng Việt trong layout hiện tại, liên kết việc cần làm và biểu đồ có số mẫu, trạng thái trống/lỗi và nút tải lại.
4. Kiểm tra các role, số mẫu/điểm stale, chu kỳ ngoài quyền, tài khoản chưa gắn nhân viên, cập nhật cơ cấu và bảo toàn dữ liệu demo.
5. Ruff, mypy, unit/integration liên quan; typecheck, lint, web tests và production build. Cập nhật README; triển khai local giữ volume.

## Phần 2: Tư vấn và hoạt động

Trạng thái phần 1 tại runtime `7d10da5`: đã triển khai và chạy local; 33 test backend liên quan đạt, 122 test web đạt, Ruff/mypy (97 file), lint/typecheck và build đạt. Ba test dashboard được chạy lại sau khi phân nhóm phòng ban bằng ID snapshot để không gộp các phòng ban trùng tên. Edge kiểm tra bốn role ở 390/1280px, tám ảnh, không tràn ngang và không gọi AI khi mở dashboard. Một yêu cầu PUBLIC thực qua API ứng dụng trên hồ sơ demo An đã tạo/lưu/đọc lại thành công bằng `gemini-3.5-flash-lite`, điểm số giữ nguyên; đây chưa phải nghiệm thu HR_PRIVATE hay chất lượng tư vấn. CI toàn bộ được theo dõi riêng theo commit runtime, chưa đánh dấu hoàn tất Phase 8.

Danh sách AI có phân trang, kiểm tra quyền trước count; PUBLIC mặc định, HR_PRIVATE chỉ HR, không gọi provider từ GET. Hoạt động gần đây dùng allowlist, không trả metadata nhạy cảm. Kiểm tra rò rỉ qua count, tên, URL và trạng thái.

## Phần 3: Nghiệm thu UX

Rà soát điều hướng theo role, bảng/form và thao tác trên màn hình hẹp; cập nhật dữ liệu sau mutation, kiểm tra trình duyệt và CI đầy đủ. Ghi rõ những phần đạt và còn lại, không suy diễn từ kiểm tra SDK sang nghiệm thu nghiệp vụ AI toàn bộ.

## Bằng chứng phần 1

[CI 39745189991](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39745189991) cho `7d10da5` đạt cả backend, frontend và Docker smoke/persistence: **821 test backend, 122 test web**, Ruff/mypy 97 source file, lint/typecheck và production build. Phần 1 đã kiểm chứng; phần 2 và rà soát UX toàn bộ ở phần 3 vẫn còn. Không coi dashboard riêng là hoàn tất Phase 8.

## Nghiệm thu cuối — 24/10/2026

- [x] GET danh sách tư vấn có phân trang, metadata projection, kiểm tra HR_PRIVATE trước count, không gọi provider.
- [x] Hoạt động allowlist theo quyền/chu kỳ, không metadata/actor/request hoặc sự kiện AI/đăng nhập.
- [x] Trang tư vấn trong layout hiện có, xem nội dung/lịch sử, bộ lọc/empty/error, quản lý focus.
- [x] Cache dashboard/danh sách cập nhật sau mutation; dashboard ẩn cache khi làm mới lỗi.
- [x] Rà soát các màn hình hiện có, sửa hướng dẫn lỗi thời, vùng cuộn bảng bằng bàn phím và bố cục responsive.
- [x] Kiểm tra role/quyền chuyển quản lý, count/trang cùng snapshot khi có ghi đồng thời; đầy đủ CI nêu trên.
- [x] Local Docker giữ volume, fingerprint dữ liệu nghiệp vụ không đổi; không seed lại hoặc tạo lời gọi Gemini mới.
- [x] README, API, kiến trúc, demo, vận hành và báo cáo được cập nhật. Công đoạn tiếp theo theo kiến trúc là Phase 9 bảo mật/tích hợp.
