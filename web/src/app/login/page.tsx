import type { Metadata } from "next";

import { safeNextPath } from "@/lib/redirect";

import LoginForm from "./LoginForm";

export const metadata: Metadata = {
  title: "Đăng nhập · AgriLog Admin",
};

const ERRORS: Record<string, string> = {
  "not-admin": "Tài khoản này không có quyền quản trị.",
  expired: "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.",
};

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  // `searchParams` là Promise từ Next.js 15 trở đi.
  const params = await searchParams;
  const rawNext = params.next;
  const rawError = params.error;

  const next = safeNextPath(rawNext);
  const notice = typeof rawError === "string" ? ERRORS[rawError] : undefined;

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="text-5xl drop-shadow-sm" aria-hidden>
            🌾
          </div>
          <h1 className="mt-3 bg-gradient-to-b from-green-700 to-green-900 bg-clip-text text-2xl font-bold text-transparent">
            AgriLog
          </h1>
          <p className="mt-1 text-sm text-slate-500">Trang quản trị hệ thống</p>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-lg shadow-green-900/[0.04] ring-1 ring-slate-900/[0.02]">
          {notice ? (
            <p
              role="alert"
              className="mb-5 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-800"
            >
              {notice}
            </p>
          ) : null}

          <LoginForm next={next} />
        </div>

        <p className="mt-6 text-center text-xs leading-relaxed text-slate-500">
          Chỉ tài khoản được cấp quyền quản trị mới đăng nhập được vào trang này.
        </p>
      </div>
    </main>
  );
}
