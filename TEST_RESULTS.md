# Phase A — kết quả kiểm thử

Ngày: 2026-11-14. Môi trường macOS arm64, Python 3.12, React 19, Vite 7, Three.js 0.180. Phiên bản dependency chính xác nằm trong hai lockfiles.

## Kết quả cuối

- `python -m pytest tests -q`: **6 passed** trong 11.29 s.
- TypeScript `tsc -b` + `vite build`: **PASS**; bundle JS khoảng 740 kB (201 kB gzip).
- Playwright / Chrome headless, server production localhost: **2 passed** trong 7.4 s.
- Verifier độc lập v1.2 trên bốn bộ mẫu gốc: **4 PASS**.
- Bốn bộ sample mới chạy qua adapter production: **4 PASS**. Hình học, SHA-256 và `print_units` khớp chính xác fixtures gốc.

| Preset | Trang | Gấp liền | Dán | Kiểm tra QA / mẫu |
| --- | ---: | ---: | ---: | ---: |
| cube_100 | 3 | 3 | 9 | 33 PASS |
| cube_200 | 12 | 8 | 36 | 33 PASS |
| cube_300 | 24 | 0 | 48 | 33 PASS |
| house_frame | 2 | 2 | 2 | 31 PASS |

## Phạm vi đã kiểm tra

Backend tests gọi API và tiến trình engine production thực, không mock kết quả: tạo dự án, Generate/job, regression 4 mẫu, deterministic geometry/layout khi tạo lại, đọc geometry/pages/QA, tải tất cả payload và đối chiếu SHA-256, ZIP/MIME/attachment, revision cũ không bị ghi đè, đổi input chặn artifacts, invalid preset/input, project CRUD/duplicate, traversal, timeout và persistence sau restart.

Browser test: tạo dự án khung nhà → Generate → SVG và canvas 3D xuất hiện → chọn trang 2 → chọn mã nối → download ZIP thực → mở QA → desktop 1440 px/mobile 390 px (không tràn chiều ngang) → đổi mẫu chặn Export → đổi sang cube 200 và Generate tự lưu, sinh 12 trang. Không có pageerror. Test thứ hai làm mới seeded Cube 100 bằng adapter cuối.

Đã mở workspace thực trong Chrome, kiểm tra screenshot desktop/mobile, bản in PDF và guide bằng raster render. Đã sửa lỗi guide v1.2 tràn chú giải; đưa header/metadata printable vào lề an toàn, không thay đổi tọa độ cut/fold/calibration. Thêm kiểm tra legend đầy đủ và bounds của chữ để giữ regression. Đã sửa trạng thái chọn dự án khi tạo mới để Generate lấy đúng draft của dự án đó.

## Giới hạn xác minh

- Docker không có trên máy: Dockerfile/Compose chưa được build hoặc chạy, không đánh dấu PASS.
- Không thử giấy thật: `physical_assembly=NOT_TESTED` cho mọi mẫu.
- Vite cảnh báo chunk lớn do Three.js; build thành công. Chưa tối ưu lazy loading.
- Dependency upstream có cảnh báo deprecation (`fitz`, Starlette/httpx); không làm thất bại tests. Chưa nâng API engine để giữ nguồn gốc nguyên vẹn.
- A4 được kiểm thử trong đợt bổ sung bên dưới. Kích thước tùy chỉnh, reconstruction và arbitrary mesh chưa triển khai.

## Kho template Noel — kiểm thử mở rộng

- Backend: **13 passed** trong 21.08 s, gồm toàn bộ regression Phase A và 7 tests mới cho catalog/6 template.
- Browser: **3 passed** trong 12.0 s: hai tests Phase A và một luồng thư viện Noel từ bộ lọc/yêu thích/chi tiết đến tạo nhà, 3D/SVG và download ZIP. Kiểm tra các dự án có trước không bị thay đổi khi tạo từ template.
- Production TypeScript/Vite build: PASS (33 modules). Không thêm dependencies.
- 6 mẫu tạo thật trong `output/christmas`: tất cả QA PASS, 22 phép kiểm tra mỗi mẫu. Geometry có 6 mặt, 11 seam pairs, 3 hinges, 8 glue seams; bottom boundary được xác định rõ là mở.
- Mẫu gb_classic, gb_candy, gb_forest, gb_chalet, gb_frost: 2 trang. gb_mini: 1 trang.
- Đã kiểm tra trực quan ảnh preview dựng từ geometry, bản in vector có mái/tường/tai dán/mã ghép và guide tiếng Việt. Screenshot thư viện desktop/mobile và workspace được lưu ở `test-results/christmas-*.png`.
- Khóa snapshot catalog trong request của mỗi revision; ZIP manifest và SHA-256 payload được kiểm tra bằng API.
- Physical assembly NOT_TESTED. Không coi QA số học là chứng nhận đã cắt/gấp/dán bằng giấy thật.

## Mã kín trên tai dán + Print — Gingerbread 1.0.1

- Backend: 13 passed (21.28 s). Browser: 4 passed (15.9 s).
- Cả 6 mẫu Noel đạt QA mới: mỗi mã dán xuất hiện một lần trên tai; toàn bộ bounding box chữ nằm trong polygon tai dán; không còn tên mặt/mái trên bản in. Sơ đồ trong guide vẫn có đúng hai đầu cho mọi seam, kể cả hinge.
- Route Print trả tất cả SVG vector với @page US Letter / margin 0, chặn stale/failed; browser test xác nhận popup và lời gọi window.print (được intercept trong test để không in vật lý).
- Headless Chrome xuất bản Print thành PDF 2 trang: mỗi trang đo được 215.9 × 279.4 mm; thước chuẩn đo 39.9999957 mm. Không có thu nhỏ hoặc trang trắng phụ.
- Các dự án Noel có sẵn được regenerate thành revision mới; mẫu ZIP trong output/christmas và ZIP tổng đã cập nhật. Source geometry, kích thước và bố trí mảnh giữ nguyên.

## A4 — 2026-11-14

- Backend: 23 passed (34.96 s), gồm 10 mẫu A4, kích thước PDF/SVG, thước chuẩn 40 mm, QA, duplicate, invalidation khi đổi giấy và từ chối A3.
- Production TypeScript/Vite build: PASS.
- Browser: 4 regression tests passed; test A4 riêng passed (6.1 s) sau khi sửa test chọn lại đúng dự án khi reload. Xác nhận lưu A4, Generate, SVG 210×297, popup Print và ẩn Print khi có thay đổi chưa xuất lại.
- PDF tải xuống: A4 210×297 mm trong sai số 0.01 mm. Chrome Print PDF: 2 trang, 209.889×297.011 mm do làm tròn kích thước trang của trình duyệt; thước 39.9993 mm, không co mẫu hoặc thêm trang trắng.
- Screenshot: test-results/a4-workspace.png. Browser PDF: test-results/browser-printed-a4.pdf.

## American Premium — 2026-11-16

- Backend: **63 passed** (56.86 s), gồm toàn bộ 26 template trên Letter và A4, 4 mẫu Phase A và regression API.
- Browser: **6 passed** (34.2 s): thư viện, tìm kiếm/lọc 20 Premium, 10 model families, chi tiết 8 mặt/4 mảnh Dutch Colonial, 3D, Generate A4, Print và mobile overflow.
- Production build PASS. 20 package A4 tạo sẵn đạt QA PASS; ZIP tổng chứa đủ 20 ZIP dự án.
- Mái phẳng/mái một dốc có mảnh mái đơn; kiểm định PDF đọc cả line, rectangle và quadrilateral để đối chiếu đường cắt. Hinge count và seam map kiểm tra theo geometry thật.
- Đã xem montage 10 dáng nhà và workspace Dutch Colonial. Họa tiết in vector, không phải khối hiên/cửa/ống khói rời. Physical assembly NOT_TESTED.

## Christmas Deluxe v3 — trang trí và phụ kiện

- Backend **90 passed**, 70.76 s. Kiểm tra 26 mẫu trên A4/Letter; họa tiết nằm trong mặt cắt, phụ kiện nằm trong đế, khe cây khớp nhau, hai khối quà có 12 cạnh chung kín.
- Mỗi package có 47 mục QA: geometry nhà, kích thước trang, đường cắt PDF/SVG, thước 40 mm, vị trí mã trên tai dán; phụ kiện không chồng nhau, đường cắt PDF đối chiếu polygon, mã quà nằm kín trên tai, guide có hai đầu ghép.
- Browser **6 passed**, 45.8 s: library, 3D, Generate A4, chọn trang phụ kiện, Print đầy đủ 4 trang cho nhà tiêu chuẩn, download và kiểm tra mobile.
- Build TypeScript/Vite PASS. 26 package A4 phiên bản 3 đạt QA PASS và được đóng gói riêng, giữ bộ cũ.
- Đã xem preview nhà + tiểu cảnh, ảnh workspace, render Poppler trang cây/quà và trang hướng dẫn mã ghép. Đế là tấm phẳng rời; không coi QA số học là thử lắp giấy thật.

## Trang trí theo ảnh tham khảo — v3.1

- Backend **91 passed** trong 111.48 s. Kiểm tra thêm chữ ký hình học trước/sau của cả 26 mẫu: panels, vertices, seams, bounds bố trí và toàn bộ đường viền phụ kiện không đổi.
- 26 package A4 xuất thật, tất cả QA PASS. Họa tiết dùng cùng dữ liệu vector cho PDF, SVG và texture 3D; bài test kiểm tra artwork không tràn khỏi panel vẫn PASS.
- Đã xem preview 3D và render Poppler bản in mặt nhà; mã vẫn chỉ trên tai, họa tiết không chèn lên mã. Hiệu ứng nổi là minh họa in trên giấy; không thêm chi tiết kết cấu theo ảnh tham khảo.

## Mái đua v4

- Backend **144 passed**, 136.73 s: 26 mẫu A4/Letter và 53 tests bổ sung cho lớp mái phủ, artwork, mặt đỡ, nếp gấp, legacy snapshot.
- Kiểm định mái phủ: bao phủ mái khung; song song/offset 0.4 mm; mép trước/sau 6 mm; hai đầu seam khớp; nếp gấp không bị cắt; diện tích không chồng lấn; fits cả Letter và A4 ở 100%.
- Chữ ký panel/seam/layout mái KHUNG, tường và hai trang phụ kiện cũ không đổi; riêng mái phủ là geometry bổ sung được người dùng yêu cầu.
- PDF/SVG mái phủ được so sánh đường cắt với polygon và đo thước 40 mm; kiểm tra mã R trên tai, sơ đồ hướng dẫn có đủ hai đầu. Đã render Poppler trang mái Dutch Colonial và xem preview 3D.
- Build TypeScript/Vite PASS. Chưa thử lắp giấy thật; không coi kiểm thử phần mềm là chứng nhận độ cứng giấy/keo.

- Browser v4: **6 passed** (1.6 phút). Chrome Print tạo đúng 5 trang cho mẫu tiêu chuẩn ở A4/Letter; thước 40 mm trên cả trang mái mới giữ đúng tỷ lệ. Bộ ZIP tổng đủ 26 ZIP con, kiểm tra CRC PASS.

## Preview cuộn liên tục — 2026-11-17

- Build TypeScript/Vite PASS (34 modules).
- 3 regression browser flows passed: A4/Print, Premium/mái đua và Phase A/SVG/download.
- Bài kiểm thử riêng continuous-preview passed (10.3 s): bỏ dropdown, render đủ 5 trang, cuộn bằng nút và bằng thanh cuộn, trạng thái nút đầu/cuối, zoom 200%, lớp mã áp dụng toàn bộ trang, chọn seam, lỗi tải một trang + retry, mobile không tràn ngang, trở lại Workspace.
- Lần chạy đầu thất bại ở bước kiểm thử mobile do chưa đưa vùng preview vào viewport ngoài; đã sửa thao tác test và xác minh lại PASS.

## Cá nhân hoá bảng tên — 2026-11-17

- Backend **197 passed**, 159.16 s. 53 tests mới bao gồm tên tiếng Việt và tên dài 24 ký tự trên 26 mẫu, vùng chữ nằm trong mặt trước, kích thước chữ tối thiểu, chuẩn hoá Unicode, preview, export, snapshot, duplicate, sửa/xoá tên và từ chối ký tự không hỗ trợ.
- Browser: A4/Print và continuous preview PASS; luồng cá nhân hoá riêng PASS (16.2 s), gồm chọn mẫu mini, preview tên Việt, mobile không tràn ngang, tạo dự án, tải lại, Print, sửa và xoá tên.
- TypeScript/Vite build PASS (35 modules). Đã xem ảnh công cụ và render Poppler PDF in từ Chrome.
- Kết cấu và đường cắt giữ nguyên; bảng tên là lớp artwork riêng trên mặt FRONT.

## Nhà 2 gian — 2026-11-17

- Thêm 6 template, 3 hình khối × 2 phối màu. Toàn bộ backend: **245 passed**, 184.89 s.
- Kiểm tra mỗi mẫu có hai đỉnh mái, bốn mặt mái và đúng một mối nối lõm; A4 có tên tiếng Việt, Letter, PDF/SVG/ZIP, mái phủ và kết cấu 26 mẫu cũ đều PASS.
- Sửa sai số kiểm tra biên phụ kiện ở mức 1e-6 mm (tọa độ 19.999999999999993 thay vì 20); không dịch chuyển hoặc thu nhỏ mảnh in.
- TypeScript/Vite build PASS. 6 bộ mẫu A4 QA PASS; ZIP tổng đủ 6 ZIP con và kiểm tra CRC PASS.
- Chrome E2E PASS (17.6 s): lọc đúng 6 mẫu 2 gian, mở Viết tên, tạo nhà, xem 3D, kiểm tra mối nối mái lõm, Print đủ trang và tải ZIP. Ảnh: `test-results/two-bay-personalize.png`; PDF: `test-results/two-bay-browser-print.pdf`.

## Noel nâng cao & bản tự tô — 2026-11-17

- Thêm 6 mẫu nâng cao; dời tai dán các cạnh tường–mái lên mặt mái cho bộ mới để tránh chồng tại thung mái hẹp. Hướng dẫn mã ghép tự sang trang khi vượt 23 mối nối.
- Bản tự tô tái sử dụng đúng vị trí và đường cắt/gấp từ SVG màu; QA đối chiếu từng trang và kích thước PDF. Nét kem dạng compound path giữ lỗ trong, không che ô cửa và họa tiết bên dưới.
- Kiểm thử riêng 6 mẫu × A4/Letter, bảng tên và API: 90 passed (40.06 s).
- Sáu bộ mẫu A4 xuất thành công, mỗi ZIP có PDF/SVG màu và tự tô. Đã xem ảnh tháp mái gãy và trang PDF tự tô biệt thự mái kép.
- Hồi quy toàn bộ: 300 passed; 2 trường hợp kiểm thử cũ bị chọn nhầm mẫu biệt thự mái kép vào nhóm 2 gian mái thường (giả định 8 mặt). Đã giới hạn bài cũ đúng bộ sưu tập Nhà 2 gian và chạy lại: 6 passed. Mẫu biệt thự mới được bao phủ bởi kiểm thử nâng cao A4/Letter.
- Chrome: 2 passed (26.8 s), gồm chuyển bản màu/tự tô, preview, Print, tải PDF đúng loại, giữ revision và hồi quy cuộn/lớp hiển thị. TypeScript/Vite build PASS; ZIP tổng 6 mẫu kiểm tra CRC PASS.

## Ống khói — 2026-11-17

- 61 tests PASS (100.62 s): xuất toàn bộ 38 mẫu, hình học 20 loại ống khói, khe khép 4 tường, diện tích net/tai không chồng, chân đúng mặt mái, miệng trên phẳng và rỗng, vừa A4/Letter, bảo toàn 26 kết cấu cũ và snapshot không có ống khói.
- TypeScript/Vite build PASS. Đã xem preview mẫu cổ điển và trang PDF ống khói tự tô.
- Chrome: 2 passed (15.8 s), gồm 4 mặt ống khói trong 3D, trang in riêng màu/tự tô, Print đủ trang và hồi quy preview cuộn liên tục.

## Bố trí ống khói — 2026-11-17

- 20 tests PASS: bỏ ống khói trên dáng cao, chọn mái dài theo chiều dài dốc, Saltbox và ảnh đối xứng của hình học, quy tắc mái bằng nhau, giữ snapshot cũ và kết cấu thân nhà.
- Xuất Saltbox A4, Dutch Colonial Letter và Forest không ống khói: QA PASS, gồm PDF màu/tự tô. Đã xem preview Saltbox với ống khói chuyển sang mái dài bên trái.
