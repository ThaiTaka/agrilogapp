# Báo cáo sự cố — Máy chủ PostgreSQL không chạy (service Windows chưa đăng ký)

**Ngày:** 11/08/2026
**Ảnh hưởng:** Issue #13 (pipeline PostgreSQL + Alembic), và mọi test đánh dấu `@pytest.mark.db`
**Mức độ:** Chặn công việc với database; không chặn phần còn lại của backend
**Trạng thái:** ✅ **Đã xử lý xong.** Service đã đăng ký, đặt khởi động tự động, và đang chạy.

---

## 1. Mô tả lỗi

Hai triệu chứng riêng biệt, một nguyên nhân gốc kèm một hệ quả kéo theo.

### Triệu chứng A — không có gì lắng nghe ở cổng 5432

```
Get-NetTCPConnection -LocalPort 5432 -State Listen
   (không có kết quả)
```

Mọi cố gắng kết nối đều cho ra:

```
psycopg.OperationalError: connection failed: Connection refused
    Is the server running on that host and accepting TCP/IP connections?
```

Bộ test pytest báo cáo điều này thành **14 skipped** thay vì thất bại, vì `tests/conftest.py` thăm dò database lúc thu thập test và chuyển tình trạng không kết nối được thành skip:

```
48 passed, 14 skipped in 2.46s
```

### Triệu chứng B — service Windows không tồn tại

```
sc.exe qc "postgresql-x64-18"
[SC] OpenService FAILED 1060:
The specified service does not exist as an installed service.
```

Chỉ có một service *liên quan* được đăng ký, và nó đang dừng:

```
Name          Status   DisplayName
----          ------   -----------
pgagent-pg18  Stopped  PostgreSQL Scheduling Agent - pgagent-pg18
```

---

## 2. Nguyên nhân gốc

**Service Windows của *máy chủ* PostgreSQL 18 chưa từng được đăng ký (hoặc đã bị gỡ), nên không có gì khởi động database lúc bật máy.**

Bằng chứng loại trừ các khả năng đáng lo hơn:

| Kiểm tra | Kết quả | Loại trừ được |
|---|---|---|
| `C:\Program Files\PostgreSQL\18\data\PG_VERSION` | tồn tại | Cụm chưa khởi tạo |
| `data\postmaster.opts` | tồn tại, hợp lệ | Cụm chưa từng chạy |
| `data\log\postgresql-2026-08-11_102422.log` | máy chủ chạy 10:24 → 10:51 cùng ngày | Cài đặt hỏng |
| Dòng log cuối | `LOG: shutting down` / `checkpoint complete: shutdown immediate` | Sập / tắt không sạch |
| `data\postmaster.pid` | không có | File khoá cũ chặn khởi động |
| `(Get-Acl data).Owner` | `BUILTIN\Administrators`, `Maxsys` ghi được | Vấn đề quyền |

Dòng quyết định trong log:

```
2026-08-11 10:51:27 +07 FATAL:  terminating connection due to administrator command
2026-08-11 10:51:27 +07 LOG:  shutting down
```

Đó là một lần **dừng có chủ đích, sạch sẽ, do quản trị viên**, không phải sự cố. Cụm dữ liệu khoẻ mạnh về mọi mặt; thứ duy nhất thiếu là mục service để đưa nó chạy lại. Nhiều khả năng bộ cài gói PostGIS/pgAgent (bản cài này có PostGIS, pgRouting, MobilityDB và pgPointCloud — xem `installation_summary.log`) đã đăng ký pgAgent nhưng service máy chủ bị gỡ hoặc chưa từng được tạo.

Việc `pgagent-pg18` có mặt và đang dừng là một **thông tin gây nhiễu**. pgAgent là bộ lập lịch công việc *kết nối tới* PostgreSQL; nó không phải database. Khởi động nó không giúp được gì, và chính nó khiến `Get-Service *postgres*` trả về một dòng làm tình hình trông đỡ tệ hơn thực tế.

### Hệ quả kéo theo: xác thực

`data\pg_hba.conf` yêu cầu mật khẩu cho mọi đường kết nối:

```
local   all   all                     scram-sha-256
host    all   all   127.0.0.1/32      scram-sha-256
host    all   all   ::1/128           scram-sha-256
```

Không có `%APPDATA%\postgresql\pgpass.conf`, không có biến môi trường `PG*`, nên mật khẩu `postgres` không lấy lại được từ máy — người phát triển phải tự cung cấp. Đây là **đúng và mong muốn** (một database dùng trust-auth trên laptop là một rủi ro), nên cách sửa là cung cấp mật khẩu chứ không phải nới lỏng `pg_hba.conf`.

---

## 3. Cách sửa từng bước

### 3.1 Khởi động máy chủ ngay — ✅ ĐÃ LÀM

```powershell
& "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" start -D "C:\Program Files\PostgreSQL\18\data" -w -t 30
```

Kết quả:

```
waiting for server to start....LOG:  redirecting log output to logging collector process
HINT:  Future log output will appear in directory "log".
 done
server started
```

**Cách này không sống sót qua lần khởi động lại máy.** Phải làm tiếp §3.2.

### 3.2 Đăng ký service để tự khởi động — ✅ ĐÃ LÀM (cần quyền Administrator)

Mở PowerShell **với quyền Administrator** (Win → gõ `powershell` → Ctrl+Shift+Enter):

```powershell
& "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" register `
    -N "postgresql-x64-18" `
    -D "C:\Program Files\PostgreSQL\18\data" `
    -S auto

Set-Service -Name "postgresql-x64-18" -StartupType Automatic
Start-Service -Name "postgresql-x64-18"
Get-Service -Name "postgresql-x64-18"
```

Kết quả xác nhận:

```
SERVICE_NAME: postgresql-x64-18
        TYPE               : 10  WIN32_OWN_PROCESS
        START_TYPE         : 2   AUTO_START
        BINARY_PATH_NAME   : "...\pg_ctl.exe" runservice -N "postgresql-x64-18" -D "...\data" -w

Name               Status StartType
postgresql-x64-18 Running Automatic
```

> Nếu `Start-Service` báo *"the service did not respond in a timely fashion"*, tức là máy chủ khởi động thủ công ở §3.1 vẫn đang giữ cổng 5432. Dừng nó trước:
> ```powershell
> & "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" stop -D "C:\Program Files\PostgreSQL\18\data" -m fast
> ```
> rồi `Start-Service` lại.

> **Vì sao dùng `-S auto` chứ không để mặc định:** không có nó, service được tạo ở chế độ *Demand start* và vấn đề sẽ tái diễn âm thầm sau lần khởi động lại tiếp theo — điều mà giữa kỳ đồ án trông y hệt như "code của tôi tự hỏng qua đêm".

### 3.3 Xác nhận mật khẩu `postgres`

```powershell
$env:PGPASSWORD = "<mật khẩu postgres của bạn>"
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -c "SELECT version();"
Remove-Item Env:\PGPASSWORD
```

Nếu không nhớ mật khẩu, phải đặt lại — thao tác này cần shell nâng quyền và tạm thời nới lỏng xác thực, nên hãy khôi phục ngay sau đó:

1. Sửa `C:\Program Files\PostgreSQL\18\data\pg_hba.conf`; **chỉ** đổi phương thức của dòng `127.0.0.1/32` từ `scram-sha-256` sang `trust`.
2. `& "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" reload -D "C:\Program Files\PostgreSQL\18\data"`
3. `psql -U postgres -h localhost -c "ALTER USER postgres PASSWORD 'mật_khẩu_mới';"`
4. **Đổi dòng đó về `scram-sha-256`** và reload lại.

Đừng bỏ bước 4. PostgreSQL ở chế độ `trust` chấp nhận mọi kết nối từ localhost với quyền superuser, kể cả từ bất kỳ chương trình nào bạn tình cờ chạy.

### 3.4 Tạo role ứng dụng và hai database

Đã có sẵn script làm việc này:

```powershell
cd d:\agrilogapp\backend
.\scripts\setup_db.ps1
```

Script hỏi mật khẩu `postgres` (nhập ẩn, không hiển thị), tạo role `agrilog` với mật khẩu đọc từ `backend\.env`, tạo hai database `agrilog` và `agrilog_test` do role đó sở hữu, rồi chạy migration. Chạy lại nhiều lần vô hại.

Ứng dụng cố ý **không** kết nối bằng superuser `postgres`. Nó chỉ cần sở hữu hai database của mình; chạy bằng superuser biến một lỗi SQL-injection từ vấn đề một database thành chiếm toàn cụm.

`agrilog_test` bắt buộc là database riêng: fixture pytest chạy `DROP SCHEMA public CASCADE` trước mỗi phiên. Trỏ nó vào `agrilog` sẽ xoá sạch dữ liệu phát triển mỗi lần chạy test.

### 3.5 Chạy migration và xác nhận

```powershell
cd d:\agrilogapp\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m pytest
```

Kỳ vọng: `alembic current` in ra `0002 (head)`, và các test trước đây bị skip nay chạy — **0 skipped**.

---

## 4. Danh sách kiểm tra

- [x] Tiến trình máy chủ đang chạy và lắng nghe cổng 5432
- [x] Service `postgresql-x64-18` đã đăng ký với chế độ khởi động `Automatic`
- [x] Service sống sót qua khởi động lại máy (đã đặt `AUTO_START`)
- [ ] Hai database `agrilog` và `agrilog_test` đã tồn tại — chạy `scripts\setup_db.ps1`
- [x] `backend\.env` đã tạo với `JWT_SECRET` sinh ngẫu nhiên
- [ ] `alembic upgrade head` thành công; `alembic current` báo `0002 (head)`
- [ ] `alembic downgrade base` rồi `upgrade head` đều thành công (tiêu chí nghiệm thu Issue #7)
- [ ] `pytest` báo 0 skipped

---

## 5. Phòng ngừa

**`GET /health/db` tồn tại đúng cho tình huống này.** Nó là phép kiểm tra *sẵn sàng*, tách biệt với `/health`: ứng dụng có thể hoàn toàn khoẻ trong khi database đứng sau thì không, và gộp hai thứ lại khiến một sự cố hạ tầng trông như lỗi ứng dụng.

```powershell
curl http://localhost:8000/health/db
# {"status":"ok","database":"reachable"}
# 503 {"status":"error","database":"unreachable","detail":"..."}
```

**Bộ test suy giảm chứ không nói dối.** `conftest.py` thăm dò một lần lúc thu thập test và chuyển các test cần DB thành skip kèm lý do, nên một máy chủ đang dừng cho ra `14 skipped` có giải thích thay vì 14 stack trace connection-refused khó hiểu. Hãy nhìn số skip chứ không chỉ nhìn dấu tích xanh — 14 skip nghĩa là các test về trigger đồng bộ và cột sinh tự động **đã không hề chạy**.

**Thêm một bước kiểm tra vào thói quen hằng ngày:**

```powershell
Get-Service postgresql-x64-18 | Select-Object Status
```

---

*Liên quan: `Data_Requirements_Database.md` §6.1 (trigger `touch_server_updated_at` mà các test này kiểm chứng), README §7 (cài đặt backend).*
