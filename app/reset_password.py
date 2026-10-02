"""
Resets a user's password directly in the database, for when someone
(including you) is locked out and there's no "forgot password" flow yet.
There's no API endpoint for this on purpose — it's a deliberate, manual
step you run yourself.

Usage:

    python -m app.reset_password someone@example.com "new-password-here"
"""

import sys

from .auth_utils import hash_password
from .database import get_db


def main():
    if len(sys.argv) != 3:
        print('Usage: python -m app.reset_password <email> "<new-password>"')
        sys.exit(1)

    email = sys.argv[1].strip().lower()
    new_password = sys.argv[2]

    if len(new_password) < 8:
        print("Password must be at least 8 characters.")
        sys.exit(1)

    db = get_db()
    result = db.users.update_one(
        {"email": email}, {"$set": {"password_hash": hash_password(new_password)}}
    )

    if result.matched_count == 0:
        print(f"No account found for {email}.")
        sys.exit(1)

    print(f"Password for {email} has been reset.")


if __name__ == "__main__":
    main()
