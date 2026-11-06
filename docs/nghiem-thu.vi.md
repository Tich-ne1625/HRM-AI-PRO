# Hướng dẫn nghiệm thu InsightHR cho người mới

Mục tiêu: tự vận hành một lượt đánh giá, biết ai làm việc gì và nhận ra kết quả đúng/sai. Dùng dữ liệu hư cấu `[DEMO]`, không cần biết lập trình. Đây là bài thực hành có thay đổi dữ liệu; gửi phản hồi, chốt kết quả và đóng kỳ không có nút hoàn tác.

## 1. Chuẩn bị trước khi bắt đầu

1. Mở Docker Desktop, chờ Docker chạy.
2. Mở terminal trong thư mục `hrm-ai`, chạy:

```powershell
docker compose --env-file .env up --build --wait
```

3. Mở **http://localhost:3000/login** trên trình duyệt.
4. Chuẩn bị mật khẩu demo đã lưu khi nạp dữ liệu. Các email demo bên dưới dùng mật khẩu được tạo lúc nạp, trừ khi bạn đã đổi riêng.
5. Chỉ khi chưa từng nạp demo, chạy:

```powershell
docker compose --env-file .env exec api python -m app.cli.seed_demo
```

Lưu mật khẩu được in một lần vào nơi riêng của bạn. Chạy lại seed không đặt lại mật khẩu, không đưa dữ liệu về ban đầu. Không xóa volume Docker để thử lại bài này. Xem thêm [tài liệu demo](demo.vi.md).

**Cách đổi người dùng:** mở tab **Cá nhân**, vào **Tài khoản**, đăng xuất rồi đăng nhập email tiếp theo. Dùng một cửa sổ cho bài thực hành là dễ nhất. Hai tab cùng trình duyệt thường dùng chung phiên; không coi đó là hai người dùng độc lập. Nếu cần so sánh đồng thời, dùng hai profile trình duyệt riêng.

**Cách đọc hướng dẫn:** chữ in đậm là tên menu/nút cần tìm. Nút trong form thu gọn chỉ xuất hiện sau khi bấm tiêu đề để mở. Trên điện thoại, bấm **Mở menu**; bảng rộng có thể cuộn ngang bên trong.

## 2. Hiểu nhanh thuật ngữ và vai trò

| Từ đang thấy | Hiểu đơn giản |
| --- | --- |
| Chu kỳ | Một đợt đánh giá, chẳng hạn quý hoặc tháng |
| KPI | Chỉ tiêu công việc; mục tiêu là số cần đạt, thực tế là số đã làm được |
| Trọng số | Mức đóng góp của một KPI hoặc nhóm điểm vào điểm cuối |
| Phản hồi 360 | Đánh giá được giao cho bản thân, quản lý, đồng nghiệp hoặc cấp dưới |
| Tính điểm | Tổng hợp bằng chứng hiện tại thành kết quả; chưa khóa hồ sơ |
| Cần tính lại | Bằng chứng đã đổi sau lần tính; điểm lưu trước chưa phản ánh dữ liệu mới |
| Chốt kết quả | HR xác nhận xong hồ sơ một người, khóa sửa KPI/phản hồi của người đó trong kỳ |
| Đóng chu kỳ | HR kết thúc cả đợt sau khi tất cả người tham gia đã được chốt |
| Tư vấn AI | Gợi ý tham khảo từ dữ liệu; không tự sửa điểm |

| Role | Trách nhiệm | Email chính trong bài |
| --- | --- | --- |
| ADMIN — quản trị viên | Quản lý tài khoản/quyền và cấu hình hệ thống | `admin.demo@example.com` |
| HR — nhân sự | Tổ chức đợt đánh giá, kiểm tra bằng chứng, chốt/đóng kỳ, tạo AI | `hr.demo@example.com` |
| MANAGER — quản lý | Nhập KPI và tính điểm cho người thuộc phạm vi; gửi phản hồi được giao | `manager.demo@example.com` |
| EMPLOYEE — nhân viên | Xem dữ liệu của mình và gửi phản hồi được giao | `binh.demo@example.com` |

ADMIN không có sẵn quyền HR. Người quản lý không được xem mọi nhân viên trong công ty. Email đăng nhập và hồ sơ nhân viên là hai phần khác nhau; tạo tài khoản thử không tự tạo nhân viên hoặc thêm vào kỳ.

## 3. Thứ tự role cần thực hiện

Không làm hết mọi việc của một role rồi mới đến role khác: quy trình cần bàn giao qua lại. Làm lần lượt từ trên xuống:

| Lượt | Đăng nhập bằng | Làm gì | Chuyển tiếp khi |
| --- | --- | --- | --- |
| 1 | ADMIN | Xem hệ thống tài khoản, hiểu quyền | Nhìn thấy danh sách và các role |
| 2 | HR | Chọn đúng kỳ, khảo sát hồ sơ | Biết Bình đang thiếu gì |
| 3 | Quản lý kỹ thuật | Nhập KPI còn thiếu của Bình | KPI đã lưu đủ thực tế |
| 4 | Bình | Gửi tự đánh giá | Phản hồi đã ghi nhận |
| 5 | Quản lý kỹ thuật | Gửi đánh giá Bình, tính điểm | Kết quả hiện tại, đủ điều kiện |
| 6 | HR | Kiểm tra, thử AI rồi chốt Bình | Hồ sơ đã chốt |
| 7 | Bình | Xem lại kết quả và tư vấn chung | Đọc được nhưng không sửa bằng chứng |
| 8 | Các tài khoản bổ sung | Thử tính lần đầu, tính lại, lịch sử và phạm vi | Hoàn thành các tình huống ở mục 11 |
| 9 | HR | Chốt các hồ sơ còn lại, đóng kỳ | Cả kỳ đã đóng |
| 10, tùy chọn | ADMIN rồi HR | Thử khóa tài khoản riêng, chuẩn bị kỳ nháp | Đã hiểu phân quyền và kỳ tiếp theo |

## 4. Lượt 1 — ADMIN kiểm tra tài khoản

1. Đăng nhập `admin.demo@example.com`.
2. Chọn tab trên **Quản trị hệ thống** → menu trái **Quản lý tài khoản**.
3. Tìm các email trong bảng ở mục 2; dùng **Trang sau** nếu chưa thấy.
4. Kiểm tra các tài khoản cần thực hành đang **Hoạt động**, đúng role.
5. Có thể mở **Cấu hình chấm điểm** để xem, nhưng chưa thay đổi trong bài cơ bản. Cấu hình của kỳ đã kích hoạt đã được đóng băng; sửa cấu hình không dùng để thay điểm kỳ hiện tại.
6. Đăng xuất.

**Đạt:** quản lý được tài khoản; không có đầy đủ màn hình nghiệp vụ HR là đúng quyền. Không đổi role hoặc vô hiệu hóa các tài khoản demo đang cần dùng.

## 5. Lượt 2 — HR chọn kỳ và đọc tình trạng

1. Đăng nhập `hr.demo@example.com` → **Tổng quan**.
2. Chọn tab trên **Tổ chức**, lần lượt xem **Nhân viên**, **Phòng ban**, **Chức danh** để hiểu danh sách. Chưa cần sửa.
3. Chọn tab trên **Đánh giá hiệu suất** → menu trái **Chu kỳ đánh giá**.
4. Mở **[DEMO] Thực hành đánh giá**, trạng thái `ACTIVE` — kỳ đang hoạt động.
5. Trong **Người tham gia**, tìm Bình. Bấm **Kết quả** trên dòng của Bình.
6. Đọc **Việc cần hoàn thành**; ghi lại phần thiếu. Nếu cần xem KPI, chọn tab **KPI và kết quả thực tế**; phản hồi nằm ở tab **Phản hồi 360**.
7. Quay lại kỳ, xem nhanh các tình huống dưới đây, rồi đăng xuất.

| Người | Trạng thái ban đầu của bộ demo chưa được thao tác | Ý nghĩa |
| --- | --- | --- |
| An | Đã có điểm hiện tại và lịch sử | Dùng để xem hai lần tính |
| Bình | Chưa tính; còn KPI/phản hồi bắt buộc | Luồng thực hành chính |
| Dũng | Đủ dữ liệu, chưa tính | Thử tính lần đầu |
| Hà | Đã chốt | Chỉ xem bằng chứng/kết quả |
| Linh | Cần tính lại | Thử cập nhật kết quả từ bằng chứng mới |

**Đạt:** mở đúng Bình trong đúng kỳ. Nếu trạng thái khác bảng, có thể bạn đã thực hành trước đó: đọc trạng thái thực tế, làm phần còn thiếu, không cố đưa về trạng thái cũ bằng seed.

## 6. Lượt 3 — Quản lý nhập thực tế KPI của Bình

1. Đăng nhập `manager.demo@example.com` — quản lý kỹ thuật Nguyễn Lan.
2. **Đánh giá hiệu suất → Chu kỳ đánh giá → [DEMO] Thực hành đánh giá**.
3. Tìm Bình → **Quản lý KPI**.
4. Tìm dòng có **Thực tế** chưa có số. Bấm **Nhập thực tế [mã KPI]** ở dòng đó.
5. Đọc mục tiêu và đơn vị; nhập ví dụ `85` vào ô thực tế rồi bấm nút lưu của form. Đây là số bài tập, không phải giá trị đúng cho mọi KPI.
6. Chờ lưu xong, tải lại trang để kiểm tra số vẫn còn. Nếu còn KPI khác thiếu thực tế, nhập đủ trước khi chuyển bước.
7. Đăng xuất.

**Đạt:** thực tế đã lưu; không sửa mục tiêu/trọng số hoặc bấm **Chỉnh phân bổ KPI** trong bài cơ bản. Các thay đổi đó có thể xóa thực tế liên quan sau xác nhận và làm bài khó đối chiếu.

## 7. Lượt 4 — Bình gửi tự đánh giá

1. Đăng nhập `binh.demo@example.com`.
2. Chọn **Cá nhân → Phản hồi của tôi**.
3. Mở phân công đánh giá **Bình** trong **[DEMO] Thực hành đánh giá**, quan hệ tự đánh giá (`SELF`), còn chờ gửi. Đọc tên người được đánh giá và kỳ trước khi nhập.
4. Chọn **Mức đánh giá** `4/5`.
5. Nhập nhận xét mẫu: “Đã hoàn thành phần lớn công việc được giao, cần cải thiện việc theo dõi tiến độ hằng tuần.”
6. Bấm **Kiểm tra và gửi**, đọc lại bản xem trước.
7. Nếu đúng, bấm **Xác nhận gửi một lần**.
8. Kiểm tra có thông báo **Phản hồi đã được ghi nhận.**, sau đó đăng xuất.

**Đạt:** phản hồi chuyển sang đã gửi; tải lại vẫn xem được nội dung. Không sửa/xóa được sau gửi là hành vi đúng. Nếu đã gửi từ lần trước thì chỉ xem, không tạo thêm phân công để gửi lại.

## 8. Lượt 5 — Quản lý gửi phản hồi và tính điểm

1. Đăng nhập lại `manager.demo@example.com`.
2. **Cá nhân → Phản hồi của tôi** → mở phân công đánh giá **Bình**, đúng kỳ thực hành, quan hệ quản lý (`MANAGER`).
3. Chọn `4/5`, nhập: “Hoàn thành công việc ổn định; nên cập nhật tiến độ và chủ động báo sớm các vướng mắc.”
4. **Kiểm tra và gửi → Xác nhận gửi một lần**. Nếu đã gửi, bỏ qua bước nhập.
5. **Đánh giá hiệu suất → Chu kỳ đánh giá → kỳ thực hành → Bình → Kết quả**.
6. Nếu có **Việc cần hoàn thành**, xử lý hết: quay sang KPI để kiểm tra số thực tế, hoặc nhờ HR xem phân công bắt buộc còn thiếu. HR không gửi thay người được giao.
7. Khi đủ điều kiện, bấm **Tính điểm hiệu suất**; nếu đã có kết quả cũ cần cập nhật, bấm **Tính lại điểm**.
8. Mở **Chi tiết lần tính …**, xem điểm KPI, phản hồi và kết quả cuối. Mở **Lịch sử tính điểm** để thấy lần vừa lưu.
9. Ghi điểm hiển thị vào phiếu ở mục 15 rồi đăng xuất.

**Đạt:** kết quả có điểm và không còn trạng thái **Cần tính lại**. Không yêu cầu Bình phải có một điểm cố định: điểm phụ thuộc thực tế, phản hồi và cấu hình đã đóng băng của kỳ. Quản lý tính điểm; HR là người chốt.

## 9. Lượt 6 — HR kiểm tra, tạo AI và chốt Bình

### 9.1 Kiểm tra trước khi chốt

1. Đăng nhập `hr.demo@example.com` → mở kết quả Bình trong kỳ thực hành.
2. Đối chiếu điểm với mục 8. Mở chi tiết lần tính để kiểm tra dữ liệu được dùng.
3. Nếu cần xem phân công hoặc phản hồi gốc, quay về dòng Bình trong kỳ → **Phân công phản hồi**. Chỉ kiểm tra, không tạo thêm phân công ở bước này.
4. Nếu có dữ liệu mới khiến kết quả **Cần tính lại**, tính lại rồi kiểm tra trước khi chốt.

### 9.2 Thử AI thật — tùy chọn, có sử dụng quota/chi phí của key

1. Trên báo cáo Bình, tìm **Tư vấn AI**, chọn **Tư vấn chung**.
2. Bấm **Tạo tư vấn AI**. Nếu đã có tư vấn hiện tại, đọc bản đó; chỉ bấm **Tạo lại tư vấn AI** khi thực sự muốn gọi thêm.
3. Đọc phạm vi dữ liệu, tích **Tôi đã kiểm tra phạm vi dữ liệu và đồng ý gửi yêu cầu.**
4. Bấm **Xác nhận tạo tư vấn** một lần và chờ kết quả. Không bấm lặp khi đang xử lý.
5. Kiểm tra có tóm tắt, điểm mạnh, điểm cần cải thiện, hành động đề xuất và giới hạn/lưu ý; không có số điểm tự bị thay đổi.
6. Tải lại trang: nội dung đã lưu vẫn còn, không tự phát sinh lượt tạo mới.
7. Có thể thử thêm **Nội bộ HR** với một xác nhận riêng để nghiệm thu phân quyền. Đây là một lượt gọi khác; bỏ qua nếu chỉ muốn thử kết nối một lần.

**Đạt:** tư vấn được lưu và đọc lại được. Nếu AI lỗi, ghi nguyên thông báo trên màn hình vào phiếu; vẫn tiếp tục nghiệm thu tính điểm/chốt vì nghiệp vụ không phụ thuộc AI. Không chụp `.env`, key hoặc mật khẩu làm bằng chứng.

### 9.3 Chốt hồ sơ Bình

1. Bấm **Chốt kết quả**.
2. Đọc phần xác nhận và số phân công chưa gửi. Phân công bắt buộc thiếu phải được hoàn thành; phân công tùy chọn còn mở cần được xem xét trước khi đồng ý.
3. Khi đã kiểm tra đúng, tích ô xác nhận rồi bấm **Xác nhận chốt kết quả**.
4. Kiểm tra trạng thái **Đã chốt**; quay sang KPI để thấy bằng chứng không còn cho sửa trong kỳ.
5. Đăng xuất.

**Đạt:** Bình đã chốt. Chỉ làm sau các bước trước vì chốt không có thao tác mở lại trong bài này.

## 10. Lượt 7 — Nhân viên xem thành quả và kiểm tra quyền

1. Đăng nhập `binh.demo@example.com`.
2. **Đánh giá hiệu suất → Chu kỳ đánh giá → kỳ thực hành → Bình → Kết quả**.
3. Kiểm tra điểm giống bản HR vừa chốt, có trạng thái **Đã chốt**.
4. Đọc tư vấn chung nếu đã tạo ở mục 9.2. Có thể mở menu **Tư vấn AI đã lưu** để tìm theo kỳ.
5. Kiểm tra không có quyền tạo tư vấn, không xem tư vấn **Nội bộ HR**, không sửa thực tế KPI hoặc chốt kết quả.
6. Mở **Phản hồi của tôi**, xem lại tự đánh giá đã gửi rồi đăng xuất.

**Đạt:** nhân viên đọc được dữ liệu được phép của mình. Menu/nút không xuất hiện do quyền là bình thường; không phải chức năng bị mất.

## 11. Lượt 8 — Các tình huống bổ sung

Làm trước khi đóng kỳ. Mỗi hàng là một bài độc lập; đăng xuất khi đổi tài khoản.

| Tình huống | Ai làm và thao tác | Kết quả cần thấy |
| --- | --- | --- |
| Tính lần đầu | Quản lý kỹ thuật mở **Dũng → Kết quả**, bấm **Tính điểm hiệu suất** khi đủ điều kiện | Có kết quả và lần tính mới |
| Tính lại | `sales.manager.demo@example.com` mở **Linh → Kết quả**, đọc tình trạng rồi **Tính lại điểm** | Hết **Cần tính lại**; lần cũ vẫn trong lịch sử |
| Xem lịch sử | HR mở **An → Kết quả → Lịch sử tính điểm → Xem lần …** | Đọc được các lần tính, không ghi đè lịch sử. Bộ demo nguyên trạng/policy mặc định có 87.00 rồi 82.80; dữ liệu đã sửa có thể khác |
| Phản hồi tùy chọn | `linh.demo@example.com` mở **Phản hồi của tôi**, gửi phân công `PEER` cho **An** nếu còn mở và An chưa chốt | Gửi thành công; kết quả An cần tính lại. Sau đó HR/quản lý kỹ thuật tính lại An trước khi chốt |
| Hồ sơ đã chốt | HR hoặc `ha.demo@example.com` xem kết quả Hà | Đọc được kết quả; không sửa bằng chứng đã khóa |
| Phạm vi quản lý | Quản lý kỹ thuật xem danh sách kỳ, rồi quản lý kinh doanh xem cùng kỳ | Kỹ thuật thấy An/Bình/Dũng; kinh doanh thấy Hà/Linh trong phạm vi tương ứng, không truy cập chéo hồ sơ |
| Thống kê nhóm nhỏ | Mở tổng hợp phản hồi An | Nhóm chưa đủ ba người gửi bị ẩn thống kê nhóm để bảo vệ riêng tư; không coi đó là mất dữ liệu |
| Giao diện nhỏ | Thu hẹp trình duyệt hoặc dùng điện thoại; thử **Mở menu**, mở form/chi tiết thu gọn | Điều hướng được, đọc được nút; bảng có vùng cuộn riêng, trang không tràn ngang |

Nếu một bài đã hoàn thành từ trước, ghi “đã có sẵn, kiểm tra lại đạt”. Không đổi tùy tiện KPI/phản hồi để ép quay về đúng số trong tài liệu.

## 12. Lượt 9 — HR đóng cả kỳ

Đây là bước cuối của bài cơ bản. Chỉ đóng khi không còn cần sửa bằng chứng hoặc thử gửi phản hồi trong kỳ này.

1. Đăng nhập HR, mở kỳ **[DEMO] Thực hành đánh giá**.
2. Mở **Kết quả** từng người: **An, Bình, Dũng, Hà, Linh**.
3. Người chưa đủ dữ liệu: đọc **Việc cần hoàn thành**, nhờ đúng người nhập/gửi. Người **Cần tính lại**: tính lại. Người có kết quả hiện tại nhưng chưa chốt: kiểm tra rồi chốt như mục 9.3. Hà đã chốt thì bỏ qua.
4. Khi cả năm người đều **Đã chốt**, quay về trang chi tiết kỳ.
5. Bấm **Đóng chu kỳ → Xác nhận đóng chu kỳ**.
6. Kiểm tra kỳ chuyển `CLOSED` — đã đóng; mở lại vẫn đọc được kết quả.
7. Vào **Tổng quan**, chọn đúng kỳ nếu màn hình có bộ chọn; kiểm tra kết quả đã kết thúc. Không yêu cầu các con số tổng quan giống dữ liệu mẫu ban đầu sau khi bạn đã thao tác.

**Đạt:** đóng được khi mọi người đã chốt. Nếu thử đóng sớm và hệ thống từ chối thì cơ chế bảo vệ đang hoạt động đúng; hoàn thành các hồ sơ còn lại trước khi thử lại. Kỳ đã đóng không mở lại.

## 13. Lượt 10 — Bài nâng cao, không bắt buộc

### Thử tài khoản và khóa quyền bằng ADMIN

1. Đăng nhập ADMIN → **Quản lý tài khoản → Tạo tài khoản**.
2. Dùng email thử riêng, ví dụ `nghiemthu.20261106@example.com` (nếu đã tồn tại, chọn email khác), role `EMPLOYEE`, mật khẩu riêng 12–128 ký tự. Không dùng email demo chính.
3. Đăng xuất, thử đăng nhập tài khoản mới: phải vào được nhưng chưa có hồ sơ nhân viên/chu kỳ được gán là bình thường.
4. Đăng xuất, vào lại ADMIN, tìm đúng email thử, đổi role sang `MANAGER` rồi về `EMPLOYEE`; mỗi thay đổi được lưu ngay. Không dùng bài này để thay role nhân viên demo.
5. Bấm **Vô hiệu hóa → Xác nhận vô hiệu hóa** cho email thử.
6. Đăng xuất, thử đăng nhập email thử: phải bị từ chối. Quay lại ADMIN có thể **Kích hoạt** nếu muốn giữ tài khoản để thử tiếp.

Để kiểm tra phiên đang mở bị thu hồi: đăng nhập tài khoản thử ở profile trình duyệt thứ hai, khóa bằng ADMIN ở profile thứ nhất, rồi thao tác/tải lại trang bên tài khoản thử. Phiên không được tiếp tục truy cập dữ liệu bảo vệ.

### Chuẩn bị kỳ tiếp theo bằng HR

1. Đăng nhập HR → mở **[DEMO] Kỳ tiếp theo — bản nháp** (`DRAFT`).
2. Xem **Thông tin bản nháp**, sửa tên/ngày nếu cần, lưu theo form. Mở **Thêm người tham gia bản nháp**, tìm và chọn nhân viên cần đánh giá, bấm **Thêm người đã chọn**.
3. Kiểm tra đủ người, tài khoản hoạt động, cơ cấu và cấu hình chấm điểm trước khi kích hoạt.
4. Chỉ sau khi kỳ ACTIVE cũ đã đóng, và bạn muốn bắt đầu một lượt mới, bấm **Kích hoạt chu kỳ → Xác nhận kích hoạt**. Danh sách tham gia và cấu hình bị đóng băng sau bước này.
5. Với kỳ mới, HR/quản lý phân bổ KPI cho từng người, tổng trọng số 100%; HR giao phản hồi qua **Phân công phản hồi**, rồi lặp luồng nhập thực tế → gửi phản hồi → tính → chốt → đóng. Xem các trường bắt buộc trực tiếp trên form.

Kỳ nháp không tự kế thừa đầy đủ bằng chứng từ kỳ đã đóng. Phần này là bài vận hành mới, không yêu cầu phải hoàn tất để nghiệm thu bộ demo.

## 14. Gặp vướng thì kiểm tra gì?

| Hiện tượng | Cách xử lý |
| --- | --- |
| Không mở được localhost:3000 | Mở Docker Desktop; chạy lệnh mục 1; dùng `docker compose ps` để kiểm tra web/API/database. Ghi lỗi terminal nếu chưa lên |
| Không nhớ mật khẩu demo | Seed lại không khôi phục mật khẩu. Nhờ người quản trị/hỗ trợ dự án xử lý; không đoán mật khẩu liên tục hoặc xóa database |
| Không thấy menu/nút trong hướng dẫn | Kiểm tra tài khoản/role, đúng tab nhóm ở header, **Mở menu** trên điện thoại và form thu gọn; kiểm tra hồ sơ đã chốt/kỳ đã đóng chưa |
| Không tìm thấy nhân viên/kỳ | Xóa bộ lọc, kiểm tra phân trang và phạm vi role. Quản lý/nhân viên không thấy toàn công ty là đúng quyền |
| Không tính/chốt được | Đọc **Việc cần hoàn thành**: đủ KPI, thực tế, tổng trọng số, phản hồi bắt buộc; nếu dữ liệu mới thay đổi thì tính lại trước |
| Không gửi phản hồi được | Kiểm tra đúng người được giao, đã gửi chưa, hạn gửi, trạng thái hủy/chốt/đóng; HR không gửi thay reviewer |
| Phân công còn mở nhưng quá hạn | Nhờ HR mở dòng nhân viên trong kỳ → **Phân công phản hồi → Mở phân công [tên người đánh giá]**, chỉnh hạn sang thời điểm tương lai theo múi giờ thiết bị, **Lưu phân công → Xác nhận thao tác**. Người được giao tải lại rồi gửi; hồ sơ phải chưa chốt và kỳ còn ACTIVE |
| Không kích hoạt kỳ nháp | Kiểm tra còn kỳ ACTIVE khác không và thông báo về người tham gia/tài khoản; chưa đóng kỳ cũ thì chưa kích hoạt kỳ mới |
| Dữ liệu đã đổi ở nơi khác | Dùng **Làm mới dữ liệu** hoặc tải lại; đọc lại trước khi xác nhận. Không gửi lặp liên tục |
| AI không có nút tạo | Phải là HR, cấu hình bật và kết quả đủ điều kiện/hiện tại; xử lý **Cần tính lại** trước |
| AI báo quota/model/kết nối/đang xử lý | Ghi thông báo; chờ nếu đang xử lý, dùng **Làm mới tư vấn** hoặc **Kiểm tra yêu cầu vừa gửi** nếu có. Kiểm tra quota/key/model và Docker đã nhận `.env`; không tạo lặp nhiều lần |
| Điểm/tổng quan khác tài liệu | Dữ liệu đã thay đổi hoặc policy khác; đối chiếu chi tiết lần tính và lịch sử, không lấy ảnh demo ban đầu làm chuẩn tuyệt đối |

## 15. Phiếu nghiệm thu để ghi kết quả

Sao chép bảng vào ghi chú riêng, điền **Đạt / Chưa đạt / Bỏ qua**. Không đánh dấu đạt chỉ vì đã bấm nút; phải quan sát kết quả ở cột cuối. Tài liệu này là hướng dẫn, không phải bằng chứng rằng bạn đã thực hiện các thao tác.

Ngày thực hiện: … / … / … · Người thực hiện: … · Chu kỳ: …

| Mã | Nội dung | Kết quả | Ghi chú/bằng chứng cần lưu |
| --- | --- | --- | --- |
| NT01 | Web mở, đăng nhập/đăng xuất và đổi role được | … | Email đang thử, không ghi mật khẩu |
| NT02 | ADMIN xem tài khoản; HR xem tổ chức/kỳ | … | Menu và phạm vi đúng |
| NT03 | Quản lý lưu thực tế KPI Bình | … | Mã KPI, số đã nhập, vẫn còn sau tải lại |
| NT04 | Bình và quản lý gửi đúng phân công | … | Hai phản hồi đã ghi nhận |
| NT05 | Bình được tính điểm | … | Điểm: …; lần tính: …; không stale |
| NT06 | HR tạo AI chung và đọc lại được | … | Trạng thái lưu, nội dung; nếu bỏ qua ghi lý do |
| NT07 | Tư vấn nội bộ chỉ HR đọc | … | Bỏ qua nếu chưa tạo tư vấn nội bộ |
| NT08 | HR chốt Bình, nhân viên xem đúng điểm | … | Bằng chứng đã khóa |
| NT09 | Dũng tính mới, Linh tính lại, An còn lịch sử | … | Điểm/lần tính tương ứng |
| NT10 | Quản lý/nhân viên không truy cập vượt phạm vi | … | Role và dữ liệu thử |
| NT11 | Mọi người chốt xong, HR đóng kỳ | … | Kỳ CLOSED, kết quả vẫn đọc được |
| NT12 | Giao diện nhỏ và form thu gọn sử dụng được | … | Màn hình, thao tác vướng nếu có |
| NT13 | Tài khoản thử bị khóa không đăng nhập được | … | Tùy chọn; chỉ dùng tài khoản riêng |
| NT14 | Chuẩn bị/kích hoạt kỳ nháp đúng điều kiện | … | Tùy chọn; ghi đã kích hoạt hay chỉ xem |

Khi báo lỗi, gửi: **mã NT → role/email thử → tên kỳ/nhân viên → bước vừa làm → mong đợi → thực tế → ảnh thông báo**. Che thông tin cá nhân, không gửi API key, cookie hoặc mật khẩu. Ví dụ: “NT05, quản lý kỹ thuật, kỳ thực hành/Bình, sau Tính điểm: mong có điểm; thực tế báo thiếu phản hồi bắt buộc”.

Hoàn thành NT01–NT05, NT08–NT12 là đã thử luồng nghiệp vụ chính. NT06–NT07 xác nhận phần AI khi chủ động bật và gọi; NT13–NT14 mở rộng quản trị/kỳ mới. Mục nào chưa đạt thì ghi lại, xử lý rồi nghiệm thu lại đúng phần đó; không cần xóa và làm lại toàn bộ dữ liệu.
