import { NextResponse } from "next/server";

import { ApiError, apiFetch } from "@/lib/api";
import { createSession, type SessionUser } from "@/lib/session";

/**
 * Cầu nối đăng nhập giữa trình duyệt và FastAPI.
 *
 * Trình duyệt gửi email/mật khẩu tới ĐÂY, không gửi thẳng sang FastAPI. Nhờ
 * vậy JWT đi từ FastAPI vào cookie `httpOnly` mà không bao giờ đi qua
 * JavaScript phía trình duyệt — token không nằm trong `localStorage`, không
 * nằm trong state React, và một lỗ hổng XSS không lấy được phiên quản trị.
 */

interface LoginBody {
  email?: unknown;
  password?: unknown;
}

interface TokenPair {
  access_token: string;
  refresh_token: string;
  user: SessionUser;
}

export async function POST(request: Request): Promise<NextResponse> {
  let body: LoginBody;
  try {
    body = (await request.json()) as LoginBody;
  } catch {
    return NextResponse.json({ error: "Dữ liệu gửi lên không hợp lệ." }, { status: 400 });
  }

  const email = typeof body.email === "string" ? body.email.trim() : "";
  const password = typeof body.password === "string" ? body.password : "";

  if (!email || !password) {
    return NextResponse.json(
      { error: "Vui lòng nhập đầy đủ email và mật khẩu." },
      { status: 400 },
    );
  }

  let pair: TokenPair;
  try {
    pair = await apiFetch<TokenPair>("/api/v1/auth/login", {
      method: "POST",
      body: { email, password },
    });
  } catch (error) {
    if (error instanceof ApiError) {
      // Thông điệp giữ nguyên như FastAPI trả về, vốn đã cố tình không phân
      // biệt "sai email" với "sai mật khẩu" — phân biệt sẽ biến trang đăng
      // nhập thành công cụ dò xem email nào có tồn tại trong hệ thống.
      return NextResponse.json(
        { error: error.message },
        { status: error.status === 0 ? 502 : error.status },
      );
    }
    throw error;
  }

  if (!pair.user.is_admin) {
    // Thu hồi luôn cặp token vừa cấp. Đăng nhập bị từ chối mà vẫn để lại một
    // refresh token sống 90 ngày là để lại đúng thứ mình vừa từ chối cấp.
    await revokeQuietly(pair.refresh_token);
    return NextResponse.json(
      { error: "Tài khoản này không có quyền quản trị." },
      { status: 403 },
    );
  }

  await createSession(pair);

  // Chỉ trả những gì giao diện cần hiển thị. Token không nằm trong phần thân
  // phản hồi — nó đã đi vào cookie `httpOnly` ở trên.
  return NextResponse.json({
    user: { email: pair.user.email, full_name: pair.user.full_name },
  });
}

async function revokeQuietly(refreshToken: string): Promise<void> {
  try {
    await apiFetch("/api/v1/auth/logout", {
      method: "POST",
      body: { refresh_token: refreshToken },
    });
  } catch {
    // Thu hồi là nỗ lực tốt nhất. Không thu hồi được thì token vẫn hết hạn
    // theo lịch, và việc đó không phải lý do để chặn phản hồi 403 ở trên.
  }
}
