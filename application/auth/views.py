from threading import Thread
import time

from flask import (
    abort, session, request, flash, redirect,
    url_for, render_template, current_app
)
from flask_bcrypt import Bcrypt
from flask_login import login_user
from flask_mail import Message, Mail
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from sqlalchemy.exc import IntegrityError

from . import auth
from .. import db, socketio
from ..models import User, Store, DeliveryGuy, Staff, Administrater
from ..forms import (
    RegistrationForm, PharmacyRegistrationForm,
    LoginForm, emailform, resetpassword, Set_StoreForm
)
from application.notification import notify_customer

# --------------------------------------------------
# EXTENSIONS
# --------------------------------------------------

bcrypt = Bcrypt()
mail = Mail()

serializer = URLSafeTimedSerializer(
    "ad40898f84d46bd1d109970e23c0360e"
)

# --------------------------------------------------
# UTILITIES
# --------------------------------------------------

def find_account_by_email(email):
    """Fast short-circuit lookup"""
    return (
        User.query.filter_by(email=email).first()
        or Store.query.filter_by(email=email).first()
        or Administrater.query.filter_by(email=email).first()
        or DeliveryGuy.query.filter_by(email=email).first()
        or Staff.query.filter_by(email=email).first()
    )


def async_task(func, *args):
    Thread(target=func, args=args, daemon=True).start()


# --------------------------------------------------
# EMAIL
# --------------------------------------------------

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception:
            import traceback
            current_app.logger.error("EMAIL ERROR")
            current_app.logger.error(traceback.format_exc())


def send_confirmation_email(email):
    token = serializer.dumps(email)
    link = url_for("auth.confirm_email", token=token, _external=True)

    msg = Message(
        subject="Confirm your SmartEats account",
        sender=current_app.config.get("MAIL_DEFAULT_SENDER"),
        recipients=[email],
        body=f"""
Welcome to SmartEats 🎉

Confirm your email by clicking the link below:
{link}

If you did not create this account, ignore this email.

SmartEats Team
"""
    )

    async_task(
        send_async_email,
        current_app._get_current_object(),
        msg
    )


def confirm_token(token, expiration=86400):
    try:
        return serializer.loads(token, max_age=expiration)
    except (SignatureExpired, BadSignature):
        return None


# --------------------------------------------------
# SOCKET SOUND (NON-BLOCKING)
# --------------------------------------------------

def send_sound(user_id, sound="login"):
    try:
        socketio.emit(
            "play_sound",
            {"sound": sound},
            room=str(user_id)
        )
    except Exception:
        pass


# --------------------------------------------------
# PARTIAL LOADER
# --------------------------------------------------

@auth.route("/auth/partial/<name>")
def auth_partial(name):
    allowed = {
        "login": "auth/partials/login.html",
        "register": "auth/partials/register.html",
        "registerstore": "auth/partials/registerstore.html",
        "reset": "auth/partials/reset.html",
    }

    template = allowed.get(name)
    if not template:
        abort(404)

    return render_template(template)


# --------------------------------------------------
# REGISTER USER
# --------------------------------------------------

@auth.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()

    if form.validate_on_submit():

        if User.query.filter_by(email=form.Email.data).first():
            flash("Email already exists", "danger")
            return redirect(url_for("auth.register"))

        hashed = bcrypt.generate_password_hash(
            form.Password.data
        ).decode("utf-8")

        user = User(
            username=form.username.data,
            lastname=form.lastName.data,
            email=form.Email.data,
            password=hashed,
            confirmed=False
        )

        db.session.add(user)

        try:
            db.session.commit()
            async_task(send_confirmation_email, user.email)
            flash("Registration successful. Check your email.", "success")
            return redirect(url_for("auth.newlogin"))
        except IntegrityError:
            db.session.rollback()
            flash("Registration failed.", "danger")

    return render_template("auth/partials/register.html", form=form)


# --------------------------------------------------
# REGISTER STORE
# --------------------------------------------------

@auth.route("/registerstore", methods=["GET", "POST"])
def registerstore():
    form = PharmacyRegistrationForm()

    if form.validate_on_submit():

        if Store.query.filter_by(email=form.email.data).first():
            flash("Email already exists", "danger")
            return redirect(url_for("auth.registerstore"))

        hashed = bcrypt.generate_password_hash(
            form.password.data
        ).decode("utf-8")

        store = Store(
            name=form.pharmacy_name.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            openinghours=form.opening_hours_and_days.data,
            password=hashed,
            confirmed=False
        )

        db.session.add(store)

        try:
            db.session.commit()
            async_task(send_confirmation_email, store.email)
            flash("Store registered. Check email.", "success")
            return redirect(url_for("auth.newlogin"))
        except IntegrityError:
            db.session.rollback()
            flash("Registration failed.", "danger")

    return render_template("auth/partials/registerstore.html", form=form)


# --------------------------------------------------
# LOGIN (FAST PATH)
# --------------------------------------------------

@auth.route("/newlogin", methods=["GET", "POST"])
def newlogin():
    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        account = find_account_by_email(email)

        if not account:
            flash("Invalid credentials", "danger")
            return redirect(url_for("auth.newlogin"))

        if not bcrypt.check_password_hash(account.password, password):
            flash("Invalid credentials", "danger")
            return redirect(url_for("auth.newlogin"))

        if hasattr(account, "confirmed") and not account.confirmed:
            flash("Please confirm your email first.", "warning")
            return redirect(url_for("auth.newlogin"))

        login_user(account)
        session["email"] = account.email

        async_task(notify_customer, account.id)
        async_task(send_sound, account.id)

        return redirect(url_for("main.home"))

    return render_template("auth/partials/login.html", form=form)


# --------------------------------------------------
# CONFIRM EMAIL
# --------------------------------------------------

@auth.route("/confirm_email/<token>")
def confirm_email(token):
    email = confirm_token(token)

    if not email:
        flash("Link expired or invalid.", "danger")
        return redirect(url_for("auth.newlogin"))

    account = find_account_by_email(email)

    if not account:
        flash("Account not found.", "danger")
        return redirect(url_for("auth.register"))

    account.confirmed = True
    db.session.commit()

    flash("Email confirmed. You can log in.", "success")
    return redirect(url_for("auth.newlogin"))


# --------------------------------------------------
# RESEND EMAIL
# --------------------------------------------------

@auth.route("/resend_email", methods=["GET", "POST"])
def resend_email():
    form = emailform()

    if form.validate_on_submit():
        account = find_account_by_email(form.email.data)

        if not account:
            flash("Email not found.", "danger")
            return redirect(url_for("auth.resend_email"))

        async_task(send_confirmation_email, account.email)
        flash("Confirmation email resent.", "success")
        return redirect(url_for("auth.newlogin"))

    return render_template("auth/partials/resend_email.html", form=form)


# --------------------------------------------------
# RESET PASSWORD
# --------------------------------------------------

@auth.route("/reset_password/<token>", methods=["GET", "POST"])
def reset(token):
    form = resetpassword()
    email = confirm_token(token)

    if not email:
        flash("Invalid or expired reset link.", "danger")
        return redirect(url_for("auth.newlogin"))

    if form.validate_on_submit():
        account = find_account_by_email(email)

        if not account:
            flash("Account not found.", "danger")
            return redirect(url_for("auth.newlogin"))

        account.password = bcrypt.generate_password_hash(
            form.password.data
        ).decode("utf-8")

        db.session.commit()
        flash("Password reset successful.", "success")
        return redirect(url_for("auth.newlogin"))

    return render_template("auth/newpassword.html", form=form)
