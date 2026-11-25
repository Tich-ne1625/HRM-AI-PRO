# Bộ dữ liệu công ty mở rộng

Đây là dữ liệu hư cấu để thực hành. Bộ mở rộng bổ sung vào bộ demo cũ, không xóa hoặc dựng lại dữ liệu bạn đã dùng.

## Quy mô sau khi bổ sung

| Thành phần demo | Trước | Sau |
| --- | ---: | ---: |
| Nhân viên | 8 | 60 |
| Phòng ban | 2 | 8 |
| Chức danh | 2 | 13 |
| Tài khoản | 10 | 62 |
| Danh mục KPI | 2 | 14 |
| Chu kỳ | 3 | 4 |
| Bài viết mới | — | 9 |
| Trao đổi trong bài mới | — | 8 |
| Cuộc trò chuyện mới | — | 8 cặp, 16 tin nhắn |

Số liệu trên tính riêng dữ liệu demo. Nhân viên, tài khoản hoặc nội dung bạn tự tạo vẫn được giữ và cộng thêm vào tổng trên giao diện.

**8 quản lý** phụ trách 8 phòng. Nhân viên mới có tên tiếng Việt, tài khoản riêng, chức danh chuyên môn và quản lý trực tiếp. HR/ADMIN là tài khoản tổ chức/quản trị, không thêm hồ sơ nhân viên để đưa vào đánh giá.

KPI mới gồm tiến độ tính năng, lỗi kiểm thử, doanh thu, khách hàng mới, lộ trình sản phẩm, thiết kế được nghiệm thu, khách hàng tiềm năng, hài lòng khách hàng, thời gian phản hồi, báo cáo tài chính, sai sót chứng từ và SLA vận hành. Có cả chỉ tiêu càng cao càng tốt và càng thấp càng tốt.

## Nạp vào Docker đang sử dụng

Tại thư mục `hrm-ai`:

```powershell
docker compose --env-file .env up --build --wait
docker compose --env-file .env exec api python -m app.cli.expand_demo
```

Nếu máy chưa từng nạp bộ demo cơ bản, chạy `python -m app.cli.seed_demo` trong container API trước. Nếu API chạy trực tiếp, dùng `python -m app.cli.expand_demo` tại `apps/api` trong môi trường đã cấu hình.

**Tài khoản mới dùng mật khẩu `1`. Tài khoản cũ giữ nguyên mật khẩu đang có.** Bộ mở rộng không đặt lại mật khẩu, đổi quyền hoặc chỉnh tiến độ thực hành của tài khoản cũ. Chạy lại trả thông báo đã có dữ liệu, không nhân bản hay khôi phục những nội dung bạn đã sửa/xóa sau đó.

Lệnh chỉ hoạt động trong development/test. Nếu mã/email dành cho bộ mở rộng đã có sẵn mà chưa có dấu nạp hoàn tất, hoặc tài khoản HR/quản lý gốc không còn hợp lệ, lệnh dừng để giữ nguyên dữ liệu. Lỗi ở bất kỳ bước nào sẽ hoàn tác toàn bộ lượt bổ sung. Không tự gọi Gemini hay tạo đầu ra AI giả.

## Có thể xem và thử ngay ở đâu?

1. **HR → Tổ chức → Nhân viên:** xem 60 hồ sơ demo, tìm theo tên/mã, lọc phòng và thử phân trang.
2. **HR → Phòng ban / Chức danh / Danh mục KPI:** xem cơ cấu và các chỉ tiêu chuyên môn mới.
3. **Bảng tin nội bộ:** có một bài chào mừng toàn công ty và một bài cho mỗi phòng, kèm @nhắc và trao đổi. HR xem được mọi phòng; nhân viên chỉ xem công ty và phòng hiện tại của mình.
4. **Chat nội bộ:** mỗi quản lý có một hội thoại với nhân viên đầu tiên trong phòng. Nhân viên mở tin đến để thử trạng thái đã đọc và trả lời.
5. **Chu kỳ đánh giá:** kỳ ACTIVE cũ vẫn giữ các tình huống An/Bình/Dũng/Hà/Linh, không thêm hoặc thay đổi bằng chứng.
6. **Chu kỳ nháp `[DEMO+] Đánh giá toàn công ty — mở rộng`:** sẵn danh sách 51 nhân viên có tài khoản và quản lý mang quyền MANAGER. Đây là danh sách chuẩn bị, chưa có KPI cá nhân/điểm/phiếu phản hồi mới. Sau khi hoàn tất và đóng kỳ ACTIVE cũ, HR mới kích hoạt kỳ nháp này, phân công phản hồi; từng quản lý giao KPI cho nhóm mình rồi tiếp tục quy trình đánh giá.

Không đưa 8 quản lý đầu phòng vào kỳ nháp vì họ chưa có cấp quản lý cao hơn trong mô hình demo. Chi vẫn thuộc An như bộ cũ để giữ tình huống phản hồi cấp dưới, nhưng không thêm Chi vào kỳ nháp mới vì An đang có quyền EMPLOYEE. Không tự đổi quan hệ hoặc quyền của những người này để làm đẹp số liệu.

## Đăng nhập tài khoản mới

Để giữ màn hình đăng nhập gọn, các ô chọn nhanh cũ vẫn dùng để thực hành 10 tài khoản nền tảng. Với người mới trong danh sách bên dưới, chọn **Dùng tài khoản riêng**, nhập email và mật khẩu `1`.

Ví dụ: `product.manager.demo@example.com` để xem nhóm Sản phẩm; `product01.demo@example.com` để xem nhân viên cùng phòng; `finance.manager.demo@example.com` để đối chiếu phạm vi khác phòng.

## Danh sách phòng ban và tài khoản mới

| Code | Phòng ban | Nhân viên demo | Email quản lý |
| --- | --- | ---: | --- |
| DEMO-TECH | Kỹ thuật | 12 | `manager.demo@example.com` |
| DEMO-SALES | Kinh doanh | 10 | `sales.manager.demo@example.com` |
| DEMO-PRODUCT | Sản phẩm | 7 | `product.manager.demo@example.com` |
| DEMO-DESIGN | Thiết kế | 6 | `design.manager.demo@example.com` |
| DEMO-MARKETING | Marketing | 7 | `marketing.manager.demo@example.com` |
| DEMO-CARE | Chăm sóc khách hàng | 6 | `care.manager.demo@example.com` |
| DEMO-FINANCE | Tài chính - Kế toán | 6 | `finance.manager.demo@example.com` |
| DEMO-OPS | Vận hành | 6 | `ops.manager.demo@example.com` |

### 52 tài khoản bổ sung

| Email | Họ tên | Phòng | Chức danh | Quản lý trực tiếp |
| --- | --- | --- | --- | --- |
| `tech01.demo@example.com` | Nguyễn Minh Khánh | TECH | Lập trình viên | manager |
| `tech02.demo@example.com` | Trần Quốc Bảo | TECH | Chuyên viên kiểm thử | manager |
| `tech03.demo@example.com` | Lê Thảo Nguyên | TECH | Chuyên viên dữ liệu | manager |
| `tech04.demo@example.com` | Phạm Đức Anh | TECH | Lập trình viên | manager |
| `tech05.demo@example.com` | Hoàng Ngọc Hân | TECH | Chuyên viên kiểm thử | manager |
| `tech06.demo@example.com` | Vũ Hải Nam | TECH | Chuyên viên dữ liệu | manager |
| `tech07.demo@example.com` | Đặng Phương Thảo | TECH | Lập trình viên | manager |
| `sales01.demo@example.com` | Bùi Tuấn Kiệt | SALES | Chuyên viên kinh doanh | sales.manager |
| `sales02.demo@example.com` | Đỗ Thanh Trúc | SALES | Chuyên viên quan hệ khách hàng | sales.manager |
| `sales03.demo@example.com` | Hồ Minh Quân | SALES | Chuyên viên kinh doanh | sales.manager |
| `sales04.demo@example.com` | Ngô Bảo Châu | SALES | Chuyên viên quan hệ khách hàng | sales.manager |
| `sales05.demo@example.com` | Dương Gia Huy | SALES | Chuyên viên kinh doanh | sales.manager |
| `sales06.demo@example.com` | Đinh Mỹ Duyên | SALES | Chuyên viên quan hệ khách hàng | sales.manager |
| `sales07.demo@example.com` | Lý Hoàng Phúc | SALES | Chuyên viên kinh doanh | sales.manager |
| `product.manager.demo@example.com` | Mai Thu Trang | PRODUCT | MANAGER | - |
| `product01.demo@example.com` | Nguyễn Nhật Minh | PRODUCT | Chuyên viên sản phẩm | product.manager |
| `product02.demo@example.com` | Trần Bích Ngọc | PRODUCT | Chuyên viên dữ liệu | product.manager |
| `product03.demo@example.com` | Lê Đức Long | PRODUCT | Chuyên viên sản phẩm | product.manager |
| `product04.demo@example.com` | Phạm Quỳnh Anh | PRODUCT | Chuyên viên dữ liệu | product.manager |
| `product05.demo@example.com` | Hoàng Anh Tú | PRODUCT | Chuyên viên sản phẩm | product.manager |
| `product06.demo@example.com` | Vũ Ngọc Ánh | PRODUCT | Chuyên viên dữ liệu | product.manager |
| `design.manager.demo@example.com` | Đặng Trung Hiếu | DESIGN | MANAGER | - |
| `design01.demo@example.com` | Bùi Khánh Linh | DESIGN | Chuyên viên thiết kế | design.manager |
| `design02.demo@example.com` | Đỗ Quốc Đạt | DESIGN | Chuyên viên thiết kế | design.manager |
| `design03.demo@example.com` | Hồ Phương Vy | DESIGN | Chuyên viên thiết kế | design.manager |
| `design04.demo@example.com` | Ngô Thành Công | DESIGN | Chuyên viên thiết kế | design.manager |
| `design05.demo@example.com` | Dương Hà My | DESIGN | Chuyên viên thiết kế | design.manager |
| `marketing.manager.demo@example.com` | Đinh Anh Khoa | MARKETING | MANAGER | - |
| `marketing01.demo@example.com` | Lý Thanh Tâm | MARKETING | Chuyên viên marketing | marketing.manager |
| `marketing02.demo@example.com` | Mai Minh Triết | MARKETING | Chuyên viên marketing | marketing.manager |
| `marketing03.demo@example.com` | Nguyễn Ngọc Diệp | MARKETING | Chuyên viên marketing | marketing.manager |
| `marketing04.demo@example.com` | Trần Tuấn Anh | MARKETING | Chuyên viên marketing | marketing.manager |
| `marketing05.demo@example.com` | Lê Hải Yến | MARKETING | Chuyên viên marketing | marketing.manager |
| `marketing06.demo@example.com` | Phạm Gia Bảo | MARKETING | Chuyên viên marketing | marketing.manager |
| `care.manager.demo@example.com` | Hoàng Mai Anh | CARE | MANAGER | - |
| `care01.demo@example.com` | Vũ Đức Huy | CARE | Chuyên viên chăm sóc khách hàng | care.manager |
| `care02.demo@example.com` | Đặng Thùy Dung | CARE | Chuyên viên quan hệ khách hàng | care.manager |
| `care03.demo@example.com` | Bùi Nhật Hào | CARE | Chuyên viên chăm sóc khách hàng | care.manager |
| `care04.demo@example.com` | Đỗ Lan Hương | CARE | Chuyên viên quan hệ khách hàng | care.manager |
| `care05.demo@example.com` | Hồ Quang Vinh | CARE | Chuyên viên chăm sóc khách hàng | care.manager |
| `finance.manager.demo@example.com` | Ngô Phương Nhi | FINANCE | MANAGER | - |
| `finance01.demo@example.com` | Dương Quốc Hưng | FINANCE | Chuyên viên tài chính - kế toán | finance.manager |
| `finance02.demo@example.com` | Đinh Ngọc Hà | FINANCE | Chuyên viên tài chính - kế toán | finance.manager |
| `finance03.demo@example.com` | Lý Minh Đức | FINANCE | Chuyên viên tài chính - kế toán | finance.manager |
| `finance04.demo@example.com` | Mai Hoài An | FINANCE | Chuyên viên tài chính - kế toán | finance.manager |
| `finance05.demo@example.com` | Nguyễn Bảo Ngọc | FINANCE | Chuyên viên tài chính - kế toán | finance.manager |
| `ops.manager.demo@example.com` | Trần Thiên Phúc | OPS | MANAGER | - |
| `ops01.demo@example.com` | Lê Tú Uyên | OPS | Chuyên viên vận hành | ops.manager |
| `ops02.demo@example.com` | Phạm Anh Duy | OPS | Chuyên viên vận hành | ops.manager |
| `ops03.demo@example.com` | Hoàng Khánh Vân | OPS | Chuyên viên vận hành | ops.manager |
| `ops04.demo@example.com` | Vũ Thành Đạt | OPS | Chuyên viên vận hành | ops.manager |
| `ops05.demo@example.com` | Đặng Minh Tâm | OPS | Chuyên viên vận hành | ops.manager |
