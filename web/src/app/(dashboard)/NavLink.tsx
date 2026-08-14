"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * Liên kết điều hướng biết mình có đang là trang hiện tại hay không.
 *
 * Client Component vì `usePathname` cần chạy ở trình duyệt. Nó chỉ nhận
 * `href` và nội dung — không chạm gì tới dữ liệu hay phiên đăng nhập.
 */
export default function NavLink({
  href,
  children,
}: {
  href: "/" | "/users";
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const active = pathname === href;

  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={
        active
          ? "rounded-lg bg-green-50 px-3 py-2 text-sm font-semibold text-green-800"
          : "rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100"
      }
    >
      {children}
    </Link>
  );
}
