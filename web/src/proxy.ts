import { NextResponse, type NextRequest } from "next/server";

/**
 * Chuyển hướng lạc quan (optimistic redirect).
 *
 * Trong Next.js 16, Middleware được đổi tên thành Proxy và phải nằm ở
 * `src/proxy.ts`. Một file `middleware.ts` viết theo thói quen cũ sẽ **không
 * chạy và cũng không báo lỗi** — nó chỉ im lặng không bảo vệ gì cả.
 *
 * File này KHÔNG PHẢI ranh giới bảo mật. Nó chỉ nhìn xem cookie phiên có tồn
 * tại hay không, và cố tình không xác minh chữ ký: Proxy chạy trên mọi request
 * kể cả các route được prefetch, nên đặt kiểm tra thật ở đây vừa chậm vừa tạo
 * cảm giác an toàn sai chỗ.
 *
 * Việc kiểm tra thật nằm ở hai lớp phía sau, và cả hai đều bắt buộc:
 *   1. `requireAdmin()` trong lib/session.ts — hỏi FastAPI xem token này là ai.
 *   2. `get_current_admin` ở FastAPI — đọc `is_admin` trên dòng dữ liệu sống,
 *      trên từng request.
 *
 * Một cookie giả sẽ qua được file này, rồi bị chặn ở cả hai lớp trên.
 */

const ACCESS_COOKIE = "agrilog_access";

export function proxy(request: NextRequest): NextResponse {
  const hasSession = request.cookies.has(ACCESS_COOKIE);
  const { pathname, search } = request.nextUrl;
  const isLoginPage = pathname === "/login";

  if (!hasSession && !isLoginPage) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    // Ghi nhớ nơi người dùng định tới, để sau khi đăng nhập quay lại đúng chỗ
    // thay vì luôn rơi về trang chủ.
    if (pathname !== "/") {
      url.searchParams.set("next", pathname + search);
    }
    return NextResponse.redirect(url);
  }

  if (hasSession && isLoginPage) {
    const url = request.nextUrl.clone();
    url.pathname = "/";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  // Bỏ qua chính các route đăng nhập/đăng xuất (nếu không, request đăng nhập
  // khi chưa có cookie sẽ bị chuyển hướng và không bao giờ tới được handler),
  // cùng với tài nguyên tĩnh.
  matcher: ["/((?!api/auth|_next/static|_next/image|favicon.ico|.*\\.svg$).*)"],
};
