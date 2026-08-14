# Kế Hoạch Thực Thi — Hoàn Thiện Mobile & Xây Web Admin Dashboard

**Ngày lập:** 13/08/2026
**Bối cảnh:** Thay đổi so với kế hoạch trước — không bàn giao frontend cho Khoa nữa. Thái (Senior/Product owner) và Claude (Senior Full-Stack Developer) cùng hoàn thiện toàn bộ dự án: Mobile, Web Admin, và phần backend còn thiếu cho Web Admin.
**Nguyên tắc thực thi:** 2 giai đoạn tách biệt, không chồng lấn, để tránh tràn ngữ cảnh (context overflow) và để mỗi giai đoạn có một "cổng" (gate) rõ ràng trước khi sang giai đoạn sau.

---

## 0. Ràng buộc thực tế cần thống nhất trước khi bắt đầu

Vài điều tôi **có thể** và **không thể** tự làm, để kỳ vọng đúng ngay từ đầu:

| Việc | Ai làm |
|---|---|
| Đọc/sửa code, chạy `tsc`/`jest`/`pytest`/`lint`, build qua `npm run android`, đọc `adb logcat` | Claude |
| Chụp màn hình emulator qua `adb exec-out screencap` rồi tự xem lại bằng công cụ đọc ảnh, để tự kiểm tra UI mà không cần bạn mô tả bằng lời | Claude |
| Bật máy ảo (mở Android Studio / `emulator -avd ...`), bật chế độ máy bay, **cầm điện thoại thật lên bấm** | **Thái** — tôi không điều khiển được thiết bị vật lý, và bật GUI máy ảo lần đầu cũng cần bạn xác nhận đã lên màn hình Home |
| Xác nhận "cảm giác dùng" (bàn phím có che input không, nút có bấm thuận tay không) | **Thái** |

→ Vì vậy Phase 1 sẽ có 2 lớp kiểm thử: **lớp tự động Claude làm được hết** (Bước 1–4 dưới đây), và **lớp thủ công chỉ Thái xác nhận được** (Bước 5) — tôi sẽ đưa checklist chính xác, bạn chạy và báo kết quả lại.

---

# PHASE 1 — HOÀN THIỆN MOBILE APP

## 1.1 Định nghĩa "100% hoàn thành" cho Phase 1

Phase 1 coi là xong khi **cả 5 điều kiện** sau đều đạt — đây là cổng bắt buộc trước khi mở Phase 2:

- [ ] `npx tsc --noEmit` sạch, `npm run lint` sạch
- [ ] `npm test` xanh toàn bộ 130 test hiện có (không vỡ test cũ, không xoá test để né lỗi)
- [ ] App build và chạy ổn định trên máy ảo, đi qua toàn bộ 12 màn hình không crash (xác nhận qua log + screenshot, không chỉ "build thành công")
- [ ] Checklist ngoại tuyến (chế độ máy bay, README §8) chạy thành công **ít nhất 1 lần**, Thái xác nhận trực tiếp
- [ ] Không còn bug đã biết nào ở mức chặn (blocking) — bug nhỏ không chặn có thể ghi lại làm việc tồn đọng, không bắt buộc hết trước Phase 2

## 1.2 Bước 0 — Kiểm tra môi trường trước khi bắt đầu (Claude làm)

```powershell
git status                                   # đảm bảo working tree sạch trước khi sửa
cd backend
.\.venv\Scripts\Activate.ps1
pytest -q                                    # xác nhận 350 test vẫn xanh (baseline không đổi)
cd ..\mobile
npm test                                     # xác nhận 130 test vẫn xanh (baseline không đổi)
npx tsc --noEmit
```

Nếu backend hoặc PostgreSQL chưa chạy, khởi động theo README §7 trước khi sang bước cần backend (Bước 4).

## 1.3 Bước 1 — Rà soát tĩnh toàn bộ 12 màn hình + navigation (Claude làm, không cần emulator)

Đọc từng file theo đúng thứ tự luồng người dùng thật (không đọc ngẫu nhiên), đối chiếu với `Data_Requirements_Database.md` và `README.md` §2:

| # | Nhóm rà soát | File |
|---|---|---|
| 1 | Đăng nhập → điều hướng gốc | `screens/auth/LoginScreen.tsx`, `navigation/index.tsx` |
| 2 | Mùa vụ | `screens/seasons/SeasonListScreen.tsx`, `SeasonFormScreen.tsx` |
| 3 | Nhật ký (+ dùng vật tư lồng trong form) | `screens/diary/DiaryListScreen.tsx`, `DiaryFormScreen.tsx`, `navigation/DiaryStack.tsx`, `components/SupplyUsageEditor.tsx` |
| 4 | Vật tư + tồn kho | `screens/supplies/SupplyListScreen.tsx`, `SupplyFormScreen.tsx`, `StockMovementScreen.tsx`, `navigation/SuppliesStack.tsx` |
| 5 | Thu chi | `screens/finance/FinanceScreen.tsx`, `ExpenseFormScreen.tsx`, `RevenueFormScreen.tsx`, `navigation/FinanceStack.tsx` |
| 6 | Báo cáo / biểu đồ | `screens/reports/ReportsScreen.tsx` |
| 7 | Trạng thái đồng bộ | `components/SyncStatusBar.tsx`, `services/sync.ts` |

Với mỗi file, tìm cụ thể (không rà soát chung chung):

- **Điều hướng:** mọi `navigation.navigate('X', {...})` có khớp tên route + đúng kiểu param khai báo trong `RootStackParamList`/`MainTabParamList`/từng Stack chưa (TypeScript đã bắt phần lớn qua `tsc`, nhưng route string được nối động thì `tsc` có thể bỏ sót).
- **WatermelonDB:** mọi thao tác ghi có nằm trong `database.write(async () => {...})` không — ghi ngoài writer là bug thật, gây lỗi WatermelonDB khó dò. Mọi màn hình danh sách có dùng `withObservables` (reactive) hay dùng `.fetch()` một lần (không tự cập nhật khi dữ liệu đổi ở màn khác) — cái sau là bug UX âm thầm.
- **Trạng thái tải/lỗi:** màn hình có xử lý loading/empty/error rõ ràng, hay để trắng màn hình khi chưa có dữ liệu.
- **Race condition khi unmount:** set state sau khi component đã unmount (thường gặp ở thao tác async trong `useEffect` không cleanup).

Kết quả bước này là **danh sách bug cụ thể theo file:dòng**, không phải cảm nhận chung.

## 1.4 Bước 2 — Sửa lỗi tìm được (Claude làm, theo từng cụm nhỏ)

- Sửa theo từng màn hình/module một, không sửa dồn nhiều module cùng lúc.
- Sau mỗi cụm sửa: chạy lại `npx tsc --noEmit` + `npm test` — phải xanh trước khi sang cụm tiếp theo.
- Không sửa các file đã biết là "vùng nhạy cảm, mới vá hôm 13/08" trừ khi bug nằm chính ở đó và có lý do rõ ràng: `metro.config.js`, `mobile/android/gradle.properties`, `mobile/patches/**`, `mobile/src/db/schema.ts`, `mobile/src/db/migrations.ts`, `mobile/src/services/sync.ts` — đây là các file vừa được vá để lần đầu build được, sửa nhầm dễ kéo lại lỗi cũ.

## 1.5 Bước 3 — Build lên máy ảo, tự xác nhận bằng log + screenshot (Claude làm, cần máy ảo đã bật sẵn)

```powershell
# Cửa sổ 1 — backend (nếu chưa chạy)
cd backend; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Cửa sổ 2 — Metro
cd mobile; npm start

# Cửa sổ 3 — build + cài
cd mobile; npm run android
```

Sau khi cài xong, tôi tự kiểm tra thay vì hỏi bạn "có chạy được không":

```powershell
adb devices                                          # xác nhận máy ảo đang kết nối
adb logcat -c                                         # xoá log cũ, bắt đầu log sạch cho phiên test
# ... điều hướng qua từng tab/màn hình (xem cách tự động hoá ở Bước 3b) ...
adb logcat *:E ReactNative:V ReactNativeJS:V -d       # đọc lỗi/exception phát sinh
adb exec-out screencap -p > screenshot_<ten_man_hinh>.png
```

Ảnh chụp màn hình lưu vào thư mục scratchpad, tôi đọc trực tiếp bằng công cụ đọc ảnh để tự xác nhận UI render đúng (không rỗng, không đè chữ, biểu đồ có vẽ) — không cần bạn mô tả bằng lời cho từng màn.

**Giới hạn thật:** tôi có thể đọc code để bấm nút một cách chương trình hoá (`adb shell input tap x y`) nếu bạn muốn tôi tự điều hướng qua toàn bộ 12 màn hình bằng tọa độ, nhưng cách này giòn (dễ vỡ khi layout đổi) — đề xuất: bạn điều hướng qua 12 màn hình 1 lần trên máy ảo trong lúc tôi `adb logcat` chạy nền, tôi đọc log sau; hoặc tôi tự bấm bằng `input tap`/`input swipe` cho luồng cố định (Login → mỗi tab) nếu bạn đồng ý cách này ở bước duyệt kế hoạch.

## 1.6 Bước 4 — Kiểm thử thủ công chỉ Thái xác nhận được (thực hiện cùng nhau)

Đây là các bước tôi **không thể** tự làm — cần bạn cầm máy/thiết bị. Tôi sẽ đưa checklist, bạn làm theo và báo kết quả (hoặc dán log/ảnh chụp màn hình lỗi nếu có) để tôi phân tích tiếp:

1. **Checklist ngoại tuyến (README §8) — quan trọng nhất:** đăng nhập 1 lần có mạng → bật máy bay → tạo 1 mùa vụ, 3 nhật ký có dùng vật tư, 1 khoản chi, 1 khoản thu, mở cả 3 biểu đồ → mọi thứ phải chạy không lỗi → tắt máy bay → Đồng bộ ngay → xác nhận dữ liệu lên PostgreSQL qua pgAdmin.
2. **Thiết bị Android vật lý:** cài và chạy thử trên ít nhất 1 điện thoại thật — hiệu năng SQLite/JSI, bàn phím ảo có che input, tab bar 60dp có đủ lớn.
3. **Đồng bộ đa thiết bị (Issue #40):** 2 máy ảo (hoặc 1 ảo + 1 thật), sửa cùng 1 bản ghi khi cả 2 offline, đưa online, xác nhận giải quyết xung đột đúng README §9.4.

## 1.7 Cổng chuyển sang Phase 2

Chỉ bắt đầu Phase 2 khi Mục 1.1 (5 điều kiện) đạt đủ. Nếu có bug không chặn (non-blocking) còn tồn, ghi vào một mục "Nợ kỹ thuật Mobile" ở cuối file này thay vì để trôi mất.

---

# PHASE 2 — WEB ADMIN DASHBOARD (Next.js)

## 2.0 Bước 0 — Backend: API quản trị tối thiểu (điều kiện tiên quyết, làm trước khi code frontend)

Đã xác nhận ở lần rà soát trước: `backend/app/models/account.py::User` **không có** khái niệm quyền quản trị, và mọi endpoint hiện tại giới hạn theo `current_household`. Vì giờ không còn ranh giới tổ chức Thái/Khoa, việc này gộp thẳng vào kế hoạch chung — Claude sẽ code, Thái review trước khi merge (đây là phần đụng vào backend/database, cần bạn duyệt kỹ hơn phần UI thuần).

| Việc | Chi tiết |
|---|---|
| Migration | Thêm cột `is_admin: bool` (mặc định `false`) vào bảng `users`, Alembic revision mới |
| Auth admin | Dependency mới trong `api/deps.py` (vd. `current_admin`) — giải mã JWT như hiện tại nhưng bắt buộc `is_admin=True`, và **không** giới hạn theo `household_id` |
| `GET /api/v1/admin/users` | Liệt kê user toàn hệ thống, phân trang, kèm tên household |
| `GET /api/v1/admin/households` | Liệt kê household toàn hệ thống |
| `PATCH /api/v1/admin/users/{id}` | Khoá/mở tài khoản (`is_active`) |
| `GET /api/v1/admin/overview` | Số liệu tổng quan cho Dashboard: tổng số household/user, hoạt động gần đây — endpoint mới, không tái dùng `/reports/*` (đang giới hạn theo household) |
| Test | Viết test theo đúng chuẩn hiện có (`tests/test_admin.py`) — không hạ chuẩn 94% coverage |
| **Cần Thái quyết định trước khi code** | **"Quản lý hiển thị ứng dụng" nghĩa chính xác là gì?** Đề xuất tạm: bảng `feature_flags` đơn giản (tên flag, bật/tắt, mô tả) admin toggle được — nhưng cần bạn xác nhận đây đúng là thứ đề cương yêu cầu trước khi thiết kế schema |

## 2.1 Bước 1 — Khởi tạo `web/` bằng Next.js + Tailwind

```powershell
cd d:\agrilogapp
npx create-next-app@latest web --typescript --tailwind --app --eslint --src-dir --import-alias "@/*"
cd web
```

Dùng **App Router** (chuẩn hiện tại của Next.js, không dùng Pages Router cũ).

## 2.2 Bước 2 — Cấu trúc thư mục & API client

```
web/src/
├── app/
│   ├── login/page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx           # layout chung có sidebar, guard đăng nhập
│   │   ├── page.tsx              # Dashboard tổng quan
│   │   └── users/page.tsx        # User Management
│   └── api/auth/route.ts         # route nội bộ Next.js, xem Bước 3
├── lib/
│   ├── apiClient.ts               # fetch wrapper trỏ tới FastAPI (NEXT_PUBLIC_API_BASE_URL)
│   └── auth.ts
└── middleware.ts                  # chặn truy cập /dashboard, /users khi chưa đăng nhập
```

`web/.env.local` chứa `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` — **không hard-code URL trong code**, đã tự động được `.gitignore` gốc chặn (pattern `.env*` không neo đường dẫn).

## 2.3 Bước 3 — Màn hình Login

**Vấn đề bảo mật cần quyết định trước khi code:** lưu JWT ở đâu?

- Lưu trong `localStorage`/state React (đơn giản nhất) → dễ bị đánh cắp qua XSS, không có `httpOnly`.
- **Đề xuất:** Next.js Route Handler (`app/api/auth/route.ts`) làm cầu nối — nhận email/password, gọi `POST /api/v1/admin-login` (hoặc `/auth/login` + kiểm tra `is_admin`) ở FastAPI, rồi set JWT vào cookie `httpOnly` + `secure` + `sameSite=lax`. Middleware đọc cookie này để chặn truy cập trang khi chưa đăng nhập. An toàn hơn đáng kể cho một công cụ quản trị có quyền cao.

## 2.4 Bước 4 — Dashboard tổng quan

Card số liệu (tổng household, tổng user, hoạt động gần đây) từ `GET /api/v1/admin/overview`. Nếu cần biểu đồ, dùng `recharts` (nhẹ, phổ biến với Next.js/Tailwind, không cần thêm UI kit nặng).

## 2.5 Bước 5 — User Management

Bảng danh sách user (email, household, trạng thái `is_active`, ngày tạo) từ `GET /api/v1/admin/users`, có tìm kiếm/phân trang, nút khoá/mở gọi `PATCH /api/v1/admin/users/{id}`.

## 2.6 Bước 6 — Kiểm thử & Definition of Done Phase 2

- [ ] `npx tsc --noEmit` sạch, `npm run build` (Next.js) không lỗi
- [ ] Đăng nhập → Dashboard → User Management chạy được với backend thật (`localhost:8000`), không phải dữ liệu giả
- [ ] Toggle khoá/mở user phản ánh đúng xuống PostgreSQL (kiểm qua pgAdmin)
- [ ] Middleware chặn truy cập khi chưa đăng nhập (test bằng cách xoá cookie thủ công rồi truy cập `/dashboard`)
- [ ] Không có API key/URL hard-code, `.env.local` không bị commit
- [ ] Backend: test mới cho `/api/v1/admin/*` xanh, coverage tổng không tụt dưới 94%

---

## 3. Nợ kỹ thuật (cập nhật dần trong lúc thực thi)

Phát hiện trong Bước 1 (14/08/2026), **không chặn Phase 2** — ghi lại để không trôi mất:

| # | Việc | Vì sao không sửa ngay |
|---|---|---|
| M1 | `recordStockTake` đọc `stockLevel` **ngoài** writer rồi mới ghi bên trong. Về lý thuyết một lượt ghi chen vào giữa sẽ làm delta sai. | App một người dùng trên một máy, chưa có đường nào tạo ra ghi đồng thời. Sửa đúng cần đưa cả phép đọc vào writer — đụng `stock.ts`, vùng vừa vá 13/08. |
| M2 | `LoginScreen` chỉ bật nút khi mật khẩu ≥ 8 ký tự, và **không nói lý do**. Tài khoản có mật khẩu cũ ngắn hơn sẽ thấy nút chết mà không hiểu tại sao. | Cần Thái quyết định: nới điều kiện, hay giữ và thêm dòng giải thích. |
| M3 | `SeasonFormScreen` hiển thị ngày bắt đầu/kết thúc ở dạng chỉ đọc — chưa có bộ chọn ngày (đã ghi TODO trong code từ #20). `DateStepper` đã có sẵn và dùng được ở nhật ký. | Là tính năng thiếu, không phải lỗi. Ngày bắt đầu mặc định = hôm nay vẫn đúng cho phần lớn trường hợp. |
| M4 | 132 test hiện có **đều là test service + schema**, không có test nào cho 12 màn hình. Đúng 4 lỗi sửa hôm nay đều nằm ở tầng màn hình và không test nào bắt được. | Thêm test màn hình là một khối việc riêng, nên tính thành hạng mục có kế hoạch chứ không chèn giữa Phase 1. |

---

## 4. Quyết định của Thái (chốt 14/08/2026)

1. **"Quản lý hiển thị ứng dụng"** — **KHÔNG** làm bảng `feature_flags` tổng quát. Phạm vi rút gọn còn đúng hai thứ: khoá/mở từng tài khoản (`is_active` trên `users`) và **một** cờ "Chế độ bảo trì hệ thống" toàn cục — bật lên thì app mobile hiện thông báo bảo trì và chặn thao tác.
2. **Kiểm thử UI trên máy ảo** — Claude tự điều hướng bằng `adb shell input tap/swipe` cho luồng cố định (Login → 4 tab). Nếu toạ độ vỡ vì layout đổi thì dừng, Thái test thủ công.
3. **Tàn dư của Khoa** — đã xoá: 3 file Markdown bàn giao, 2 nhánh `khoa-*` ở cả local lẫn `origin`. Hai nhánh này không có commit riêng nên không mất code.
4. **Nhánh làm việc** — code và push thẳng lên `main`, không dùng `feature/*` + PR.

---

*Kế hoạch này được lập với sự hỗ trợ của Claude (Anthropic), theo tinh thần công khai đóng góp AI ở `README.md` §15. Chưa có dòng code nào được viết tại thời điểm lập kế hoạch — chờ Thái duyệt trước khi thực thi Phase 1.*
