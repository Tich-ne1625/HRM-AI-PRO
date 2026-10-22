# Phase 8 — kế hoạch thực hiện

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
