# Báo cáo Phase 8 — Dashboard và trải nghiệm web

Ngày kiểm tra: **24/10/2026**. Trạng thái: **hoàn thành và nghiệm thu Phase 8 theo hợp đồng**.

Runtime cuối **`88700d8`**, kế thừa phần triển khai chính `72854dd`, đã qua [CI 40086271058](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40086271058): **830 test backend, 133 test web**, Ruff/mypy sạch (99 source file), ESLint/typecheck/production build và Docker smoke/persistence đều đạt. Báo cáo/tài liệu được lưu ở commit tiếp theo; không thay đổi runtime đã kiểm tra.

Đối chiếu [hợp đồng](phase-8-contract.md), [kế hoạch](superpowers/plans/2026-10-22-phase-8-dashboard.md) và kiến trúc tổng thể. Báo cáo này tổng hợp phần dashboard đã nghiệm thu trước đó và phần tư vấn/hoạt động/UX vừa hoàn thiện.

## Chức năng đã hoàn thiện

| Phần | Kết quả |
| --- | --- |
| Tổng quan | Chọn chu kỳ, tiến độ chưa tính/cần tính lại/hiện hành/đã chốt, số mẫu và trung bình hợp lệ, phân bố điểm, tỷ lệ nhập thực tế KPI, bảng phòng ban snapshot |
| Tư vấn AI đã lưu | Trang `/ai-reports`, bộ lọc chu kỳ/phạm vi, phân trang, model/ngày/phiên bản, đối chiếu với lần tính hiện tại, mở nội dung và báo cáo liên quan |
| Hoạt động gần đây | Tối đa 6 sự kiện đã lọc theo role, phạm vi nhân viên hiện tại và chu kỳ; không trả metadata, actor, mã request hoặc sự kiện AI/đăng nhập |
| Điều hướng | Header và menu trái theo role, tư vấn nằm trong nhóm đánh giá, tab KPI/phản hồi/kết quả giữ nhân viên và chu kỳ |
| Trải nghiệm | Trạng thái tải/lỗi/trống, tải lại chủ động, bộ lọc đưa về trang 1, focus mở/đóng tư vấn, vùng cuộn bảng bằng bàn phím, focus-visible và reduced-motion |
| Cập nhật số liệu | Cache dashboard và danh sách AI được đánh dấu cần tải lại sau mutation thành công hoặc lỗi; không tự lặp thao tác ghi hay tạo AI |
| Dữ liệu demo | Tái sử dụng bộ mẫu 10 tài khoản, 8 hồ sơ, 2 phòng ban, 3 chu kỳ; không seed lại hay đặt lại tiến độ |

## Phạm vi theo vai trò

| Vai trò | Dashboard | Tư vấn đã lưu | Hoạt động |
| --- | --- | --- | --- |
| ADMIN | Tổng tài khoản và số theo role; hộp việc phản hồi của mình | Không truy cập | Tạo tài khoản, đổi role/trạng thái; không tên tài khoản đích |
| HR | Toàn bộ nhân sự | PUBLIC và HR_PRIVATE, chỉ truy vấn riêng khi chọn | Tính/chốt kết quả trong chu kỳ đang xem |
| MANAGER | Bản thân và nhân viên trực tiếp hiện tại | PUBLIC trong cùng phạm vi | Tính/chốt kết quả trong cùng phạm vi và chu kỳ |
| EMPLOYEE | Chỉ bản thân | PUBLIC của bản thân | Tính/chốt kết quả của bản thân trong chu kỳ |

Quyền reviewer được giao phản hồi vẫn độc lập với quyền đọc báo cáo. Được giao đánh giá một người không tự cấp quyền xem tư vấn/hiệu suất của người đó. Chuyển quản lý thay đổi quyền đọc danh sách và hoạt động, giữ nguyên lịch sử.

## Bằng chứng kiểm tra

- Backend kiểm tra phạm vi/count trước phân trang, riêng HR_PRIVATE, UUID ngoài quyền, filter không hợp lệ, lịch sử khi KPI đổi, chuyển quản lý, projection không chứa nội dung riêng và allowlist audit. Một test ghi đồng thời vào PostgreSQL giữa COUNT và đọc trang chứng minh cả hai dùng chung snapshot.
- Frontend kiểm tra ADMIN không gửi request nhân sự; quản lý/nhân viên chỉ gửi PUBLIC; nội dung chỉ được tải khi chọn; lọc/phân trang/trống/lỗi/thử lại; điều hướng; cache tải lại sau mutation thành công/lỗi, không lặp mutation. Dashboard ẩn cả số liệu và hoạt động đã cache nếu tải lại thất bại.
- Kiểm tra Edge production trên runtime cuối: **32 trường hợp, 80 ảnh ở 390/1280 px**, với 7 tài khoản đại diện đủ ADMIN/HR/MANAGER/EMPLOYEE và trạng thái chưa tính/cần tính lại/đã chốt. Không tràn ngang toàn trang, không exception JavaScript, không request ghi API khi duyệt; mở/đóng tư vấn xác nhận focus đúng. Đã mở thêm form tạo/chỉnh hồ sơ, nhập thực tế/phân bổ KPI, bộ lọc nội bộ HR trống; phím ArrowRight thực sự cuộn được bảng.
- Các màn hình đã duyệt: tổng quan, tài khoản/đổi mật khẩu, nhân viên/thêm/chỉnh sửa, phòng ban/chức danh, danh sách và chi tiết chu kỳ ACTIVE/DRAFT, danh mục/phân bổ KPI, tổng hợp phản hồi, inbox/form phản hồi, quản trị phân công, kết quả/lịch sử, tư vấn đã lưu/chi tiết, quản trị tài khoản và cấu hình chấm điểm. Form chỉ mở/xem; không gửi thử vào database của người dùng.
- Docker production được build lại và local stack khỏe. Không thêm migration, thư viện UI hoặc service. Pipeline Docker có smoke dashboard kỳ đóng/kỳ mới, hoạt động, danh sách AI và quyền role qua proxy, cùng kiểm tra dữ liệu sau khởi động lại.
- Fingerprint các bảng được kiểm tra trước/sau triển khai khớp: **13 tài khoản, 8 hồ sơ, 3 chu kỳ, 9 lượt tham gia, 14 KPI được giao, 19 phân công, 16 phản hồi, 5 báo cáo, 6 revision và 3 lượt AI hiện hữu**, cùng 2 phòng ban và 2 chức danh. SHA-256 của các bản ghi được kiểm tra (tài khoản chỉ lấy thuộc tính không bí mật): `214624134e042ca1511419c7b3a067eeaa313d6389c382649b222be7771242ba`. Auth sessions/audit đăng nhập không nằm trong dấu vì kiểm tra cần đăng nhập/đăng xuất.

Bằng chứng chi tiết trên máy nằm trong thư mục ignored `.superpowers/sdd/phase-8/`: báo cáo/ảnh `final-ui/`, fingerprint `domain-before.json` và `domain-after.json`. Không chứa API key hoặc mật khẩu. Dữ liệu test provider giả chỉ ở môi trường test; không cấy tư vấn giả vào database đang sử dụng.

## Cách xem trên máy

Local stack đã cập nhật. Mở **http://localhost:3000/dashboard** hoặc **http://localhost:3000/ai-reports**, đăng nhập tài khoản đang dùng. Chọn chu kỳ trên dashboard; hoạt động có liên kết tới đúng báo cáo. Trong tư vấn, HR có thể chọn nội bộ HR; mọi người chỉ đọc nội dung trong quyền của mình. Bản chưa có tư vấn hiện trạng thái trống và hướng dẫn đến báo cáo để HR tạo sau xác nhận.

Để dựng lại khi có code mới:

```powershell
docker compose --env-file .env up --build --detach --wait
```

Không cần nạp lại demo. Mở/tải lại danh sách hoặc đọc tư vấn đã lưu không phát sinh lời gọi Gemini.

## Giới hạn và công đoạn tiếp theo

Nghiệm thu Phase 8 là phạm vi chức năng/UX theo hợp đồng; không phải chứng nhận bảo mật hoặc kiểm chứng chất lượng quyết định nhân sự. Lượt PUBLIC thật đã tạo/lưu/đọc thành công ngày 22/10 được giữ lại; lần này không gọi Gemini mới. HR_PRIVATE và tình huống provider/concurrency được kiểm tra offline bằng SDK transport/provider giả, chưa nghiệm thu toàn bộ bằng dịch vụ Gemini thật.

Danh sách phân trang bằng offset, page_size tối đa 100; bộ lọc chu kỳ/dashboard và nhóm phòng ban có giới hạn công khai. Chưa có bằng chứng tải lớn để cam kết độ trễ ở quy mô doanh nghiệp. Rà soát bảo mật/tích hợp chuyên sâu và đo tải thuộc **Phase 9**; Kubernetes và tài liệu vận hành triển khai thuộc **Phase 10** theo kiến trúc đã duyệt. Không mở rộng hai phase đó trong lượt hoàn thiện này.
