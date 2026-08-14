# Checklist kiểm thử ngoại tuyến (README §8)

**Người thực hiện:** Thái · **Thiết bị:** máy ảo `emulator-5554` (hoặc điện thoại thật)
**Mục đích:** chứng minh cam kết cốt lõi của đồ án — app dùng được đầy đủ khi **không có mạng**. Đây là mức chấp nhận của Issue #38 và #47.

> **Lưu ý về dữ liệu:** máy ảo đang có sẵn dữ liệu test tôi tạo lúc chạy kịch bản UI (tài khoản `uitest2@agrilog-test.com` / mật khẩu `uitest12345`, 1 mùa vụ, 1 vật tư, 1 nhật ký, 1 khoản thu). Bạn dùng luôn tài khoản này, hoặc đăng nhập tài khoản của bạn — cả hai đều được.

---

## A. Chuẩn bị (còn mạng)

- [ ] **A1.** Backend đang chạy: mở `http://localhost:8000/docs` thấy Swagger UI
- [ ] **A2.** Mở app, **đăng nhập một lần** → vào được màn hình "Mùa vụ"
- [ ] **A3.** Bấm **Đồng bộ** một lần, chờ thanh trạng thái hiện **"Đã đồng bộ"** (chấm xanh)

> A3 quan trọng: nó đặt mốc "trước khi offline" để bước D so sánh được.

---

## B. Bật chế độ máy bay

- [ ] **B1.** Vuốt thanh thông báo xuống → bật **Chế độ máy bay** (biểu tượng ✈)
- [ ] **B2.** Xác nhận biểu tượng Wi-Fi/sóng đã tắt trên thanh trạng thái

---

## C. Làm việc khi KHÔNG có mạng — phần quan trọng nhất

Mỗi mục dưới đây phải chạy **ngay lập tức**: không vòng xoay chờ, không thông báo lỗi, không màn hình trống.

- [ ] **C1.** Tab **Nhật ký** → tạo **1 mùa vụ** mới (tên + loại cây trồng)
- [ ] **C2.** Mở mùa vụ đó → ghi **nhật ký thứ nhất**, có khai vật tư đã dùng
- [ ] **C3.** Ghi **nhật ký thứ hai**, có khai vật tư
- [ ] **C4.** Ghi **nhật ký thứ ba**, có khai vật tư
- [ ] **C5.** Tab **Vật tư** → kiểm tra tồn kho **đã trừ đúng** theo 3 nhật ký vừa ghi
- [ ] **C6.** Tab **Thu chi** → ghi **1 khoản chi** tay
- [ ] **C7.** Tab **Thu chi** → ghi **1 khoản thu**
- [ ] **C8.** Tab **Thu chi** → xác nhận có các khoản chi **"Tự động từ nhật ký"** sinh từ C2–C4
- [ ] **C9.** Tab **Báo cáo** → cả **3 biểu đồ** đều vẽ ra (đường thu/chi · tròn vật tư · cột so sánh mùa vụ)

**Nếu bất kỳ mục nào từ C1–C9 thất bại → yêu cầu offline-first CHƯA ĐẠT.** Chụp màn hình và báo tôi.

Ngoài đúng/sai, xin bạn để ý giúp 2 điểm chỉ người cầm máy mới cảm nhận được:

- [ ] **C10.** Bàn phím ảo có che mất ô đang nhập hay nút bấm không?
- [ ] **C11.** Thanh tab dưới cùng (60dp) có đủ lớn để bấm bằng ngón cái không?

---

## D. Tắt máy bay và đồng bộ

- [ ] **D1.** Tắt **Chế độ máy bay**, chờ sóng/Wi-Fi trở lại
- [ ] **D2.** Trên app, thanh trạng thái hiện **"N thay đổi chờ gửi"** (chấm cam) — N phải khớp số bản ghi bạn vừa tạo
- [ ] **D3.** Bấm **Đồng bộ** → hiện **"Đã gửi N thay đổi"** rồi chuyển về **"Đã đồng bộ"** (chấm xanh)
- [ ] **D4.** Mở **pgAdmin** → database `agrilog` → kiểm tra dữ liệu đã lên:

```sql
SELECT name, crop_type, status FROM seasons        ORDER BY created_at DESC LIMIT 5;
SELECT work_type, entry_date, title FROM diary_entries ORDER BY created_at DESC LIMIT 5;
SELECT category, amount, source FROM expenses      ORDER BY created_at DESC LIMIT 8;
SELECT amount, buyer FROM revenues                 ORDER BY created_at DESC LIMIT 5;
SELECT txn_type, quantity, total_cost FROM stock_transactions ORDER BY created_at DESC LIMIT 8;
```

- [ ] **D5.** Số dòng ở D4 khớp với những gì bạn tạo ở bước C
- [ ] **D6.** Các khoản chi tự động có `source = 'diary_auto'`, khoản chi tay có `source = 'manual'`

---

## E. Báo kết quả

Nhắn lại cho tôi theo mẫu ngắn:

```
A: đạt / lỗi ở A?
B: đạt
C: C1..C9 đạt hết / lỗi ở C? — kèm ảnh chụp
C10 (bàn phím): ...
C11 (tab bar):  ...
D: đạt / lệch số liệu ở D?
```

Nếu có lỗi, kèm giúp tôi ảnh chụp màn hình. Nếu app văng, chạy lệnh này rồi dán kết quả cho tôi:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" logcat -d *:E ReactNativeJS:V | Select-Object -Last 40
```
