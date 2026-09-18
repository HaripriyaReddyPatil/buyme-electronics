from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from auth import login_required
from extensions import db
from models import (
    Alert,
    Category,
    Item,
    OutbidNotification,
    SupportQuestion,
    User,
)
from services import decode_alert_payload


auth_bp = Blueprint(
    "auth_routes",
    __name__,
)


@auth_bp.route(
    "/register",
    methods=["GET", "POST"],
)
def register():
    if request.method == "POST":
        username = request.form[
            "username"
        ].strip()

        email = request.form[
            "email"
        ].strip()

        password = request.form[
            "password"
        ]

        if User.query.filter_by(
            username=username
        ).first():
            flash(
                "Username already taken.",
                "danger",
            )

            return redirect(
                url_for(
                    "auth_routes.register"
                )
            )

        if User.query.filter_by(
            email=email
        ).first():
            flash(
                "Email already registered.",
                "danger",
            )

            return redirect(
                url_for(
                    "auth_routes.register"
                )
            )

        user = User(
            username=username,
            email=email,
            password=generate_password_hash(
                password,
                method="pbkdf2:sha256",
            ),
        )

        db.session.add(user)
        db.session.commit()

        flash(
            "Account created! Please log in.",
            "success",
        )

        return redirect(
            url_for(
                "auth_routes.login"
            )
        )

    return render_template(
        "register.html"
    )


@auth_bp.route(
    "/login",
    methods=["GET", "POST"],
)
def login():
    if request.method == "POST":
        username = request.form[
            "username"
        ].strip()

        password = request.form[
            "password"
        ]

        user = User.query.filter_by(
            username=username
        ).first()

        if (
            user
            and user.is_active
            and check_password_hash(
                user.password,
                password,
            )
        ):
            session.clear()
            session.permanent = True

            session["user_id"] = (
                user.user_id
            )

            session["username"] = (
                user.username
            )

            flash(
                f"Welcome back, {user.username}!",
                "success",
            )

            return redirect(
                url_for(
                    "public.index"
                )
            )

        flash(
            "Invalid credentials.",
            "danger",
        )

    return render_template(
        "login.html"
    )


@auth_bp.route("/logout")
def logout():
    session.clear()

    flash(
        "Logged out.",
        "info",
    )

    return redirect(
        url_for(
            "public.index"
        )
    )


@auth_bp.route("/profile")
@login_required
def profile():
    user = db.session.get(
        User,
        session["user_id"],
    )

    my_items = (
        Item.query
        .filter_by(
            seller_id=user.user_id
        )
        .order_by(
            Item.created_at.desc()
        )
        .all()
    )

    my_alerts = (
        Alert.query
        .filter_by(
            user_id=user.user_id
        )
        .all()
    )

    for alert in my_alerts:
        alert.attr_filters = (
            decode_alert_payload(
                alert.attr_filters
            )
        )

    my_notifications = (
        OutbidNotification.query
        .filter_by(
            user_id=user.user_id
        )
        .order_by(
            OutbidNotification.created_at.desc()
        )
        .limit(20)
        .all()
    )

    my_questions = (
        SupportQuestion.query
        .filter_by(
            user_id=user.user_id
        )
        .order_by(
            SupportQuestion.created_at.desc()
        )
        .all()
    )

    categories = (
        Category.query
        .filter_by(parent_id=None)
        .all()
    )

    return render_template(
        "profile.html",
        user=user,
        my_items=my_items,
        my_alerts=my_alerts,
        my_notifications=my_notifications,
        my_questions=my_questions,
        categories=categories,
    )


@auth_bp.route(
    "/toggle_anonymous",
    methods=["POST"],
)
@login_required
def toggle_anonymous():
    user = db.session.get(
        User,
        session["user_id"],
    )

    user.is_anonymous = (
        not user.is_anonymous
    )

    db.session.commit()

    state = (
        "enabled"
        if user.is_anonymous
        else "disabled"
    )

    flash(
        f"Anonymous bidding {state}.",
        "info",
    )

    return redirect(
        url_for(
            "auth_routes.profile"
        )
    )


@auth_bp.route(
    "/notifications/mark_read",
    methods=["POST"],
)
@login_required
def mark_notifications_read():
    (
        OutbidNotification.query
        .filter_by(
            user_id=session["user_id"],
            is_read=False,
        )
        .update(
            {
                "is_read": True
            }
        )
    )

    db.session.commit()

    return redirect(
        url_for(
            "auth_routes.profile"
        )
    )


@auth_bp.route("/support")
@login_required
def support():
    user = db.session.get(
        User,
        session["user_id"],
    )

    my_questions = (
        SupportQuestion.query
        .filter_by(
            user_id=user.user_id
        )
        .order_by(
            SupportQuestion.created_at.desc()
        )
        .all()
    )

    return render_template(
        "support.html",
        user=user,
        my_questions=my_questions,
    )


@auth_bp.route("/questions")
def questions():
    q = request.args.get(
        "q",
        "",
    ).strip()

    query = (
        SupportQuestion.query
        .filter_by(
            status="answered"
        )
    )

    if q:
        query = query.filter(
            SupportQuestion.subject.ilike(
                f"%{q}%"
            )
            | SupportQuestion.question.ilike(
                f"%{q}%"
            )
            | SupportQuestion.answer.ilike(
                f"%{q}%"
            )
        )

    questions = (
        query
        .order_by(
            SupportQuestion.answered_at.desc()
        )
        .all()
    )

    return render_template(
        "questions.html",
        questions=questions,
        q=q,
    )


@auth_bp.route(
    "/delete_account",
    methods=["POST"],
)
@login_required
def delete_account():
    user = db.session.get(
        User,
        session["user_id"],
    )

    user.is_active = False

    db.session.commit()
    session.clear()

    flash(
        "Account deactivated.",
        "info",
    )

    return redirect(
        url_for(
            "public.index"
        )
    )
