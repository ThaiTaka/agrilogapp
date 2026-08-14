"use server";

import { revalidatePath } from "next/cache";

import { updateUserActive } from "@/lib/admin";
import { ApiError } from "@/lib/api";
import { getSessionUser } from "@/lib/session";

export interface ToggleResult {
  ok: boolean;
  error?: string;
}

/**
 * Khoá / mở một tài khoản.
 *
 * `getSessionUser()` được gọi NGAY TRONG hàm này, không dựa vào việc trang đã
 * kiểm quyền. Server Function nhận được cả POST gửi thẳng tới nó, không chỉ
 * qua giao diện — nên một hàm tin rằng "trang gọi mình đã kiểm rồi" là một
 * endpoint quản trị không có khoá.
 *
 * `redirect()` cố tình KHÔNG dùng ở đây: hàm này được gọi từ một nút bấm, và
 * trả về thông báo lỗi để hiển thị tại chỗ thì hữu ích hơn là đá người dùng
 * sang trang khác giữa chừng.
 */
export async function toggleUserActive(
  userId: string,
  isActive: boolean,
): Promise<ToggleResult> {
  const admin = await getSessionUser();
  if (!admin) {
    return { ok: false, error: "Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại." };
  }
  if (!admin.is_admin) {
    return { ok: false, error: "Tài khoản này không có quyền quản trị." };
  }

  try {
    await updateUserActive(userId, isActive);
  } catch (error) {
    if (error instanceof ApiError) {
      // Máy chủ từ chối vì lý do nghiệp vụ — tự khoá mình, hoặc khoá tài khoản
      // quản trị hoạt động cuối cùng. Thông điệp của nó đã viết cho người đọc.
      return { ok: false, error: error.message };
    }
    throw error;
  }

  revalidatePath("/users");
  // Trang tổng quan đếm số tài khoản đang hoạt động / bị khoá, nên nó cũng
  // vừa sai đi sau thao tác này.
  revalidatePath("/");
  return { ok: true };
}
