import type { Metadata } from "next";
import Link from "next/link";

import { fetchUsers } from "@/lib/admin";
import { requireAdmin } from "@/lib/session";

import UserActions from "./UserActions";

export const metadata: Metadata = { title: "Tài khoản" };

const PAGE_SIZE = 20;

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleDateString("vi-VN", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });
}

export default async function UsersPage({ searchParams }: PageProps<"/users">) {
  const admin = await requireAdmin();
  const params = await searchParams;

  const search = typeof params.q === "string" ? params.q : "";
  const filter = typeof params.status === "string" ? params.status : "all";
  const page = Math.max(1, Number(params.page) || 1);

  const data = await fetchUsers({
    search: search || undefined,
    is_active: filter === "active" ? true : filter === "locked" ? false : undefined,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });

  const from = data.total === 0 ? 0 : data.offset + 1;
  const to = data.offset + data.items.length;
  const hasPrev = page > 1;
  const hasNext = to < data.total;

  const linkFor = (next: Record<string, string | number>) => {
    const sp = new URLSearchParams();
    if (search) sp.set("q", search);
    if (filter !== "all") sp.set("status", filter);
    for (const [k, v] of Object.entries(next)) sp.set(k, String(v));
    const qs = sp.toString();
    return qs ? `/users?${qs}` : "/users";
  };

  return (
    <div className="px-6 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Tài khoản</h1>
        <p className="mt-1 text-sm text-slate-500">
          Toàn bộ tài khoản trong hệ thống, không giới hạn theo nông hộ.
        </p>
      </header>

      {/* Biểu mẫu GET: bộ lọc nằm trong URL, nên chia sẻ được và F5 không mất. */}
      <form method="GET" className="mb-5 flex flex-wrap items-center gap-3">
        <input
          type="search"
          name="q"
          defaultValue={search}
          placeholder="Tìm theo email, tên, nông hộ…"
          aria-label="Tìm tài khoản"
          className="min-w-56 flex-1 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-sm shadow-sm outline-none transition duration-150 focus:border-green-600 focus:ring-2 focus:ring-green-600/20"
        />
        <select
          name="status"
          defaultValue={filter}
          aria-label="Lọc theo trạng thái"
          className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm outline-none transition duration-150 focus:border-green-600 focus:ring-2 focus:ring-green-600/20"
        >
          <option value="all">Tất cả trạng thái</option>
          <option value="active">Đang hoạt động</option>
          <option value="locked">Đã khoá</option>
        </select>
        <button
          type="submit"
          className="rounded-xl bg-green-700 px-4 py-2 text-sm font-semibold text-white shadow-sm transition duration-150 hover:bg-green-800 hover:shadow-md focus:ring-2 focus:ring-green-600/40 focus:outline-none active:scale-[0.98]"
        >
          Lọc
        </button>
        {(search || filter !== "all") && (
          <Link href="/users" className="text-sm text-slate-500 hover:underline">
            Xoá bộ lọc
          </Link>
        )}
      </form>

      <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white shadow-sm ring-1 ring-slate-900/[0.02]">
        <table className="w-full min-w-3xl text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50/70 text-left text-xs tracking-wide text-slate-500 uppercase">
              <th className="px-4 py-3 font-medium">Tài khoản</th>
              <th className="px-4 py-3 font-medium">Nông hộ</th>
              <th className="px-4 py-3 font-medium">Trạng thái</th>
              <th className="px-4 py-3 font-medium">Ngày tạo</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {data.items.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-slate-500">
                  Không có tài khoản nào khớp bộ lọc.
                </td>
              </tr>
            ) : (
              data.items.map((user) => (
                <tr
                  key={user.id}
                  className="border-b border-slate-100 transition-colors duration-150 last:border-0 hover:bg-green-50/40"
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">
                      {user.full_name}
                      {user.is_admin ? (
                        <span className="ml-2 rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-800">
                          Quản trị
                        </span>
                      ) : null}
                      {user.id === admin.id ? (
                        <span className="ml-2 text-xs text-slate-400">(bạn)</span>
                      ) : null}
                    </div>
                    <div className="text-slate-500">{user.email}</div>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{user.household_name}</td>
                  <td className="px-4 py-3">
                    <span
                      className={
                        user.is_active
                          ? "inline-flex items-center gap-1.5 text-green-700"
                          : "inline-flex items-center gap-1.5 text-red-700"
                      }
                    >
                      <span
                        aria-hidden
                        className={`size-2 rounded-full ${
                          user.is_active ? "bg-green-600" : "bg-red-600"
                        }`}
                      />
                      {user.is_active ? "Đang hoạt động" : "Đã khoá"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500 tabular-nums">
                    {formatDate(user.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    {/*
                      Không hiện nút cho chính mình: máy chủ vẫn từ chối thao
                      tác này (409), nhưng một nút chỉ để báo lỗi thì không nên
                      tồn tại.
                    */}
                    {user.id === admin.id ? (
                      <span className="block text-right text-xs text-slate-400">
                        không tự khoá được
                      </span>
                    ) : (
                      <UserActions
                        userId={user.id}
                        isActive={user.is_active}
                        fullName={user.full_name}
                      />
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
        <p>
          {data.total === 0
            ? "Không có kết quả"
            : `Hiển thị ${from}–${to} trên ${data.total.toLocaleString("vi-VN")}`}
        </p>
        <div className="flex gap-2">
          <Link
            href={hasPrev ? linkFor({ page: page - 1 }) : "#"}
            aria-disabled={!hasPrev}
            className={
              hasPrev
                ? "rounded-xl border border-slate-300 bg-white px-3.5 py-1.5 shadow-sm transition duration-150 hover:border-green-300 hover:bg-green-50 hover:text-green-800"
                : "pointer-events-none rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-1.5 text-slate-300"
            }
          >
            Trước
          </Link>
          <Link
            href={hasNext ? linkFor({ page: page + 1 }) : "#"}
            aria-disabled={!hasNext}
            className={
              hasNext
                ? "rounded-xl border border-slate-300 bg-white px-3.5 py-1.5 shadow-sm transition duration-150 hover:border-green-300 hover:bg-green-50 hover:text-green-800"
                : "pointer-events-none rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-1.5 text-slate-300"
            }
          >
            Sau
          </Link>
        </div>
      </div>
    </div>
  );
}
