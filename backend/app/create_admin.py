"""Create the first administrator without placing a password in shell history.

Run from the repository root: python -m backend.app.create_admin
"""
import asyncio
import argparse
import getpass

from sqlalchemy import select

from backend.app.core.security import hash_password
from backend.app.database.session import AsyncSessionLocal
from backend.app.models.models import User


async def create_admin(role: str = "admin") -> None:
    username = input("Administrator username: ").strip()
    if not username or len(username) > 50:
        raise SystemExit("Username must contain 1 to 50 characters.")
    password = getpass.getpass("Administrator password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    hashed = hash_password(password)
    async with AsyncSessionLocal() as db:
        exists = await db.scalar(select(User.id).where(User.username == username))
        if exists:
            raise SystemExit("That username already exists; no account was changed.")
        db.add(User(username=username, email=f"{username}@local.invalid", hashed_password=hashed,
                    full_name=username, role=role, is_active=True))
        await db.commit()
    print("Administrator account created.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create an application account with a securely prompted password.")
    parser.add_argument("--role", choices=("admin", "operator", "analyst", "viewer"), default="admin")
    args = parser.parse_args()
    asyncio.run(create_admin(args.role))
