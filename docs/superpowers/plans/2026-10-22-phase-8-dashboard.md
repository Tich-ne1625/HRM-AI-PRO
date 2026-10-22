# Phase 8 — kế hoạch thực hiện

Đối chiếu: `docs/architecture.md`, `docs/phase-8-contract.md`, các module performance/AI hiện có và dữ liệu thực hành trong `docs/demo.vi.md`.

## Phần 1: Dashboard

1. Xác minh Gemini đang chạy, sửa phân loại lỗi 400/404 an toàn và đổi model local đã được Google hỗ trợ. Không ghi key vào repository.
2. Thêm GET `/api/v1/dashboard` với aggregate SQL và policy hiện có, snapshot nhất quán, không phát sinh ghi dữ liệu.
3. Thêm trang tổng quan tiếng Việt trong layout hiện tại, liên kết việc cần làm và biểu đồ có số mẫu, trạng thái trống/lỗi và nút tải lại.
4. Kiểm tra các role, số mẫu/điểm stale, chu kỳ ngoài quyền, tài khoản chưa gắn nhân viên, cập nhật cơ cấu và bảo toàn dữ liệu demo.
5. Ruff, mypy, unit/integration liên quan; typecheck, lint, web tests và production build. Cập nhật README; triển khai local giữ volume.

## Phần 2: Tư vấn và hoạt động

Danh sách AI có phân trang, kiểm tra quyền trước count; PUBLIC mặc định, HR_PRIVATE chỉ HR, không gọi provider từ GET. Hoạt động gần đây dùng allowlist, không trả metadata nhạy cảm. Kiểm tra rò rỉ qua count, tên, URL và trạng thái.

## Phần 3: Nghiệm thu UX

Rà soát điều hướng theo role, bảng/form và thao tác trên màn hình hẹp; cập nhật dữ liệu sau mutation, kiểm tra trình duyệt và CI đầy đủ. Ghi rõ những phần đạt và còn lại, không suy diễn từ kiểm tra SDK sang nghiệm thu nghiệp vụ AI toàn bộ.
