import { requireAdmin } from "@/lib/session";

import LogoutButton from "./LogoutButton";

/**
 * Trang tạm sau khi đăng nhập.
 *
 * Bước 4 (Dashboard tổng quan) và Bước 5 (Quản lý người dùng) sẽ thay thế
 * trang này. Nó tồn tại ở bước 3 để chứng minh vòng đăng nhập chạy trọn vẹn:
 * cookie được đặt, máy chủ đọc được, và danh tính lấy về là danh tính thật do
 * FastAPI xác nhận chứ không phải thứ giao diện tự đoán.
 */
export default async function HomePage() {
  const user = await requireAdmin();

  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <header className="flex items-start justify-between gap-6">
        <div>
          <h1 className="text-2xl font-bold text-green-800">AgriLog Admin</h1>
          <p className="mt-1 text-sm text-slate-500">
            Đăng nhập với tư cách{" "}
            <span className="font-medium text-slate-700">{user.full_name}</span>{" "}
            ({user.email})
          </p>
        </div>
        <LogoutButton />
      </header>

      <section className="mt-10 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="font-semibold text-slate-900">Đang xây dựng</h2>
        <ul className="mt-3 space-y-2 text-sm text-slate-600">
          <li>✅ Bước 1–2 — Khởi tạo Next.js, cấu trúc thư mục, API client</li>
          <li>✅ Bước 3 — Đăng nhập bảo mật bằng cookie httpOnly</li>
          <li>⬜ Bước 4 — Dashboard tổng quan</li>
          <li>⬜ Bước 5 — Quản lý người dùng</li>
        </ul>
      </section>
    </main>
  );
}
