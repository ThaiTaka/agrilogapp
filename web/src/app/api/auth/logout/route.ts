import { NextResponse } from "next/server";

import { apiFetch } from "@/lib/api";
import { destroySession, getRefreshToken } from "@/lib/session";

/**
 * Đăng xuất: thu hồi refresh token ở máy chủ, rồi xoá cookie.
 *
 * Thứ tự đó là cố ý. Chỉ xoá cookie thôi thì phiên chỉ biến mất khỏi trình
 * duyệt này, còn refresh token vẫn sống 90 ngày ở máy chủ — ai cầm được nó
 * vẫn đổi ra phiên mới được.
 */
export async function POST(): Promise<NextResponse> {
  const refresh = await getRefreshToken();

  if (refresh) {
    try {
      await apiFetch("/api/v1/auth/logout", {
        method: "POST",
        body: { refresh_token: refresh },
      });
    } catch {
      // Máy chủ không phản hồi vẫn phải đăng xuất được ở phía này. Người dùng
      // bấm "Đăng xuất" trên một máy tính chung mà bị từ chối vì lỗi mạng là
      // kết cục tệ hơn nhiều so với một token còn sống tới hạn.
    }
  }

  await destroySession();
  return NextResponse.json({ ok: true });
}
