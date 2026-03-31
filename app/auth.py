from __future__ import annotations

from functools import wraps
from http import HTTPStatus
from typing import Any, Callable
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    Flask,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue
from flask_login import (  # type: ignore[import-untyped]
    current_user,
    login_required,
    login_user,
    logout_user,
)
from sqlalchemy import select

from app.extensions import login_manager
from app.models import User
from app.services import (
    authenticate_user,
    create_user,
    latest_outbox_message,
    record_login,
    send_password_reset_email,
    update_user,
)

bp = Blueprint("auth", __name__, url_prefix="/auth")


def init_auth(app: Flask) -> None:
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "error"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str) -> object | None:
        from app.extensions import db

        return db.session.get(User, int(user_id))


@bp.route("/login", methods=["GET", "POST"])
def login() -> ResponseReturnValue:
    if current_user.is_authenticated:
        return redirect(_post_login_redirect())

    next_url = request.args.get("next", type=str)
    if request.method == "POST":
        identity = request.form.get("identity", "", type=str)
        password = request.form.get("password", "", type=str)
        user = authenticate_user(identity=identity, password=password)
        if user is None:
            flash("Login failed. Check your username/email and password.", "error")
        else:
            login_user(user)
            record_login(user)
            flash(f"Welcome back, {user.display_name}.", "success")
            return redirect(_safe_next_url(request.form.get("next")) or _post_login_redirect(user))

    return render_template(
        "auth/login.html",
        next_url=_safe_next_url(next_url),
        signup_enabled=current_app.config["AUTH_SIGNUP_ENABLED"],
    )


@bp.post("/logout")
@login_required
def logout() -> ResponseReturnValue:
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/signup", methods=["GET", "POST"])
def signup() -> ResponseReturnValue:
    if not current_app.config["AUTH_SIGNUP_ENABLED"]:
        abort(HTTPStatus.NOT_FOUND)
    if current_user.is_authenticated:
        return redirect(_post_login_redirect())

    if request.method == "POST":
        password = request.form.get("password", "", type=str)
        password_confirm = request.form.get("password_confirm", "", type=str)
        if password != password_confirm:
            flash("Password confirmation did not match.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            try:
                user = create_user(
                    username=request.form.get("username", "", type=str),
                    email=request.form.get("email", "", type=str),
                    password=password,
                    firstname=request.form.get("firstname", type=str),
                    lastname=request.form.get("lastname", type=str),
                )
            except ValueError as exc:
                flash(str(exc), "error")
            else:
                login_user(user)
                record_login(user)
                if user.site_admin:
                    flash(
                        "Account created. You are the first user, so site admin access is enabled.",
                        "success",
                    )
                else:
                    flash("Account created.", "success")
                return redirect(_post_login_redirect(user))

    return render_template("auth/signup.html")


@bp.route("/password-reset", methods=["GET", "POST"])
def password_reset_request() -> ResponseReturnValue:
    reset_url: str | None = None
    email_message: dict[str, str] | None = None
    if request.method == "POST":
        email = request.form.get("email", "", type=str).strip().lower()
        user = _find_user_by_email(email)
        if user is not None and user.active:
            token = user.get_reset_password_token()
            reset_url = url_for("auth.password_reset", token=token, _external=True)
            email_message = send_password_reset_email(user=user, reset_url=reset_url)
        flash(
            "If an active account matches that email, a password reset message has been prepared.",
            "success",
        )

    preview_url = reset_url if current_app.config["AUTH_SHOW_RESET_LINKS"] else None
    return render_template(
        "auth/password_reset_request.html",
        reset_url=preview_url,
        email_message=email_message or latest_outbox_message(),
    )


@bp.route("/password-reset/<token>", methods=["GET", "POST"])
def password_reset(token: str) -> ResponseReturnValue:
    user = User.verify_reset_password_token(
        token,
        max_age=current_app.config["RESET_PASSWORD_TOKEN_MAX_AGE"],
    )
    if user is None:
        flash("That password reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.password_reset_request"))

    if request.method == "POST":
        password = request.form.get("password", "", type=str)
        password_confirm = request.form.get("password_confirm", "", type=str)
        if password != password_confirm:
            flash("Password confirmation did not match.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            update_user(
                user,
                username=user.username,
                email=user.email,
                password=password,
                firstname=user.firstname,
                lastname=user.lastname,
                account_type=user.account_type,
                preference_tags=user.preference_tags,
                tags=user.tags,
                home_town=user.home_town,
                home_state=user.home_state,
                home_country=user.home_country,
                home_gym=user.home_gym,
                home_latlng=user.home_latlng,
                geoll=user.geoll,
                active=user.active,
                site_admin=user.site_admin,
            )
            flash("Password updated. Please log in with your new password.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/password_reset.html", token=token, user=user)


@bp.get("/account")
@login_required
def account() -> ResponseReturnValue:
    return render_template("auth/account.html")


@bp.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit() -> ResponseReturnValue:
    if request.method == "POST":
        password = request.form.get("password", "", type=str).strip()
        password_confirm = request.form.get("password_confirm", "", type=str).strip()
        if password and password != password_confirm:
            flash("Password confirmation did not match.", "error")
        elif password and len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            try:
                update_user(
                    current_user,
                    username=request.form.get("username", "", type=str),
                    email=request.form.get("email", "", type=str),
                    password=password or None,
                    firstname=request.form.get("firstname", type=str),
                    lastname=request.form.get("lastname", type=str),
                    account_type=current_user.account_type,
                    preference_tags=_csv_list_value(
                        request.form.get("preference_tags", "", type=str)
                    ),
                    tags=_csv_list_value(request.form.get("tags", "", type=str)),
                    home_town=request.form.get("home_town", type=str),
                    home_state=request.form.get("home_state", type=str),
                    home_country=request.form.get("home_country", type=str),
                    home_gym=request.form.get("home_gym", type=str),
                    home_latlng=request.form.get("home_latlng", type=str),
                    geoll=request.form.get("geoll", type=str),
                    active=current_user.active,
                    site_admin=current_user.site_admin,
                )
            except ValueError as exc:
                flash(str(exc), "error")
            else:
                flash("Account saved.", "success")
                return redirect(url_for("auth.account"))

    return render_template("auth/account_edit.html")


def site_admin_required(view: Callable[..., Any]) -> Callable[..., ResponseReturnValue]:
    @wraps(view)
    def wrapped_view(*args: Any, **kwargs: Any) -> ResponseReturnValue:
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not getattr(current_user, "active", False):
            logout_user()
            flash("Your account is inactive.", "error")
            return redirect(url_for("auth.login"))
        if not getattr(current_user, "site_admin", False):
            abort(HTTPStatus.FORBIDDEN)
        return view(*args, **kwargs)

    return wrapped_view


def _safe_next_url(next_url: str | None) -> str | None:
    if not next_url:
        return None
    parts = urlsplit(next_url)
    if parts.scheme or parts.netloc or not next_url.startswith("/"):
        return None
    return next_url


def _post_login_redirect(user: User | None = None) -> str:
    effective_user = user or current_user
    if getattr(effective_user, "site_admin", False):
        return url_for("core.admin_dashboard_route")
    return url_for("auth.account")


def _find_user_by_email(email: str) -> User | None:
    from app.extensions import db

    return db.session.scalar(select(User).where(User.email == email).limit(1))


def _csv_list_value(raw_value: str) -> list[str] | None:
    values = [item.strip() for item in raw_value.split(",")]
    filtered = [item for item in values if item]
    return filtered or None
