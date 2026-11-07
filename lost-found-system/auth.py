from functools import wraps
import re
from flask import session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from db import users
from datetime import datetime

SUPPORTED_LANGUAGE_CODES = {"en", "fr", "sw", "rw", "es", "de", "zh", "ja"}

# Register a new user
def register_user(username, email, password, role="student", student_id=None):
    username = (username or "").strip()
    email = (email or "").strip().lower()
    student_id = (student_id or "").strip() or None
    if not username or not email or not password:
        return False, "Name, email, and password are required."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."

    # Check if user already exists
    if users.find_one({
        "$or": [
            {"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}},
            {"username": username},
        ],
    }):
        return False, "Email or Username already exists."
    
    if student_id and users.find_one({"student_id": student_id}):
        return False, "Student ID already registered."

    # Create user document
    user_data = {
        "username": username,
        "email": email,
        "password": generate_password_hash(password), # Hash password for security
        "role": role,
        "language": "en",
        "created_at": datetime.utcnow()
    }
    if student_id:
        user_data["student_id"] = student_id
    users.insert_one(user_data)
    return True, "Registration successful."

# Log in a user
def login_user(email, password):
    if not email or not password:
        return False, "Email and password are required."
    email = email.strip()
    user = users.find_one({"email": email})
    if not user:
        user = users.find_one({
            "email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}
        })
    if user and check_password_hash(user["password"], password):
        # Save user info in session
        session["user_id"] = str(user["_id"])
        session["role"] = user["role"]
        session["username"] = user["username"]
        language = user.get("language", "en")
        session["language"] = language if language in SUPPORTED_LANGUAGE_CODES else "en"
        return True, "Login successful."
    return False, "Invalid email or password."


def change_user_password(user, current_password, new_password):
    if not current_password or not check_password_hash(user["password"], current_password):
        return False, "Your current password is incorrect."
    if len(new_password or "") < 8:
        return False, "Password must be at least 8 characters."

    users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {"password": generate_password_hash(new_password)},
            "$unset": {"password_reset_hash": ""},
        },
    )
    return True, "Password updated successfully."

# Log out
def logout_user():
    session.clear()

# Decorators to protect routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Administrator access required.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function