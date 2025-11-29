from threading import Thread
from flask import (
    session, request, flash, redirect, url_for, render_template, current_app
)
from application.notification import *
from flask_bcrypt import Bcrypt
from flask_login import login_user, current_user
from flask_mail import Message, Mail
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import InternalServerError
from . import auth
from .. import db, login_manager, socketio  # added socketio import
from ..forms import (
    RegistrationForm, PharmacyRegistrationForm, LoginForm,
    emailform, resetpassword, Set_StoreForm
)
from ..models import User, Store, DeliveryGuy, Staff, Administrater

bcrypt = Bcrypt()
mail = Mail()
s = URLSafeTimedSerializer('ad40898f84d46bd1d109970e23c0360e')


# ------------------- UTILS -------------------

def send_async_email(app, msg):
    """Send email asynchronously."""
    with app.app_context():
        try:
            mail.send(msg)
            current_app.logger.info(f"Email sent to {msg.recipients}")
        except Exception as e:
            current_app.logger.error(f"Failed to send email: {e}")


def send_confirmation_email(form, is_store=False):
    """Prepare and send confirmation email asynchronously."""
    recipient = form.email.data if is_store else form.Email.data
    username = getattr(form, 'username', None)
    token = s.dumps(recipient)
    link = url_for('auth.confirm_email', token=token, _external=True)

    msg = Message(
        subject="Confirm your SmartEats account",
        sender='pitechcorp7@gmail.com',
        recipients=[recipient]
    )

    if is_store:
        msg.body = (
            f"Hello,\n\n"
            f"Thank you for registering your store with SmartEats.\n"
            f"Confirm your email: {link}\n\n"
            "If you did not register, ignore this email.\n\n"
            "SmartEats Team"
        )
    else:
        msg.body = (
            f"Hi {username.data if username else ''},\n\n"
            f"Please confirm your email to complete registration:\n{link}\n\n"
            "SmartEats Team"
        )

    Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()
    flash("A confirmation email has been sent. Please check your inbox.", "success")
    return token


def adduser(form):
    hashed_password = bcrypt.generate_password_hash(form.Password.data).decode('utf-8')
    return User(
        username=form.username.data,
        lastname=form.lastName.data,
        email=form.Email.data,
        password=hashed_password
    )


def addpharma(form):
    hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
    return Store(
        name=form.pharmacy_name.data,
        email=form.email.data,
        phone=form.phone.data,
        address=form.address.data,
        openinghours=form.opening_hours_and_days.data,
        password=hashed_password
    )


def confirm_token(token, expiration=86400):
    try:
        email = s.loads(token, max_age=expiration)
        return email
    except SignatureExpired:
        print("Token expired.")
        return False
    except BadSignature:
        print("Invalid token.")
        return False


# ------------------- Socket helper -------------------

def send_sound(user_id, sound_name="login"):
    """
    Emit a play_sound event to the specific user's room.
    This does not replace any existing notify_* functions — it just triggers the browser sound.
    """
    try:
        # socketio might be None/uninitialized in some contexts, so guard it
        if socketio:
            socketio.emit('play_sound', {'sound': sound_name}, room=str(user_id))
    except Exception as e:
        # log but do not break existing flow
        current_app.logger.debug(f"Failed to emit play_sound for user {user_id}: {e}")


# ------------------- ROUTES -------------------

@auth.route("/registerstore", methods=['GET', 'POST'])
def registerstore():
    formpharm = Set_StoreForm()
    form = PharmacyRegistrationForm()
    if request.method == "POST" and form.validate_on_submit():
        if Store.query.filter_by(email=form.email.data).first():
            flash('Email already exists')
            return redirect(url_for('auth.registerstore'))

        new_pharmacy = addpharma(form)
        db.session.add(new_pharmacy)
        try:
            db.session.commit()
            flash('Store registered successfully. Please check your email to confirm your account.', 'success')
            return redirect(url_for('auth.newlogin'))
            #token = send_confirmation_email(form, is_store=True)
            #return redirect(url_for('auth.unconfirmed', token=token))
        except IntegrityError:
            db.session.rollback()
            flash('Check your input details.')
            return redirect(url_for('auth.registerstore'))

    return render_template('auth/registerphar.html', form=form, formpharm=formpharm)


@auth.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    formpharm = Set_StoreForm()
    if request.method == "POST" and form.validate_on_submit():
        if User.query.filter_by(email=form.Email.data).first():
            flash('Email already exists')
            return redirect(url_for('auth.register'))

        users = adduser(form)
        db.session.add(users)
        try:
            db.session.commit()
            flash('Registered successfully. Please check your email to confirm your account.', 'success')       
            return redirect(url_for('auth.newlogin'))
            #token = send_confirmation_email(form)
            #return redirect(url_for('auth.unconfirmed', token=token))
        except IntegrityError:
            db.session.rollback()
            flash('Username or email already exists.')
            return redirect(url_for('auth.register'))

    return render_template('auth/register.html', form=form, formpharm=formpharm)


@auth.route('/newlogin', methods=['GET', 'POST'])
def newlogin():
    form = LoginForm()
    formpharm = Set_StoreForm()
    if request.method == "POST" and form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user_types = [
            (User, 'customer'),
            (Administrater, 'administrator'),
            (Store, 'store'),
            (DeliveryGuy, 'delivery_guy'),
            (Staff, 'store')
        ]

        for model, session_type in user_types:
            account = model.query.filter_by(email=email).first()
            print('account found')
            if account and bcrypt.check_password_hash(account.password, password):
                print('password matched')
                if session_type == 'store' and not account.confirmed:
                    flash('You need to activate your email before login.')
                    return redirect(url_for('auth.newlogin'))

                login_user(account)
                session['user_type'] = session_type
                session['email'] = account.email

                # Play sound (server -> browser) for the logged-in user.
                # Keep existing notify_customer(...) calls (they may do other things),
                # and ALSO emit a socket event so the browser can play audio.
                if session_type == 'customer':
                    flash(f'Login Successful, welcome {account.username}', 'success')
                    print("play sound for customer login")
                    try:
                        notify_customer(account.id)
                    except Exception:
                        current_app.logger.debug("notify_customer failed during login (customer).")
                    send_sound(account.id, sound_name="new_order")
                    return redirect(url_for('main.home'))

                elif session_type == 'administrator':
                    session['admin_id'] = account.id
                    print('admin id set in session')
                    print("play sound for admin login")
                    try:
                        print("Calling the notify function.")
                        notify_customer(account.id)
                    except Exception:
                        current_app.logger.debug("notify_customer failed during login (admin).")
                    send_sound(account.id, sound_name="login")
                    return redirect(url_for('admin.admindash'))

                elif session_type == 'store':
                    session['store_id'] = account.id
                    print("play sound for store login")
                    try:
                        notify_customer(account.id)
                    except Exception:
                        current_app.logger.debug("notify_customer failed during login (store).")
                    send_sound(account.id, sound_name="login")
                    flash(f'Login Successful, welcome {account.name}')
                    return redirect(url_for('store.adminpage'))

                elif session_type == 'delivery_guy':
                    session['delivery_guy_id'] = account.id
                    flash(f'Login Successful, welcome {account.names}', 'success')
                    print("play sound")
                    try:
                        notify_customer(account.id)
                    except Exception:
                        current_app.logger.debug("notify_customer failed during login (delivery).")
                    send_sound(account.id, sound_name="login")
                    return redirect(url_for('delivery.dashboard'))

        flash("Invalid login credentials", 'danger')

    return render_template('auth/newlogin.html', form=form, formpharm=formpharm)


@auth.route('/resend_email', methods=['GET','POST'])
def resend_email():
    form = emailform()
    if request.method == "POST" and form.validate_on_submit():
        email = form.email.data
        owner = Store.query.filter_by(email=email).first()
        user = User.query.filter_by(email=email).first()
        token = ''
        if owner:
            token = send_confirmation_email(owner, is_store=True)
        if user:
            token = send_confirmation_email(user)
        if not owner and not user:
            flash("Invalid email, try the one you used during registration")
            return redirect(url_for('auth.resend_email'))

        return redirect(url_for('auth.unconfirmed', token=token))
    return render_template('auth/resend_email.html', form=form)


@auth.route('/reset password/<token>', methods=['POST', 'GET'])
def reset(token):
    form = resetpassword()
    if form.validate_on_submit():
        newpassword = form.password.data
        email = confirm_token(token)
        if not email:
            flash("The link is invalid or expired.")
            return redirect(url_for('auth.newlogin'))

        store = Store.query.filter_by(email=email).first()
        user = User.query.filter_by(email=email).first()

        target = store or user
        if target:
            target.password = bcrypt.generate_password_hash(newpassword).decode('utf-8')
            db.session.commit()
            flash('Password reset successfully')
            return redirect(url_for('auth.newlogin'))

    return render_template('auth/newpassword.html', form=form)


@auth.route('/confirm_email/<token>', methods=['GET'])
def confirm_email(token):
    form = LoginForm()
    formpharm = Set_StoreForm()
    email = confirm_token(token)
    if not email:
        flash('The confirmation link is invalid or expired.')
        return redirect(url_for('auth.register'))

    user = User.query.filter_by(email=email).first()
    store = Store.query.filter_by(email=email).first()
    target = user or store
    if target:
        target.confirmed = True
        db.session.commit()
        flash('Your account has been successfully confirmed. You can now log in.', 'success')
        return render_template('auth/newlogin.html', form=form, formpharm=formpharm)
    else:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.register'))


@auth.route('/unconfirmed')
def unconfirmed():
    return render_template('auth/email/unconfirmed.html')
