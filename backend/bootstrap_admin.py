"""
backend/bootstrap_admin.py — Secure One-Time Main Admin Bootstrap CLI
Creates the initial Main Admin account strictly for the @iilm.edu domain.
"""

import sys
import os
import getpass
import argparse
from werkzeug.security import generate_password_hash
from flask import Flask, has_app_context

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models import db, User
from backend.database import DB_PATH

ALLOWED_DOMAIN = "@iilm.edu"


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app


def bootstrap_main_admin(email: str, full_name: str, password: str) -> bool:
    email = (email or "").strip().lower()
    full_name = (full_name or "").strip()

    if not email.endswith(ALLOWED_DOMAIN):
        print(f"[ERROR] Registration rejected: Email must end with '{ALLOWED_DOMAIN}'. Provided: {email}")
        return False

    if len(password) < 8:
        print("[ERROR] Password must be at least 8 characters long.")
        return False

    ctx = None
    if not has_app_context():
        app = create_app()
        ctx = app.app_context()
        ctx.push()

    try:
        # Ensure tables exist
        db.create_all()

        existing_main = User.query.filter_by(is_main_admin=True).first()
        if existing_main:
            print(f"[ABORT] Main Admin already exists ({existing_main.email}). No additional bootstrap permitted.")
            return False

        existing_user = User.query.filter_by(email=email).first()
        hashed_pwd = generate_password_hash(password, method="scrypt")

        if existing_user:
            existing_user.role = "MAIN_ADMIN"
            existing_user.is_main_admin = True
            existing_user.is_verified = True
            existing_user.status = "ACTIVE"
            existing_user.password_hash = hashed_pwd
            db.session.commit()
            print(f"[SUCCESS] Existing account '{email}' promoted to Main Admin.")
            return True

        new_admin = User(
            email=email,
            full_name=full_name or "System Main Administrator",
            password_hash=hashed_pwd,
            role="MAIN_ADMIN",
            is_main_admin=True,
            is_verified=True,
            status="ACTIVE"
        )
        db.session.add(new_admin)
        db.session.commit()
        print(f"[SUCCESS] Main Admin account '{email}' successfully created and verified.")
        return True
    finally:
        if ctx:
            ctx.pop()


def main():
    parser = argparse.ArgumentParser(description="Bootstrap initial OxySense Main Admin account.")
    parser.add_argument("--email", help="Institutional @iilm.edu admin email")
    parser.add_argument("--name", default="Main Administrator", help="Admin Full Name")
    parser.add_argument("--password", help="Admin Password")

    args = parser.parse_args()

    email = args.email or os.environ.get("BOOTSTRAP_ADMIN_EMAIL")
    name = args.name or os.environ.get("BOOTSTRAP_ADMIN_NAME", "Main Administrator")
    pwd = args.password or os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")

    if not email:
        email = input(f"Enter Main Admin Email ({ALLOWED_DOMAIN}): ").strip()
    if not pwd:
        pwd = getpass.getpass("Enter Main Admin Password (min 8 characters): ")

    success = bootstrap_main_admin(email, name, pwd)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
