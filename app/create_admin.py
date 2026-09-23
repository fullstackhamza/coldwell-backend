"""
Promotes an already-registered user to admin. There's no API endpoint for
this on purpose — it's a deliberate, manual step you run yourself.

Usage: sign up normally through the site first, then run:

    python -m app.create_admin someone@example.com
"""

import sys

from .database import get_db


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m app.create_admin <email>")
        sys.exit(1)

    email = sys.argv[1].strip().lower()
    db = get_db()
    result = db.users.update_one({"email": email}, {"$set": {"role": "admin"}})

    if result.matched_count == 0:
        print(f"No account found for {email}. Sign up on the site first, then re-run this.")
        sys.exit(1)

    print(f"{email} is now an admin.")


if __name__ == "__main__":
    main()
