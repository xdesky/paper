# Papercraft Engine v1.2 — Two-Face Connected Fold

Bản cập nhật cho Print Play Magic theo yêu cầu: **hai mặt liền nhau trên cùng tờ US Letter, giữ nguyên giấy tại cạnh nối và gấp 90° ở giữa**, giảm tai dán. Trên hai mảnh ở **cùng mặt phẳng**, engine ưu tiên **liền phẳng** và không tạo nếp gấp giả.

## Mẫu khung nhà 4 tường (demo mới)

- **Thành phẩm:** rộng 120 × sâu 90 × cao 180 mm.
- **Chỉ có bốn tường** — chưa có sàn, mái, cửa hay chi tiết Gingerbread.
- **Trang 1:** BACK + LEFT, liền nhau tại gấp 90° mã `H03`.
- **Trang 2:** FRONT + RIGHT, liền nhau tại gấp 90° mã `H01`.
- **Chỉ dán:** `H02` (RIGHT-BACK) và `H04` (LEFT-FRONT).
- **Kết quả:** 4 tường → **2 mảnh giấy / 2 tờ**; giảm 4 mối dán góc còn **2**.
- In trang ở 100%, đo chuẩn 40 mm trước khi cắt. Phần này chưa được thử gấp dán thực tế.

## So sánh bản v1.1 và v1.2

| Mẫu | Số trang trước → sau | Nếp gấp 90° liền giấy | Mối liền phẳng | Mối cần dán trước → sau |
|---|---:|---:|---:|---:|
| Lập phương 100 mm | 3 → 3 | 3 | 0 | 12 → **9** |
| Lập phương 200 mm | 12 → 12 | 8 | 4 | 48 → **36** |
| Lập phương 300 mm | 24 → 24 | 0 | 0 | 48 → **48** |
| Khung nhà 120×90×180 mm | 4 tường rời → 2 tờ | 2 | 0 | 4 → **2** |

**Lý do cube 300 mm không có hai mặt liền giấy:** Bản v1.1 chia mỗi mặt 300 × 300 thành 4 ô 150 × 150. Hai ô 150 × 150 đặt chung theo cạnh yêu cầu ít nhất 300 mm theo một chiều, vượt kích thước vùng in 199.9 × 235 mm. Có thể chia nhỏ hơn để tạo cặp, nhưng sẽ tăng mạnh số mối ghép khác; v1.2 ưu tiên không làm vấn đề dán xấu hơn.

**Cơ chế:** tạo các panel đúng hình học → lập đồ thị cặp cạnh có thể mở phẳng → tìm maximum matching cho nếp gấp góc 90° → nối phẳng các ô còn dư → bỏ tai dán trên cạnh liền giấy → xếp từng cụm vào trang giấy → tạo vector và xác minh lại tọa độ.

## Cách đọc bản in
- Viền **đen liền**: cắt đường bao ngoài.
- **Tím đứt**: nếp gấp góc 90°, **không cắt**.
- **Không có đường ở giữa** hai ô cùng mặt màu: liền phẳng, không cắt/gấp.
- **Xanh/vàng đứt** tại chân tai màu vàng nhạt: gấp tai, dán vào cạnh khác có **cùng mã**.
- `H01`..`H04`: mã các góc của khung nhà. `F...`: mối cùng mặt phẳng của lập phương; `E...`: mối góc.

## File trong mỗi thư mục mẫu
- `printable_us_letter.pdf`: bản vector đúng tỷ lệ 100%.
- `svg_pages/page_###.svg`: SVG vector từng tờ, đơn vị mm.
- `printable_preview.png`: ảnh xem trước, không dùng để in.
- `assembly_guide.pdf`: thứ tự cắt, gấp, dán và tra mã ghép.
- `model_spec.json`: dữ liệu đã khóa gồm geometry SHA-256, mặt, seam, unit, trang.
- `validation_report.json`: kết quả kiểm tra tự động (độc lập với kiểm thử vật lý).
- `model_3d_preview.png`: hình dựng từ hình học 3D; khung nhà là vỏ tường mở.
- `model.obj`: có với mẫu cube.

## Chạy lại bằng Python

```bash
python -m pip install -r requirements.txt
python generate_connected_nets_v1_2.py --out ./output
python verify_package_v1_2.py ./output
```

`engine_v1_1_base.py` là module geometry nguồn của v1.1 được đóng gói cùng script mới. Không cần truy cập file từ cuộc hội thoại khác.

## Chú ý
Các đường được kiểm tra bằng hình học và đối chiếu dữ liệu vector PDF/SVG; **chưa có thử nghiệm lắp ráp bằng giấy thật**. Giới hạn hiện tại: hai primitive demo (cube, wall frame), chưa unfold mô hình 3D tuỳ ý hoặc dựng hình từ ảnh AI.
