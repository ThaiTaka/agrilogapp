"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { safeNextPath } from "@/lib/redirect";

/**
 * Biểu mẫu đăng nhập.
 *
 * Gửi tới `/api/auth/login` của chính Next.js, không gửi thẳng sang FastAPI.
 * Component này không bao giờ nhìn thấy JWT — nó nằm trong cookie `httpOnly`
 * do Route Handler đặt, và mã phía trình duyệt không đọc được.
 */
export default function LoginForm({ next }: { next?: string }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;

    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });

      if (!response.ok) {
        const data = (await response.json().catch(() => null)) as {
          error?: string;
        } | null;
        setError(data?.error ?? "Đăng nhập thất bại. Vui lòng thử lại.");
        return;
      }

      // `refresh()` trước khi điều hướng: layout của bảng điều khiển là Server
      // Component đọc cookie phiên, nên nếu không làm mới bộ đệm router thì
      // trang đích có thể được dựng lại từ phiên bản "chưa đăng nhập".
      router.refresh();
      // Lọc lại lần nữa dù máy chủ đã lọc: hai lớp cùng gọi một hàm, nên lớp
      // này không phải tin rằng lớp kia đã làm đúng.
      router.replace(safeNextPath(next) ?? "/");
    } catch {
      setError("Không kết nối được máy chủ. Kiểm tra lại kết nối mạng.");
    } finally {
      setBusy(false);
    }
  }

  const canSubmit = email.trim().length > 0 && password.length > 0 && !busy;

  return (
    <form onSubmit={onSubmit} className="space-y-5" noValidate>
      <div>
        <label
          htmlFor="email"
          className="mb-1.5 block text-sm font-medium text-slate-700"
        >
          Email
        </label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="username"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            setError(null);
          }}
          disabled={busy}
          placeholder="quantri@example.com"
          className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-green-600 focus:ring-2 focus:ring-green-600/20 disabled:bg-slate-50"
        />
      </div>

      <div>
        <label
          htmlFor="password"
          className="mb-1.5 block text-sm font-medium text-slate-700"
        >
          Mật khẩu
        </label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            setError(null);
          }}
          disabled={busy}
          className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-slate-900 outline-none transition focus:border-green-600 focus:ring-2 focus:ring-green-600/20 disabled:bg-slate-50"
        />
      </div>

      {error ? (
        <p
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700"
        >
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full rounded-lg bg-green-700 px-4 py-2.5 font-semibold text-white transition hover:bg-green-800 focus:outline-none focus:ring-2 focus:ring-green-600/40 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {busy ? "Đang đăng nhập…" : "Đăng nhập"}
      </button>
    </form>
  );
}
