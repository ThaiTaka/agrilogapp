import type { Metadata } from "next";

import { fetchOverview } from "@/lib/admin";
import { requireAdmin } from "@/lib/session";

export const metadata: Metadata = { title: "Tổng quan" };

function StatCard({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: number;
  hint?: string;
  tone?: "default" | "warning";
}) {
  return (
    <div className="group rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm ring-1 ring-slate-900/[0.02] transition duration-200 hover:-translate-y-0.5 hover:border-green-200 hover:shadow-md">
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <p
        className={`mt-1.5 text-3xl font-bold tabular-nums ${
          tone === "warning" && value > 0 ? "text-amber-600" : "text-slate-900"
        }`}
      >
        {/* Định dạng theo vi-VN: 1.234 chứ không phải 1,234. */}
        {value.toLocaleString("vi-VN")}
      </p>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

export default async function OverviewPage() {
  // Gọi lại dù layout đã gọi: trang tự bảo vệ mình.
  await requireAdmin();
  const data = await fetchOverview();

  return (
    <div className="px-6 py-8">
      <header className="mb-7">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Tổng quan
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Số liệu toàn hệ thống, đọc trực tiếp từ máy chủ.
        </p>
      </header>

      {data.maintenance_enabled ? (
        <p
          role="status"
          className="mb-6 rounded-xl border border-amber-300 bg-gradient-to-r from-amber-50 to-amber-100/50 px-4 py-3 text-sm font-medium text-amber-900 shadow-sm"
        >
          ⚠ Chế độ bảo trì đang BẬT — ứng dụng di động đang hiển thị thông báo
          bảo trì cho người dùng.
        </p>
      ) : null}

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Nông hộ" value={data.total_households} />
        <StatCard
          label="Tài khoản"
          value={data.total_users}
          hint={`${data.active_users.toLocaleString("vi-VN")} đang hoạt động`}
        />
        <StatCard
          label="Tài khoản bị khoá"
          value={data.locked_users}
          tone="warning"
        />
        <StatCard
          label="Tài khoản mới"
          value={data.new_users_last_30_days}
          hint="30 ngày qua"
        />
      </section>

      <h2 className="mt-8 mb-4 text-sm font-semibold tracking-wide text-slate-500 uppercase">
        Hoạt động canh tác
      </h2>
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Mùa vụ" value={data.total_seasons} />
        <StatCard label="Nhật ký canh tác" value={data.total_diary_entries} />
        <StatCard
          label="Nhật ký mới"
          value={data.diary_entries_last_7_days}
          hint="7 ngày qua"
        />
      </section>

      {/*
        Nói rõ vì sao con số có thể thấp hơn thực tế. Không có dòng này, một
        người quản trị nhìn "0 mùa vụ" sẽ kết luận nhầm rằng không ai dùng app,
        trong khi dữ liệu vẫn đang nằm trên máy của bà con.
      */}
      <p className="mt-8 max-w-2xl text-xs leading-relaxed text-slate-500">
        Số liệu mùa vụ và nhật ký chỉ tính phần đã đồng bộ lên máy chủ. Ứng dụng
        hoạt động ngoại tuyến, nên dữ liệu bà con vừa ghi có thể còn nằm trên
        máy cho tới lần đồng bộ kế tiếp. Bản ghi đã xoá không được tính.
      </p>
    </div>
  );
}
