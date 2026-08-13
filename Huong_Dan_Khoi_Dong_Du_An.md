# Hướng Dẫn Khởi Động Dự Án AgriLog (Từ Đầu Đến Đăng Nhập Thành Công)

> Làm theo đúng thứ tự 5 bước bên dưới. Mỗi bước có lệnh chính xác — copy và dán, không cần đoán.
> Tổng thời gian: khoảng 5-10 phút nếu không gặp lỗi.

---

## Bước 0: Kiểm tra nhanh PostgreSQL (chỉ mất 5 giây)

Máy chủ PostgreSQL đã được cấu hình để **tự khởi động cùng Windows**, nên bình thường bạn không cần làm gì. Nhưng để chắc chắn sau khi restart máy, mở PowerShell và chạy:

```powershell
Get-Service postgresql-x64-18 | Select-Object Name, Status, StartType
```

Kết quả mong đợi:

```
Name                Status  StartType
----                ------  ---------
postgresql-x64-18  Running  Automatic
```

- Nếu `Status` là `Running` → bỏ qua, sang Bước 1.
- Nếu `Status` là `Stopped` → chạy lệnh sau rồi kiểm tra lại:

```powershell
Start-Service postgresql-x64-18
```

---

## Bước 1: Khởi động Máy ảo Android (Android Emulator)

1. Mở **Android Studio**.
2. Nếu hiện màn hình chào (Welcome), chọn **"More Actions" → "Virtual Device Manager"**.
   Nếu đang mở sẵn một project, vào **"Tools" → "Device Manager"** ở thanh menu bên phải.
3. Trong danh sách máy ảo (AVD), tìm thiết bị bạn đã tạo trước đó (ví dụ `Pixel_...` hoặc `Medium_Phone_API_...`).
4. Bấm nút **▶ (Play/Launch)** bên cạnh tên thiết bị.
5. Đợi máy ảo khởi động hoàn toàn — thấy màn hình Home của Android (có icon, thanh điều hướng) là xong. Đừng làm gì tiếp cho tới khi thấy màn hình này.

> **Mẹo:** Nếu không muốn mở Android Studio, có thể khởi động máy ảo bằng terminal:
> ```powershell
> emulator -list-avds
> emulator -avd <tên_avd_vừa_liệt_kê>
> ```

---

## Bước 2: Khởi động Backend (FastAPI)

1. Trong **VS Code**, mở một **Terminal mới**: menu **Terminal → New Terminal** (hoặc phím tắt `` Ctrl+` ``).
2. Đảm bảo terminal đang dùng **PowerShell** (mặc định trên Windows).
3. Di chuyển vào thư mục `backend`, kích hoạt môi trường ảo, rồi chạy server:

```powershell
cd d:\agrilogapp\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> **Vì sao phải có `--host 0.0.0.0 --port 8000`:** máy ảo Android không gọi được `127.0.0.1` của máy tính host — nó gọi qua địa chỉ đặc biệt `10.0.2.2`. Nếu server chỉ bind vào loopback (`127.0.0.1`), app trên máy ảo sẽ không bao giờ kết nối được, dù backend chạy hoàn toàn bình thường.

4. Đợi thấy dòng log tương tự:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
AgriLog API v... starting (env=development)
INFO:     Application startup complete.
```

**Không đóng terminal này** — server phải chạy xuyên suốt trong khi bạn dùng app.

### Nếu bị lỗi kết nối database ở bước này

Nếu log báo `psycopg.OperationalError` hoặc tương tự, quay lại Bước 0 kiểm tra service PostgreSQL. Nếu service chạy tốt nhưng bảng dữ liệu chưa có, chạy migration (mở terminal PowerShell khác, đừng tắt terminal đang chạy uvicorn):

```powershell
cd d:\agrilogapp\backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

---

## Bước 3: Tạo Tài khoản qua Swagger UI

Giữ nguyên terminal backend đang chạy ở Bước 2, mở trình duyệt.

1. Truy cập: **http://localhost:8000/docs**
2. Cuộn xuống nhóm **auth**, tìm dòng **`POST /api/v1/auth/register`** — bấm vào để mở rộng.
3. Bấm nút **"Try it out"** ở góc phải khung.
4. Trong ô **Request body**, xoá nội dung mẫu và dán đúng nội dung sau:

```json
{
  "email": "lethanhthai0805@gmail.com",
  "password": "[YOUR_PASSWORD]",
  "full_name": "Le Thanh Thai",
  "household_name": "Ho Le Thanh Thai",
  "phone": null,
  "province": null,
  "commune": null
}
```

5. Bấm nút **"Execute"** (màu xanh).
6. Cuộn xuống phần **"Server response"** — kiểm tra:
   - **Code `201`** → **Thành công!** Tài khoản đã được tạo, kèm sẵn `access_token`. Chuyển sang Bước 4.
   - **Code `409`** → Email này đã tồn tại từ trước (có thể bạn đã đăng ký lần trước). Không sao — bỏ qua bước này, sang thẳng Bước 5 và đăng nhập bằng email/mật khẩu đó luôn.
   - **Code `422`** → Sai định dạng JSON (thường do thiếu dấu ngoặc hoặc dấu phẩy) — kiểm tra lại đã dán đúng khối JSON ở trên chưa.

---

## Bước 4: Khởi động Mobile App (React Native)

1. Trong VS Code, mở **thêm một terminal mới** (đừng tắt terminal đang chạy backend): bấm icon **"+"** ở góc phải panel Terminal, hoặc `` Ctrl+Shift+` ``.
2. Di chuyển vào thư mục `mobile` và cài đặt gói (chỉ cần nếu chưa `npm install` trước đó — nếu đã cài rồi có thể bỏ qua lệnh `npm install`):

```powershell
cd d:\agrilogapp\mobile
npm install
```

3. Khởi động **Metro bundler** (giữ terminal này chạy xuyên suốt, giống terminal backend):

```powershell
npm start
```

Đợi thấy giao diện Metro (logo React Native dạng ASCII) là Metro đã sẵn sàng.

4. Mở **một terminal thứ ba** (terminal build/cài app), di chuyển vào `mobile`, rồi chạy:

```powershell
cd d:\agrilogapp\mobile
npm run android
```

   (Lệnh này tương đương `npx react-native run-android` — đã được cấu hình sẵn trong `package.json`.)

5. Đợi Gradle build xong (lần đầu có thể mất vài phút) — app sẽ **tự động cài và mở** trên máy ảo đang chạy ở Bước 1.

6. **(Nên làm)** Xác minh cầu nối máy ảo ↔ Metro đã được thiết lập:

```powershell
adb reverse --list
```

   Phải thấy dòng `host-... tcp:8081 tcp:8081` trong kết quả. Nếu không thấy, xem mục xử lý lỗi ngay bên dưới.

> **Vì sao cần bước này:** app debug không đóng gói sẵn JS — nó tải bundle qua HTTP từ Metro mỗi lần mở. Trên máy ảo, `localhost:8081` mà app gọi tới là localhost **của chính máy ảo**, không phải của máy tính host. Lệnh `adb reverse tcp:8081 tcp:8081` là cầu nối giữa hai bên, và `npm run android` tự chạy lệnh này **một lần** ngay sau khi cài app. Nhưng đây là thiết lập gắn với phiên kết nối ADB hiện tại — không tồn tại vĩnh viễn. Nó **mất đi** khi bạn khởi động lại máy ảo, restart ADB server, hoặc thiết bị ngắt/kết nối lại — kể cả khi Metro vẫn đang chạy hoàn toàn bình thường. Đây là nguyên nhân phổ biến nhất của lỗi "Unable to load script" khi bạn *reload* app mà không chạy lại `npm run android`.

### Nếu app báo lỗi "Unable to load script"

Thử theo đúng thứ tự sau — đa số trường hợp dừng ở bước 1.

**1. Kiểm tra ánh xạ `adb reverse` (nguyên nhân phổ biến nhất, sửa trong vài giây, không cần build lại):**

```powershell
netstat -ano | findstr ":8081"      # phải thấy dòng LISTENING -> Metro còn sống
adb reverse --list                   # phải có dòng "tcp:8081 tcp:8081"
```

- Nếu Metro **đang** lắng nghe (`LISTENING`) nhưng `adb reverse --list` **không** có dòng `tcp:8081 tcp:8081` → chạy lại lệnh này rồi bấm **Reload** trên máy ảo (`Ctrl+M` → Reload), **không cần** khởi động lại Metro hay build lại app:
  ```powershell
  adb reverse tcp:8081 tcp:8081
  ```

**2. Nếu Metro không hề lắng nghe ở cổng 8081 (`netstat` không ra gì)** — nghĩa là terminal Metro (Bước 4.3) đã bị đóng hoặc crash thật sự. Kiểm tra log của terminal đó:
- Nếu thấy log dừng đột ngột với `Error: ENOENT... watch`, chạy lại Metro với cache sạch:
  ```powershell
  npx react-native start --port 8081 --reset-cache
  ```
  Chi tiết nguyên nhân đã ghi trong `Error_Metro_Watcher_Crash_CXX_Build.md` (dự án đã có cấu hình `metro.config.js` để né lỗi này, nên bình thường sẽ không gặp lại).
- Sau khi Metro chạy lại, chạy lại `npm run android` để cài lại `adb reverse` và mở app.

### Nếu build Android báo lỗi liên quan `BuildConfig` / WatermelonDB

Lỗi đã được vá sẵn bằng `patch-package` (tự chạy khi `npm install`). Nếu vẫn gặp lỗi `cannot find symbol BuildConfig`, chạy:

```powershell
npx patch-package
```

rồi build lại. Chi tiết trong `Error_WatermelonDB_BuildConfig_AGP9.md`.

---

## Bước 5: Đăng nhập trên Máy ảo

App đã mở trên máy ảo, đang ở màn hình **Login**.

1. Chạm vào ô **Email**, nhập: `lethanhthai0805@gmail.com`
2. Chạm vào ô **Mật khẩu**, nhập: `[YOUR_PASSWORD]`
3. Bấm nút **"Đăng nhập"**.
4. Nếu thành công, app sẽ chuyển sang màn hình chính (Dashboard/Trang chủ).

---

## Tóm tắt: 3 Terminal cần chạy song song

| Terminal | Thư mục | Lệnh | Có được tắt không? |
|---|---|---|---|
| 1 — Backend | `backend` | `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` | Không, giữ suốt phiên làm việc |
| 2 — Metro | `mobile` | `npm start` | Không, giữ suốt phiên làm việc |
| 3 — Build | `mobile` | `npm run android` | Có, sau khi build xong app đã cài lên máy ảo |

---

## Checklist nhanh nếu có sự cố

- [ ] `Get-Service postgresql-x64-18` → `Running`
- [ ] Terminal backend không báo lỗi kết nối database
- [ ] `http://localhost:8000/health/db` trả về `{"status":"ok","database":"reachable"}`
- [ ] Máy ảo Android đã hiện màn hình Home **trước khi** chạy `npm run android`
- [ ] Terminal Metro (`npm start`) vẫn đang chạy, không bị tắt/crash
- [ ] `adb reverse --list` có dòng `tcp:8081 tcp:8081` (mất dòng này là nguyên nhân số 1 của "Unable to load script" dù Metro vẫn chạy tốt)
- [ ] Đã đăng ký tài khoản qua Swagger UI (code `201`) hoặc đã có tài khoản từ trước (code `409` khi đăng ký lại là bình thường)
