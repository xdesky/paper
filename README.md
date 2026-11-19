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

### American Premium — 20 template / 10 kiến trúc

Kho template → **American Premium** gồm Cape Cod, Colonial, Saltbox, Dutch Colonial, Craftsman, Farmhouse, Ranch, Brownstone, A-frame và Modern Shed. Mỗi kiến trúc có Heritage Christmas và Midnight & Gold; giữ 6 mẫu Noel cũ (tổng 26).

Hình học là vỏ nhà đơn giản hóa lấy cảm hứng từ kiến trúc Mỹ, với mái hai dốc, mái lệch, mái gãy gambrel, mái phẳng và mái một dốc. Mặt đứng có họa tiết vector gạch/ván, cửa chớp, cửa chia ô và vòng lá. Cửa, phào và họa tiết là chi tiết in; chưa có hiên, cửa sổ mái hoặc ống khói khối rời. Tất cả đáy mở, chưa lắp giấy thật.

Mỗi mẫu hỗ trợ A4/US Letter 100%, PDF, SVG, OBJ, texture 3D, hướng dẫn ghép và ZIP. Mã ghép nằm trên tai dán; sơ đồ hướng dẫn ghi cả hai đầu. Metadata số mặt, mảnh, nếp gấp và mối dán tính theo geometry, không cố định 6 mặt.

Bộ A4 tạo sẵn: `output/american-premium-a4/american-premium-20-templates-a4.zip` (20 ZIP dự án). Catalog 2.0.0, generator gingerbread-2.0.0; snapshot dự án cũ vẫn được giữ.

### Christmas Deluxe v3 — nhà và tiểu cảnh

Cả 26 mẫu có trang trí kem tuyết, hạt đường, đèn màu, viền kẹo và sao. Phối Heritage chuyển sang nâu bánh gừng/mái đỏ; Midnight giữ tông xanh và vàng. Họa tiết vector dùng chung cho 3D, preview, PDF và SVG.

Mỗi bộ thêm 2 trang phụ kiện: đế tuyết phẳng rộng hơn nhà 60 mm và sâu hơn 70 mm (dán lên bìa cứng), 1 cây thông 65 mm gồm 2 mảnh ghép chéo khe 0.6 mm, 2 hộp quà kín 20 mm và 16 mm. Nhà vẫn đáy mở đặt lên đế rời. Cây in một mặt, có thể tô xanh mặt sau; khe có thể cần keo tùy giấy. Hộp quà có 7 mối dán/mẫu, mã chỉ nằm trên tai và sơ đồ hướng dẫn có cả 2 đầu.

PDF chính, SVG/Print đã gồm phụ kiện; có thêm `accessories.pdf`, `accessories_guide.pdf` và `display_scene.obj`. Preview 3D thể hiện đầy đủ tiểu cảnh. Hướng dẫn chính cũng có trang lắp phụ kiện. Đối với dự án cũ, bấm Generate để tạo revision mới; các file revision cũ được giữ nguyên.

Bộ A4 mới: `output/christmas-deluxe-a4-v3/christmas-deluxe-26-templates-a4.zip`. Đã kiểm định bằng phần mềm, chưa thử cắt/gấp/dán giấy thật.

### Confectionery v3.1 — họa tiết theo ảnh tham khảo

Lớp trang trí mới dùng nền bánh gừng, kem trắng dày có bóng đổ, kẹo đỏ/xanh bóng, peppermint xoáy, lá holly, cửa vòm vàng và cửa đỏ có vòng lá. Cây thông có tuyết và quả châu; hộp quà có nơ in; đế có tuyết đùn và đường đá. Tất cả là họa tiết vector in phẳng, hiệu ứng nổi được tạo bằng bóng/điểm sáng. Không thêm ống khói hoặc bộ phận hình học theo ảnh.

Module `backend/confectionery.py` chỉ tạo artwork; khung nhà, đế, cây/quà, seam và layout giữ nguyên. `tests/test_structure_preserved.py` đối chiếu chữ ký 26 bộ phận với dữ liệu lưu trước khi sửa họa tiết. Bộ A4 mới: `output/christmas-reference-a4-v3.1/christmas-reference-26-templates-a4.zip`. Generate tạo revision mới cho dự án cũ.

### Mái đua phủ tuyết v4

26 mẫu có thêm lớp mái phủ thật, đua 6 mm ở trước/sau và 4 mm đo dọc dốc ở hai mép ngoài. Mái khung cũ, tường, đế và phụ kiện giữ nguyên để làm bề mặt đỡ/dán. Lắp mái khung trước, gấp và ghép mái phủ, căn sống mái rồi dán lên trên; không ép phần đua xuống tường. Bản 3D dùng khoảng cách 0.4 mm để thể hiện giấy/keo.

Mái phủ có 1 trang in riêng trên A4/Letter, 1 mảnh cho mái thường hoặc 2 mảnh cho mái gãy Dutch Colonial; mã R chỉ in trên tai dán. Guide bổ sung hướng dẫn và sơ đồ đầy đủ hai đầu ghép. Số trang/mảnh trong thư viện và Print đã bao gồm mái phủ. Không thu nhỏ mô hình để vừa giấy. Snapshot cũ không có tham số mái đua vẫn tạo kết cấu khít tường như trước.

Trang trí thêm bông tuyết, holly, điểm sáng, viền kem và diềm tuyết. Viewer 3D có bóng đổ và mặt dưới mái màu giấy. Bộ mẫu: `output/christmas-overhang-a4-v4/christmas-overhang-26-templates-a4.zip`. Chưa thử lắp giấy thật.

Tham khảo hình thức phần đua đầu hồi/mép mái: HUD Residential Structural Design Guide, hình 5.9, https://www.huduser.gov/Publications/pdf/res2000_3.pdf . Đây là tham khảo hình thức; kết cấu mô hình giấy do ứng dụng tạo và kiểm định riêng.

### Preview cuộn liên tục

Trang in 2D hiển thị tất cả SVG theo chiều dọc trong cùng vùng cuộn. Nút ‹ / › cuộn tới trang trước/sau; bộ đếm cập nhật theo vị trí xem, không thay trang đang render. Zoom và lớp Cắt/Gấp/Tai dán/Mã cạnh áp dụng trên mọi trang. Trang tải lỗi có nút thử lại riêng; đổi dự án/revision hủy yêu cầu cũ và đưa preview về đầu.

### Công cụ tạo nhà cá nhân hoá

Chọn **✦ Tạo nhà riêng** ở thanh bên, hoặc **✦ Viết tên** trên mẫu trong thư viện. Chọn một trong 26 mẫu, nhập tên (tối đa 24 ký tự, hỗ trợ tiếng Việt có dấu), chọn A4/US Letter và bấm **Tạo nhà & bản in**. Preview cập nhật khi nhập. Bảng tên đặt ở vùng an toàn trên mặt trước; tên dài tự xuống hai dòng và co vừa bảng. Để trống để bỏ bảng tên.

Tên được lưu riêng với tên dự án, đi theo bản sao và snapshot revision. Trong Workspace có ô **Tên trên ngôi nhà** để sửa/xoá, sau đó Generate. Đổi tên in sẽ vô hiệu bản xuất cũ. Chữ dùng outline vector từ DejaVu Sans Bold để SVG, PDF, preview và texture 3D hiển thị thống nhất, không phụ thuộc font của máy in.

API thêm `personal_name` vào create/edit project và `POST /api/templates/{id}/personalize-preview`. SQLite migration giữ dữ liệu cũ với tên in mặc định rỗng. Preview không tạo dự án hoặc revision.

### Nhà bánh gừng 2 gian — catalog 4.1.0

Kho template → **Nhà 2 gian** thêm 6 mẫu: Song đôi, Cổ tích (gian chính–gian phụ), Nông trại Noel; mỗi kiểu có Heritage Christmas và Midnight & Gold. Tổng thư viện hiện có 32 mẫu. Hai gian chung thân nhà đáy mở, có hai chóp mái thật và thung mái lõm nối giữa, không có vách ngăn nội thất. Mỗi gian có cửa, cửa sổ, hoạ tiết và lối đi riêng trên đế tuyết. Giữ mái đua, cây thông, hộp quà và bảng tên cá nhân hoá; bảng tên nằm dưới vùng thung mái để không đè vào đường cắt.

Hỗ trợ A4/US Letter ở tỷ lệ 100%, hướng dẫn phân biệt đỉnh mái lồi và thung mái lõm. Bộ 6 file mẫu A4: `output/two-bay-a4-v4.1/nha-banh-gung-2-gian-6-mau-a4.zip`. Đã kiểm định hình học và bản in; chưa lắp giấy thật.

### Noel nâng cao & bản tự tô — catalog 4.2.0

Thêm 6 mẫu trong **Noel nâng cao**: Tháp kẹo mái gãy (5 mặt mái), Biệt thự mái kép (8 mặt mái), Nhà 3 gian Giáng sinh (6 mặt mái); mỗi kiểu có Rose Candy và Peppermint Mint. Thư viện hiện có 38 mẫu. Đây là kết cấu giấy từ hệ thống, lấy cảm hứng màu sắc từ ảnh tham khảo; chưa có ống khói hoặc mái chóp đa giác rời.

Sau Generate, chọn **Bản in → Bản màu / Bản tự tô (nét đen)** ở thanh công cụ. Preview 2D và Print đổi theo lựa chọn; trong **Xuất file**, nút **Tải PDF** tải đúng phiên bản đã chọn. Cả hai phiên bản có sẵn trong ZIP, áp dụng cho mọi mẫu bánh gừng và cả A4/US Letter. Dự án cũ cần Generate một lần để bổ sung file tự tô; đổi kiểu bản in không tạo revision mới. Mô hình 3D vẫn hiển thị phối màu gốc.

Bản tự tô dùng nét vector đen trên nền trắng, bỏ texture và bóng đổ, giữ cửa/cửa sổ/kem/kẹo/bảng tên, đường cắt, nét đứt gấp, mã ghép, kích thước và vạch 40 mm. Các SVG đặt tại `coloring_svg_pages/`, PDF có hậu tố `_coloring.pdf`. API `/pages` và `/print` nhận `?style=coloring` (mặc định `color`). Bộ mẫu: `output/advanced-coloring-a4-v4.2/noel-nang-cao-6-mau-mau-va-tu-to.zip`.

### Ống khói nhà cổ điển — catalog 4.3.0

Bổ sung ống khói cho 6 mẫu Noel ban đầu và các dòng Cape Cod, Colonial, Saltbox, Dutch Colonial, Craftsman, Farmhouse, Ranch (20 mẫu). Ống khói là phần giấy 3D rỗng miệng, thân gạch viền tuyết, một mảnh liền với 3 nếp gấp đứng, tai đóng mép C1 và 4 tai chân vát theo mặt mái. Thêm một trang in, giữ nguyên kết cấu thân nhà, mái và các phụ kiện trước đó. Khung định vị được in trên mặt mái phủ; hướng dẫn chỉ rõ cách gấp chân vào trong và dán lên mái, không khoét mái.

Có trong preview thư viện, 3D, OBJ toàn cảnh, PDF/SVG màu và tự tô. Dự án cũ bấm Generate để lấy mẫu mới; snapshot lịch sử không có trường `chimney` vẫn giữ thiết kế cũ. Chưa cắt/dán thử bằng giấy thật.

### Bố trí ống khói theo dáng nhà — catalog 4.4.0

Chỉ 14 mẫu dáng thấp phù hợp còn ống khói. Loại các dáng cao (tường từ 95 mm hoặc tổng chiều cao trên 140 mm), gồm Forest, Frost, Colonial và Farmhouse. Với mẫu mới, chọn mặt mái có chiều dài dốc thực tế lớn nhất; nếu bằng nhau chọn bên phải. Khung định vị và chân vát được tính lại theo mặt mái được chọn. Snapshot v4.3 vẫn giữ vị trí cũ; Generate dự án để cập nhật quy tắc mới.

### Workspace phối mẫu và cập nhật tự động

Dữ liệu mới khởi động không tự tạo dự án mẫu; Workspace hiển thị “Chưa có dự án”, dẫn sang Kho template. Dự án đã tạo vẫn được giữ lại. Trong Workspace, chọn thân nhà, hoạ tiết mái/tường, cây thông và hộp quà bằng thumbnail. Các lựa chọn tự lưu và tạo lại 3D/2D sau 650 ms không đổi lựa chọn; không cần bấm Generate. Trong khi xuất, giao diện báo tiến trình và tạm khóa lựa chọn để tránh bản in không khớp mô hình. Lỗi xuất có thể thử lại bằng Generate.

Thêm 5 dáng cây thông (thanh mảnh, tán tròn, nhiều tầng, ngôi sao, kẹo ngọt) và 5 mẫu trang trí hộp quà (sọc kẹo, chấm bi, bông tuyết, lá Noel, sao vàng), ngoài mẫu cổ điển. Hộp quà vẫn là hai khối 20/16 mm; cây thông có hình cắt mới và khe ghép chéo. Hoạ tiết mái/tường chọn độc lập, có cả bản màu và bản tự tô. Cấu hình lưu trong trường `design`, đi theo bản sao, revision và manifest; SQLite tự nâng cấp dữ liệu cũ.

### Production interface — US English

The interface, template catalog, design options, validation messages, and newly generated print/assembly text use US English. Existing project names and previously exported revisions are preserved. Select Rebuild to refresh older print files in English.

Two-option paper and print-style selectors use keyboard-accessible switches with explicit labels and visible states. Multi-option selectors remain unchanged. Major layout blocks share a 20 px spacing token, including the workspace, template cards, creator, downloads, and metrics. The desktop sidebar has a scrollable project list; design settings scroll independently. Mobile layouts keep the same 20 px section spacing.

### Accounts and saved projects

Account registration/sign-in is now required to create and access projects. The public Template library remains available without signing in. My projects saves each account's designs separately. See [ACCOUNTS.md](ACCOUNTS.md) for persistent storage, optional one-time Lifetime checkout, deployment settings, and deliberate migration of existing local projects. Purchases are disabled until payment configuration is supplied.
