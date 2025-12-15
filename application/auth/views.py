from threading import Thread
from flask import (
    session, request, flash, redirect,
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

bcrypt = Bcrypt()
mail = Mail()

serializer = URLSafeTimedSerializer('ad40898f84d46bd1d109970e23c0360e')

# --------------------------------------------------
# EMAIL HELPERS
# --------------------------------------------------

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
            current_app.logger.info(f"Email sent to {msg.recipients}")
        except Exception:
            import traceback
            current_app.logger.error("EMAIL ERROR:")
            current_app.logger.error(traceback.format_exc())


def send_confirmation_email(email):
    token = serializer.dumps(email)
    print("Generated token:", token)
    link = url_for('auth.confirm_email', token=token, _external=True)

    msg = Message(
        subject="Confirm your SmartEats account",
        sender=current_app.config['MAIL_USERNAME'],
        recipients=[email],
        body=f"""
Welcome to SmartEats 🎉

Please confirm your email by clicking the link below:
{link}

If you did not create this account, ignore this email.

SmartEats Team
"""
    )

    Thread(
        target=send_async_email,
        args=(current_app._get_current_object(), msg)
    ).start()
    print(f"Confirmation email sent to {email}")

def confirm_token(token, expiration=86400):
    try:
        return serializer.loads(token, max_age=expiration)
    except (SignatureExpired, BadSignature):
        return None

# --------------------------------------------------
# SOCKET SOUND
# --------------------------------------------------

def send_sound(user_id, sound="login"):
    try:
        if socketio:
            socketio.emit(
                'play_sound',
                {'sound': sound},
                room=str(user_id)
            )
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
            return redirect(url_for('auth.register'))

        hashed_password = bcrypt.generate_password_hash(
            form.Password.data
        ).decode('utf-8')

        user = User(
            username=form.username.data,
            lastname=form.lastName.data,
            email=form.Email.data,
            password=hashed_password
        )
        print("Created user:", user.email)

        db.session.add(user)
        try:
            print("Attempting to commit user to database.")
            db.session.commit()
            send_confirmation_email(user.email)
            flash("Registration successful. Check your email to confirm.", "success")
            return redirect(url_for('auth.newlogin'))
        except IntegrityError:
            db.session.rollback()
            flash("Registration failed. Try again.", "danger")

    return render_template(
        "auth/register.html",
        form=form,
        formpharm=formpharm
    )

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
            return redirect(url_for('auth.registerstore'))

        hashed_password = bcrypt.generate_password_hash(
            form.password.data
        ).decode('utf-8')

        store = Store(
            name=form.pharmacy_name.data,
            password=hashed_password,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            openinghours=form.opening_hours_and_days.data
        )

        db.session.add(store)
        try:
            db.session.commit()
            send_confirmation_email(store.email)
            flash("Store registered. Check email to confirm.", "success")
            return redirect(url_for('auth.newlogin'))
        except IntegrityError:
            db.session.rollback()
            flash("Registration failed.", "danger")

    return render_template(
        "auth/registerphar.html",
        form=form,
        formpharm=formpharm
    )

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
                if role == "administrator":
                    session["admin_id"] = account.id
                    return redirect(url_for("admin.admindash"))
                if role == "store":
                    session["store_id"] = account.id
                    return redirect(url_for("store.adminpage"))
                if role == "delivery_guy":
                    session["delivery_guy_id"] = account.id
                    return redirect(url_for("delivery.dashboard"))

        flash("Invalid login credentials", "danger")

    return render_template(
        "auth/newlogin.html",
        form=form,
        formpharm=formpharm
    )

# --------------------------------------------------
# CONFIRM EMAIL
# --------------------------------------------------

@auth.route("/confirm_email/<token>")
def confirm_email(token):
    email = confirm_token(token)

    if not email:
        flash("Confirmation link invalid or expired.", "danger")
        return redirect(url_for("auth.newlogin"))

    user = User.query.filter_by(email=email).first()
    store = Store.query.filter_by(email=email).first()

    target = user or store

    if not target:
        flash("Account not found.", "danger")
        return redirect(url_for("auth.register"))

    target.confirmed = True
    db.session.commit()

    flash("Email confirmed. You can now log in.", "success")
    return redirect(url_for("auth.newlogin"))

# --------------------------------------------------
# RESEND EMAIL
# --------------------------------------------------

@auth.route("/resend_email", methods=["GET", "POST"])
def resend_email():
    form = emailform()

    if form.validate_on_submit():
        email = form.email.data

        account = (
            User.query.filter_by(email=email).first()
            or Store.query.filter_by(email=email).first()
        )

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
        hashed = bcrypt.generate_password_hash(
            form.password.data
        ).decode("utf-8")

        account = (
            User.query.filter_by(email=email).first()
            or Store.query.filter_by(email=email).first()
        )

        if account:
            account.password = hashed
            db.session.commit()
            flash("Password reset successful.", "success")
            return redirect(url_for("auth.newlogin"))

    return render_template("auth/newpassword.html", form=form)

# --------------------------------------------------
# UNCONFIRMED
# --------------------------------------------------

@auth.route("/unconfirmed")
def unconfirmed():
    return render_template("auth/email/unconfirmed.html")
