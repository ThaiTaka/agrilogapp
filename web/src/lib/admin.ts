import "server-only";

import { apiFetch } from "./api";
import { getAccessToken } from "./session";

/**
 * Tầng truy cập dữ liệu quản trị.
 *
 * Mọi lời gọi tới `/api/v1/admin/*` đi qua đây, nên chỉ có một chỗ biết cách
 * lấy token và một chỗ định nghĩa hình dạng dữ liệu. Các kiểu dưới đây phải
 * khớp `backend/app/schemas/admin.py`.
 */

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface AdminOverview {
  total_households: number;
  total_users: number;
  active_users: number;
  locked_users: number;
  total_seasons: number;
  total_diary_entries: number;
  diary_entries_last_7_days: number;
  new_users_last_30_days: number;
  maintenance_enabled: boolean;
}

export interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_admin: boolean;
  household_id: string;
  household_name: string;
  created_at: string;
}

export interface AdminHousehold {
  id: string;
  name: string;
  phone: string | null;
  province: string | null;
  commune: string | null;
  user_count: number;
  created_at: string;
}

/**
 * Token cho một request quản trị.
 *
 * Ném khi không có, thay vì gọi API mà không kèm token rồi nhận 401 mơ hồ:
 * "chưa đăng nhập" và "máy chủ từ chối" là hai chuyện khác nhau, và lẫn lộn
 * chúng làm việc dò lỗi khó hơn hẳn.
 */
async function requireToken(): Promise<string> {
  const token = await getAccessToken();
  if (!token) {
    throw new Error("Không có phiên đăng nhập.");
  }
  return token;
}

export async function fetchOverview(): Promise<AdminOverview> {
  return apiFetch<AdminOverview>("/api/v1/admin/overview", {
    token: await requireToken(),
  });
}

export interface UserQuery {
  search?: string;
  is_active?: boolean;
  limit?: number;
  offset?: number;
}

export async function fetchUsers(query: UserQuery = {}): Promise<Page<AdminUser>> {
  return apiFetch<Page<AdminUser>>("/api/v1/admin/users", {
    token: await requireToken(),
    query: {
      search: query.search,
      is_active: query.is_active,
      limit: query.limit ?? 20,
      offset: query.offset ?? 0,
    },
  });
}

export async function fetchHouseholds(
  query: {search?: string; limit?: number; offset?: number} = {},
): Promise<Page<AdminHousehold>> {
  return apiFetch<Page<AdminHousehold>>("/api/v1/admin/households", {
    token: await requireToken(),
    query: {
      search: query.search,
      limit: query.limit ?? 20,
      offset: query.offset ?? 0,
    },
  });
}

export async function updateUserActive(
  userId: string,
  isActive: boolean,
): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/api/v1/admin/users/${userId}`, {
    method: "PATCH",
    token: await requireToken(),
    body: { is_active: isActive },
  });
}
