# Phase A

Engine nguồn: `papercraft-v1.2/`. Đã đọc README, CHANGELOG, master instructions, schema, generator, base engine, verifier và mẫu. Tái sử dụng nguyên thuật toán hình học, chọn hinge, packing và export. Adapter xử lý font portable, tiến độ, provenance và QA bổ sung.

Phạm vi: Cube 100/200/300 mm, Four-wall Frame 120×90×180 mm; US Letter 100%; React/TypeScript + Three.js; FastAPI + SQLite; jobs subprocess có timeout, revisions bất biến, download thực.

Trình tự: baseline engine → adapter/API → frontend → integration/regression và browser smoke → README/kết quả. Kết quả thực tế ghi trong TEST_RESULTS.md.

Giới hạn giữ nguyên: pairing tối đa 2 panel, shelf packing heuristic; cube 300 mm 24 trang, không có hinge liên tục; không tự dựng ảnh/mesh hoặc kích thước tùy chỉnh (Phase B/C). A4 đã được bổ sung theo yêu cầu. Hướng mountain/valley chưa được engine phân loại. Physical assembly NOT_TESTED.

## Hoàn tất Phase A — 2026-11-14

Đã có source backend/frontend, production build, SQLite jobs/revisions, sample exports, README/.env và tests. 6 backend tests, 2 browser tests đạt. Bốn mẫu đạt QA và khớp geometry/layout gốc. Sửa guide overflow và vị trí chữ header/footer ở adapter, không sửa nguồn geometry. Chi tiết: TEST_RESULTS.md. Docker có cấu hình nhưng chưa xác minh runtime; Phase B/C chưa triển khai.

## Kho template Noel — 2026-11-14

Mở rộng theo yêu cầu mới: thư viện 6 nhà gable có geometry và bộ xuất thật; vector artwork, texture 3D, bộ lọc/tìm kiếm/yêu thích, xem chi tiết và tạo dự án tự Generate. Giữ engine v1.2 nguyên vẹn và thêm module geometry cho nhà có mái. Mỗi revision lưu snapshot catalog để không phụ thuộc những thay đổi catalog sau đó. Đã tạo sample packages trong output/christmas. Chưa triển khai kích thước tự do, cửa khoét, sàn, ống khói; physical assembly NOT_TESTED.
