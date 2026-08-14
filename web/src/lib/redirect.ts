/**
 * Lọc tham số `?next=` trước khi dùng nó làm đích chuyển hướng.
 *
 * Không lọc thì trang đăng nhập trở thành bàn đạp chuyển hướng mở (open
 * redirect): kẻ xấu gửi một liên kết mang tên miền thật của hệ thống, người
 * dùng thấy quen nên bấm, đăng nhập xong thì bị đưa sang trang khác — thường
 * là một trang đăng nhập giả để thu mật khẩu.
 *
 * Cạm bẫy đáng nói: chỉ kiểm `startsWith("/")` là KHÔNG đủ. `//ke-xau.example`
 * bắt đầu bằng "/" nhưng trình duyệt hiểu đó là URL tuyệt đối theo giao thức
 * hiện tại và sẽ rời khỏi tên miền. Chuỗi `/\ke-xau.example` cũng vậy trên một
 * số trình duyệt.
 *
 * Dùng ở CẢ hai phía — máy chủ khi dựng trang và trình duyệt khi điều hướng —
 * nên không bên nào phải tin bên kia đã lọc hộ.
 */
export function safeNextPath(value: unknown): string | undefined {
  if (typeof value !== "string" || value.length === 0) {
    return undefined;
  }
  if (!value.startsWith("/")) {
    return undefined;
  }
  // "//host" và "/\host" đều đưa trình duyệt ra khỏi tên miền hiện tại.
  if (value.startsWith("//") || value.startsWith("/\\")) {
    return undefined;
  }
  return value;
}
