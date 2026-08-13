# Hướng Dẫn Bàn Giao Cho Khoa — Quy Trình Git

**Áp dụng từ:** 13/08/2026, khi dự án chuyển từ 1 người sang 2 người.
**Nguyên tắc chung:** `main` là nhánh triển lãm — luôn phải chạy được, chỉ nhận code đã qua review. Mọi thay đổi của Khoa đi qua **Pull Request**, không bao giờ push thẳng vào `main` hay `develop`.

---

## 0. Điều kiện tiên quyết (Thái làm trước, Khoa không cần làm)

Trước khi Khoa clone repo, Thái đã:
1. Đồng bộ `develop` cho khớp với `main` (trước đó `develop` bị bỏ quên, chậm 16 commit).
2. Tạo nhánh `khoa-mobile-ui-fixes` từ `develop` và push lên GitHub.

Nếu Khoa chạy `git fetch` mà không thấy nhánh `khoa-mobile-ui-fixes`, nghĩa là bước này chưa xong — báo Thái, đừng tự tạo nhánh trùng tên.

---

## Bước 1 — Cài đặt & clone

```powershell
git clone https://github.com/ThaiTaka/agrilogapp.git
cd agrilogapp
```

Nếu chưa từng dùng Git trên máy này, cấu hình danh tính trước khi commit lần đầu:

```powershell
git config --global user.name "Nguyễn Hoàng Anh Khoa"
git config --global user.email "<email GitHub của bạn>"
```

---

## Bước 2 — Lấy đúng nhánh của bạn

**Không làm việc trên `main` hay `develop`.** Lấy nhánh đã được tạo sẵn cho bạn:

```powershell
git fetch origin
git checkout khoa-mobile-ui-fixes
```

Kiểm tra lại đang đứng đúng nhánh:

```powershell
git branch --show-current
# phải in ra: khoa-mobile-ui-fixes
```

---

## Bước 3 — Dựng môi trường

Làm theo `README.md` §6–§8 và `Nhiem_Vu_Cua_Khoa.md` §1. Không dùng thông tin đăng nhập trong `Huong_Dan_Khoi_Dong_Du_An.md` (file cá nhân của Thái) — tự đăng ký tài khoản riêng.

---

## Bước 4 — Làm việc & commit

Quy tắc commit theo đúng `README.md` §12 (Conventional Commits), scope `mobile`:

```
fix(mobile): mô tả ngắn, ở thì hiện tại
feat(mobile): ...
test(mobile): ...
docs(mobile): ...
```

Ví dụ thật: `fix(mobile): xác nhận react-native-svg render đúng 3 biểu đồ trên thiết bị thật`

**Trước khi `git add`, luôn chạy `git status` và đọc kỹ danh sách file.** Không dùng `git add .` hay `git add -A` theo phản xạ — chỉ định rõ file:

```powershell
git status
git add mobile/src/screens/reports/ReportsScreen.tsx
git commit -m "fix(mobile): ..."
```

Lý do quy tắc này không phải hình thức: trong lần rà soát đầu tiên của repo, một file cấu hình editor (`.vscode/settings.json`) suýt bị commit kèm mật khẩu database thật, vì nó nằm lẫn trong một thư mục tưởng như vô hại. `git add` chọn lọc là cách duy nhất tránh việc này lặp lại.

---

## Bước 5 — Đồng bộ khi `develop` có cập nhật mới từ Thái

Làm việc này **thường xuyên**, đừng để nhánh của bạn lệch quá xa:

```powershell
git fetch origin
git merge origin/develop
```

Nếu có xung đột (conflict), Git sẽ đánh dấu trực tiếp trong file — sửa thủ công, sau đó:

```powershell
git add <file đã sửa xung đột>
git commit
```

Nếu xung đột nằm trong file bạn không chắc (đặc biệt bất kỳ thứ gì liên quan sync/backend), **dừng lại và hỏi Thái** thay vì tự đoán cách giải quyết.

---

## Bước 6 — Đẩy code & tạo Pull Request

```powershell
git push -u origin khoa-mobile-ui-fixes
```

Sau đó vào GitHub → tab **Pull requests** → **New pull request**:

- **base:** `develop`   ← không phải `main`
- **compare:** `khoa-mobile-ui-fixes`
- **Reviewer:** gán Thái (`ThaiTaka`)
- Nếu PR đóng một issue cụ thể trong `AgriLog_GitHub_Issues_and_Kanban.md`, ghi trong mô tả PR: `Closes #NN`

Hoặc bằng GitHub CLI nếu đã cài `gh`:

```powershell
gh pr create --base develop --head khoa-mobile-ui-fixes --title "fix(mobile): ..." --reviewer ThaiTaka --body "Mô tả đã test gì, trên thiết bị nào (thật hay ảo)."
```

Sau khi mở PR, **đợi Thái review** — không tự merge, kể cả khi CI (khi đã thiết lập) báo xanh.

---

## Ranh giới bắt buộc — KHÔNG được tự sửa

Đây là phần quan trọng nhất của file này. Các đường dẫn sau thuộc backend hoặc sync engine — sai một dòng có thể làm lệch dữ liệu giữa mobile và server, hoặc làm lại crash build vừa được vá hôm nay:

```
backend/**                              ← toàn bộ backend, không ngoại lệ
mobile/src/services/sync.ts             ← sync adapter, nối vào synchronize() của WatermelonDB
mobile/src/db/schema.ts                 ← schema WatermelonDB — phải song song tuyệt đối với PostgreSQL
mobile/src/db/migrations.ts             ← migration WatermelonDB
mobile/src/db/models/**                 ← model WatermelonDB
mobile/metro.config.js                  ← vừa vá lỗi crash Metro hôm nay (Error_Metro_Watcher_Crash_CXX_Build.md)
mobile/android/gradle.properties        ← cấu hình Hermes/AGP
mobile/patches/**                       ← patch WatermelonDB cho AGP9 (Error_WatermelonDB_BuildConfig_AGP9.md)
```

Nếu công việc của bạn có vẻ **cần** sửa một trong các file trên (ví dụ: một màn hình cần thêm trường mới mà schema chưa có) — đây là dấu hiệu đúng lúc cần trao đổi với Thái, không phải tự thêm vào. Mở issue mô tả bạn cần gì và tại sao, gắn nhãn liên quan, hoặc nhắn trực tiếp trước khi code.

Phần bạn **toàn quyền chỉnh sửa:** `mobile/src/screens/**`, `mobile/src/components/**`, `mobile/src/navigation/**`, và test tương ứng trong `mobile/src/**/__tests__/**`, `mobile/__tests__/**`.

---

## Quy tắc an toàn

- **Không bao giờ commit** file `.env`, mật khẩu, token, hoặc bất kỳ credential thật nào — kể cả trong comment hay file tài liệu ví dụ. Nếu cần ví dụ, dùng placeholder (`<mật khẩu của bạn>`), không dùng giá trị thật.
- `node_modules/`, `.venv/`, file `.apk`/`.aab`, `android/app/build/` đã được `.gitignore` chặn sẵn — nếu `git status` hiện bất kỳ thứ nào trong số này là untracked, dừng lại và kiểm tra trước khi add, đừng ép add bằng `-f`.
- Không `git push --force` lên `khoa-mobile-ui-fixes` sau khi đã mở PR và Thái bắt đầu review — nếu cần sửa sau góp ý, commit thêm bình thường.
- Không đổi tên hoặc xoá file trong phạm vi ranh giới ở trên, kể cả khi có vẻ "không dùng nữa".

---

## Checklist trước khi mở PR

- [ ] `npm test` xanh toàn bộ (không làm vỡ bộ 130 test hiện có)
- [ ] `npx tsc` không lỗi
- [ ] `npm run lint` sạch
- [ ] `git diff --stat` đã xem lại — không có file ngoài phạm vi mobile UI, không có `.env`/credential
- [ ] Mô tả PR ghi rõ đã test trên thiết bị thật hay chỉ máy ảo
- [ ] Nếu phát hiện bug ở backend/sync trong lúc test: đã tạo issue riêng, **không** tự sửa trong nhánh này
