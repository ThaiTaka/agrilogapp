# Hướng Dẫn Khởi Động AgriLog — Toàn Tập

> Tài liệu này đủ để một người **chưa từng chạm vào dự án** khởi động toàn bộ hệ thống và đăng nhập thành công. Mỗi lệnh copy–dán được, không cần đoán.
>
> **Thời gian:** khoảng 10 phút nếu máy đã cài sẵn môi trường (xem `README.md` §6 nếu cài từ đầu).

---

## Mục lục

- [0. Hệ thống gồm những gì](#0-hệ-thống-gồm-những-gì)
- [1. Khởi động PostgreSQL](#1-khởi-động-postgresql)
- [2. Bật Backend FastAPI — cổng 8000](#2-bật-backend-fastapi--cổng-8000)
- [3. Bật Web Admin Next.js — cổng 3000](#3-bật-web-admin-nextjs--cổng-3000)
- [4. Bật Mobile App qua Metro — máy ảo](#4-bật-mobile-app-qua-metro--máy-ảo)
- [5. Chạy app trên điện thoại Android thật](#5-chạy-app-trên-điện-thoại-android-thật)
- [6. Tra cứu cơ sở dữ liệu bằng pgAdmin](#6-tra-cứu-cơ-sở-dữ-liệu-bằng-pgadmin)
- [7. Từ điển dữ liệu](#7-từ-điển-dữ-liệu)
- [8. Bảng tóm tắt & checklist sự cố](#8-bảng-tóm-tắt--checklist-sự-cố)

---

## 0. Hệ thống gồm những gì

Ba phần chạy độc lập, nối với nhau qua HTTP:

```
┌──────────────────┐         ┌──────────────────┐
│  App di động     │         │   Web Admin      │
│  (Android)       │         │   Next.js :3000  │
│  React Native    │         │   Trình duyệt    │
└────────┬─────────┘         └────────┬─────────┘
         │  đồng bộ khi có mạng       │  luôn cần mạng
         └──────────┬─────────────────┘
                    ▼
          ┌──────────────────┐
          │  Backend FastAPI │
          │      :8000       │
          └────────┬─────────┘
                   ▼
          ┌──────────────────┐
          │  PostgreSQL      │
          │      :5432       │
          │  database:agrilog│
          └──────────────────┘
```

**Điểm khác biệt quan trọng để hiểu khi demo:** app di động **không cần** backend để hoạt động. Nó ghi thẳng vào SQLite trên máy và chỉ gọi backend khi đồng bộ. Web Admin thì ngược lại — mọi thao tác đều cần backend.

**Thứ tự bật bắt buộc:** PostgreSQL → Backend → (Web Admin và Mobile, thứ tự nào trước cũng được).

---

## 1. Khởi động PostgreSQL

PostgreSQL đã được cấu hình **tự chạy cùng Windows**, nên bình thường không cần làm gì. Kiểm tra cho chắc:

```powershell
Get-Service postgresql-x64-18 | Select-Object Name, Status, StartType
```

Kết quả mong đợi:

```
Name                Status  StartType
----                ------  ---------
postgresql-x64-18  Running  Automatic
```

- `Running` → sang bước 2.
- `Stopped` → chạy `Start-Service postgresql-x64-18` rồi kiểm tra lại.
- Không tìm thấy service → xem [docs/troubleshooting/Error_PostgreSQL_Service_Missing.md](docs/troubleshooting/Error_PostgreSQL_Service_Missing.md).

**Thông tin kết nối** (dùng ở bước 6):

| Mục | Giá trị |
|---|---|
| Host | `localhost` |
| Port | `5432` |
| Database | `agrilog` |
| User | `postgres` |
| Mật khẩu | đặt lúc cài PostgreSQL — cũng nằm trong `backend/.env` |

---

## 2. Bật Backend FastAPI — cổng 8000

Mở **Terminal 1** trong VS Code (`` Ctrl+` ``), đảm bảo là PowerShell:

```powershell
cd d:\agrilogapp\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Đợi tới khi thấy:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
AgriLog API v... starting (env=development)
INFO:     Application startup complete.
```

> **Vì sao bắt buộc `--host 0.0.0.0`:** nếu chỉ bind vào `127.0.0.1`, backend chỉ nghe từ chính máy tính. Máy ảo Android gọi qua địa chỉ `10.0.2.2`, còn điện thoại thật gọi qua IP LAN — cả hai đều là "từ máy khác" nên sẽ không kết nối được, dù backend chạy hoàn toàn bình thường.

**Giữ terminal này chạy suốt phiên demo.**

### Kiểm tra nhanh

Mở trình duyệt:

- **http://localhost:8000/health/db** → phải trả `{"status":"ok","database":"reachable"}`
- **http://localhost:8000/docs** → Swagger UI, xem được toàn bộ API

### Nếu báo lỗi database

```powershell
# Mở terminal MỚI, đừng tắt terminal uvicorn
cd d:\agrilogapp\backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

Lệnh này tạo/cập nhật toàn bộ bảng. Chạy lại được nhiều lần, không hỏng dữ liệu sẵn có.

---

## 3. Bật Web Admin Next.js — cổng 3000

Mở **Terminal 2**:

```powershell
cd d:\agrilogapp\web
npm install        # chỉ cần lần đầu
npm run dev
```

Đợi thấy:

```
▲ Next.js 16.3.1
- Local:   http://localhost:3000
✓ Ready in ...
```

Truy cập **http://localhost:3000** → tự chuyển sang trang đăng nhập.

> **Nếu báo `Port 3000 is in use`:** đã có một server chạy sẵn. Dùng luôn cái đó, hoặc tắt bằng `taskkill /PID <số PID trong thông báo> /F` rồi chạy lại.

### Đăng nhập tài khoản quản trị

Trang này **chỉ nhận tài khoản có quyền quản trị**. Tài khoản thường đăng nhập sẽ bị từ chối với thông báo rõ ràng.

**Xem ai đang có quyền quản trị:**

```powershell
cd d:\agrilogapp\backend
.\.venv\Scripts\Activate.ps1
python -m scripts.make_admin --list
```

**Cấp quyền cho một tài khoản đã đăng ký:**

```powershell
python -m scripts.make_admin email-cua-ban@example.com
```

**Thu hồi quyền:**

```powershell
python -m scripts.make_admin email-cua-ban@example.com --revoke
```

> **Vì sao phải chạy lệnh mà không bấm nút trên web:** không có endpoint nào cấp được quyền quản trị. Một API làm được việc đó là một API có thể bị lợi dụng để tự nâng quyền. Việc thăng quyền vì vậy đòi hỏi quyền truy cập vào máy chủ — thứ mà một request HTTP không vượt qua được. Script cũng từ chối thu hồi tài khoản quản trị **cuối cùng**, để không ai tự khoá mình ra ngoài.

### Web Admin có gì

| Trang | Nội dung |
|---|---|
| `/` — Tổng quan | Số nông hộ, tài khoản, mùa vụ, nhật ký; hoạt động 7/30 ngày qua |
| `/users` — Tài khoản | Toàn bộ tài khoản mọi nông hộ; tìm kiếm, lọc, phân trang, khoá/mở |

> Số mùa vụ và nhật ký chỉ đếm **phần đã đồng bộ lên máy chủ**. Dữ liệu bà con vừa ghi trên điện thoại còn nằm ở máy tới lần đồng bộ kế tiếp — con số thấp không có nghĩa là không ai dùng app.

---

## 4. Bật Mobile App qua Metro — máy ảo

### 4.1. Khởi động máy ảo trước

1. Mở **Android Studio**.
2. **More Actions → Virtual Device Manager** (hoặc **Tools → Device Manager** nếu đã mở project).
3. Bấm **▶** cạnh thiết bị ảo.
4. **Đợi tới khi thấy màn hình Home của Android.** Đừng chạy bước tiếp theo trước lúc đó.

Không cần Android Studio thì dùng terminal:

```powershell
emulator -list-avds
emulator -avd <tên_vừa_liệt_kê>
```

### 4.2. Metro bundler — Terminal 3

```powershell
cd d:\agrilogapp\mobile
npm install        # chỉ cần lần đầu
npm start
```

Giữ terminal này chạy suốt phiên.

### 4.3. Build và cài app — Terminal 4

```powershell
cd d:\agrilogapp\mobile
npm run android
```

Lần đầu Gradle build có thể mất vài phút. Xong thì app **tự cài và mở** trên máy ảo.

### 4.4. Xác minh cầu nối Metro

```powershell
adb reverse --list
```

Phải thấy dòng `tcp:8081 tcp:8081`.

> **Vì sao cần:** bản debug không đóng gói sẵn mã JavaScript — nó tải bundle từ Metro qua HTTP mỗi lần mở. `localhost:8081` mà app gọi là localhost **của máy ảo**, không phải của máy tính. Lệnh `adb reverse` là cầu nối, và `npm run android` chạy nó **một lần** sau khi cài. Nó **mất đi** khi khởi động lại máy ảo hoặc restart ADB — đây là nguyên nhân số một của lỗi "Unable to load script" dù Metro vẫn chạy tốt. Chạy lại `adb reverse tcp:8081 tcp:8081` là xong, không cần build lại.

### 4.5. Tạo tài khoản và đăng nhập

Nếu chưa có tài khoản, tạo qua Swagger — **http://localhost:8000/docs** → `POST /api/v1/auth/register` → **Try it out**:

```json
{
  "email": "demo@agrilog.vn",
  "password": "matkhau123",
  "full_name": "Nguyen Van A",
  "household_name": "Ho Nguyen Van A"
}
```

- Code `201` → tạo thành công.
- Code `409` → email đã tồn tại, dùng luôn tài khoản đó để đăng nhập.

Sau đó mở app trên máy ảo, nhập email/mật khẩu, bấm **Đăng nhập**.

> Chỉ cần đăng nhập **một lần**. Sau đó app hoạt động đầy đủ kể cả khi tắt hẳn mạng — đó chính là điểm cốt lõi của đồ án. Muốn demo, bật **chế độ máy bay** rồi tạo mùa vụ / ghi nhật ký / xem biểu đồ bình thường, tắt máy bay rồi bấm **Đồng bộ**.

---

## 5. Chạy app trên điện thoại Android thật

Máy ảo đủ để demo, nhưng chạy trên máy thật thuyết phục hơn nhiều. Phần này làm được trong khoảng 10 phút.

### 5.1. Bật chế độ nhà phát triển trên điện thoại

1. Vào **Cài đặt → Giới thiệu điện thoại** (Settings → About phone).
2. Tìm dòng **Số hiệu bản dựng** (Build number). Trên máy Samsung nó nằm sâu hơn: **Giới thiệu điện thoại → Thông tin phần mềm**.
3. **Chạm liên tiếp 7 lần** vào dòng đó. Máy sẽ đếm ngược "Bạn còn 3 bước nữa…" rồi báo **"Bạn đã là nhà phát triển!"**.
4. Quay lại **Cài đặt → Hệ thống → Tùy chọn nhà phát triển** (Developer options). Một số máy để ở **Cài đặt → Tùy chọn nhà phát triển** ngoài cùng.
5. Bật **Tùy chọn nhà phát triển** (công tắc trên cùng).
6. Bật **Gỡ lỗi qua USB** (USB debugging).

### 5.2. Cắm cáp và cho phép kết nối

1. Cắm điện thoại vào máy tính bằng **cáp USB truyền dữ liệu** (cáp chỉ để sạc sẽ không nhận — đây là lỗi hay gặp nhất).
2. Trên điện thoại hiện hộp thoại **"Cho phép gỡ lỗi USB?"** → tích **"Luôn cho phép từ máy tính này"** → **OK**.
3. Nếu không thấy hộp thoại, kéo thanh thông báo xuống, chạm mục USB và chọn chế độ **Truyền tệp (File Transfer / MTP)**.

Kiểm tra máy tính đã nhận:

```powershell
adb devices
```

Kết quả mong đợi:

```
List of devices attached
R58M12ABCDE     device
```

- `device` → tốt.
- `unauthorized` → chưa bấm đồng ý trên điện thoại, xem lại mục 2.
- Không có dòng nào → thử cáp khác, cổng USB khác, hoặc cài driver USB của hãng điện thoại.

### 5.3. Đổi địa chỉ IP để app gọi được Backend ⚠️

**Đây là bước quan trọng nhất, và là bước dễ quên nhất.**

Địa chỉ `10.0.2.2` chỉ có ý nghĩa **bên trong máy ảo Android** — đó là bí danh mà máy ảo dùng để gọi về máy tính chủ. Điện thoại thật không hiểu địa chỉ này; với nó, `10.0.2.2` là một máy nào đó không tồn tại. App sẽ báo **"Không kết nối được máy chủ"** ở màn hình đăng nhập.

**Bước 1 — Tìm địa chỉ IPv4 LAN của máy tính:**

```powershell
ipconfig | Select-String -Pattern "IPv4"
```

Hoặc gọn hơn, chỉ lấy IP của card mạng đang dùng:

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.InterfaceAlias -notmatch 'Loopback|vEthernet|WSL' } |
  Select-Object InterfaceAlias, IPAddress
```

Kết quả ví dụ:

```
InterfaceAlias   IPAddress
--------------   ---------
Wi-Fi            192.168.1.11
```

→ Địa chỉ cần dùng là **`192.168.1.11`** (máy bạn sẽ ra số khác).

**Bước 2 — Sửa địa chỉ trong mã nguồn:**

Mở file **`mobile/src/services/api.ts`**, tìm dòng 18:

```ts
export const API_BASE_URL = 'http://10.0.2.2:8000';
```

Đổi thành IP vừa tìm được:

```ts
export const API_BASE_URL = 'http://192.168.1.11:8000';
```

**Bước 3 — Cho phép tường lửa Windows mở cổng 8000:**

Lần đầu chạy `uvicorn`, Windows thường hiện hộp thoại hỏi quyền — chọn **Cho phép truy cập** và **nhớ tích ô "Mạng riêng"**. Nếu đã lỡ bấm Hủy, mở PowerShell **quyền Administrator** và chạy:

```powershell
New-NetFirewallRule -DisplayName "AgriLog Backend 8000" `
  -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
```

**Bước 4 — Điện thoại và máy tính phải chung một mạng Wi-Fi.** Điện thoại dùng 4G sẽ không thấy được máy tính.

**Bước 5 — Kiểm tra trước khi build.** Mở trình duyệt **trên điện thoại**, vào:

```
http://192.168.1.11:8000/health
```

Thấy JSON `{"status":"ok",...}` là mạng đã thông. Nếu không thấy, vấn đề nằm ở tường lửa hoặc Wi-Fi — sửa xong hãy build, đừng build rồi mới dò.

### 5.4. Build lên điện thoại

```powershell
cd d:\agrilogapp\mobile
npm run android
```

Với đúng một thiết bị đang cắm, lệnh này tự chọn nó. Nếu vừa mở máy ảo vừa cắm điện thoại, chỉ định rõ:

```powershell
adb devices                                   # xem mã thiết bị
npx react-native run-android --deviceId R58M12ABCDE
```

### 5.5. Metro trên điện thoại thật

Metro **không cần đổi IP** nếu điện thoại nối bằng cáp USB — `adb reverse` hoạt động y hệt như với máy ảo:

```powershell
adb reverse tcp:8081 tcp:8081
```

`npm run android` đã tự chạy lệnh này. Nếu app báo "Unable to load script", chạy lại lệnh trên rồi lắc điện thoại → **Reload**.

### 5.6. Giải pháp thay thế khi Wi-Fi chặn thiết bị nói chuyện với nhau

Wi-Fi ở trường học, quán cà phê, hội trường thường bật **AP isolation** — các thiết bị cùng mạng không gọi được nhau. Khi đó cách ở mục 5.3 sẽ không chạy dù làm đúng hết.

Cách vòng qua, **chỉ cần cáp USB, không phụ thuộc Wi-Fi**:

1. Trong `mobile/src/services/api.ts`, đổi thành:
   ```ts
   export const API_BASE_URL = 'http://localhost:8000';
   ```
2. Bắc cầu cổng 8000 qua USB:
   ```powershell
   adb reverse tcp:8000 tcp:8000
   ```

Lúc này `localhost:8000` trên điện thoại được ADB chuyển thẳng về cổng 8000 của máy tính. **Đây là cách đáng tin cậy nhất khi demo ở hội trường** — nhớ chạy lại `adb reverse` sau mỗi lần rút/cắm cáp.

### 5.7. Lưu ý về bản release

Hướng dẫn trên áp dụng cho **bản debug**. Bản debug cho phép gọi HTTP không mã hoá (`usesCleartextTraffic="true"`), nên `http://192.168.1.11:8000` chạy được. Bản **release** đặt cờ này thành `false` và Android sẽ chặn mọi kết nối HTTP — bản phát hành thật cần HTTPS. Điều này không ảnh hưởng tới việc demo đồ án.

---

## 6. Tra cứu cơ sở dữ liệu bằng pgAdmin

Dùng để chứng minh dữ liệu từ điện thoại đã thật sự lên máy chủ.

### 6.1. Kết nối lần đầu

1. Mở **pgAdmin 4** (cài kèm PostgreSQL, tìm trong Start Menu).
2. Panel trái, chuột phải **Servers → Register → Server…**
3. Tab **General** → **Name:** `AgriLog` (tên tuỳ ý, chỉ để bạn nhận ra).
4. Tab **Connection** điền:

   | Trường | Giá trị |
   |---|---|
   | Host name/address | `localhost` |
   | Port | `5432` |
   | Maintenance database | `postgres` |
   | Username | `postgres` |
   | Password | mật khẩu đặt lúc cài PostgreSQL |

   Tích **Save password** cho đỡ nhập lại.
5. Bấm **Save**.

### 6.2. Tìm tới bảng dữ liệu

Trong cây bên trái, đi theo đường:

```
Servers → AgriLog → Databases → agrilog → Schemas → public → Tables
```

Chuột phải một bảng → **View/Edit Data → All Rows** để xem nội dung.

> **Dùng DBeaver thay thế?** Được. Tạo kết nối PostgreSQL với đúng thông số ở bảng trên. DBeaver nhẹ hơn và không kén phiên bản.

### 6.3. Vài câu lệnh SQL hay dùng khi demo

Mở **Tools → Query Tool** rồi dán:

```sql
-- Toàn bộ mùa vụ, mới nhất trước
SELECT name, crop_type, status, to_timestamp(start_date/1000)::date AS ngay_bat_dau
FROM seasons WHERE deleted_at IS NULL
ORDER BY created_at DESC;

-- Nhật ký canh tác gần đây
SELECT work_type, title, to_timestamp(entry_date/1000)::date AS ngay
FROM diary_entries WHERE deleted_at IS NULL
ORDER BY created_at DESC LIMIT 10;

-- TỒN KHO hiện tại — tính từ sổ cái, không đọc sẵn ở đâu cả.
-- COALESCE để vật tư chưa phát sinh giao dịch nào hiện 0 thay vì ô trống.
SELECT s.name, s.unit,
       COALESCE(SUM(CASE WHEN t.txn_type = 'out' THEN -t.quantity ELSE t.quantity END), 0) AS ton_kho
FROM supplies s
LEFT JOIN stock_transactions t ON t.supply_id = s.id AND t.deleted_at IS NULL
WHERE s.deleted_at IS NULL
GROUP BY s.id, s.name, s.unit;

-- Thu chi và lãi từng mùa vụ
SELECT sea.name,
       COALESCE((SELECT SUM(amount) FROM revenues r
                 WHERE r.season_id = sea.id AND r.deleted_at IS NULL), 0) AS doanh_thu,
       COALESCE((SELECT SUM(amount) FROM expenses e
                 WHERE e.season_id = sea.id AND e.deleted_at IS NULL), 0) AS chi_phi
FROM seasons sea WHERE sea.deleted_at IS NULL;

-- Phân biệt chi phí tự sinh từ nhật ký với chi phí nhập tay
SELECT source, COUNT(*) AS so_khoan, SUM(amount) AS tong_tien
FROM expenses WHERE deleted_at IS NULL GROUP BY source;
```

> **Vì sao câu nào cũng có `deleted_at IS NULL`:** hệ thống **xoá mềm**. Bản ghi bị xoá vẫn nằm lại trong bảng với dấu thời gian ở `deleted_at`, để thiết bị khác biết mà xoá theo khi đồng bộ. Quên điều kiện này thì báo cáo sẽ đếm cả những thứ người dùng đã xoá.

---

## 7. Từ điển dữ liệu

Giải thích bằng ngôn ngữ thường ngày. Chi tiết kỹ thuật đầy đủ nằm ở `Data_Requirements_Database.md`.

### 7.1. Luồng chảy của dữ liệu

```
        households (nông hộ)
             │
             ├──── users (người đăng nhập)
             │
             └──── seasons (mùa vụ)
                      │
                      ├──── diary_entries (nhật ký công việc)
                      │            │
                      │            │ dùng vật tư thì tự sinh ra
                      │            ▼
                      │     stock_transactions (sổ cái kho) ──► supplies
                      │            │
                      │            │ và tự sinh tiếp
                      │            ▼
                      ├──── expenses (khoản chi)
                      │
                      └──── revenues (khoản thu)
```

Đọc theo lời: **một nông hộ** có nhiều **tài khoản**, mỗi hộ trồng nhiều **mùa vụ**. Trong mỗi mùa vụ, người dùng ghi **nhật ký**. Nếu nhật ký đó có dùng vật tư, hệ thống **tự động** trừ kho và **tự động** tạo khoản chi tương ứng — người dùng chỉ nhập một lần.

### 7.2. Các bảng cốt lõi

| Bảng | Nói nôm na là gì | Điểm cần biết |
|---|---|---|
| **`households`** | **Nông hộ** — đơn vị sở hữu dữ liệu | Mọi bảng dữ liệu đều gắn với một nông hộ. Hộ này tuyệt đối không đọc được dữ liệu hộ kia. |
| **`users`** | **Tài khoản đăng nhập** | Một hộ có thể nhiều tài khoản (bố và con dùng hai điện thoại). `is_active` = còn dùng được không, `is_admin` = có vào được Web Admin không. Mật khẩu lưu dạng băm bcrypt, không lưu bản gốc. |
| **`refresh_tokens`** | **Phiếu giữ phiên đăng nhập** | Sống 90 ngày, để điện thoại ở vùng mất sóng ba tuần vẫn đồng bộ được khi có mạng lại mà không phải đăng nhập lại. |
| **`seasons`** | **Mùa vụ** — ví dụ "Vụ Đông Xuân 2026" | Có tên, loại cây, diện tích, ngày bắt đầu/kết thúc, trạng thái (`planning` chuẩn bị / `active` đang canh tác / `harvested` đã thu hoạch / `closed` đã kết thúc). Mọi chi phí, doanh thu, nhật ký đều quy về mùa vụ để tính lãi lỗ. |
| **`diary_entries`** | **Nhật ký canh tác** — "hôm nay tôi làm gì ngoài ruộng" | Loại công việc: làm đất, gieo trồng, bón phân, phun thuốc, tưới nước, làm cỏ, thu hoạch, khác. Kèm ngày, thời tiết, số giờ công, ghi chú. |
| **`supplies`** | **Danh mục vật tư** — "tôi có những loại gì trong kho" | Đây chỉ là **danh sách tên gọi**: tên, nhóm (phân bón / thuốc BVTV / giống / nhiên liệu / dụng cụ), đơn vị tính, đơn giá, ngưỡng cảnh báo sắp hết. **Không chứa số lượng tồn.** |
| **`stock_transactions`** | **Sổ cái kho** — "từng lần vật tư ra vào" | Bảng quan trọng nhất để hiểu hệ thống. Mỗi dòng là một lần **nhập** (`in`), **xuất** (`out`) hoặc **kiểm kê điều chỉnh** (`adjust`). Tồn kho **không được lưu ở đâu cả** — nó luôn được tính lại bằng cách cộng dồn bảng này. |
| **`expenses`** | **Khoản chi** | Có `source` phân biệt hai nguồn gốc: `manual` là người dùng tự nhập (thuê nhân công, tiền dầu…), `diary_auto` là hệ thống tự sinh khi nhật ký tiêu thụ vật tư. Khoản `diary_auto` **không sửa trực tiếp được** — muốn đổi phải sửa lượng vật tư trong nhật ký. |
| **`revenues`** | **Khoản thu** — bán nông sản | Ghi sản lượng, đơn giá, thành tiền, người mua. Thành tiền có thể nhập tay khác với sản lượng × đơn giá, vì thực tế hay bị trừ hao ẩm hoặc làm tròn. |
| **`app_settings`** | **Cấu hình hệ thống** cho quản trị viên | Đúng **một dòng duy nhất**, ràng buộc ở tầng database. Chứa cờ bật/tắt chế độ bảo trì và thông báo hiển thị cho người dùng. |
| **`sync_sessions`** | **Nhật ký đồng bộ** | Ghi lại mỗi lượt điện thoại gửi/nhận dữ liệu: thiết bị nào, lúc nào, thành công hay lỗi. Dùng để dò khi hai máy bất đồng dữ liệu. |

### 7.3. Ba điều làm hội đồng dễ hiểu sai

**1. Tồn kho không nằm trong bảng `supplies`.**
Nhìn vào `supplies` sẽ không thấy cột nào ghi số lượng. Đó là cố ý. Nếu lưu sẵn một con số rồi cho hai điện thoại cùng trừ đi khi đang offline, lúc đồng bộ sẽ ra một con số **sai mà không cách nào phát hiện**. Cộng dồn sổ cái thì luôn ra đúng, dù bao nhiêu thiết bị và bao nhiêu lần mất mạng.

**2. Ngày tháng lưu bằng số, không phải kiểu ngày.**
Các cột `start_date`, `entry_date`, `txn_date`… là số nguyên — **mili-giây tính từ 1/1/1970**. Muốn đọc trong SQL thì dùng `to_timestamp(cot/1000)`. Lưu kiểu này để điện thoại và máy chủ không bao giờ hiểu lệch nhau về múi giờ.

**3. Xoá là xoá mềm.**
Không dòng nào bị xoá thật. Chúng được đánh dấu `deleted_at` và giữ lại, để thiết bị khác biết mà xoá theo ở lần đồng bộ kế tiếp. Xoá thật sẽ khiến máy còn lại không bao giờ biết là đã có gì đó bị xoá.

---

## 8. Bảng tóm tắt & checklist sự cố

### Các terminal cần mở

| # | Thư mục | Lệnh | Tắt được không? |
|---|---|---|---|
| 1 | `backend` | `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` | ❌ Giữ suốt phiên |
| 2 | `web` | `npm run dev` | ❌ Giữ nếu cần demo Web Admin |
| 3 | `mobile` | `npm start` (Metro) | ❌ Giữ suốt phiên |
| 4 | `mobile` | `npm run android` | ✅ Tắt sau khi app đã cài xong |

### Các cổng

| Cổng | Của ai |
|---|---|
| 5432 | PostgreSQL |
| 8000 | Backend FastAPI |
| 3000 | Web Admin Next.js |
| 8081 | Metro bundler |

### Checklist khi có sự cố

- [ ] `Get-Service postgresql-x64-18` → `Running`
- [ ] `http://localhost:8000/health/db` → `{"status":"ok","database":"reachable"}`
- [ ] `http://localhost:3000` → ra trang đăng nhập, không phải lỗi kết nối
- [ ] Máy ảo đã hiện màn hình Home **trước khi** chạy `npm run android`
- [ ] Terminal Metro vẫn chạy, chưa bị tắt
- [ ] `adb reverse --list` có `tcp:8081 tcp:8081` — mất dòng này là nguyên nhân số 1 của "Unable to load script"
- [ ] Web Admin không vào được → đã cấp quyền chưa? `python -m scripts.make_admin --list`
- [ ] Điện thoại thật không gọi được API → đã đổi `API_BASE_URL` sang IP LAN chưa? Đã mở tường lửa cổng 8000 chưa?

### Sổ tay xử lý lỗi

Các sự cố đã gặp và cách khắc phục nằm ở **[docs/troubleshooting/](docs/troubleshooting/)**:

| File | Nội dung |
|---|---|
| [Error_PostgreSQL_Service_Missing.md](docs/troubleshooting/Error_PostgreSQL_Service_Missing.md) | Service PostgreSQL chưa đăng ký |
| [Error_Metro_Watcher_Crash_CXX_Build.md](docs/troubleshooting/Error_Metro_Watcher_Crash_CXX_Build.md) | Metro sập, lỗi "Unable to load script" |
| [Error_WatermelonDB_BuildConfig_AGP9.md](docs/troubleshooting/Error_WatermelonDB_BuildConfig_AGP9.md) | Build Android lỗi `BuildConfig` |
| [Error_Postgres_Locale_Case_Folding.md](docs/troubleshooting/Error_Postgres_Locale_Case_Folding.md) | `lower()` không hạ được chữ tiếng Việt |
| [Error_Sync_Cursor_Transaction_Timestamp.md](docs/troubleshooting/Error_Sync_Cursor_Transaction_Timestamp.md) | Con trỏ đồng bộ làm mất dữ liệu âm thầm |

---

*Tài liệu này được lập với sự hỗ trợ của Claude (Anthropic), theo tinh thần công khai đóng góp AI ở `README.md` §15.*
