# Báo Cáo Tiến Độ Dự Án AgriLog

**Ngày báo cáo:** 13/08/2026
**Phạm vi:** Rà soát toàn bộ codebase (backend FastAPI, mobile React Native/WatermelonDB, test suite, tài liệu) tại thời điểm chuyển từ thực hiện một mình (Thái) sang mô hình hai người (Thái + Khoa).
**Phương pháp:** Không dựa trên tài liệu cũ — mọi số liệu trong báo cáo này đều lấy trực tiếp từ việc chạy test thật (`pytest`, `jest`), đếm file/dòng thật, và đọc mã nguồn thật tại thời điểm báo cáo.

> Lưu ý: đề cương đồ án có mốc **M5 — Báo cáo tiến độ lần 1** vào 24/9–28/9/2026 (xem `README.md` §11). Báo cáo này phục vụ việc bàn giao nội bộ, không thay thế báo cáo M5 chính thức nộp cho giáo viên hướng dẫn.

---

## 1. Tóm tắt điều hành

Backend đã hoàn thiện và được kiểm thử ở mức đáng tin cậy: **7 module API, 350 test tự động, 100% xanh, 94% độ phủ code**. Toàn bộ giao diện di động cũng đã được **xây xong về mặt code** — 12 màn hình trên 5 module — và hôm nay (13/08) lần đầu tiên chạy thành công trên máy ảo Android thật (không còn chỉ chạy trong môi trường giả lập của Jest). Tuy nhiên, phần mobile **chưa được kiểm thử ở mức người dùng thật**: chưa test trên thiết bị vật lý, chưa chạy qua kịch bản ngoại tuyến (máy bay mode) mà README chính dự án gọi là "phép thử quan trọng nhất của cả đồ án", và không có bất kỳ test tự động nào ở tầng giao diện (chỉ có test tầng service/DB cục bộ).

Đây chính là ranh giới bàn giao hợp lý: **Thái giữ backend + sync engine (đã chín)**, **Khoa nhận mobile UI + toàn bộ phần kiểm thử người dùng thật (đang là lỗ hổng lớn nhất của dự án)**.

Quá trình rà soát cũng phát hiện **2 rủi ro cần xử lý trước khi push lên GitHub** — xem Mục 6.

---

## 2. Đối chiếu với lộ trình đề cương

| Mốc | Nội dung | Thời gian | Trạng thái theo `README.md` | Trạng thái thực tế sau rà soát |
|---|---|---|---|---|
| M1 | Phân tích đề tài | 10/8–16/8 | ✅ | ✅ |
| M2 | Thiết kế chi tiết | 17/8–26/8 | ✅ | ✅ (ADR, data model đã có) |
| M3 | Nền tảng Backend & Mobile | 27/8–9/9 | 🔶 backend xong | ✅ backend xong; **mobile foundation cũng đã xong** (WatermelonDB schema, nav shell, sync adapter) — README chưa cập nhật dòng này |
| M4 | Module Nhật ký & Chi phí | 10/9–23/9 | 🔶 backend xong | ✅ backend xong; **UI mobile cũng đã xây xong**, chưa kiểm thử người dùng thật |
| M5 | Báo cáo tiến độ lần 1 | 24/9–28/9 | ⬜ | việc bàn giao này đi trước mốc chính thức ~6 tuần |
| M6 | Sync Engine | 29/9–12/10 | 🔶 backend xong | ✅ backend xong (push/pull, ghi-sau-thắng, hợp nhất theo trường); **mobile sync adapter đã code xong nhưng chưa kiểm thử đồng bộ đa thiết bị thật** |
| M7 | Kiểm thử ngoại tuyến & đồng bộ | 13/10–22/10 | ⬜ | ⬜ **chưa bắt đầu — đây là trọng tâm công việc của Khoa** |
| M8 | Module Báo cáo & Trực quan hóa | 23/10–1/11 | 🔶 backend xong | ✅ backend xong (3 endpoint tổng hợp); **3 biểu đồ mobile đã code xong, chưa xác nhận render đúng trên thiết bị** |
| M9 | Báo cáo tiến độ lần 2 | 2/11–5/11 | ⬜ | ⬜ |
| M10 | Tối ưu & hoàn thiện | 6/11–12/11 | ⬜ | ⬜ |
| M11 | Bảo vệ đồ án | 13/11–15/11 | ⬜ | ⬜ |

**Nhận xét:** dự án đang **vượt tiến độ về khối lượng code** (M3/M4/M6/M8 mobile thực chất đã code xong, sớm hơn mốc đề cương) nhưng **chưa chạm tới M7** (kiểm thử ngoại tuyến/đồng bộ) — đúng bằng phần việc sẽ giao cho Khoa.

---

## 3. Backend — hoàn thành và đã kiểm thử (xác nhận bằng cách chạy thật)

```
cd backend && pytest -q            → 350 passed, 0 failed
cd backend && pytest --cov=app     → TOTAL 94% (2525 statements, 150 miss)
```

| Module | Router | File test | Số test |
|---|---|---|---|
| Xác thực (JWT + refresh rotation) | `api/v1/auth.py` | `test_auth.py` | 39 |
| Mùa vụ (CRUD, cascading soft delete) | `api/v1/seasons.py` | `test_seasons.py` | 38 |
| Nhật ký (hoàn kho, tự sinh chi phí) | `api/v1/diary.py` | `test_diary.py` | 46 |
| Vật tư / tồn kho | `api/v1/supplies.py` | `test_supplies.py` | 44 |
| Thu chi | `api/v1/finance.py` | `test_finance.py` | 34 |
| Báo cáo (3 endpoint tổng hợp) | `api/v1/reports.py` | `test_reports.py` | 33 |
| Đồng bộ (push/pull) | `api/v1/sync.py` | `test_sync.py` + `test_sync_contract.py` | 48 + 5 |
| Bảo mật (hash mật khẩu, JWT core) | `core/security.py` | `test_security.py` | 16 |
| Xử lý thời gian (epoch-ms, kẹp lệch đồng hồ) | `core/timeutils.py` | `test_timeutils.py` | 14 |
| Song song schema ORM ↔ migration | — | `test_schema_integrity.py` | 14 |
| Song song schema PostgreSQL ↔ WatermelonDB | — | `test_schema_parity.py` | 11 |
| Health probe | `main.py` | `test_health.py` | 8 |

Tất cả 9 router (`auth`, `seasons`, `supplies`, `diary` ×2, `finance` ×2, `reports`, `sync`) đã được gắn vào ứng dụng thật trong `main.py::_register_v1_routers` — không có module nào "có file nhưng chưa nối vào app". Không còn `TODO`/`FIXME` nào trong `backend/app`.

**Điểm phủ test thấp hơn mặt bằng chung (không phải lỗi, nhưng đáng lưu ý):**

| File | Độ phủ | Ghi chú |
|---|---|---|
| `db/session.py` | 67% | Chỉ 12 dòng, phần chưa chạm là nhánh cấu hình connection pool ít dùng |
| `finance_service.py` | 88% | File nghiệp vụ có độ phủ thấp nhất trong toàn backend |
| `sync_service.py` | 91% | Một số nhánh lỗi hiếm (retry, SAVEPOINT) chưa có test riêng |
| `main.py` | 86% | Chủ yếu là nhánh guard `JWT_SECRET` khi `APP_ENV=production` |

**Sai lệch nhỏ so với tài liệu:** `README.md` ghi "345 test" — con số thật tại thời điểm rà soát là **350** (đã cộng dồn theo từng file `pytest --collect-only`). Độ phủ 94% khớp chính xác với README.

---

## 4. Mobile — đã xây dựng, CHƯA được kiểm thử ở mức người dùng thật

### 4.1 Số liệu xác nhận lại (khác với ước tính ban đầu)

| Số liệu | Ước tính ban đầu | Số liệu thật sau khi đếm |
|---|---|---|
| Số màn hình | ~13 | **12** (liệt kê đầy đủ bên dưới) |
| Dòng code UI (screens + components + navigation) | ~6500 | **5.329 dòng** |
| Tổng dòng code `mobile/src` (kể cả services, db, utils, không kể test) | — | **8.538 dòng** |

### 4.2 12 màn hình hiện có

| Module | Màn hình | File |
|---|---|---|
| Đăng nhập | Login | `screens/auth/LoginScreen.tsx` |
| Mùa vụ | Danh sách mùa vụ | `screens/seasons/SeasonListScreen.tsx` |
| Mùa vụ | Form mùa vụ | `screens/seasons/SeasonFormScreen.tsx` |
| Nhật ký | Danh sách nhật ký | `screens/diary/DiaryListScreen.tsx` |
| Nhật ký | Form nhật ký (kèm dùng vật tư) | `screens/diary/DiaryFormScreen.tsx` |
| Vật tư | Danh mục vật tư | `screens/supplies/SupplyListScreen.tsx` |
| Vật tư | Form vật tư | `screens/supplies/SupplyFormScreen.tsx` |
| Vật tư | Giao dịch kho (nhập/xuất) | `screens/supplies/StockMovementScreen.tsx` |
| Thu chi | Tổng kết thu chi theo mùa vụ | `screens/finance/FinanceScreen.tsx` |
| Thu chi | Form chi phí | `screens/finance/ExpenseFormScreen.tsx` |
| Thu chi | Form doanh thu | `screens/finance/RevenueFormScreen.tsx` |
| Báo cáo | 3 biểu đồ (thu-chi, vật tư, so sánh mùa vụ) | `screens/reports/ReportsScreen.tsx` |

Điều hướng: 1 stack gốc (Login ↔ Main) + 4 tab (Nhật ký, Vật tư, Thu chi, Báo cáo) + 3 stack con.

### 4.3 Cột mốc hôm nay: lần đầu chạy thật trên máy ảo

Commit `886031b` (13/08/2026) là **lần đầu tiên** ứng dụng chạy trên môi trường Android thật (Pixel 6a AVD) thay vì chỉ chạy trong Jest (dùng LokiJS giả lập, không phải SQLite thật). Quá trình này phát hiện và vá 2 lỗi chặn build hoàn toàn, đã ghi lại đầy đủ nguyên nhân gốc theo đúng quy trình xử lý lỗi của dự án:

- **`Error_WatermelonDB_BuildConfig_AGP9.md`** — thư viện WatermelonDB không biên dịch được dưới AGP 9 (thiếu `buildFeatures.buildConfig`). Đã vá bằng `patch-package`, tự áp dụng lại mỗi lần `npm install`.
- **`Error_Metro_Watcher_Crash_CXX_Build.md`** — Metro bundler sập khi thiếu Watchman (fallback `fs.watch` ném `ENOENT` chưa bắt được khi CMake tạo/xoá thư mục tạm). Đã vá bằng `resolver.blockList` trong `metro.config.js`.

Kết quả xác nhận được: **BUILD SUCCESSFUL, WatermelonDB khởi tạo SQLite thật trên thiết bị thành công ("Schema set up successfully"), app không crash qua vòng render giao diện đầu tiên.**

> **Điều chỉnh khung yêu cầu ban đầu:** nguyên nhân gốc không phải là "lỗi cổng 8081" — cổng 8081 chỉ là nơi triệu chứng xuất hiện (`adb reverse tcp:8081`, thông báo "Unable to load script"). Lỗi thật là Metro watcher crash (đã vá) và một đặc điểm vận hành đã biết: ánh xạ `adb reverse tcp:8081` bị mất mỗi khi máy ảo khởi động lại hoặc ADB kết nối lại — không phải bug, không sửa được bằng code, chỉ cần biết quy trình khôi phục (đã ghi trong `Huong_Dan_Khoi_Dong_Du_An.md`).

### 4.4 Khoảng trống kiểm thử thật sự (trọng tâm việc của Khoa)

| Đã có | Chưa có |
|---|---|
| 130 test Jest, 7 suite, 100% xanh | **0 test ở tầng giao diện/màn hình** — cả 130 test đều kiểm tra tầng service/DB cục bộ (hoàn kho, tổng hợp tài chính, rút gọn dữ liệu biểu đồ) hoặc smoke-test khởi động app (`__tests__/App.test.tsx`, 3 test: không lỗi khi mở, không gọi mạng lúc khởi động, hiện màn hình Login) |
| Build thành công 1 lần trên 1 AVD (Pixel 6a) | Chưa test trên **thiết bị Android vật lý** nào |
| WatermelonDB xác nhận khởi tạo SQLite thật | Chưa chạy **CRUD đầy đủ** (tạo/sửa/xoá) cho từng module trên thiết bị thật dưới Hermes — mới xác nhận app "không crash lúc mở" |
| `react-native-svg` có trong `package.json`, dùng qua `react-native-chart-kit` cho 3 biểu đồ | Chưa xác nhận **bằng mắt** cả 3 biểu đồ vẽ đúng, không crash, đọc được trên kích thước màn hình thật |
| Checklist "cam kết ngoại tuyến" (chế độ máy bay) đã viết sẵn ở `README.md` §8 | **Chưa chạy lần nào** — chính README gọi đây là "phép thử thủ công quan trọng nhất của cả đồ án" |
| Issue #37 (test CRUD ngoại tuyến), #40 (xung đột 2 thiết bị) đã có trong Kanban | Chưa thực hiện |
| — | **Không có golden fixture / snapshot test nào cho UI** — đã rà soát toàn repo (`grep -ri "golden\|fixture\|snapshot"`), không tìm thấy artefact tham chiếu nào cho giao diện. Việc "đối chiếu UI với golden fixture" hiện chỉ có thể hiểu là đối chiếu thủ công với bảng chức năng README §2 và `Data_Requirements_Database.md`, trừ khi nhóm quyết định tự dựng bộ snapshot test (đề xuất ở `Nhiem_Vu_Cua_Khoa.md`) |

---

## 5. Chưa xây dựng / chưa bắt đầu

- **CI/CD:** `README.md` §13 mô tả "CI chạy lint + test cho mỗi push và PR ở cả hai codebase (Issue #18)" nhưng **không tồn tại workflow nào** (`.github/workflows/` rỗng). Đây là gap giữa tài liệu và thực tế cần đóng sớm — nhất là khi bắt đầu nhận PR từ Khoa, vì CI chính là lưới an toàn cho code review.
- Load test đồng bộ (Issue #39, 500+ thay đổi tồn đọng).
- M9/M10 (báo cáo tiến độ lần 2, tối ưu & hoàn thiện).
- Test thiết bị vật lý, test đa thiết bị (Issue #40).

---

## 6. Phát hiện cần xử lý trước khi push lên GitHub

Rà soát phát hiện **2 file chưa được track chứa thông tin nhạy cảm dạng plaintext**. Cả hai hiện **chưa** vào git (an toàn), nhưng sẽ bị cuốn vào lần commit tới nếu dùng `git add .` / `git add -A`:

| File | Nội dung nhạy cảm | Khuyến nghị |
|---|---|---|
| `.vscode/settings.json` | Mật khẩu PostgreSQL thật của role `agrilog` (cấu hình kết nối SQLTools), dạng plaintext | Xoá trường `password` khỏi file trước khi commit (để SQLTools hỏi mật khẩu mỗi lần), hoặc đổi mật khẩu role `agrilog` sau khi xử lý. `.gitignore` hiện đang **cho phép** commit file này (`!.vscode/settings.json`) — cân nhắc bỏ dòng cho phép đó nếu không cần chia sẻ cấu hình editor |
| `Huong_Dan_Khoi_Dong_Du_An.md` | Mật khẩu tài khoản mẫu ở dạng ví dụ JSON thật (Bước 3) | Thay bằng placeholder trước khi commit, hoặc giữ file này ở máy cá nhân (thêm vào `.gitignore`) nếu không muốn chia sẻ |

File thứ ba, `AgriLog DB.session.sql` (untracked), đang **rỗng** — không có rủi ro, nhưng là rác từ extension SQL client của editor; khuyến nghị xoá thay vì commit.

Xem Mục "Lệnh Git" trong phản hồi chính để biết cách commit an toàn (loại trừ 2 file trên).

---

## 7. Phân công từ đây

| Người | Phạm vi | Lý do |
|---|---|---|
| **Thái** | Backend (FastAPI/SQLAlchemy/Alembic), database, sync engine, CI, review PR của Khoa | Đã xây và hiểu toàn bộ tầng này; đây cũng đúng phần việc "Thai" trong `AgriLog_GitHub_Issues_and_Kanban.md` gốc |
| **Khoa** | Mobile UI, kiểm thử thiết bị thật, kiểm thử ngoại tuyến/đồng bộ (M7) | Đúng phần việc "Khoa" đã phân công sẵn trong Kanban gốc (55 issue, ví dụ #16, #17, #37, #40); đây cũng chính là khoảng trống kiểm thử lớn nhất hiện nay |

Chi tiết nhiệm vụ: xem `Nhiem_Vu_Cua_Khoa.md`. Quy trình Git: xem `Huong_Dan_Ban_Giao_Khoa.md`.

---

*Báo cáo này được tổng hợp với sự hỗ trợ của Claude (Anthropic), theo đúng tinh thần công khai đóng góp AI đã nêu ở `README.md` §15. Toàn bộ số liệu được xác nhận bằng cách chạy test và đọc mã nguồn thật tại thời điểm 13/08/2026, không suy diễn từ tài liệu cũ.*
