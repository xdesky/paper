# Print Play Magic Studio — Phase A

Ứng dụng local React/TypeScript + Three.js và FastAPI, tái sử dụng engine Python v1.2 được cung cấp. Chọn Cube 100/200/300 mm hoặc khung nhà bốn tường 120×90×180 mm → Generate → xem 3D/SVG → QA → tải PDF/SVG/Guide/OBJ (cube)/PNG/JSON/ZIP thật.

## Chạy ngay trên workspace hiện tại

Dependencies và frontend production đã được cài/build tại workspace này:

```sh
./scripts/start-local.sh
```

Mở http://127.0.0.1:8000. Nếu server đã chạy thì mở URL trực tiếp. API docs: http://127.0.0.1:8000/docs.

Lần chạy đầu trên database trống tự tạo bốn dự án mẫu và Generate Cube 100 mm. Các mẫu khác bấm Generate để tạo. Generate tự lưu thiết lập đang chỉnh. Mỗi lần tạo lại dùng revision mới; bản đã xuất không bị ghi đè. Khi đổi mẫu, bản cũ bị chặn tải cho đến khi revision mới đạt QA.

## Cài mới

Yêu cầu Python 3.12+, Node.js 22.12+, pnpm 11.25.0. Chạy từ thư mục repository:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
corepack enable
corepack prepare pnpm@11.25.0 --activate
pnpm --dir frontend install --frozen-lockfile
./scripts/build-frontend.sh
cp .env.example .env
./scripts/start-local.sh
```

`requirements.lock.txt` và `frontend/pnpm-lock.yaml` ghi phiên bản đã kiểm thử. `requirements.txt` mô tả dependencies trực tiếp; file lock có cả dependencies gián tiếp. Adapter lấy font DejaVu đi kèm Matplotlib, không phụ thuộc đường dẫn font Linux của engine.

Development sau khi cài đặt, dùng hai terminal:

```sh
.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

```sh
pnpm --dir frontend dev
```

Frontend dev: http://127.0.0.1:5173; Vite proxy `/api` về backend 8000. Chỉ `start-local.sh` tự nạp `.env`; khi chạy uvicorn trực tiếp, export biến môi trường cần dùng. Không dùng nhiều uvicorn workers: SQLite/job runner hiện thiết kế cho một process server.

## Docker (cấu hình có sẵn, chưa kiểm thử trên máy này)

```sh
docker compose up --build
```

Mở http://127.0.0.1:8000. Dữ liệu lưu trong named volume `studio-data`. Máy triển khai hiện không có Docker, nên không coi image build/run là đã được xác minh.

## Chức năng đã triển khai

- Tạo, đổi tên, sao chép, xóa dự án; bốn preset Phase A; SQLite persistence.
- Revision snapshot bất biến. `version=1.2.0` là phiên bản schema/engine gốc, `revision` là lần sinh của dự án.
- Queue tối đa 8 jobs, một subprocess engine mỗi lần; timeout mặc định 180 s; lỗi và trạng thái lưu SQLite. Job dở dang khi server khởi động lại được đánh FAILED.
- Progress theo các hàm engine thực sự chạy. Chọn hinge/trải mặt/tạo tai dán là một stage tổng hợp vì v1.2 gộp các thao tác này.
- Viewer Three.js từ tọa độ panel trong Model Spec, xoay/zoom/pan, wireframe; SVG vector đa trang, zoom/layers; chọn mã cạnh để highlight seam 3D.
- PDF vector, SVG từng trang, assembly guide đã sửa tràn chú giải và thêm ảnh 3D dựng từ geometry, OBJ cube, PNG, Model Spec, QA và ZIP.
- Metadata provenance trong PDF/SVG/PNG/OBJ; JSON và manifest ghi model ID, engine version, project revision, geometry hash, input snapshot hash. Manifest liệt kê SHA-256 của các payload; không tự hash manifest hoặc ZIP chứa chính nó.
- QA trước và sau xuất: source polygons/vector contours, seam pairs, hinge/tab, overlap/bounds, scale, PDF/SVG 40 mm, số trang, mã nối PDF đúng hai lần, vùng chữ và guide legend.
- Không cho download khi project DRAFT/GENERATING/STALE/FAILED. Path traversal bị chặn. Không có endpoint upload hoặc thực thi mã từ người dùng.

## Tests và mẫu xuất

```sh
.venv/bin/python -m pytest tests -q
./scripts/build-frontend.sh
# Cần server ở cổng 8000 và Google Chrome đã cài:
cd frontend
pnpm exec playwright test
```

E2E tạo dữ liệu test và làm mới dự án seeded Cube 100 mm. Chạy trên database phát triển riêng khi muốn tránh thay đổi demo. Chi tiết kết quả và giới hạn xác minh: `TEST_RESULTS.md`.

Bộ mẫu mới sinh từ adapter production nằm trong `output/samples/`:

| Mẫu | Trang | Mảnh cắt | Gấp liền | Mối dán |
| --- | ---: | ---: | ---: | ---: |
| Cube 100 mm | 3 | 3 | 3 | 9 |
| Cube 200 mm | 12 | 12 | 8 | 36 |
| Cube 300 mm | 24 | 24 | 0 | 48 |
| House frame 120×90×180 mm | 2 | 2 | 2 | 2 |

Mỗi thư mục có `project.zip` chứa bộ xuất đầy đủ. `scripts/generate_samples.py` tạo lại mẫu khi thư mục đích chưa tồn tại để tránh ghi đè snapshot. Bộ mẫu gốc vẫn nguyên vẹn trong `papercraft-v1.2/`.

## Cấu trúc và API

- `backend/app.py`: FastAPI, SQLite, projects/revisions, bounded queue, timeout và artifact access.
- `backend/worker.py`: adapter portable, progress, gọi nguyên engine v1.2, metadata, guide layout, QA bổ sung và ZIP.
- `papercraft-v1.2/`: nguồn engine và fixtures gốc; không sửa thuật toán.
- `frontend/src/`: workspace tiếng Việt, Three.js và SVG viewer.
- `tests/`, `frontend/e2e/`: regression/integration/browser tests.
- `.data/`: SQLite và `<project-id>/<revision>/artifacts/`, request snapshot, progress và worker log; không commit.

API: `/api/health`, `/api/presets`, `/api/projects`, `/api/projects/{id}` (GET/PATCH/DELETE), `/duplicate`, `/generate`, `/geometry`, `/pages`, `/validation`, `/artifacts`, `/artifacts/{filename}`, `/api/jobs/{id}`. Route `/generate` tự tạo/khóa revision, không có nút Lock Model hoặc endpoint versions riêng trong Phase A. Xóa dự án khỏi database sẽ ngừng phục vụ mọi file; lịch sử artifact trên đĩa được giữ lại, chưa có UI restore/purge.

## Giới hạn / chưa triển khai

- US Letter hoặc A4 portrait, tỷ lệ 100%; lề trái/phải 8 mm. Tai dán mẫu Phase A 7 mm cố định. Cỡ tùy chỉnh và kéo thả bố trí chưa hỗ trợ.
- Pairing tối đa 2 panel; shelf packing heuristic. Cube 300 mm không ghép hai ô 150×150 lên cùng trang, không co nhỏ. Chưa phân loại mountain/valley theo hướng mặt.
- Image upload/reconstruction, mesh inspection/unfold bất kỳ, prompt tự do: Phase C, chưa triển khai. Không có API AI hoặc khóa trả phí.
- Không có authentication/multi-user/cloud deployment. Dùng localhost; không public server này trực tiếp.
- UI chủ yếu tiếng Việt, guide/QA engine giữ tiếng Anh; chưa có bộ chuyển ngôn ngữ EN/VI.
- Lớp SVG chỉ điều khiển cách xem; không thay đổi bản in xuất. Mối liền phẳng không có đường ở giữa theo đúng engine, không vẽ đường gấp giả.
- Physical assembly luôn `NOT_TESTED`. PASS là kiểm định tự động, không phải chứng nhận cắt/dán thực tế. In Actual Size / 100%, không Fit to Page; đo vạch 40 mm trước khi cắt.

## Kho template nhà bánh gừng Noel

Mở mục **Kho template Noel** trên sidebar, hoặc URL `http://127.0.0.1:8000/#templates`.

Bộ sưu tập đầu tiên có 6 mẫu: Ngôi nhà bánh gừng, Tiệm kẹo Giáng sinh, Căn nhà rừng thông, Chalet phủ tuyết, Ngôi nhà băng đường, Nhà bánh gừng mini. Có tìm kiếm, lọc bộ sưu tập, lưu yêu thích trên trình duyệt và xem thông số chi tiết.

Bấm **Dùng mẫu này** để tạo một dự án riêng và tự Generate. Khi QA đạt, workspace hiển thị nhà 3D có họa tiết, bản in vector và nút Export All. Thay đổi hoặc tạo lại một dự án vẫn theo cơ chế revision bất biến của Phase A.

- Hình học: 4 tường (2 mặt ngũ giác) và 2 mặt mái, đáy mở; 3 mảnh cắt, 3 nếp gấp liền, 8 mối dán. Không có sàn hoặc ống khói.
- Các mẫu tiêu chuẩn dùng 2 tờ US Letter; mẫu mini dùng 1 tờ. Tai dán 5 mm, in 100%.
- Họa tiết kem, cửa, cửa sổ, cây thông, kẹo và bông tuyết là vector trên mặt giấy. Cửa/cửa sổ **không khoét rỗng**.
- Ảnh thumbnail, preview PNG và texture 3D đều dựng từ chính geometry/họa tiết của template; không dùng ảnh AI giả bản in.
- Snapshot revision lưu toàn bộ thông số template và phiên bản. Geometry hash và design hash được lưu riêng; gói ZIP có manifest với hash từng file.
- Guide tiếng Việt ghi mã ghép và góc gấp thực. Mọi mẫu giữ `physical_assembly=NOT_TESTED`.

Source: `backend/template_catalog.py` (catalog), `backend/gingerbread.py` (mở rộng gable house), `frontend/src/TemplateLibrary.tsx` (thư viện). Phần mới tái sử dụng hàm tạo tai dán, rigid transforms, PaperUnit và shelf packing của v1.2; không thay đổi geometry cube/frame gốc.

API bổ sung: `GET /api/templates`, `GET /api/templates/{id}/preview.svg`. Các template được tạo/xuất bằng API projects/generate/artifacts hiện có. Không có file download giả hoặc hardcode kết quả QA.

Bộ file tạo sẵn: `output/christmas/<template-id>/project.zip`. Sinh lại vào thư mục trống bằng:

```sh
.venv/bin/python scripts/generate_christmas_samples.py
```

Kiểm thử thêm: `tests/test_templates.py`, `frontend/e2e/templates.spec.ts`. Catalog chỉ cung cấp các kích thước đã kiểm định; chỉnh kích thước tự do chưa hỗ trợ. Có thể đổi sang A4 trong Workspace → Giấy & bản in.

### Mã ghép kín đáo và Print (Gingerbread 1.0.1)

Bản in Noel chỉ ghi mã nhỏ trên tai dán, được che sau khi ráp. Bỏ mã và tên mặt khỏi họa tiết trang trí. `assembly_guide.pdf` bổ sung sơ đồ từng trang có đầy đủ hai đầu mã cạnh và tên panel để tra vị trí nhận tai dán. QA mở lại PDF và kiểm tra toàn bộ vùng chữ mã nằm trong tai dán; mã trên sơ đồ phải đủ hai đầu.

Nút **Print** trong workspace mở một tab in riêng và gọi hộp thoại in của trình duyệt. Tab này dùng toàn bộ SVG vector đã xuất, khổ US Letter 215.9 × 279.4 mm hoặc A4 210 × 297 mm theo dự án, không in giao diện workspace; checkbox lớp xem không ảnh hưởng bản in. Chọn khổ giấy tương ứng, Scale 100%, tắt headers/footers; nếu hộp thoại không tự mở, bấm **Print / In ngay** trong tab. Route `/api/projects/{id}/print` chặn revision chưa đạt QA hoặc đã stale như download.

### Khổ A4

Trong Workspace → **Giấy & bản in → Khổ giấy**, chọn **A4** rồi bấm **Generate**. Khổ giấy được lưu theo dự án và snapshot revision; đổi khổ giấy cần tạo lại bộ xuất. PDF (`printable_a4.pdf`), SVG, hướng dẫn và Print dùng cùng khổ A4 210 × 297 mm; hình học không bị co giãn. Dự án cũ vẫn mặc định US Letter. Kiểm thử: `tests/test_a4.py` (10 mẫu) và `frontend/e2e/a4.spec.ts`.
