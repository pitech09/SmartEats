from threading import Thread

from flask import (
    session, flash, redirect,
    url_for, render_template, current_app
)
from flask_bcrypt import Bcrypt
from flask_login import login_user
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from sqlalchemy.exc import IntegrityError

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail as SGMail

from . import auth
from .. import db, socketio
from ..models import User, Store, DeliveryGuy, Staff, Administrater
from ..forms import (
    RegistrationForm, PharmacyRegistrationForm,
    LoginForm, emailform, resetpassword, Set_StoreForm
)
from application.notification import notify_customer

# --------------------------------------------------
# INIT
# --------------------------------------------------
bcrypt = Bcrypt()


# --------------------------------------------------
# SERIALIZER (SAFE)
# --------------------------------------------------
def get_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


# --------------------------------------------------
# SENDGRID HELPERS
# --------------------------------------------------
def send_async_email(app, message):
    with app.app_context():
        try:
            sg = SendGridAPIClient(app.config["SENDGRID_API_KEY"])
            response = sg.send(message)
            app.logger.info(f"SendGrid email sent | Status: {response.status_code}")
        except Exception as e:
            app.logger.error("SENDGRID EMAIL ERROR")
            app.logger.error(str(e))


def send_confirmation_email(email):
    serializer = get_serializer()
    token = serializer.dumps(email)
    link = url_for("auth.confirm_email", token=token, _external=True)

    message = SGMail(
        from_email=current_app.config["SENDGRID_FROM_EMAIL"],
        to_emails=email,
        subject="Confirm your SmartEats account",
        html_content=f"""
        <h2>Welcome to SmartEats 🎉</h2>
        <p>Please confirm your email:</p>
        <p><a href="{link}">Confirm my account</a></p>
        <br>
        <p>If you did not create this account, ignore this email.</p>
        """
    )

    Thread(
        target=send_async_email,
        args=(current_app._get_current_object(), message),
        daemon=True
    ).start()


def send_reset_email(email):
    serializer = get_serializer()
    token = serializer.dumps(email)
    link = url_for("auth.reset", token=token, _external=True)

    message = SGMail(
        from_email=current_app.config["SENDGRID_FROM_EMAIL"],
        to_emails=email,
        subject="Reset your SmartEats password",
        html_content=f"""
        <h3>Password Reset</h3>
        <p><a href="{link}">Reset Password</a></p>
        <br>
        <p>If you didn’t request this, ignore this email.</p>
        """
    )

    Thread(
        target=send_async_email,
        args=(current_app._get_current_object(), message),
        daemon=True
    ).start()


def confirm_token(token, expiration=86400):
    serializer = get_serializer()
    try:
        return serializer.loads(token, max_age=expiration)
    except (SignatureExpired, BadSignature):
        return None


# --------------------------------------------------
# SOCKET SOUND
# --------------------------------------------------
def send_sound(user_id, sound="login"):
    try:
        socketio.emit("play_sound", {"sound": sound}, room=str(user_id))
    except Exception:
        pass


# --------------------------------------------------
# REGISTER CUSTOMER
# --------------------------------------------------
@auth.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    formpharm = Set_StoreForm()

    if form.validate_on_submit():
        if User.query.filter_by(email=form.Email.data).first():
            flash("Email already exists", "danger")
            return redirect(url_for("auth.register"))

        user = User(
            username=form.username.data,
            lastname=form.lastName.data,
            email=form.Email.data,
            password=bcrypt.generate_password_hash(form.Password.data).decode("utf-8")
        )

        db.session.add(user)
        try:
            db.session.commit()
            send_confirmation_email(user.email)
            flash("Registration successful. Check your email to confirm.", "success")
            return redirect(url_for("auth.newlogin"))
        except IntegrityError:
            db.session.rollback()
            flash("Registration failed. Try again.", "danger")

    return render_template("auth/register.html", form=form, formpharm=formpharm)


# --------------------------------------------------
# REGISTER STORE
# --------------------------------------------------
@auth.route("/registerstore", methods=["GET", "POST"])
def registerstore():
    form = PharmacyRegistrationForm()
    formpharm = Set_StoreForm()

    if form.validate_on_submit():
        if Store.query.filter_by(email=form.email.data).first():
            flash("Email already exists", "danger")
            return redirect(url_for("auth.registerstore"))

        store = Store(
            name=form.pharmacy_name.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            openinghours=form.opening_hours_and_days.data,
            password=bcrypt.generate_password_hash(form.password.data).decode("utf-8"),
            confirmed=False
        )

        db.session.add(store)
        try:
            db.session.commit()
            send_confirmation_email(store.email)
            flash("Store registered. Check email to confirm.", "success")
            return redirect(url_for("auth.newlogin"))
        except IntegrityError:
            db.session.rollback()
            flash("Registration failed.", "danger")

    return render_template("auth/registerphar.html", form=form, formpharm=formpharm)


# --------------------------------------------------
# LOGIN
# --------------------------------------------------
@auth.route("/newlogin", methods=["GET", "POST"])
def newlogin():
    form = LoginForm()
    formpharm = Set_StoreForm()

    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        user_sets = [
            (User, "customer"),
            (Administrater, "administrator"),
            (Store, "store"),
            (DeliveryGuy, "delivery_guy"),
            (Staff, "store")
        ]

        for model, role in user_sets:
            account = model.query.filter_by(email=email).first()
            if account and bcrypt.check_password_hash(account.password, password):
                if hasattr(account, "confirmed") and not account.confirmed:
                    flash("Please confirm your email first.", "warning")
                    return redirect(url_for("auth.newlogin"))

                login_user(account)
                session["user_type"] = role
                session["email"] = account.email

                notify_customer(account.id)
                send_sound(account.id)

                if role == "customer":
                    return redirect(url_for("main.home"))
                elif role == "administrator":
                    session["admin_id"] = account.id
                    return redirect(url_for("admin.admindash"))
                elif role == "store":
                    session["store_id"] = account.id
                    return redirect(url_for("store.adminpage"))
                elif role == "delivery_guy":
                    session["delivery_guy_id"] = account.id
                    return redirect(url_for("delivery.dashboard"))

        flash("Invalid login credentials", "danger")

    return render_template("auth/newlogin.html", form=form, formpharm=formpharm)


# --------------------------------------------------
# CONFIRM EMAIL
# --------------------------------------------------
@auth.route("/confirm_email/<token>")
def confirm_email(token):
    email = confirm_token(token)
    if not email:
        flash("Confirmation link invalid or expired.", "danger")
        return redirect(url_for("auth.newlogin"))

    account = User.query.filter_by(email=email).first() or Store.query.filter_by(email=email).first()
    if not account:
        flash("Account not found.", "danger")
        return redirect(url_for("auth.register"))

    account.confirmed = True
    db.session.commit()
    flash("Email confirmed. You can now log in.", "success")
    return redirect(url_for("auth.newlogin"))


# --------------------------------------------------
# RESEND CONFIRMATION EMAIL
# --------------------------------------------------
@auth.route("/resend_email", methods=["GET", "POST"])
def resend_email():
    form = emailform()
    if form.validate_on_submit():
        email = form.email.data
        account = User.query.filter_by(email=email).first() or Store.query.filter_by(email=email).first()
        if not account:
            flash("Email not found.", "danger")
            return redirect(url_for("auth.resend_email"))

        send_confirmation_email(email)
        flash("Confirmation email resent.", "success")
        return redirect(url_for("auth.newlogin"))

    return render_template("auth/resend_email.html", form=form)


# --------------------------------------------------
# RESET PASSWORD
# --------------------------------------------------
@auth.route("/reset_password/<token>", methods=["GET", "POST"])
def reset(token):
    form = resetpassword()
    email = confirm_token(token)
    if not email:
        flash("Reset link invalid or expired.", "danger")
        return redirect(url_for("auth.newlogin"))

    if form.validate_on_submit():
        account = User.query.filter_by(email=email).first() or Store.query.filter_by(email=email).first()
        if account:
            account.password = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
            db.session.commit()
            flash("Password reset successful.", "success")
            return redirect(url_for("auth.newlogin"))

    return render_template("auth/newpassword.html", form=form)


# --------------------------------------------------
# UNCONFIRMED PAGE
# --------------------------------------------------
@auth.route("/unconfirmed")
def unconfirmed():
    return render_template("auth/email/unconfirmed.html")
