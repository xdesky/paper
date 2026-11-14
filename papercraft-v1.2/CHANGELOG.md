# Changelog

## v1.2.0 — Fold-first two-face layouts
- Ưu tiên cặp mặt kề nhau nằm **trên cùng một tờ giấy**, nối bằng nếp gấp 90° không cắt.
- Những ô cùng một mặt phẳng được giữ liền giấy (0°) nếu vẫn vừa khổ.
- Bỏ tai dán tại cạnh đã nối liền, còn lại đúng một tai trên mỗi mối phải dán.
- Sử dụng maximum-cardinality graph matching với thứ tự ổn định để tránh output drift.
- Giữ kích thước 100% và fallback cho hai ô không thể đặt cạnh nhau trên US Letter.
- Sinh bản vẽ thực tế cho khung nhà bốn tường 120 × 90 × 180 mm, hai tờ, hai nếp gấp.
- Lưu tọa độ 3D của từng panel vào `model_spec.json`, SHA-256 theo cấu trúc hình học.
- Kiểm tra endpoints 3D, pháp tuyến 0°/90°, chồng lấn 2D, tai dán, vector PDF/SVG, vùng in và vạch 40 mm.
- Bổ sung bộ kiểm tra độc lập sau khi xuất file và sơ đồ hướng dẫn.

### Chưa hỗ trợ
- Tạo mái nhà, mở cửa sổ/cửa chính, unfold mesh tùy ý, tối ưu xếp trang toàn cục, tái dựng chính xác từ một ảnh AI.
- Lắp thử bằng giấy thật: chưa thực hiện.
