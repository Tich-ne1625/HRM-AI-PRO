# Kế hoạch Phase 13 — AI cố vấn theo công việc và tiến trình

Ngày **25/11/2026**. **Kế hoạch để xem xét; chưa triển khai, chưa nghiệm thu.** Baseline **`2f2e29d`**, head **`20261125_0012`**. Đọc [dự thảo contract](../../phase-13-contract.vi.md), [báo cáo Phase 12](../../phase-12-report.vi.md) và [lộ trình tổng thể](../../nang-cap-quan-ly-hieu-suat-lien-tuc.vi.md).

## 1. Kết quả muốn đạt

Người dùng hỏi được AI **trước khi có kết quả đánh giá cuối kỳ**, trong đúng công việc/kế hoạch/check-in đang xem. AI dùng dữ kiện có nguồn để gợi ý cách xử lý, người dùng quyết định có dùng/chia sẻ không. Việc được tạo, lời khuyên được chia sẻ và kết quả công việc sau đó có đường truy vết; không chỉ có một khung chat trả lời chung chung.

Ba câu hỏi demo chính:

1. **Huy:** “Tôi đang chờ QA từ đối tác. Tôi nên làm gì tiếp, cần hỏi quản lý điều gì?”
2. **Mai Anh:** “Buổi check-in này tôi cần hỗ trợ Huy ở điểm nào? Phân biệt số đã xác minh và số còn chờ.”
3. **HR:** “Kỳ này đang tắc ở khâu nộp số, xác minh hay check-in? Tôi cần nhắc khâu nào?”

Đầu ra phải giải thích được **AI biết gì → dựa trên nguồn nào → chưa biết gì → gợi ý gì → ai xác nhận sử dụng → bản ghi nghiệp vụ nào phát sinh**. Không làm điểm/chốt CONTINUOUS, baseline/handover hoặc scheduler của Phase 14–15.

## 2. Đối chiếu với code và quyết định chính

| Hiện có | Cách dùng trong Phase 13 |
| --- | --- |
| `AIService` gắn `review_id`/calculation revision, HR yêu cầu sinh báo cáo | Giữ nguyên; thêm `coaching` không phụ thuộc có điểm cuối kỳ |
| `GeminiProvider` cố định `AnalysisOutput` sáu trường | Tái dùng cấu hình, lifecycle/timeout/lọc lỗi qua helper hẹp; schema và provider protocol coaching riêng |
| `authorize_domain_write`, guard tổ chức, session/role/version | Dùng lại cho reserve/complete/handoff; không giữ transaction trong lúc gọi AI |
| WorkPlan/WorkEvent/MeasurementRevision/ProgressSnapshot/CheckinPublication | Dựng ngữ cảnh và dẫn tới đúng nguồn/version, phân biệt xác minh/chờ/treo |
| `measurement_version` chỉ thể hiện thay đổi số đo | Fingerprint còn phải bao gồm work/check-in/nguồn được chọn; không dùng riêng counter này cho toàn context |
| HR metadata và check-in preparation riêng/chia sẻ | HR chỉ hỏi điều phối; loại private preparation khỏi context tự động |
| Manager `create_work` tạo TODO; employee tạo PROPOSED | Preview nói đúng hậu quả theo role; không gọi thao tác này “lưu nháp” đối với manager |
| `CheckinService.prepare` có version riêng của preparation | Dùng đúng expected version, không lấy nhầm version check-in; không ghi đè phần đang chia sẻ |
| Modal, thông báo SSE, cache fencing và chat nội bộ | Một panel AI theo ngữ cảnh, dùng lại lớp hiển thị; chat người–người vẫn riêng |

Chốt audience/scope, danh mục nguồn, kiểu handoff và giới hạn trong contract. Không thêm vector DB, tìm kiếm toàn công ty, API model mới, SDK mới hay hạ tầng queue chỉ để có hội thoại nhiều lượt.

## 3. Các task và thứ tự

| Task | Phụ thuộc | Đầu ra có thể review | Trạng thái |
| --- | --- | --- | --- |
| 0 | Phase 12 | Chốt nghiệp vụ, ví dụ, output, quyền, wireframe và budget | Chưa thực hiện gate |
| 1 | 0 | Migration/thread/turn/context/handoff/usage constraints | Chưa triển khai |
| 2 | 1 | Context builder có nguồn, giới hạn, tính toán và freshness | Chưa triển khai |
| 3 | 1–2 | Một lượt hỏi an toàn, schema/adapter/lease/replay/quota | Chưa triển khai |
| 4 | 2–3 | Hội thoại nhiều lượt và lịch sử riêng tư theo scope | Chưa triển khai |
| 5 | 3–4 | Panel AI theo ngữ cảnh cho nhân viên, quản lý và HR | Chưa triển khai |
| 6 | 2–5 | Preview/handoff/chia sẻ có người xác nhận và truy vết | Chưa triển khai |
| 7 | 0–6 | Demo, hồi quy, chất lượng câu trả lời, tài liệu và nâng cấp an toàn | Chưa triển khai |

Thực hiện theo lát cắt: một câu hỏi của Huy trên một work item → nguồn/đáp án đúng → Mai Anh riêng tư → HR metadata → lịch sử và các đề xuất có xác nhận. Không chờ cuối phase mới kiểm tra quyền hoặc rollback.

## Task 0 — Chốt hợp đồng và câu chuyện vận hành

- Đối chiếu head/working tree tại lúc bắt đầu; kế thừa baseline Phase 12, không suy ra đã có coaching.
- Chốt ba audience riêng, anchor bất biến, điều kiện DRAFT/ACTIVE/CLOSED: DRAFT tư vấn kế hoạch đọc được nhưng không tạo việc; ACTIVE cho tư vấn và handoff theo domain; CLOSED chỉ đọc/hỏi lại dữ kiện được phép, không mở ghi dữ liệu đã khóa.
- Kiểm tra điều kiện ghi/deadline thực tế của API nhận handoff, không chỉ điều kiện ẩn nút trên UI. Nếu thiếu chốt hạn hoặc scope cần thiết, sửa tại domain service và thêm regression trước khi mở đường từ AI; không cho handoff trở thành đường vòng.
- Chốt danh mục nguồn từng role, bộ chọn/giới hạn từng truy vấn và byte budget; lịch sử không lẫn scope; không gửi chuẩn bị riêng, chat riêng, 360 gốc hoặc HR_PRIVATE.
- Chốt schema output, cách thể hiện nguồn/tình trạng cũ và bộ tình huống/rubric. Khi không có mốc tiến độ, AI phải hỏi làm rõ thay vì tự suy ra không đạt.
- Wireframe desktop/mobile với bốn tab hiện có, panel AI và quy tắc chuyển panel/form, bản chưa gửi và focus. Chốt ba kiểu handoff trong contract, nói rõ PROPOSED/TODO/chuẩn bị riêng/comment chia sẻ.
- Chốt cấu hình hạn mức dự kiến và thông báo lỗi; xác định helper giao dịch cần tách từ domain service để receipt/entity commit cùng nhau, không nested transaction.

**Gate:** có input/đáp án mong đợi cho “thiếu số”, “số chờ chưa vào actual”, “QA bị chặn”, “không có mốc kỳ vọng”, “HR hỏi nội dung riêng”, “quản lý mất quyền”, “chia sẻ đoạn lời khuyên”; không còn quyết định ảnh hưởng FK/unique/private audience bị để sau migration.

## Task 1 — Schema và repository theo scope

- Module mới `apps/api/app/modules/coaching`; migration dự kiến `20261125_0013` nối head hiện có, kiểm tra lại số revision khi code.
- Tạo năm nhóm bảng trong contract; FK owner/anchor cùng cycle/plan, question/context/identity và receipt đã xác nhận bất biến; projection trạng thái có version.
- Unique actor/request UUID, thứ tự turn theo thread, partial unique RUNNING mỗi actor, constraint trạng thái/lease/hash. Budget bền vững/cập nhật nguyên tử, không phụ thuộc một replica.
- List/detail theo owner và quyền hiện tại trong SQL trước pagination; metadata DTO khác DTO nội dung. Tách lưu trữ nội dung riêng khỏi audit/log chung.
- Thiết kế nguồn đã mất quyền: không trả output/context hoặc chuyển nó sang history provider. Không dùng chỉ owner/thread ID để mở lại dữ liệu đã bị thu hồi.

**Gate:** fresh migration + metadata parity; FK/unique/check/immutability; upgrade fixture 0012 gồm LEGACY và CONTINUOUS giữ cột cũ/password/role/evidence. Chưa nạp lịch sử hội thoại từ dữ liệu cũ hoặc sửa DB chính.

## Task 2 — Context builder và nguồn dữ kiện

- Đọc nhất quán theo role/anchor/window; dùng lại scoped repository/progress aggregation, không tái hiện phép SUM/LAST/RATIO/MILESTONE bằng prompt.
- Lập allowlist source aliases/ID/version; lựa chọn ổn định có số lượng bị cắt, freshness manifest, dữ kiện số do server và timestamp/múi giờ. Không tự lưu progress snapshot khi hỏi.
- Bản nộp chờ, correction, VOID và nguồn treo giữ đúng nhãn; phiên bản lịch sử không bị thay bằng hiện hành. HR builder chỉ dùng dữ liệu coordination được phép.
- Loại định danh không cần thiết, private preparation, hội thoại khác, raw 360, HR_PRIVATE, nội dung chat/bảng tin và URL chưa fetch. Chuỗi trong bằng chứng được coi là dữ liệu không đáng tin.
- Không có time-phased expectation thì không cung cấp “chậm X%”; số học/khả năng hành động hiện tại do server, nhận xét AI là lời khuyên.
- Chốt byte/request/history/source cap; lịch sử thành công cùng scope tối đa sáu cặp, không tự gọi AI tóm tắt lịch sử.

**Gate:** unit/contract fixtures cho bốn phương pháp đo, null/0, chờ/VOID/reopen, timezone/cutoff, thiếu mốc; scope negative tests và sentinel bí mật không xuất hiện trong payload; membership/version đổi làm manifest đổi đúng; query count hữu hạn với 60 người/1.000 nguồn.

## Task 3 — Provider và một lượt hỏi có lease

- Schema coaching riêng; parser nghiêm ngặt chống JSON trùng key/non-finite/quá dài, citation/action allowlist; kiểm tra cả provider giả.
- Giữ `.env`, model cấu hình và SDK khóa; thử adapter bằng MockTransport trước, không dùng model alias hard-code. Lịch sử được serialize do server quản lý; chưa dùng phiên hội thoại lưu phía provider hoặc stream token.
- Reserve → gọi ngoài transaction → complete/fence; kiểm tra lại phiên/role/quan hệ quản lý, scope và freshness. Ghi thất bại có thể kiểm toán nhưng không trả output khi đã mất quyền.
- Chống double-click/replay, một lượt mỗi actor, giới hạn toàn coaching và counter cooldown/window nguyên tử. Lease quá hạn chỉ được xử lý bằng lệnh ghi; GET không âm thầm đổi lịch sử.
- Timeout/quota/model unavailable/invalid output trả mã lỗi an toàn, giữ câu hỏi. Retry rõ ràng là attempt mới; gửi lại UUID cũ không tính phí/call lặp. Không tự retry SDK và không hứa exactly-once billing.

**Gate:** race cùng UUID/khác payload/hai tab, vượt hạn mức giữa hai process, expired lease/late completion, revoke/đổi manager khi đang gọi, stale source, lỗi ghi audit/output; khẳng định không giữ connection/khóa DB trong lúc provider bị chặn. AI lỗi không ảnh hưởng thao tác Phase 11–12.

## Task 4 — Hội thoại và lịch sử riêng

- Create/list/detail thread/turn theo owner + scope đang có; không chuyển anchor/audience, không xem thread người khác cùng role.
- Chọn lịch sử có giới hạn theo quy tắc cố định, đánh dấu lời khuyên quá khứ là nội dung tham khảo tại thời điểm cũ; không đưa phát biểu AI cũ thành dữ kiện xác minh.
- Nếu nguồn bị thu hồi, che nội dung phụ thuộc và bỏ khỏi context về sau; nếu chỉ đổi số, giữ lời khuyên lịch sử với nhãn STALE. Nguồn/link kiểm tra quyền mỗi lần mở.
- Có trạng thái RUNNING/FAILED/SUCCEEDED và CURRENT/STALE/RESTRICTED riêng; poll không gọi provider, không sửa DB. Thread ACTIVE/CLOSED vẫn phải tuân quyền/workflow hiện hành.

**Gate:** history vượt giới hạn, cắt nguồn không âm thầm, chuyển người/role/logout và request về muộn không hiện dữ liệu cũ; HR không đọc được private turn của nhân viên/quản lý; không gộp lịch sử giữa hai scope vào request Gemini.

## Task 5 — Panel AI theo công việc

- Feature `apps/web/src/features/coaching`; nút theo Plan/Work/Checkin và HR coordination. Không thêm tab công việc chính thứ năm hoặc menu ADMIN.
- Header ngữ cảnh + “Riêng tư” + as-of; panel Trao đổi/Nguồn/Lượt trước; gợi ý câu hỏi chỉ điền ô nhập, bấm Gửi mới gọi AI.
- Tách rõ số thực tế/đang chờ, quan sát có nguồn/giả thuyết/gợi ý và giới hạn; click citation mở đúng phiên bản đã dùng trong cùng lớp UI.
- Reuse modal/focus/session fencing; một lớp AI/chat/thông báo đang hoạt động, tránh overlay chồng; giữ draft khi lỗi/chuyển tab, cảnh báo khi đổi người. Không lưu nội dung riêng vào localStorage chung.
- Trạng thái disabled/quota/timeout/lỗi cấu hình có nút xử lý rõ; rời panel không được mô tả thành đã hủy lượt provider. UI không hiển thị quyền/action mà server không cho phép.

**Gate:** component tests và browser 1280/390 px cho employee/manager/HR/admin, keyboard/Escape/đóng/mở lại, thay đổi role, mạng lỗi, AI disabled, số liệu stale, retry; tải lịch sử không phát sinh một request AI mới.

## Task 6 — Đưa lời khuyên vào công việc thật

- Preview server-owned từ block đã chọn; phân biệt nguyên văn AI và người dùng sửa/viết thêm. Destination và source thuộc scope, kiểm tra freshness/người nhận ở preview và confirm.
- CREATE_WORK dùng form đang có, người dùng tự chọn mã nguồn/goal/hạn; kết quả EMPLOYEE=PROPOSED, MANAGER=TODO sau xác nhận đúng nhãn.
- PREPARE_CHECKIN chỉ ghi phần riêng, kiểm tra version preparation, ghép bản đang có sau preview đầy đủ; nếu đã shared thì sang form thường, không đổi shared hoặc ghi đè ngầm.
- SHARE_EXCERPT chỉ vào comment một work item cùng plan, nêu người nhận và nhãn AI; không đưa cả thread hoặc nguồn ngoài quyền. HR coordination không có handoff cá nhân.
- Tách helper giao dịch tối thiểu từ service hiện có để cùng transaction cho domain entity + receipt + audit + notification. Không sao chép quyền/state machine, không nested begin/commit, không dùng URL/action tùy ý do model trả về.
- Double-submit/replay trả cùng entity; khác nội dung cùng UUID hoặc stale target/preview phải bị chặn. Gửi thông báo sau commit bằng hạ tầng sẵn có; nhận thông báo không mở thread riêng.

**Gate:** preview không có side effect; xác nhận mới tạo đúng một bản ghi; race hai tab, đổi quyền/deadline/target sau preview, lỗi receipt/audit/notification rollback trọn vẹn. Người nhận xem được đúng excerpt và nguồn được phép, không đọc lịch sử private. Gợi ý chưa dùng không thành “đã thực hiện”.

## Task 7 — Demo, chất lượng và nghiệm thu

- Bộ demo riêng dự kiến **13059/18059**, DB `_test` mới trên tmpfs, marker `continuous-coaching-demo-v1`. Kiểm tra cổng trước khi dùng; tái dùng câu chuyện Mai Anh–Huy và dữ kiện Phase 12 bằng domain services. Không đóng kỳ/main reseed, sửa `.env`, bật Gemini hoặc thay mật khẩu cũ để thử.
- Seed chỉ tạo dữ liệu hư cấu, không gọi provider hoặc chèn fake output thành lời khuyên Gemini thật. Fake provider dùng trong test/runner chuyên biệt, không được bật thành lời khuyên thật trong stack chính.
- Chạy bằng form: Huy hỏi khi chưa có điểm → xem nguồn → chọn đoạn → preview/chia sẻ → Mai Anh nhận thông báo nhưng không xem được thread → Mai Anh hỏi riêng/chuẩn bị check-in → xử lý hỗ trợ qua Phase 12 → số đổi → lời khuyên cũ mang nhãn cũ, số hiện hành đúng.
- HR hỏi khâu đang tắc và chỉ thấy metadata; ADMIN không thấy chức năng. Kiểm tra prompt injection trong body việc/nguồn, citation giả, output sai số, yêu cầu truy cập người khác, private source bị thu hồi, quota/timeout và cache sau đổi role.
- Bộ đánh giá cố định có đáp án kiểm tra được: câu trả lời bám dữ kiện, nêu thiếu thông tin, gợi ý khả thi và đúng thẩm quyền. Fake/MockTransport chứng minh contract, không thay đánh giá nội dung Gemini thật. Báo cáo tách rõ hai loại.
- Tùy cấu hình/ủy quyền hiện hữu khi triển khai, một lượt thử Gemini thật được thực hiện riêng trên dữ liệu hư cấu, request có giới hạn; ghi model/thời điểm/số request/kết quả hoặc lý do chưa kiểm chứng. Không coi live quality là đạt khi chỉ chạy fake.
- Unit/integration/race/privacy/schema/upgrade, web/quality/production build và Docker smoke; giới hạn concurrency phù hợp máy. Test PostgreSQL Windows dùng địa chỉ IPv4 rõ và connect timeout, ghi tiến độ để không lặp lỗi chờ kết nối Phase 12.
- Đo context size/query count/provider latency tách khỏi thời gian DB, xác nhận không N+1/quét toàn công ty. Không suy ra sẵn sàng production từ fixture nhỏ hoặc tạo số test đã đạt trước khi chạy.
- Cập nhật hướng dẫn theo role, API/database/architecture/AI design, báo cáo Phase 13 bằng số liệu thật. Backup/fingerprint trước nâng cấp, đối chiếu cột/bản ghi cũ/password/role và AI đã lưu. Chỉ deploy image qua các gate; chưa có bước này trong lượt lập kế hoạch.

**Gate cuối:** người chưa biết dự án làm được luồng “hỏi → hiểu nguồn/giới hạn → chọn → xác nhận → thấy việc/trao đổi phát sinh → kiểm tra kết quả sau đó”, không lộ private chat, không có tác vụ tự động ngoài quyền, không biến AI thành engine chấm điểm. Phase 11–12 và AI báo cáo cũ vẫn hoạt động khi Gemini bị tắt/lỗi.

## 4. Điều kiện bàn giao

Phase 13 chỉ được báo hoàn thành theo phạm vi đã kiểm chứng: nêu rõ offline contract đạt và live provider đã/chưa kiểm chứng. Khi các gate đạt mới lập Phase 14 về đối soát cuối kỳ, giải trình và điểm/chốt CONTINUOUS từ nguồn xác minh. Lời khuyên AI và việc người dùng chọn chia sẻ có nguồn gốc rõ, nhưng không tự trở thành điểm, bằng chứng đã nghiệm thu hoặc sự đồng ý của nhân viên.
