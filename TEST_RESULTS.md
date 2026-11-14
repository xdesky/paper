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
