from threading import Thread
from flask import (
    abort, redirect, session, request, flash, jsonify,
    url_for, current_app
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
    link = url_for('auth.confirm_email', token=token, _external=True)
    msg = Message(
        subject="Confirm your SmartEats account",
        sender=current_app.config['MAIL_USERNAME'],
        recipients=[email],
        body=f"Welcome! Confirm your email: {link}"
    )
    Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()

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
            socketio.emit('play_sound', {'sound': sound}, room=str(user_id))
    except Exception:
        pass

# --------------------------------------------------
# AJAX AUTH ROUTES
# --------------------------------------------------

# REGISTER CUSTOMER
@auth.route("/register", methods=["POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.Email.data).first():
            return jsonify({'status': 'error', 'message': 'Email already exists'}), 400

        hashed_password = bcrypt.generate_password_hash(form.Password.data).decode('utf-8')
        user = User(
            username=form.username.data,
            lastname=form.lastName.data,
            email=form.Email.data,
            password=hashed_password
        )

        db.session.add(user)
        try:
            db.session.commit()
            send_confirmation_email(user.email)
            return jsonify({'status': 'success', 'message': 'Registration successful. Check email to confirm.'})
        except IntegrityError:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': 'Registration failed. Try again.'}), 500

    return jsonify({'status': 'error', 'errors': form.errors}), 400

# REGISTER STORE
@auth.route("/registerstore", methods=["POST"])
def registerstore():
    form = PharmacyRegistrationForm()
    if form.validate_on_submit():
        if Store.query.filter_by(email=form.email.data).first():
            return jsonify({'status': 'error', 'message': 'Email already exists'}), 400

        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
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
            return jsonify({'status': 'success', 'message': 'Store registered. Check email to confirm.'})
        except IntegrityError:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': 'Registration failed.'}), 500

    return jsonify({'status': 'error', 'errors': form.errors}), 400

# LOGIN
@auth.route("/newlogin", methods=["POST"])
def newlogin():
    form = LoginForm()
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
                    return jsonify({'status': 'error', 'message': 'Please confirm your email first.'}), 403

                login_user(account)
                session["user_type"] = role
                session["email"] = account.email

                notify_customer(account.id)
                send_sound(account.id)

                redirect_url = {
                    "customer": url_for("main.home"),
                    "administrator": url_for("admin.admindash"),
                    "store": url_for("store.adminpage"),
                    "delivery_guy": url_for("delivery.dashboard")
                }.get(role, url_for("main.home"))

                if role == "administrator":
                    session["admin_id"] = account.id
                if role == "store":
                    session["store_id"] = account.id
                if role == "delivery_guy":
                    session["delivery_guy_id"] = account.id

                return jsonify({'status': 'success', 'redirect': redirect_url})

        return jsonify({'status': 'error', 'message': 'Invalid login credentials'}), 401

    return jsonify({'status': 'error', 'errors': form.errors}), 400

# RESEND EMAIL
@auth.route("/resend_email", methods=["POST"])
def resend_email():
    form = emailform()
    if form.validate_on_submit():
        email = form.email.data
        account = User.query.filter_by(email=email).first() or Store.query.filter_by(email=email).first()

        if not account:
            return jsonify({'status': 'error', 'message': 'Email not found'}), 404

        send_confirmation_email(email)
        return jsonify({'status': 'success', 'message': 'Confirmation email resent.'})

    return jsonify({'status': 'error', 'errors': form.errors}), 400

# RESET PASSWORD
@auth.route("/reset_password/<token>", methods=["POST"])
def reset(token):
    form = resetpassword()
    email = confirm_token(token)

    if not email:
        return jsonify({'status': 'error', 'message': 'Reset link invalid or expired.'}), 400

    if form.validate_on_submit():
        hashed = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
        account = User.query.filter_by(email=email).first() or Store.query.filter_by(email=email).first()
        if account:
            account.password = hashed
            db.session.commit()
            return jsonify({'status': 'success', 'message': 'Password reset successful.'})

    return jsonify({'status': 'error', 'errors': form.errors}), 400

# CONFIRM EMAIL
@auth.route("/confirm_email/<token>")
def confirm_email(token):
    email = confirm_token(token)
    if not email:
        flash("Confirmation link invalid or expired.", "danger")
        return redirect(url_for("auth.newlogin"))

    account = User.query.filter_by(email=email).first() or Store.query.filter_by(email=email).first()
    if account:
        account.confirmed = True
        db.session.commit()
        flash("Email confirmed. You can now log in.", "success")
    return redirect(url_for("auth.newlogin"))
