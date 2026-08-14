"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function LogoutButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function onLogout() {
    setBusy(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      // Điều hướng dù có lỗi: cookie đã bị xoá ở phía máy chủ, giữ người dùng
      // lại trên một trang trông như đã đăng nhập chỉ gây hiểu nhầm.
      router.refresh();
      router.replace("/login");
    }
  }

  return (
    <button
      type="button"
      onClick={onLogout}
      disabled={busy}
      className="shrink-0 rounded-lg border border-slate-300 px-3.5 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:opacity-50"
    >
      {busy ? "Đang thoát…" : "Đăng xuất"}
    </button>
  );
}
