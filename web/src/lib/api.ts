import "server-only";

/**
 * Máy khách gọi FastAPI — chỉ chạy phía máy chủ.
 *
 * `server-only` ở trên không phải trang trí: nó biến việc lỡ import file này
 * vào một Client Component thành lỗi biên dịch, chứ không phải một sự cố rò rỉ
 * token phát hiện được sau khi đã lên production.
 *
 * Trình duyệt KHÔNG BAO GIỜ gọi thẳng FastAPI. Mọi request đều đi qua máy chủ
 * Next.js, và điều đó mang lại ba thứ cùng lúc:
 *
 *   1. JWT nằm trong cookie `httpOnly`, JavaScript phía trình duyệt không đọc
 *      được — một lỗ hổng XSS không lấy được phiên quản trị.
 *   2. Không cần cấu hình CORS, vì gọi từ máy chủ sang máy chủ thì trình duyệt
 *      không tham gia.
 *   3. Địa chỉ FastAPI không lọt vào bundle của trình duyệt.
 */

const BASE_URL = process.env.API_BASE_URL;

if (!BASE_URL) {
  // Ném ngay khi nạp module, chứ không phải khi request đầu tiên tới. Thiếu
  // cấu hình mà chỉ lộ ra lúc người dùng bấm đăng nhập thì trông như lỗi đăng
  // nhập, không phải lỗi thiếu biến môi trường.
  throw new Error(
    "Thiếu API_BASE_URL. Sao chép web/.env.example thành web/.env.local.",
  );
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  /** Access token. Bỏ trống cho các endpoint công khai (login, maintenance). */
  token?: string;
  /** Tham số truy vấn; giá trị `undefined` được bỏ qua. */
  query?: Record<string, string | number | boolean | undefined>;
}

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, token, query } = options;

  const url = new URL(path, BASE_URL);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      // Dữ liệu quản trị phải luôn tươi. Một bảng danh sách người dùng lấy từ
      // cache sẽ hiện tài khoản vừa bị khoá là vẫn đang hoạt động — đúng câu
      // hỏi mà người quản trị vừa thao tác để trả lời.
      cache: "no-store",
    });
  } catch {
    // Status 0 nghĩa là request chưa từng tới được máy chủ — khác hẳn với việc
    // máy chủ trả lỗi, và người dùng cần biết là nên kiểm tra FastAPI có đang
    // chạy không chứ không phải kiểm tra dữ liệu vừa nhập.
    throw new ApiError(0, "Không kết nối được máy chủ AgriLog.");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  const payload: unknown = text ? JSON.parse(text) : undefined;

  if (!response.ok) {
    throw new ApiError(response.status, extractDetail(payload, response.status));
  }

  return payload as T;
}

/**
 * FastAPI trả `detail` là chuỗi cho lỗi nghiệp vụ, nhưng là MẢNG khi Pydantic
 * từ chối request. Ghép thẳng mảng đó vào giao diện sẽ ra "[object Object]".
 */
function extractDetail(payload: unknown, status: number): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail)) {
      const first = detail[0];
      if (first && typeof first === "object" && "msg" in first) {
        return String((first as { msg: unknown }).msg);
      }
    }
  }
  return `Máy chủ trả lỗi (${status}).`;
}
