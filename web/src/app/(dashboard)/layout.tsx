import Link from "next/link";

import { requireAdmin } from "@/lib/session";

import LogoutButton from "./LogoutButton";
import NavLink from "./NavLink";

/**
 * Khung chung của trang quản trị.
 *
 * `requireAdmin()` ở đây chặn mọi trang trong nhóm `(dashboard)` cùng một lúc.
 * Từng trang vẫn gọi lại nó — thừa một chút, nhưng một trang tự bảo vệ mình thì
 * không phụ thuộc vào việc người viết sau nhớ đặt nó vào đúng thư mục.
 *
 * `(dashboard)` là route group: dấu ngoặc làm thư mục này KHÔNG xuất hiện
 * trong URL, nên `(dashboard)/page.tsx` phục vụ `/`, không phải `/dashboard`.
 */
export default async function DashboardLayout({
  children,
}: LayoutProps<"/">) {
  const user = await requireAdmin();

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-200 bg-white/80 shadow-sm backdrop-blur-sm sm:flex">
        <div className="border-b border-slate-200 px-5 py-5">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-2xl" aria-hidden>
              🌾
            </span>
            <span className="font-bold text-green-800">AgriLog</span>
          </Link>
          <p className="mt-0.5 text-xs text-slate-500">Trang quản trị</p>
        </div>

        <nav className="flex flex-1 flex-col gap-1 p-3">
          <NavLink href="/">Tổng quan</NavLink>
          <NavLink href="/users">Tài khoản</NavLink>
        </nav>

        <div className="border-t border-slate-200 p-3">
          <p className="truncate px-2 text-sm font-medium text-slate-700">
            {user.full_name}
          </p>
          <p className="mb-3 truncate px-2 text-xs text-slate-500">{user.email}</p>
          <LogoutButton />
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        {/* Thanh điều hướng cho màn hình hẹp, nơi sidebar bị ẩn. */}
        <div className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 sm:hidden">
          <span className="text-xl" aria-hidden>
            🌾
          </span>
          <NavLink href="/">Tổng quan</NavLink>
          <NavLink href="/users">Tài khoản</NavLink>
          <div className="ml-auto">
            <LogoutButton />
          </div>
        </div>

        {children}
      </main>
    </div>
  );
}
