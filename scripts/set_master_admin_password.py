import getpass
import sys

from dotenv import load_dotenv

from services.admin_auth_service import set_master_admin_password


def main():
    load_dotenv(".env")

    username = (input("Admin username [chainkasera]: ").strip() or "chainkasera").lower()
    password = getpass.getpass("New password: ")
    confirm = getpass.getpass("Confirm password: ")

    if len(password) < 8:
        print("Password must be at least 8 characters.")
        return 1
    if password != confirm:
        print("Passwords do not match.")
        return 1

    ok, message = set_master_admin_password(username, password)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
