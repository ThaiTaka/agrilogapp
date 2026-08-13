# Nhiệm Vụ Của Khoa — Mobile UI, Web Admin Dashboard & Kiểm Thử Thiết Bị Thật

**Nhánh mobile:** `khoa-mobile-ui-fixes` (đã tạo từ `develop`)
**Nhánh web:** `khoa-web-admin-dashboard` (nhánh riêng — xem `Huong_Dan_Ban_Giao_Khoa.md`)
**Cập nhật:** 13/08/2026, lần 2 — bổ sung Web Admin Dashboard, phần mobile giữ nguyên không đổi.

---

## 0. Bối cảnh

Bạn giờ phụ trách **toàn bộ phần frontend** của đồ án: app di động (React Native) **và** trang quản trị web mới (React Admin). Thái giữ nguyên backend + sync engine + sẽ xây thêm API quản trị cho phần web (xem Mục B.5). Đọc `Bao_Cao_Tien_Do_AgriLog.md` Mục 1, 4, 5 trước khi bắt đầu — đó là bức tranh đầy đủ, xác nhận bằng cách chạy test thật, không phải ước tính.

File này chia làm 2 phần độc lập — làm phần nào trước tuỳ bạn sắp xếp, nhưng **không trộn công việc của 2 phần vào cùng 1 nhánh/1 PR** (xem `Huong_Dan_Ban_Giao_Khoa.md`).

---

# PHẦN A — MOBILE (không đổi so với bản trước)

## A.0 Đọc trước khi bắt đầu

Toàn bộ 12 màn hình mobile đã **code xong**, biên dịch sạch. Ngày 13/08 app lần đầu chạy được trên máy ảo Android thật. Phần "viết code" gần xong, phần "chứng minh nó chạy đúng cho người dùng thật" gần như chưa bắt đầu — đây là trọng tâm Phần A.

Đọc trước: `README.md` §2, §8, §9, §13; `Error_WatermelonDB_BuildConfig_AGP9.md`; `Error_Metro_Watcher_Crash_CXX_Build.md`.

## A.1 Dựng môi trường

Theo `README.md` §6–§8. Lưu ý:

1. **Cài Watchman trước khi chạy Metro lần đầu** (máy Thái thiếu Watchman đã gây crash Metro thật — vá đã có sẵn trong `metro.config.js`, nhưng cài Watchman vẫn là khuyến nghị chính thức).
2. Vẫn cần chạy backend cục bộ (PostgreSQL + FastAPI) — làm theo README §7.
3. `npm install` xong, kiểm tra patch WatermelonDB tự áp dụng (`postinstall` chạy `patch-package`).
4. **Không dùng mật khẩu mẫu cũ trong `Huong_Dan_Khoi_Dong_Du_An.md`** — file đã được redact, tự đăng ký tài khoản riêng qua Swagger UI.

## A.2 Xác nhận môi trường Metro/adb ổn định trên máy bạn

Không phải sửa lỗi — đã vá trong `metro.config.js` (commit `886031b`). Xác nhận vá đó đứng vững trên máy bạn; nắm quy trình khôi phục "Unable to load script" ở `Huong_Dan_Khoi_Dong_Du_An.md`. Gặp lỗi mới → viết `Error_<Tên>.md` theo đúng mẫu 2 file hiện có.

## A.3 Kiểm thử WatermelonDB dưới Hermes — vượt xa "app mở được"

Với từng module (Mùa vụ, Nhật ký, Vật tư, Thu chi): tạo/sửa/xoá đầy đủ trên thiết bị thật, xác nhận UI cập nhật đúng qua `withObservables`. Chú ý riêng nghiệp vụ hoàn kho tự động khi sửa/xoá nhật ký đã dùng vật tư — logic cài đối xứng cả 2 phía, cần xác nhận phía mobile đúng trên thiết bị thật.

## A.4 Test trên thiết bị Android vật lý (chưa từng làm)

Xác nhận tới giờ chỉ trên 1 máy ảo (Pixel 6a AVD). Bắt buộc: cài & chạy trên ít nhất 1 điện thoại thật, so sánh hiệu năng SQLite/JSI, kiểm tra bàn phím ảo không che input, tab bar 60dp có đủ lớn để bấm bằng ngón tay thật.

## A.5 Xác minh `react-native-svg` / biểu đồ báo cáo

Vào màn hình Báo cáo, kiểm tra cả 3 biểu đồ (Thu-Chi, Vật tư tiêu thụ, So sánh mùa vụ) vẽ đúng, đọc được, không crash — kể cả khi chưa có dữ liệu (mùa vụ mới tạo).

## A.6 QA giao diện — chưa có "golden fixture" nào tồn tại

Đã rà soát repo: không có snapshot/ảnh tham chiếu nào cho UI. QA thủ công theo `README.md` §2 (bảng chức năng) + `Data_Requirements_Database.md`. (Nên làm nếu có thời gian) tự dựng snapshot test Jest cơ bản cho các màn hình chính bằng `react-test-renderer` (đã có sẵn, xem cách `__tests__/App.test.tsx` làm).

## A.7 Checklist ngoại tuyến — ưu tiên cao nhất

README §8 gọi đây là "phép thử quan trọng nhất của cả đồ án": đăng nhập 1 lần → bật máy bay → tạo mùa vụ + 3 nhật ký dùng vật tư + 1 chi + 1 thu + mở 3 biểu đồ, tất cả phải chạy không lỗi → tắt máy bay → Đồng bộ ngay → xác nhận dữ liệu lên PostgreSQL. Tiêu chí nghiệm thu Issue #38, #47.

## A.8 Test đồng bộ đa thiết bị (Issue #40)

2 máy ảo (hoặc 1 ảo + 1 thật), sửa cùng bản ghi khi cả hai offline, đưa online, xác nhận giải quyết xung đột đúng README §9.4, không mất dữ liệu, không trùng bản ghi.

## A.9 Log bug

Issue riêng trên GitHub, liên kết Issue #41. Không tự sửa nếu nguyên nhân ở backend/sync — báo Thái.

### Bảng 12 màn hình mobile để dò khi QA

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

# PHẦN B — WEB ADMIN DASHBOARD (mới)

## B.0 Mục tiêu

Trang quản trị web cho system admin — tách biệt hoàn toàn khỏi app di động nông hộ. Ba chức năng theo đề cương: **quản lý người dùng**, **xem báo cáo**, **quản lý hiển thị ứng dụng**. Xem phân tích đầy đủ ở `Bao_Cao_Tien_Do_AgriLog.md` Mục 5.

**Quan trọng:** backend hiện **chưa có** khái niệm admin/role nào (đã xác nhận bằng cách đọc `backend/app/models/account.py` — model `User` không có cột phân quyền). Việc này không chặn bạn bắt đầu — xem B.4 (làm ngay bằng dữ liệu giả) và B.5 (phần phải chờ Thái).

## B.1 Công nghệ

**Vite + React + TypeScript**, khung quản trị **react-admin**, biểu đồ bằng **recharts**. Lý do chọn (so với Next.js / Vite thuần): xem bảng so sánh ở `Bao_Cao_Tien_Do_AgriLog.md` Mục 5.3 — tóm lại, react-admin sinh sẵn màn hình CRUD từ khai báo resource và có data provider giả để code trước khi API admin thật tồn tại.

## B.2 Khởi tạo thư mục `web/`

Chạy từ thư mục gốc repo:

```powershell
cd d:\agrilogapp
npm create vite@latest web -- --template react-ts
cd web
npm install react-admin ra-data-fakerest recharts
npm install -D @types/node
```

Cấu trúc đề xuất bên trong `web/src/`:

```
web/src/
├── App.tsx                 # <Admin> gốc của react-admin
├── dataProvider.ts          # bắt đầu bằng ra-data-fakerest, đổi sang REST thật sau
├── authProvider.ts          # stub trước, nối JWT thật khi B.5 xong
├── resources/
│   ├── users.tsx             # List/Edit/Show cho quản lý người dùng
│   ├── households.tsx        # List/Edit/Show cho quản lý household
│   └── ...
└── dashboard/
    └── Dashboard.tsx          # trang tổng quan, nhúng 3 biểu đồ recharts
```

`node_modules/`, `dist/`, `.env` trong `web/` **tự động được `.gitignore` gốc chặn** (pattern không neo đường dẫn) — không cần sửa `.gitignore`.

## B.3 Việc làm NGAY — không cần chờ Thái

1. Dựng khung react-admin, layout, màn hình đăng nhập (giao diện thôi, chưa nối auth thật).
2. Resource "users" và "households" với `ra-data-fakerest` — dữ liệu giả trong bộ nhớ, đủ để có giao diện List/Edit/Create chạy được ngay hôm nay.
3. Trang Dashboard với 3 biểu đồ recharts, dùng dữ liệu giả **cùng hình dạng** với response thật — tham chiếu field tại `backend/app/schemas/report.py` để không phải sửa lại UI khi nối API thật.
4. Màn hình "quản lý hiển thị ứng dụng" — dựng UI trước (danh sách toggle bật/tắt), phần lưu trữ thật chờ Thái chốt phạm vi (xem B.5, mục 5).

## B.4 Definition of Done cho từng phần việc web

- [ ] Chạy được bằng `npm run dev`, không lỗi console
- [ ] `npx tsc` sạch
- [ ] Không có API key/URL backend thật hard-code trong code — dùng biến môi trường (`web/.env`, đã được gitignore tự động)
- [ ] UI đã đối chiếu với 3 chức năng yêu cầu ở B.0
- [ ] Khi đổi từ `ra-data-fakerest` sang data provider thật: chỉ sửa `dataProvider.ts`, không sửa lại các file `resources/*`

## B.5 Việc PHẢI chờ Thái (đừng tự làm ở backend)

Không tự thêm các mục này vào `backend/`. Khi cần, mở issue mô tả rõ bạn cần field/endpoint gì, hoặc trao đổi trực tiếp:

1. Cột `is_admin` (hoặc bảng `admin_users` riêng) trên backend + migration.
2. Dependency xác thực admin (khác `current_household` hiện tại — cần nhìn xuyên household).
3. Endpoint `/api/v1/admin/users`, `/api/v1/admin/households` (liệt kê, khoá/mở).
4. Endpoint báo cáo cấp admin (toàn hệ thống, không giới hạn 1 household như 3 endpoint `/reports/*` hiện có).
5. Phạm vi cụ thể của "quản lý hiển thị ứng dụng" — cần thống nhất với Thái **trước khi** anh ấy thiết kế bảng dữ liệu, vì đây là khái niệm hoàn toàn mới, chưa có trong `Data_Requirements_Database.md`.

Khi các mục trên sẵn sàng, việc của bạn chỉ là viết `dataProvider.ts`/`authProvider.ts` thật, dựa trên OpenAPI docs tại `http://localhost:8000/docs`.

---

## KHÔNG được làm (áp dụng cho cả 2 phần)

Xem đầy đủ ở `Huong_Dan_Ban_Giao_Khoa.md`. Tóm tắt: không sửa `backend/**`; không sửa sync engine mobile (`mobile/src/services/sync.ts`, `mobile/src/db/schema.ts`, `mobile/src/db/migrations.ts`, `mobile/src/db/models/**`); không đụng `metro.config.js` / `mobile/android/gradle.properties` / `mobile/patches/**`. Với web, khi cần thay đổi gì ở backend (Mục B.5), báo Thái — không tự thêm route/model/migration.
