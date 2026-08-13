# Hướng Dẫn Bàn Giao Cho Khoa — Quy Trình Git

**Cập nhật:** 13/08/2026, lần 2 — Khoa giờ làm việc trên **2 thư mục** (`mobile/` và `web/` mới), vẫn giữ nguyên nguyên tắc cốt lõi: không đụng `backend/`.
**Nguyên tắc chung:** `main` là nhánh triển lãm — luôn phải chạy được, chỉ nhận code đã qua review. Mọi thay đổi của Khoa đi qua **Pull Request**, không bao giờ push thẳng vào `main` hay `develop`.

---

## 0. Điều gì thay đổi so với bản trước

Trước đây Khoa chỉ có 1 nhánh (`khoa-mobile-ui-fixes`) cho 1 việc (mobile). Giờ có **2 việc độc lập** (mobile UI/QA, và dựng mới Web Admin Dashboard) nên có **2 nhánh riêng, 2 PR riêng**:

| Nhánh | Việc | Thư mục | Trạng thái |
|---|---|---|---|
| `khoa-mobile-ui-fixes` | QA, kiểm thử thiết bị thật, sửa UI mobile | `mobile/**` | Đã tạo từ `develop`, đã push |
| `khoa-web-admin-dashboard` | Dựng mới trang quản trị web | `web/**` (thư mục mới) | Thái tạo từ `develop`, sẽ push trước khi Khoa cần |

**Vì sao tách 2 nhánh thay vì dồn vào 1:** đây là hai mảng việc không liên quan tới nhau (fix UI trên code đã có, và dựng một ứng dụng mới từ đầu). Gộp chung sẽ tạo ra 1 PR khổng lồ, khó review, khó revert riêng lẻ nếu một bên có vấn đề. Quy tắc chung: **1 nhánh/1 PR ứng với 1 mảng việc**, đúng tinh thần `feature/*`, `fix/*` đã quy ước ở `README.md` §12.

**Không code cả mobile lẫn web trên cùng một nhánh**, kể cả khi tiện tay đang mở sẵn VS Code. Chuyển nhánh trước khi đổi việc:

```powershell
# Đang sửa mobile, muốn chuyển sang làm web
git add <file mobile đang dở, nếu muốn giữ tạm>
git commit -m "..."          # hoặc git stash nếu chưa muốn commit
git checkout khoa-web-admin-dashboard
```

---

## 1. Điều kiện tiên quyết (Thái làm trước, Khoa không cần làm)

Trước khi Khoa cần tới nhánh web, Thái đã:
1. Đảm bảo `develop` đang khớp với `main`.
2. Tạo nhánh `khoa-web-admin-dashboard` từ `develop` và push lên GitHub.

Nếu `git fetch` không thấy nhánh này, báo Thái — đừng tự tạo nhánh trùng tên hoặc nhánh web dựa trên nhánh mobile.

---

## Bước 1 — Cài đặt & clone (chỉ làm 1 lần)

```powershell
git clone https://github.com/ThaiTaka/agrilogapp.git
cd agrilogapp
git config --global user.name "Nguyễn Hoàng Anh Khoa"
git config --global user.email "<email GitHub của bạn>"
```

---

## Bước 2 — Lấy đúng nhánh cho việc bạn đang làm

**Không làm việc trên `main` hay `develop`.**

```powershell
git fetch origin

# Làm mobile
git checkout khoa-mobile-ui-fixes

# Làm web admin
git checkout khoa-web-admin-dashboard
```

Kiểm tra lại đang đứng đúng nhánh trước khi code:

```powershell
git branch --show-current
```

---

## Bước 3 — Dựng môi trường

- **Mobile:** `README.md` §6–§8 và `Nhiem_Vu_Cua_Khoa.md` Phần A.1.
- **Web:** `Nhiem_Vu_Cua_Khoa.md` Phần B.2 (`npm create vite@latest web -- --template react-ts` rồi cài `react-admin`, `ra-data-fakerest`, `recharts`). Web cần backend chạy cục bộ như mobile (cùng `http://localhost:8000`), trỏ qua biến môi trường trong `web/.env` — không hard-code URL/API key trong code.

Không dùng thông tin đăng nhập trong `Huong_Dan_Khoi_Dong_Du_An.md` — tự đăng ký tài khoản riêng qua Swagger UI.

---

## Bước 4 — Làm việc & commit

Conventional Commits, scope theo đúng thư mục đang sửa:

```
fix(mobile): mô tả ngắn
feat(web): mô tả ngắn
test(mobile): ...
docs(web): ...
```

Ví dụ thật: `feat(web): dựng resource list cho users bằng ra-data-fakerest`

**Trước khi `git add`, luôn chạy `git status` và chỉ định rõ file — không dùng `git add .` / `git add -A` theo phản xạ:**

```powershell
git status
git add web/src/resources/users.tsx
git commit -m "feat(web): ..."
```

Lý do quy tắc này không phải hình thức: lần rà soát đầu tiên của repo suýt để lọt 2 file chứa mật khẩu thật vào git vì chúng nằm lẫn trong thư mục tưởng như vô hại. Quy tắc này áp dụng như nhau cho cả `mobile/` lẫn `web/` — **đặc biệt chú ý `web/.env` một khi bạn tạo nó**, vì đây sẽ là nơi chứa base URL và có thể cả token khi test.

**Mỗi commit chỉ thuộc về 1 nhánh/1 mảng việc.** Nếu đang đứng trên `khoa-mobile-ui-fixes` mà `git status` hiện thay đổi trong `web/`, dừng lại — bạn đang ở sai nhánh.

---

## Bước 5 — Đồng bộ khi `develop` có cập nhật mới từ Thái

Làm trên **từng nhánh riêng biệt**, thường xuyên:

```powershell
git checkout khoa-mobile-ui-fixes
git fetch origin
git merge origin/develop

git checkout khoa-web-admin-dashboard
git fetch origin
git merge origin/develop
```

Xung đột liên quan bất kỳ thứ gì ngoài `mobile/` hoặc `web/` (tức là bạn thấy conflict trong file `backend/`) → dừng lại, hỏi Thái, đừng tự giải quyết.

---

## Bước 6 — Đẩy code & tạo Pull Request (một PR cho một nhánh)

```powershell
git push -u origin khoa-mobile-ui-fixes
# hoặc
git push -u origin khoa-web-admin-dashboard
```

Trên GitHub → **Pull requests** → **New pull request**:

- **base:** `develop` (không phải `main`)
- **compare:** nhánh tương ứng với việc vừa làm
- **Reviewer:** Thái (`ThaiTaka`)
- Mở PR riêng cho mobile và riêng cho web — **không gộp 2 việc vào 1 PR** dù cả hai đều "đã xong" cùng lúc
- Nếu đóng issue cụ thể, ghi `Closes #NN` trong mô tả

Hoặc bằng `gh`:

```powershell
gh pr create --base develop --head khoa-web-admin-dashboard --title "feat(web): ..." --reviewer ThaiTaka --body "Mô tả đã dựng gì, đang dùng data provider giả hay đã nối API thật."
```

Đợi Thái review — không tự merge.

---

## Ranh giới bắt buộc — KHÔNG được tự sửa

```
backend/**                              ← toàn bộ backend, không ngoại lệ — kể cả khi Web Admin "chỉ cần thêm 1 field nhỏ"
mobile/src/services/sync.ts             ← sync adapter
mobile/src/db/schema.ts                 ← schema WatermelonDB
mobile/src/db/migrations.ts             ← migration WatermelonDB
mobile/src/db/models/**                 ← model WatermelonDB
mobile/metro.config.js                  ← vừa vá lỗi crash Metro (Error_Metro_Watcher_Crash_CXX_Build.md)
mobile/android/gradle.properties        ← cấu hình Hermes/AGP
mobile/patches/**                       ← patch WatermelonDB cho AGP9
```

**Đặc biệt với Web Admin:** toàn bộ endpoint quản trị (`is_admin`, danh sách user/household xuyên hệ thống, báo cáo cấp admin, "quản lý hiển thị") **chưa tồn tại ở backend** — xem `Nhiem_Vu_Cua_Khoa.md` Mục B.5. Đây là công việc của Thái. Nếu web cần một field/endpoint chưa có, mở issue mô tả chính xác bạn cần gì (tên field, kiểu dữ liệu, ví dụ response mong muốn) thay vì tự thêm route vào `backend/`.

**Phần bạn toàn quyền chỉnh sửa:**
- `mobile/src/screens/**`, `mobile/src/components/**`, `mobile/src/navigation/**` và test tương ứng
- `web/**` toàn bộ (thư mục mới, chưa có gì để làm hỏng — nhưng vẫn theo quy tắc commit chọn lọc ở Bước 4)

---

## Quy tắc an toàn (áp dụng cả `mobile/` và `web/`)

- Không bao giờ commit `.env`, mật khẩu, token, API key thật — kể cả trong comment hay ví dụ trong tài liệu. Dùng placeholder.
- `node_modules/`, `.venv/`, `dist/`, `.apk`/`.aab`, `android/app/build/` đã bị `.gitignore` gốc chặn ở mọi thư mục con — nếu `git status` hiện bất kỳ thứ nào trong số này là untracked, dừng lại kiểm tra, đừng ép add bằng `-f`.
- Không `git push --force` lên nhánh nào sau khi PR đã mở và Thái bắt đầu review.
- Không đổi tên/xoá file trong phạm vi "Ranh giới bắt buộc" ở trên.

---

## Checklist trước khi mở PR

**Mobile:**
- [ ] `npm test` xanh toàn bộ (130 test hiện có)
- [ ] `npx tsc` không lỗi, `npm run lint` sạch
- [ ] `git diff --stat` không có file ngoài `mobile/`, không có `.env`/credential

**Web:**
- [ ] `npm run dev` chạy không lỗi console
- [ ] `npx tsc` không lỗi
- [ ] `git diff --stat` không có file ngoài `web/`, không có `.env`/credential, không có API key hard-code

**Cả hai:**
- [ ] Mô tả PR ghi rõ đã test gì (thiết bị thật/máy ảo cho mobile; data provider giả hay đã nối backend thật cho web)
- [ ] Nếu phát hiện cần thay đổi ở `backend/`: đã tạo issue riêng, **không** tự sửa
