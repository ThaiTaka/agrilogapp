# Báo Cáo Tiến Độ Dự Án AgriLog

**Ngày báo cáo:** 13/08/2026 (cập nhật lần 2 — bổ sung yêu cầu Web Admin Dashboard)
**Phạm vi:** Rà soát toàn bộ codebase (backend FastAPI, mobile React Native/WatermelonDB, test suite, tài liệu) tại thời điểm chuyển từ thực hiện một mình (Thái) sang mô hình hai người (Thái + Khoa).
**Phương pháp:** Mọi số liệu backend/mobile trong báo cáo này lấy trực tiếp từ việc chạy test thật (`pytest`, `jest`), đếm file/dòng thật, và đọc mã nguồn thật — không suy diễn từ tài liệu cũ.

> Lưu ý: đề cương đồ án có mốc **M5 — Báo cáo tiến độ lần 1** vào 24/9–28/9/2026 (xem `README.md` §11). Báo cáo này phục vụ việc bàn giao nội bộ, không thay thế báo cáo M5 chính thức nộp cho giáo viên hướng dẫn.

---

## 1. Tóm tắt điều hành

Dự án hiện có **ba mảng** thay vì hai: Backend, Mobile, và **Web Admin Dashboard** (yêu cầu vừa được phát hiện lại từ đề cương đồ án, chưa từng xuất hiện trong `README.md` hay `AgriLog_GitHub_Issues_and_Kanban.md` — đã kiểm tra bằng grep toàn repo, không có issue nào trong 55 issue hiện có nhắc tới "web" hay "admin dashboard").

| Mảng | Trạng thái | Người phụ trách |
|---|---|---|
| Backend (FastAPI + PostgreSQL + Sync) | ✅ Hoàn thiện, đã test (350 test, 94% coverage) | Thái |
| Mobile (React Native + WatermelonDB) | 🔶 Đã xây xong code (12 màn hình), **chưa kiểm thử người dùng thật** | Khoa |
| **Web Admin Dashboard** | ⬜ **Chưa bắt đầu — chưa có 1 dòng code, chưa có cả thư mục `web/`** | Khoa |

Điểm cần lưu ý ngay: yêu cầu "quản lý user, xem báo cáo, quản lý hiển thị ứng dụng" **không chỉ là việc dựng frontend**. Đã kiểm tra trực tiếp `backend/app/models/account.py` — model `User` hiện chỉ có `id, household_id, email, full_name, password_hash, is_active`, **không có khái niệm quyền quản trị (`is_admin`/role) nào**, và toàn bộ API hiện tại (`api/deps.py::current_household`) chỉ cho phép một user thấy dữ liệu của **household của chính mình** — không có endpoint nào nhìn xuyên household. Nghĩa là Web Admin cần **API mới ở backend**, không phải chỉ nối vào API sẵn có. Chi tiết ở Mục 5.

---

## 2. Đối chiếu với lộ trình đề cương

| Mốc | Nội dung | Thời gian | Trạng thái |
|---|---|---|---|
| M1 | Phân tích đề tài | 10/8–16/8 | ✅ |
| M2 | Thiết kế chi tiết | 17/8–26/8 | ✅ |
| M3 | Nền tảng Backend & Mobile | 27/8–9/9 | ✅ backend + mobile foundation xong |
| M4 | Module Nhật ký & Chi phí | 10/9–23/9 | ✅ backend xong; UI mobile xong, chưa kiểm thử người dùng thật |
| M5 | Báo cáo tiến độ lần 1 | 24/9–28/9 | việc bàn giao này đi trước mốc chính thức |
| M6 | Sync Engine | 29/9–12/10 | ✅ backend xong; mobile sync adapter code xong, chưa kiểm thử đa thiết bị |
| M7 | Kiểm thử ngoại tuyến & đồng bộ | 13/10–22/10 | ⬜ chưa bắt đầu — trọng tâm việc mobile của Khoa |
| M8 | Module Báo cáo & Trực quan hóa | 23/10–1/11 | ✅ backend xong; 3 biểu đồ mobile code xong, chưa xác nhận trên thiết bị |
| **M?** | **Web Admin Dashboard** | **chưa có mốc chính thức trong đề cương gốc** | ⬜ **mới bổ sung — cần chèn vào lộ trình, đề xuất song song M7–M9** |
| M9 | Báo cáo tiến độ lần 2 | 2/11–5/11 | ⬜ |
| M10 | Tối ưu & hoàn thiện | 6/11–12/11 | ⬜ |
| M11 | Bảo vệ đồ án | 13/11–15/11 | ⬜ |

**Khuyến nghị:** vì Web Admin không có mốc riêng trong bảng gốc, nên chèn nó chạy **song song** với M7/M8 (không nối đuôi phía sau) — nếu không, đồ án dồn toàn bộ phần web vào sát M9-M10 và rủi ro không kịp bảo vệ ngày 13-15/11.

---

## 3. Backend — hoàn thành và đã kiểm thử (không đổi so với lần rà soát trước)

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
| Xử lý thời gian | `core/timeutils.py` | `test_timeutils.py` | 14 |
| Song song schema ORM ↔ migration | — | `test_schema_integrity.py` | 14 |
| Song song schema PostgreSQL ↔ WatermelonDB | — | `test_schema_parity.py` | 11 |
| Health probe | `main.py` | `test_health.py` | 8 |

Tất cả 9 router đã gắn vào app thật (`main.py::_register_v1_routers`), không còn `TODO`/`FIXME` nào trong `backend/app`. **Chưa có** router hay model nào phục vụ vai trò quản trị hệ thống — xem Mục 5.4.

---

## 4. Mobile — đã xây dựng, CHƯA được kiểm thử ở mức người dùng thật (không đổi)

| Số liệu | Giá trị thật (đã đếm) |
|---|---|
| Số màn hình | 12 (Đăng nhập, Mùa vụ ×2, Nhật ký ×2, Vật tư ×3, Thu chi ×3, Báo cáo ×1) |
| Dòng code UI (screens+components+navigation) | 5.329 dòng |
| Tổng dòng code `mobile/src` (không kể test) | 8.538 dòng |
| Test Jest | 130 test / 7 suite, 100% xanh — **chỉ kiểm tra tầng service/DB cục bộ + 1 smoke-test khởi động app, không có test giao diện từng màn hình** |

Cột mốc 13/08: lần đầu build thành công trên máy ảo (Pixel 6a AVD), WatermelonDB khởi tạo SQLite thật lần đầu. Hai lỗi build đã vá và ghi lại (`Error_WatermelonDB_BuildConfig_AGP9.md`, `Error_Metro_Watcher_Crash_CXX_Build.md`). Chưa test trên thiết bị vật lý, chưa chạy checklist ngoại tuyến README §8, chưa có golden fixture/snapshot nào cho UI. Chi tiết đầy đủ và bảng 12 màn hình: xem `Nhiem_Vu_Cua_Khoa.md`.

---

## 5. Web Admin Dashboard — yêu cầu mới, CHƯA bắt đầu

### 5.1 Yêu cầu (theo đề cương)

Hệ thống quản trị web cho system admin: **quản lý người dùng**, **xem báo cáo**, **quản lý hiển thị ứng dụng**. Đây là bắt buộc theo đề cương đồ án, tách biệt hoàn toàn khỏi app di động dành cho nông hộ.

### 5.2 Hiện trạng

- Không có thư mục `web/` trong repo (đã kiểm tra).
- Không có khái niệm "admin" ở bất kỳ đâu trong backend (đã grep `is_admin|role|admin` trong `backend/app`, không có kết quả).
- Không có issue nào trong `AgriLog_GitHub_Issues_and_Kanban.md` (55 issue hiện có) đề cập web admin.
- 3 endpoint báo cáo hiện có (`/reports/income-expense`, `/reports/supply-consumption`, `/reports/season-comparison`) đều đang giới hạn theo `current_household` — dùng được cho "xem báo cáo" cấp *một* household, nhưng admin cần xem **toàn hệ thống**, đây là một API mới, không phải API cũ dùng lại nguyên trạng.

### 5.3 Đề xuất công nghệ

| Lựa chọn | Ưu điểm | Vì sao không chọn (hoặc chọn) cho ca này |
|---|---|---|
| **React Admin + Vite (đề xuất)** | Sinh sẵn màn hình List/Edit/Create/Show từ khai báo "resource" — đúng khuôn mẫu "quản lý user, quản lý hiển thị"; có `ra-data-fakerest` để Khoa code UI ngay bằng dữ liệu giả **trước khi** API admin thật tồn tại, rồi đổi sang data provider REST thật sau — khớp chính xác với thực trạng "backend admin chưa có" ở Mục 5.2; auth provider cắm được vào luồng JWT hiện có | Giao diện mặc định theo Material UI, không đồng bộ theme với mobile — chấp nhận được vì đây là công cụ nội bộ, không phải sản phẩm nông hộ dùng |
| Vite + React thuần | Nhẹ nhất, toàn quyền kiểm soát UI | Phải tự viết bảng/phân trang/form CRUD/auth guard từ đầu — chậm hơn nhiều cho một trang quản trị tiêu chuẩn, rủi ro cao khi chỉ có 1 người vừa làm mobile vừa làm web |
| Next.js | Mạnh nếu cần SSR/SEO | Thừa cho trang sau-đăng-nhập; API routes của Next trùng chức năng với FastAPI đã có sẵn — tốn thời gian dựng không dùng tới |

**Kết luận:** `web/` dựng bằng **Vite + React + TypeScript**, thêm **react-admin** làm khung quản trị, **recharts** cho phần biểu đồ (thư viện phổ biến nhất để nhúng chart tuỳ biến vào react-admin). TypeScript để đồng bộ quy ước với `mobile/`.

### 5.4 Việc backend phải làm trước/song song (Thái)

Đây là phần chặn Khoa nếu không làm sớm — liệt kê cụ thể để không bị phát hiện muộn:

1. Thêm quyền quản trị: cột `is_admin` trên `User` (hoặc bảng `admin_users` riêng nếu muốn tách hẳn khỏi user nông hộ) + migration Alembic mới.
2. Dependency xác thực admin mới trong `api/deps.py`, khác với `current_household` hiện tại — phải cho phép nhìn **xuyên** household thay vì giới hạn trong một household.
3. Endpoint quản lý user/household cấp hệ thống: liệt kê, khoá/mở (`is_active`), xem chi tiết — ví dụ `/api/v1/admin/households`, `/api/v1/admin/users`.
4. Endpoint báo cáo cấp admin (tổng hợp toàn hệ thống hoặc lọc theo household do admin chọn) — khác 3 endpoint `/reports/*` hiện tại đang tự động giới hạn theo `current_household`.
5. Làm rõ nghĩa cụ thể của **"quản lý hiển thị ứng dụng"** — hiện chưa đủ chi tiết để thiết kế bảng dữ liệu (feature flag theo module? bật/tắt bảo trì? ẩn/hiện theo household?). Cần Thái và Khoa thống nhất phạm vi trước khi Thái thiết kế schema.

### 5.5 Việc Khoa có thể làm ngay, không cần chờ Mục 5.4

- Khởi tạo `web/`, dựng khung react-admin, layout, màn hình đăng nhập (UI, chưa nối auth thật).
- Dựng các màn hình List/Edit cho "user" và "household" bằng `ra-data-fakerest` (dữ liệu giả trong bộ nhớ) để có giao diện chạy được ngay hôm nay.
- Dựng trang Dashboard với 3 biểu đồ bằng recharts, dùng dữ liệu giả cùng hình dạng với response thật của `/reports/*` (đã có sẵn field trong `backend/app/schemas/report.py` để tham chiếu đúng shape).
- Khi Mục 5.4 xong, việc còn lại chỉ là đổi data provider từ giả sang REST thật — không phải viết lại UI.

Chi tiết nhiệm vụ đầy đủ: `Nhiem_Vu_Cua_Khoa.md`. Quy trình Git (nhánh riêng cho web): `Huong_Dan_Ban_Giao_Khoa.md`.

---

## 6. Chưa xây dựng / chưa bắt đầu (tổng hợp)

- **Web Admin Dashboard** — toàn bộ, kể cả backend API quản trị (Mục 5).
- **CI/CD:** `README.md` §13 mô tả CI chạy lint+test mỗi push/PR (Issue #18) nhưng `.github/workflows/` không tồn tại. Nên thiết lập trước khi PR đầu tiên của Khoa (mobile hoặc web) được mở.
- Load test đồng bộ (Issue #39).
- Test thiết bị vật lý, test đa thiết bị (Issue #40).
- M9/M10 (báo cáo tiến độ lần 2, tối ưu & hoàn thiện).

---

## 7. Rủi ro bảo mật — đã xử lý (ghi lại để không lặp lại)

Lần rà soát trước phát hiện 2 file chứa credential dạng plaintext (`vscode/settings.json` — mật khẩu PostgreSQL; `Huong_Dan_Khoi_Dong_Du_An.md` — mật khẩu tài khoản mẫu). Cả hai đã được redact và commit an toàn (commit `657eb88`). Bài học áp dụng tiếp cho `web/`: **không bao giờ hard-code API key, mật khẩu, hay connection string trong code hoặc file `.md`** — kể cả trong ví dụ hướng dẫn.

---

## 8. Phân công từ đây (cập nhật)

| Người | Phạm vi | Lý do |
|---|---|---|
| **Thái** | Backend (FastAPI/SQLAlchemy/Alembic), database, sync engine, **API quản trị mới cho Web Admin (Mục 5.4)**, CI, review PR của Khoa | Toàn quyền và hiểu trọn tầng backend |
| **Khoa** | Mobile UI + kiểm thử thiết bị thật (không đổi) **cộng thêm Web Admin Dashboard (`web/`) trọn gói: dựng, UI, nối API khi Thái sẵn sàng** | Theo yêu cầu mới nhất — Khoa nhận toàn bộ phần frontend (mobile + web), Thái giữ nguyên backend |

**Rủi ro cần theo dõi:** một người (Khoa) vừa gánh mobile QA/kiểm thử thiết bị thật (vốn đã là khối lượng lớn — xem `Nhiem_Vu_Cua_Khoa.md`) vừa dựng một sản phẩm web mới từ đầu. Đề xuất: Khoa dùng Mục 5.5 (bắt đầu bằng dữ liệu giả) để không bị chặn bởi Mục 5.4, và hai bên revisit khối lượng công việc ở mốc M5/M9 nếu web admin kéo chậm phần mobile.

---

*Báo cáo này được tổng hợp với sự hỗ trợ của Claude (Anthropic), theo đúng tinh thần công khai đóng góp AI đã nêu ở `README.md` §15. Số liệu backend/mobile giữ nguyên từ lần rà soát 13/08/2026 (chưa có commit code mới kể từ đó); phần Web Admin (Mục 5) là đánh giá hiện trạng + đề xuất mới, không phải số liệu đo được vì chưa có code.*
