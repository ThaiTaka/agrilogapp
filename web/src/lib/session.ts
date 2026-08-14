import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { ApiError, apiFetch } from "./api";

/**
 * Tầng truy cập phiên đăng nhập.
 *
 * Đây là nơi DUY NHẤT đọc/ghi cookie phiên, và là nơi duy nhất trả lời câu hỏi
 * "ai đang gọi?". Rải logic này ra nhiều chỗ là cách một trang bị quên mất
 * bước kiểm tra.
 *
 * Quan trọng: `proxy.ts` chỉ chuyển hướng dựa trên việc cookie CÓ TỒN TẠI hay
 * không — nó không xác minh gì cả. Ranh giới bảo mật thật nằm ở đây và ở
 * FastAPI: `requireAdmin()` hỏi máy chủ xem token này là ai, và mọi endpoint
 * `/admin/*` tự kiểm tra `is_admin` trên dòng dữ liệu sống một lần nữa.
 */

const ACCESS_COOKIE = "agrilog_access";
const REFRESH_COOKIE = "agrilog_refresh";

// Khớp ACCESS_TOKEN_EXPIRE_MINUTES / REFRESH_TOKEN_EXPIRE_DAYS của backend.
// Cookie sống lâu hơn token sẽ tạo ra một phiên "trông như đang đăng nhập"
// nhưng mọi thao tác đều 401.
const ACCESS_MAX_AGE = 60 * 60 * 24 * 7;
const REFRESH_MAX_AGE = 60 * 60 * 24 * 90;

export interface SessionUser {
  id: string;
  household_id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_admin: boolean;
}

interface TokenPair {
  access_token: string;
  refresh_token: string;
  user: SessionUser;
}

function cookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    // `secure` bật theo môi trường, không cứng nhắc: cookie `secure` không
    // được gửi qua http://localhost, nên bật cứng sẽ làm đăng nhập im lặng
    // không hoạt động khi phát triển.
    secure: process.env.COOKIE_SECURE === "1",
    // `lax` chứ không phải `none`: trình duyệt sẽ không đính cookie này vào
    // request POST xuất phát từ trang khác, nên một trang độc hại không thể
    // mượn phiên quản trị để gọi API thay người dùng (CSRF).
    sameSite: "lax" as const,
    path: "/",
    maxAge,
  };
}

export async function createSession(pair: TokenPair): Promise<void> {
  const store = await cookies();
  store.set(ACCESS_COOKIE, pair.access_token, cookieOptions(ACCESS_MAX_AGE));
  store.set(REFRESH_COOKIE, pair.refresh_token, cookieOptions(REFRESH_MAX_AGE));
}

export async function destroySession(): Promise<void> {
  const store = await cookies();
  store.delete(ACCESS_COOKIE);
  store.delete(REFRESH_COOKIE);
}

export async function getAccessToken(): Promise<string | undefined> {
  return (await cookies()).get(ACCESS_COOKIE)?.value;
}

export async function getRefreshToken(): Promise<string | undefined> {
  return (await cookies()).get(REFRESH_COOKIE)?.value;
}

/**
 * Người dùng hiện tại, hỏi thẳng máy chủ.
 *
 * Không nhân bản tên/quyền vào cookie: một bản sao như vậy sẽ tiếp tục nói
 * "quản trị viên" sau khi quyền đã bị thu hồi, cho tới lúc cookie hết hạn.
 *
 * `cache()` gộp mọi lời gọi trong CÙNG một request thành một round-trip, nên
 * layout và trang cùng hỏi "ai đang đăng nhập?" không thành hai lần gọi mạng.
 * Nó không cache xuyên request — mỗi lần tải trang vẫn hỏi lại từ đầu.
 */
export const getSessionUser = cache(async (): Promise<SessionUser | null> => {
  const token = await getAccessToken();
  if (!token) {
    return null;
  }
  try {
    return await apiFetch<SessionUser>("/api/v1/auth/me", { token });
  } catch (error) {
    // 401 (token hết hạn/không hợp lệ) và 403 (tài khoản đã bị khoá) đều dẫn
    // tới cùng một kết luận: không có phiên dùng được. Lỗi mạng cũng vậy —
    // không xác minh được thì coi như chưa đăng nhập, không đoán mò.
    if (error instanceof ApiError) {
      return null;
    }
    throw error;
  }
});

/**
 * Cổng cho mọi trang quản trị.
 *
 * Trả về người dùng, hoặc chuyển hướng. Gọi ở đầu mỗi trang trong nhóm
 * `(dashboard)` — kể cả khi layout đã gọi rồi, vì một trang tự bảo vệ mình thì
 * không phụ thuộc vào việc ai đó nhớ bọc nó trong đúng layout.
 */
export async function requireAdmin(): Promise<SessionUser> {
  const user = await getSessionUser();
  if (!user) {
    redirect("/login");
  }
  if (!user.is_admin) {
    redirect("/login?error=not-admin");
  }
  return user;
}
