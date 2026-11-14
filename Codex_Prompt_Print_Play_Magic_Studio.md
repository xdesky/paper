# CODEX MASTER BUILD PROMPT — PRINT PLAY MAGIC STUDIO

Bạn là Principal Full-stack Engineer + Computational Geometry Engineer + Product Designer. Hãy xây dựng một ứng dụng web **thật sự chạy được** tên **Print Play Magic Studio — Papercraft Generator**. Không tạo mockup, landing page thuần trình diễn, ảnh AI giả dạng mẫu cắt dán hoặc nút download giả.

## 0. Input và quy tắc đầu tiên

Tôi sẽ cung cấp file `Papercraft_Engine_v1_2_Fold_First_US_Letter.zip` trong workspace/repository. **Trước khi code, phải đọc** `README.md`, `CHANGELOG.md`, `master_instructions_v1_2.md`, `model_spec.schema.json`, `generate_connected_nets_v1_2.py`, `engine_v1_1_base.py`, `verify_package_v1_2.py` và các mẫu kiểm thử. Đọc/khai thác lại phần code tính hình học đã có, không viết lại tùy tiện và không phỏng đoán các tính năng mà engine hiện chưa làm được.

Engine v1.2 hiện hỗ trợ thực tế: lập phương 100/200/300 mm, khung bốn tường mở 120×90×180 mm, mô hình hình học xác định, Fold-First nối hai mặt bằng nếp gấp, tai dán và mã ghép, PDF/SVG vector, Model Spec và QA. **Chưa hỗ trợ tự động dựng mesh từ ảnh hoặc unfold mesh bất kỳ.** Các tính năng chưa phát triển phải hiển thị đúng trạng thái, không ngụy tạo thành công.

## 1. Mục tiêu sản phẩm

Quy trình: **Input (prompt / ảnh / file 3D) → Phân tích → Model Spec → Geometry → 3D Preview → Fold-first Unfolding → Multi-page Layout → QA → PDF/SVG/Guide/ZIP**.

Chạy web trên máy tính và điện thoại, tối ưu desktop cho thao tác chỉnh sửa. Đối tượng: người thiết kế papercraft printable để in tại nhà và bán file số. Ngôn ngữ UI mặc định tiếng Việt, thiết kế sẵn kiến trúc i18n để thêm tiếng Anh.

**Quy tắc bất biến**: bản PDF phải có hình học chính xác, không được sử dụng ảnh gen AI để giả lập printable; tất cả bản xuất phải sinh từ cùng một Model Spec/version/geometry hash. Không tự co giãn mẫu để ép vừa trang giấy. Không đánh dấu “tested physically” nếu chưa có kết quả cắt/dán thực tế.

## 2. Công nghệ đề xuất

- Frontend: React + TypeScript + Vite, Tailwind CSS, React Three Fiber / Three.js, SVG cho bộ chỉnh sửa trang, Zustand hoặc state management tương đương, TanStack Query (nếu cần).
- Backend: Python FastAPI + Pydantic. Tách module `geometry`, `unfolding`, `packing`, `tabs`, `export`, `validation`, `jobs`.
- Tái sử dụng Shapely, trimesh, NetworkX, ReportLab, PyMuPDF và những thư viện hiện có trong v1.2 khi thích hợp; chỉ thêm thư viện khi có lý do.
- Development persistence: SQLite + thư mục dữ liệu có kiểm soát. Thiết kế trừu tượng để chuyển sang PostgreSQL/object storage về sau.
- Chạy local bằng một lệnh Docker Compose hoặc hai lệnh rõ ràng frontend/backend; có `.env.example`. Cấu hình CORS, upload limits và job timeout hợp lý.
- Không khóa vào dịch vụ AI trả phí. Chỉ thêm adapter AI có thể bật khi cấu hình API key hợp lệ; không lưu API key trên frontend.

Nếu workspace có thiết lập tương đương sẵn thì ưu tiên sử dụng và giải thích lựa chọn.

## 3. Tính năng MVP PHẢI chạy thật

### 3.1 Project Manager
- Tạo, đổi tên, sao chép và xóa dự án.
- Mỗi dự án lưu: `project_id`, `model_id`, phiên bản, `model_spec.json`, tham số in, trạng thái xử lý, kết quả xuất, báo cáo QA và timestamp.
- Bản đã khóa là immutable; sửa đổi phải tạo version mới. Nếu input thay đổi, báo stale và vô hiệu hóa file cũ cho đến khi regenerate.
- Có sample projects: Cube 100/200/300 mm, House Frame 120×90×180 mm.

### 3.2 Input
Có ba tab:
1. **Prompt**: biểu mẫu mô tả mô hình + chọn loại mẫu có engine xác định (Cube / Rectangular Box / Four-Wall House Frame). Với các primitive được hỗ trợ, parse giá trị có cấu trúc và yêu cầu người dùng xác nhận kích thước; không tuyên bố hiểu hoàn hảo mọi câu tự nhiên.
2. **Image**: upload JPG/PNG/WEBP; xem ảnh, ghi chú giả định, có thể chuyển sang workflow dựng geometry thủ công. Nếu không tích hợp dịch vụ image-to-3D thực tế, hiển thị `Reconstruction not configured`, tuyệt đối không cho giả download printable đã tính từ ảnh.
3. **3D file**: upload OBJ/STL/GLB/GLTF, viewer đọc model, tính bounding box/mesh diagnostics. Nếu generalized unfolding chưa hoàn tất, phải hiển thị trạng thái `Preview and geometry inspection only` thay vì export giả.

### 3.3 3D & 2D Workspace
- Layout 3 cột: trái = input/cài đặt, giữa = 3D viewer xoay/zoom/pan/wireframe, phải = 2D printable page viewer nhiều trang.
- Trang 2D biểu diễn vector thật, chọn trang, zoom, bật/tắt CUT / FOLD / FLAT CONTINUOUS / GLUE TAB / EDGE CODE.
- Chọn cạnh trên 2D sẽ highlight cạnh tương ứng trong 3D nếu dữ liệu seam có sẵn.
- Hiển thị model dimensions mm, số trang, số mảnh, số nếp gấp liền, số mối phải dán, warnings.
- Các thao tác kéo thả mảnh (nếu triển khai) phải cập nhật layout thật và chạy QA lại; nếu chưa có, ẩn/disable có giải thích, không chỉ tạo hiệu ứng giả.

### 3.4 Fold-First & Unfolding
- Ưu tiên ghép **hai mặt liền nhau trên cùng tờ** thành một hình cắt không đứt, nếp gấp giữa; **không cắt và không có tai dán tại cạnh liền giấy**.
- Hai panel đồng phẳng nếu ghép được thì là `FLAT_CONTINUOUS`, không vẽ đường gấp giả.
- Cặp mặt gấp phải có cạnh 3D chung chính xác; unfolding chỉ dùng phép biến đổi cứng (quay/tịnh tiến), không phản chiếu/kéo méo.
- Chỉ dùng glue tabs khi cạnh bắt buộc phải tách; mã ghép phải có đúng hai đầu tương ứng.
- Với mô hình vượt vùng in, tự chia mặt lớn thành subpanels, tạo seam mới và mã ghép duy nhất. Ưu tiên giảm mối dán/tổng số mảnh, nhưng không đánh đổi bằng việc vượt khổ giấy.
- Tối ưu đồng thời theo trọng số: (1) geometry correctness, (2) fewer glue seams, (3) fewer cut pieces, (4) fewer pages. Có thể dùng greedy/deterministic packing trước, nhưng đánh dấu là heuristic, **không quảng cáo đạt tối ưu toán học**.
- Đừng giới hạn engine bởi cách chọn `maximum matching` chỉ ghép 2 panel nếu có thể mở rộng connected nets nhiều mặt; giai đoạn đầu giữ thuật toán v1.2 hoạt động thật và có test regression, sau đó thêm algorithm generic với kiểm tra overlap và phát hiện cycle.
- Với nếp gấp, tính mountain/valley từ thông tin định hướng mặt 3D; không giả định tất cả đều cùng loại.

### 3.5 Paper & Print Settings
- Khổ giấy mặc định US Letter = **215.9 × 279.4 mm**, tùy chọn A4 = 210 × 297 mm.
- Orientation portrait/landscape; margin mặc định 8 mm (cho phép chừa thêm header/footer); tab width mặc định 7 mm, có thể chỉnh; inter-piece gap; nét cắt/nếp gấp; show/hide numbers/texture.
- Kích thước thành phẩm tùy chỉnh theo mm; scale 100% khi xuất. Nếu mặt lớn hơn vùng in, tile ra nhiều trang/mảnh; không thu nhỏ trong im lặng.
- Mỗi trang có nhãn `Page n/N`, `Model ID`, `Version`, legend và đoạn thước kiểm chuẩn **40 mm**.
- PDF phải ghi đúng kích thước trang trong point (72 pt/inch). SVG dùng units mm và viewBox nhất quán. Có cảnh báo `Actual Size / 100% — no Fit to Page`.

### 3.6 Export
- PDF vector đa trang có CUT/FOLD/GLUE TABS/EDGE CODES.
- SVG riêng từng trang (có thể zip).
- Assembly Guide PDF: mô hình 3D, mã face/panel, đường gấp, thứ tự ghép và chú giải.
- Model Spec JSON, mesh OBJ khi thực sự có, Validation Report JSON, preview PNG, ZIP toàn dự án.
- Không cho download bản xuất có QA FAIL như bản đã được chứng nhận; hiển thị rõ cảnh báo và cho xuất gói debug nếu cần.
- Tất cả artifacts phải có trùng `model_id`, version và geometry hash; link download phải hoạt động thật.

### 3.7 QA Engine
Chạy tự động mỗi lần Generate / đổi tham số ảnh hưởng hình học:
- Mesh diagnostics (watertight nếu thiết kế là solid kín; khung tường mở được xác định là open shell hợp lệ).
- Dimension/scale/area preservation; cạnh ghép cùng chiều dài trong tolerance cấu hình.
- 2D panel+tab polygon validity; no unintended overlap.
- Every seam has two and only two valid occurrences; no duplicated or orphan labels.
- Fold-connected seams have no cut/tabs at the hinge.
- No output outside printable bounds including text/legends/tabs.
- Page size and 40 mm calibration measured in PDF and SVG.
- Re-open exported vector files to verify the important coordinates, not just check pre-export data.
- Report `PASS`, `WARNING`, `FAIL`; `physical_assembly: NOT_TESTED` by default. Show test list and detailed errors on UI.

## 4. API endpoints (có thể điều chỉnh, nhưng phải có OpenAPI docs)

- `POST /api/projects` / `GET /api/projects` / `GET /api/projects/{id}`
- `PATCH /api/projects/{id}` / `DELETE /api/projects/{id}`
- `POST /api/projects/{id}/inputs` (prompt/image/mesh)
- `POST /api/projects/{id}/versions` (new immutable version)
- `POST /api/projects/{id}/generate` (background job with persisted status)
- `GET /api/jobs/{job_id}` (progress/stage/error)
- `GET /api/projects/{id}/geometry`
- `GET /api/projects/{id}/pages`
- `GET /api/projects/{id}/validation`
- `GET /api/projects/{id}/artifacts/{filename}`
- `GET /api/health`

Validate user input, isolate per-project artifact paths, protect against filename/path traversal and zip bombs, enforce file type/size limits, and do not run uploaded code.

## 5. UI/UX cụ thể

Giao diện sáng, đẹp, sạch, phù hợp sản phẩm sáng tạo; sidebar có `Projects`, `New Model`, `Workspace`, `Exports`, `Settings`.

Trang Workspace có toolbar Generate, Lock Model, Export All. Tab bên trái gồm `Source`, `Model Dimensions`, `Paper Settings`, `Unfold Settings`. Trung tâm là canvas 3D; bên phải là trang printable với thumbnail trang, zoom và legend.

Khi Generate, có progress thực: `Validate Input → Build Geometry → Choose Hinges → Unfold → Add Tabs → Pack Pages → Export → QA`. Hiển thị lỗi rõ ràng, không dùng spinner vô tận hoặc thông báo hoàn tất giả.

Thiết kế responsive, có empty states và hoạt động tốt với bàn phím. Thêm một demo seeded project có thể mở và download ngay sau khi cài đặt.

## 6. Kiến trúc chống loạn ngữ cảnh / sai lệch Model Spec

- Model Spec chuẩn là canonical source; mọi kết quả derived từ một snapshot bất biến.
- Geometry hash SHA-256 dựa trên normalized/canonical JSON; không hash metadata dễ thay đổi như timestamp khi mục tiêu là hình học.
- Generated artifacts lưu `source_spec_hash`; nếu mismatch, cảnh báo STALE.
- Lưu `generation_manifest.json` liệt kê input hash, thuật toán/version, output paths và QA status.
- Mỗi thay đổi tạo revision log và tăng version; không sửa âm thầm bản đã khóa.
- API AI chỉ tạo structured draft có schema validate; không được trực tiếp điền kết quả printable bằng hình ảnh.

## 7. Tests / acceptance criteria bắt buộc

Làm test tự động bằng pytest cho engine và integration tests cho API; frontend smoke/E2E bằng Playwright nếu khả thi. Các bài kiểm tra tối thiểu:

**Fixture A: Cube 100 mm** — chạy từ UI -> backend -> PDF/SVG/QA, hiển thị đúng 6 mặt 100×100, download hoạt động.

**Fixture B: Cube 200 mm** — nhiều trang; test ghép liền bằng fold nơi mặt và trang cho phép.

**Fixture C: Cube 300 mm** — tile mặt lớn thành nhiều panel hợp lệ ở 100%, mã ghép đủ cặp, không ép 2 ô 150×150 mm vào US Letter.

**Fixture D: Four-wall frame 120×90×180 mm** — có hai cụm mặt liền với nếp gấp 90° ở giữa; ít hơn 4 mối dán góc, không có tai dán trên nếp gấp liền.

**Fixture E: Oversized rectangular house wall** — chia trang tự động, kiểm tra đầy đủ mối nối nội bộ và biên ngoài.

**Fixture F: Invalid mesh/image** — validation error hoặc NEEDS_RECONSTRUCTION rõ ràng; không tạo PDF giả.

Kiểm tra hình học và page clipping trước và sau khi export; test scale 40 mm, page count, download MIME, multi-page page numbering, no overlap, stable deterministic reruns. Không hardcode chỉ để PASS fixture; tests phải thực sự gọi cùng pipeline production.

## 8. Quy trình triển khai của Codex

1. Xem cấu trúc repository và archive; báo tóm tắt phần có thể tái sử dụng và giới hạn trước khi sửa code.
2. Tạo architecture/short plan trong `IMPLEMENTATION_PLAN.md` nhưng **bắt đầu code luôn**, không dừng ở kế hoạch.
3. Phase A (hoàn thiện trước): chạy engine v1.2 trong service FastAPI, frontend chọn cube 100/200/300 & house frame, generate/export/QA thật, download thật, không mock.
4. Phase B: editable dimensions, A4, multi-page tiling, cải tiến connected nets và packing.
5. Phase C: image upload và 3D mesh inspect; thêm image-to-3D adapter chỉ khi có dịch vụ/khóa thật. Nếu chưa khả dụng, trạng thái unconfigured.
6. Mỗi phase: chạy tests, fix bugs, lưu kết quả cụ thể và cập nhật README. Không phá regression của engine v1.2.
7. Cuối cùng cung cấp source code, README setup/run, `.env.example`, test commands/results, sample outputs, known limitations và next steps. Nếu chưa hoàn thiện một chức năng, nói rõ `Not implemented`/`Partial` thay vì đánh dấu DONE.

**Definition of Done cho phiên bản web MVP:** Tôi mở localhost, tạo/ chọn dự án Cube hoặc House Frame, chỉnh cỡ giấy và kích thước hỗ trợ, bấm Generate, nhìn thấy 3D model và trang 2D, kiểm tra QA, tải được PDF/SVG/Guide/ZIP thật; PDF in ở Actual Size 100%, có mã nối, tai dán và nếp gấp Fold-First chính xác. Chỉ khi luồng này chạy end-to-end mới ưu tiên tính năng AI/image-to-3D.

Bắt đầu thực hiện trong repository hiện tại. Không chỉ trả lời bằng kiến trúc hay đoạn code minh họa — hãy tạo và kiểm thử ứng dụng có thể chạy.
