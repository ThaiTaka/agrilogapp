"""Grant or revoke the admin flag on an existing account.

    python -m scripts.make_admin nguoidung@example.com
    python -m scripts.make_admin nguoidung@example.com --revoke
    python -m scripts.make_admin --list

Deliberately a script and not an endpoint. Any route able to grant admin is a
route that can be tricked into granting it — through a mass-assignment bug, a
forgotten field in an update schema, or a stolen admin session escalating
itself further. Promotion therefore requires shell access to the server, which
is a boundary an HTTP request cannot cross.

Run from the `backend` directory with the virtualenv active.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models import Household, User


def _find(db: Session, email: str) -> User | None:
    # Matched case-insensitively, the same way the login path does: the unique
    # index is on lower(email), so 'Thai@x.vn' and 'thai@x.vn' are one account
    # and looking up by the exact string would miss it.
    return db.execute(
        select(User).where(func.lower(User.email) == email.strip().lower())
    ).scalar_one_or_none()


def list_admins(db: Session) -> int:
    rows = db.execute(
        select(User, Household.name)
        .join(Household, User.household_id == Household.id)
        .where(User.is_admin.is_(True))
        .order_by(User.created_at)
    ).all()

    if not rows:
        print("Chưa có tài khoản quản trị nào.")
        return 0

    print(f"{len(rows)} tài khoản quản trị:")
    for user, household in rows:
        state = "đang hoạt động" if user.is_active else "ĐÃ KHOÁ"
        print(f"  - {user.email:<40} {household:<28} {state}")
    return 0


def set_admin(db: Session, email: str, *, grant: bool) -> int:
    user = _find(db, email)
    if user is None:
        print(f"Không tìm thấy tài khoản: {email}", file=sys.stderr)
        return 1

    if user.is_admin == grant:
        print(f"{user.email} đã ở đúng trạng thái rồi (is_admin={grant}). Không đổi gì.")
        return 0

    if not grant:
        remaining = db.execute(
            select(func.count())
            .select_from(User)
            .where(User.is_admin.is_(True), User.id != user.id)
        ).scalar_one()
        if remaining == 0:
            print(
                "Từ chối: đây là tài khoản quản trị cuối cùng. "
                "Thu hồi xong sẽ không ai vào được trang quản trị nữa.",
                file=sys.stderr,
            )
            return 1

    user.is_admin = grant
    db.commit()
    print(f"{'Đã cấp quyền quản trị cho' if grant else 'Đã thu hồi quyền quản trị của'} {user.email}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Cấp/thu hồi quyền quản trị AgriLog")
    parser.add_argument("email", nargs="?", help="Email của tài khoản đã đăng ký")
    parser.add_argument("--revoke", action="store_true", help="Thu hồi thay vì cấp")
    parser.add_argument("--list", action="store_true", help="Liệt kê tài khoản quản trị")
    args = parser.parse_args()

    if not args.list and not args.email:
        parser.error("cần một email, hoặc --list")

    with Session(engine) as db:
        if args.list:
            return list_admins(db)
        return set_admin(db, args.email, grant=not args.revoke)


if __name__ == "__main__":
    raise SystemExit(main())
