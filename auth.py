from functools import wraps

from flask import flash, redirect, session, url_for

from extensions import db
from models import User


def get_current_user():
    """Return the active database user associated with this session."""
    user_id = session.get("user_id")

    if not user_id:
        return None

    user = db.session.get(User, user_id)

    if user is None or not user.is_active:
        session.clear()
        return None

    return user


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()

        if user is None:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()

            if user is None:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))

            if user.role not in roles:
                flash("Access denied.", "danger")
                return redirect(url_for("index"))

            return f(*args, **kwargs)

        return decorated

    return decorator
