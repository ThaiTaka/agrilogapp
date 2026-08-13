# Nhiệm Vụ Của Khoa — Mobile UI & Kiểm Thử Thiết Bị Thật

**Nhánh làm việc:** `khoa-mobile-ui-fixes` (tạo từ `develop`)
**Cập nhật:** 13/08/2026, dựa trên rà soát mã nguồn thật — không phải ước tính.

---

## 0. Bối cảnh — đọc trước khi bắt đầu

Toàn bộ 12 màn hình mobile (Đăng nhập, Mùa vụ ×2, Nhật ký ×2, Vật tư ×3, Thu chi ×3, Báo cáo ×1) đã **code xong** và biên dịch sạch (`tsc` không lỗi). Hôm nay (13/08) app **lần đầu tiên** chạy được trên máy ảo Android thật — trước đó mọi thứ chỉ chạy qua Jest với LokiJS (một database giả lập trong bộ nhớ, không phải SQLite thật).

Nói cách khác: **phần "viết code" gần như xong, phần "chứng minh nó chạy đúng cho người dùng thật" gần như chưa bắt đầu.** Đây chính là công việc của bạn. Không cần viết lại UI từ đầu — trọng tâm là kiểm thử, sửa lỗi phát sinh khi kiểm thử, và lấp khoảng trống test.

Trước khi đọc file này, đọc qua:
- `README.md` — đặc biệt §2 (bảng chức năng), §8 (cài đặt mobile + checklist ngoại tuyến), §9 (cơ chế đồng bộ), §13 (chiến lược test)
- `Error_WatermelonDB_BuildConfig_AGP9.md` và `Error_Metro_Watcher_Crash_CXX_Build.md` — 2 lỗi build đã gặp và cách đã vá, để không tốn thời gian gặp lại
- `Huong_Dan_Ban_Giao_Khoa.md` — quy trình Git, **đặc biệt phần ranh giới không được đụng tới**

---

## 1. Dựng môi trường trên máy của bạn

Làm theo `README.md` §6–§8 (yêu cầu môi trường + cài đặt backend + cài đặt mobile). Vài điểm cần chú ý vì máy bạn là môi trường mới, chưa chắc giống máy Thái:

1. **Cài Watchman trước khi chạy Metro lần đầu**, kể cả khi tài liệu không bắt buộc. Lý do: máy Thái thiếu Watchman đã gây crash Metro thật (xem `Error_Metro_Watcher_Crash_CXX_Build.md`) — vá đã có sẵn trong `metro.config.js` nên bạn không nên gặp lại lỗi đó, nhưng cài Watchman vẫn là khuyến nghị chính thức của React Native cho Windows và tránh mọi rủi ro tương tự.
2. Bạn **vẫn cần chạy backend cục bộ** (PostgreSQL + FastAPI) để mobile có API gọi vào — làm theo README §7. Nếu thấy bất tiện khi phải dựng cả backend chỉ để sửa UI, trao đổi với Thái — có thể cân nhắc một backend dùng chung qua LAN thay vì mỗi người tự chạy.
3. `npm install` xong nhớ kiểm tra patch WatermelonDB đã tự áp dụng (`postinstall` chạy `patch-package` tự động — nếu quên, chạy tay `npx patch-package`).
4. **Không dùng `Huong_Dan_Khoi_Dong_Du_An.md` để lấy tài khoản đăng nhập mẫu** — file đó có mật khẩu thật của Thái và sẽ được thay bằng placeholder hoặc gỡ khỏi repo. Tự đăng ký tài khoản riêng của bạn qua Swagger UI (`http://localhost:8000/docs` → `POST /api/v1/auth/register`), theo đúng hướng dẫn ở README §7.5.

---

## 2. Nhiệm vụ chính

### 2.1 Xác nhận môi trường Metro / adb ổn định trên máy bạn

Đây **không phải sửa lỗi code** — lỗi crash Metro đã được vá trong `metro.config.js` (commit `886031b`). Việc của bạn là xác nhận vá đó cũng đứng vững trên máy bạn:

- Build và chạy app, xác nhận Metro không crash trong lúc Gradle build native (CMake).
- Nắm quy trình khôi phục khi gặp "Unable to load script" (đã ghi chi tiết ở `Huong_Dan_Khoi_Dong_Du_An.md`, phần "Nếu app báo lỗi..."): 90% trường hợp chỉ cần `adb reverse tcp:8081 tcp:8081` rồi reload, **không cần** build lại — ánh xạ này mất mỗi khi máy ảo khởi động lại hoặc ADB kết nối lại, kể cả khi Metro vẫn chạy tốt.
- Nếu bạn gặp một lỗi build/runtime **mới**, chưa có trong 2 file `Error_*.md` hiện tại: viết một file `Error_<Tên_Ngắn>.md` mới theo đúng mẫu của 2 file đó (mô tả lỗi → nguyên nhân gốc → cách sửa từng bước) — đây là quy ước đã thiết lập của dự án, không phải tuỳ chọn.

### 2.2 Kiểm thử WatermelonDB dưới Hermes — vượt xa "app mở được"

Xác nhận hôm nay mới dừng ở: app không crash lúc mở, WatermelonDB khởi tạo SQLite thành công. Việc còn lại:

- Với **từng module** (Mùa vụ, Nhật ký, Vật tư, Thu chi): thực hiện đủ **tạo / sửa / xoá** trên thiết bị thật (không phải Jest), xác nhận dữ liệu lưu đúng, UI cập nhật đúng qua observable query (`withObservables`), không đứng hình, không crash.
- Chú ý riêng nghiệp vụ **hoàn kho tự động** khi sửa/xoá nhật ký đã dùng vật tư (README §2, đoạn "Cộng thêm yêu cầu ở §3 đề cương") — logic này cài đặt đối xứng ở cả backend lẫn WatermelonDB, cần xác nhận phía mobile hoạt động đúng trên thiết bị thật, không chỉ đúng trong Jest.

### 2.3 Test trên thiết bị Android vật lý (chưa từng làm)

Toàn bộ xác nhận tới giờ chỉ trên **1 máy ảo** (Pixel 6a AVD). Nhiệm vụ bắt buộc:

- Cài và chạy app trên ít nhất **1 điện thoại Android thật**.
- So sánh với máy ảo: hiệu năng SQLite/JSI thật có khác biệt gì không, bàn phím ảo có che input không, các nút có đủ lớn để bấm bằng ngón tay thật không (README có ghi chú riêng: tab bar cao 60dp "vì thanh này sẽ bị chạm bằng ngón tay vừa ở trong đất" — kiểm tra điều đó có đúng cảm giác thật không).

### 2.4 Xác minh `react-native-svg` / biểu đồ báo cáo

`react-native-svg` có trong `package.json` (`^15.15.5`), dùng làm nền cho `react-native-chart-kit` để vẽ 3 biểu đồ ở màn hình Báo cáo. Chưa ai xác nhận bằng mắt việc này hoạt động trên thiết bị thật. Vào màn hình **Báo cáo** và kiểm tra cả 3:

| Biểu đồ | Cần kiểm tra |
|---|---|
| Thu vs Chi theo thời gian | Bucket rỗng (không hoạt động) vẫn hiện giá trị 0, không làm gãy hình dạng đường biểu đồ |
| Vật tư tiêu thụ | Khi một nhóm vật tư trộn đơn vị (vd. phân bón vừa có `kg` vừa có `bao`), cờ `unit_mixed` phải khiến biểu đồ vẽ theo **chi phí**, không cộng lẫn đơn vị |
| So sánh mùa vụ | Đúng số liệu, đọc được nhãn trên màn hình nhỏ |

Kiểm tra thêm: không crash khi **không có dữ liệu** (mùa vụ mới tạo, chưa có nhật ký/thu chi nào).

### 2.5 QA giao diện — lưu ý quan trọng về "golden fixtures"

Đã rà soát toàn bộ repo: **hiện chưa có golden fixture / snapshot test nào cho UI** (không có ảnh tham chiếu, không có snapshot Jest, không có bộ dữ liệu mẫu chuẩn hoá cho từng màn hình). Vì vậy "đối chiếu với golden fixture" cụ thể hoá thành hai việc:

1. **QA thủ công theo đặc tả**, dùng làm chuẩn đối chiếu: bảng chức năng ở `README.md` §2 và mô hình dữ liệu ở `Data_Requirements_Database.md`. Đi qua từng màn hình trong bảng 12 màn hình ở Mục 3 bên dưới, xác nhận đúng field, đúng validation, đúng luồng.
2. **(Nên làm nếu có thời gian)** Tự dựng một bộ snapshot test Jest cơ bản cho các màn hình chính (`react-test-renderer` đã có sẵn trong `devDependencies`, dùng cùng cách `__tests__/App.test.tsx` đang làm) — biến "golden fixture" từ khái niệm chưa tồn tại thành thứ thật sự có trong repo. Không bắt buộc cho vòng đầu, nhưng nêu ra để nhóm quyết định.

### 2.6 Checklist ngoại tuyến (chế độ máy bay) — ưu tiên cao nhất

`README.md` §8 gọi đây là **"phép thử thủ công quan trọng nhất của cả đồ án"** — chưa ai chạy qua lần nào:

1. Đăng nhập một lần khi còn mạng.
2. Bật chế độ máy bay.
3. Tạo 1 mùa vụ, ghi 3 nhật ký có dùng vật tư, ghi 1 khoản chi + 1 khoản thu, mở cả 3 biểu đồ.
4. Mọi thứ phải chạy — không vòng xoay chờ, không lỗi, không màn hình trống.
5. Tắt máy bay, bấm Đồng bộ ngay, kiểm tra dữ liệu lên PostgreSQL qua pgAdmin.

Đây là tiêu chí nghiệm thu của Issue #38 và #47 — nếu bước 3 thất bại ở bất kỳ đâu, ghi lại chính xác thao tác gây lỗi.

### 2.7 Test đồng bộ đa thiết bị (Issue #40)

Dựng 2 máy ảo (hoặc 1 máy ảo + 1 thiết bị thật), sửa cùng một bản ghi ở cả hai khi cả hai offline, đưa cả hai online, xác nhận:
- Giải quyết xung đột đúng như README §9.4 (ghi-sau-thắng theo `updated_at` ở server, hợp nhất theo từng trường ở client).
- Không mất dữ liệu âm thầm, không tạo bản ghi trùng.

### 2.8 Log bug

Mọi lỗi phát hiện trong quá trình trên: tạo issue riêng trên GitHub, liên kết về Issue #41 (theo đúng cấu trúc Kanban đã có sẵn trong `AgriLog_GitHub_Issues_and_Kanban.md`), không sửa trực tiếp nếu nguyên nhân nằm ở backend/sync — báo Thái (xem ranh giới ở `Huong_Dan_Ban_Giao_Khoa.md`).

---

## 3. Bảng 12 màn hình để dò khi QA

| # | Module | Màn hình | File |
|---|---|---|---|
| 1 | Đăng nhập | Login | `screens/auth/LoginScreen.tsx` |
| 2 | Mùa vụ | Danh sách | `screens/seasons/SeasonListScreen.tsx` |
| 3 | Mùa vụ | Form | `screens/seasons/SeasonFormScreen.tsx` |
| 4 | Nhật ký | Danh sách | `screens/diary/DiaryListScreen.tsx` |
| 5 | Nhật ký | Form (kèm dùng vật tư) | `screens/diary/DiaryFormScreen.tsx` |
| 6 | Vật tư | Danh mục | `screens/supplies/SupplyListScreen.tsx` |
| 7 | Vật tư | Form | `screens/supplies/SupplyFormScreen.tsx` |
| 8 | Vật tư | Giao dịch kho | `screens/supplies/StockMovementScreen.tsx` |
| 9 | Thu chi | Tổng kết theo mùa vụ | `screens/finance/FinanceScreen.tsx` |
| 10 | Thu chi | Form chi phí | `screens/finance/ExpenseFormScreen.tsx` |
| 11 | Thu chi | Form doanh thu | `screens/finance/RevenueFormScreen.tsx` |
| 12 | Báo cáo | 3 biểu đồ | `screens/reports/ReportsScreen.tsx` |

---

## 4. Định nghĩa hoàn thành (Definition of Done)

Một nhiệm vụ ở Mục 2 chỉ tính là xong khi:

- [ ] Đã test trên **thiết bị thật**, không chỉ máy ảo
- [ ] Đã test **chế độ máy bay** cho luồng liên quan (nếu có ghi/sửa/xoá dữ liệu)
- [ ] `npm test` vẫn xanh (130 test hiện có không được vỡ)
- [ ] `tsc` không lỗi, `npm run lint` sạch
- [ ] Bug phát hiện đã thành issue GitHub, không phải note rời
- [ ] Nếu là lỗi build/môi trường mới: đã có file `Error_*.md` tương ứng

---

## 5. KHÔNG được làm

Xem chi tiết đầy đủ ở `Huong_Dan_Ban_Giao_Khoa.md`. Tóm tắt: không sửa `backend/**`, không sửa sync engine mobile (`mobile/src/services/sync.ts`, `mobile/src/db/schema.ts`, `mobile/src/db/migrations.ts`, `mobile/src/db/models/**`), không đụng `metro.config.js` / `mobile/android/gradle.properties` / `mobile/patches/**` — đây đúng là những file vừa được vá hôm nay để lần đầu build được, sửa nhầm sẽ làm lại crash đã fix.
