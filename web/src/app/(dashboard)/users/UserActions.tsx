"use client";

import { useState, useTransition } from "react";

import { toggleUserActive } from "./actions";

/**
 * Nút khoá / mở cho một dòng trong bảng.
 *
 * Không cập nhật lạc quan: khoá một tài khoản là thao tác máy chủ có quyền từ
 * chối (tự khoá mình, hoặc khoá quản trị viên cuối cùng), và hiện trạng thái
 * "đã khoá" rồi lật ngược lại khi bị từ chối thì tệ hơn là chờ nửa giây.
 */
export default function UserActions({
  userId,
  isActive,
  fullName,
}: {
  userId: string;
  isActive: boolean;
  fullName: string;
}) {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function onToggle() {
    setError(null);
    if (isActive && !confirm(`Khoá tài khoản của ${fullName}?`)) {
      return;
    }
    startTransition(async () => {
      const result = await toggleUserActive(userId, !isActive);
      if (!result.ok) {
        setError(result.error ?? "Không thực hiện được.");
      }
    });
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={onToggle}
        disabled={pending}
        className={
          isActive
            ? "rounded-xl border border-red-200 bg-white px-3.5 py-1.5 text-sm font-medium text-red-700 shadow-sm transition duration-150 hover:border-red-300 hover:bg-red-50 hover:shadow-md active:scale-[0.97] disabled:opacity-50"
            : "rounded-xl border border-green-300 bg-white px-3.5 py-1.5 text-sm font-medium text-green-800 shadow-sm transition duration-150 hover:bg-green-50 hover:shadow-md active:scale-[0.97] disabled:opacity-50"
        }
      >
        {pending ? "Đang lưu…" : isActive ? "Khoá" : "Mở khoá"}
      </button>
      {error ? (
        <p role="alert" className="max-w-xs text-right text-xs text-red-600">
          {error}
        </p>
      ) : null}
    </div>
  );
}
