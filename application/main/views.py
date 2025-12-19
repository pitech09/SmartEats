import os
import secrets
from datetime import datetime
from flask import render_template, redirect, url_for, flash, session, jsonify, request, current_app
from flask_login import login_required, current_user, logout_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy import desc, or_
from . import main
from ..forms import *
from ..models import *
from PIL import Image
import cloudinary
from cloudinary.uploader import upload
from dateutil.relativedelta import relativedelta
from application.notification import *
from application.auth.views import send_sound
from application.utils.cache import cart_cache, products_cache
from application import db, socketio

PRODUCTS_PER_PAGE = 9

# --------------------------
# User loader for Flask-Login
# --------------------------
@login_manager.user_loader
def load_user(user_id):
    user_type = session.get('user_type')
    if user_type == 'store':
        return Store.query.get(user_id) or Staff.query.get(user_id)
    elif user_type == 'customer':
        return User.query.get(user_id)
    elif user_type == 'delivery_guy':
        return DeliveryGuy.query.get(user_id)
    elif user_type == 'administrator':
        return Administrater.query.get(user_id)
    return None


# --------------------------
# Helper Functions
# --------------------------
def update_product_status(products):
    """Mark low-stock products or delete zero-stock products."""
    for item in products:
        if item.quantity <= 0:
            db.session.delete(item)
        elif item.quantity < 10:
            item.warning = "Low Stock"
    db.session.commit()


def calculate_loyalty_points(user, sale_amount):
    points_earned = int(sale_amount // 10)
    user.loyalty_points = (user.loyalty_points or 0) + points_earned
    db.session.commit()
    return points_earned


def upload_to_cloudinary(file, folder='payment_proofs'):
    result = upload(
        file,
        folder=folder,
        use_filename=True,
        unique_filename=True,
        resource_type='image',
        transformation=[
            {'width': 300, 'height': 300, 'crop': 'fill'},
            {'quality': 'auto'}
        ]
    )
    return result


def human_duration(start_date, end_date=None):
    """Return duration between two dates in human-readable form."""
    if not start_date:
        return "Unknown"
    end_date = end_date or datetime.utcnow()
    delta = relativedelta(end_date, start_date)
    total_seconds = (end_date - start_date).total_seconds()

    if delta.years >= 1:
        return f"{delta.years} year{'s' if delta.years > 1 else ''}"
    elif delta.months >= 1:
        return f"{delta.months} month{'s' if delta.months > 1 else ''}"
    elif delta.days >= 7:
        weeks = delta.days // 7
        return f"{weeks} week{'s' if weeks > 1 else ''}"
    elif delta.days >= 1:
        return f"{delta.days} day{'s' if delta.days > 1 else ''}"
    elif total_seconds >= 3600:
        hours = int(total_seconds // 3600)
        return f"{hours} hour{'s' if hours > 1 else ''}"
    else:
        minutes = int(total_seconds // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''}"


def save_product_picture(file):
    size = (300, 300)
    random_hex = secrets.token_hex(9)
    _, f_ext = os.path.splitext(file.filename)
    filename = random_hex + f_ext
    path = os.path.join(current_app.root_path, current_app.config['UPLOAD_PRODUCTS'], filename)
    try:
        img = Image.open(file)
        img.thumbnail(size)
        img.save(path)
        return filename
    except Exception as e:
        current_app.logger.error(f"Error saving image: {e}")
        return None


def save_update_profile_picture(file):
    random_hex = secrets.token_hex(9)
    _, f_ext = os.path.splitext(file.filename)
    filename = random_hex + f_ext
    path = os.path.join(current_app.root_path, current_app.config['UPLOAD_PATH'], filename)
    file.save(path)
    return filename


# --------------------------
# Routes
# --------------------------
@main.route('/')
def landing():
    return render_template('customer/landingpage.html')


@main.route('/home', methods=['GET', 'POST'])
@login_required
def home():
    store_id = session.get('store_id')
    if not store_id:
        flash('Please select a store first.')
        return redirect(url_for('main.landing'))

    formpharm = Set_StoreForm()
    pharmacies = Store.query.all()
    formpharm.store.choices = [(-1, "Select a Store")] + [(p.id, p.name) for p in pharmacies]

    cart = Cart.query.filter_by(user_id=current_user.id, store_id=store_id).first()
    total_amount = sum(item.product.price * item.quantity for item in cart.cart_items) if cart else 0.0
    total_count = sum(item.quantity for item in cart.cart_items) if cart else 0

    return render_template(
        "customer/home.html",
        user=current_user,
        total_amount=total_amount,
        total_count=total_count,
        pharmacies=pharmacies,
        formpharm=formpharm
    )


@main.route('/store/<int:store_id>')
def details(store_id):
    store = Store.query.get_or_404(store_id)
    registered_for = human_duration(store.registered_on)
    return render_template(
        'customer/restuarantdetails.html',
        restaurant=store,
        registered_for=registered_for
    )


# --------------------------
# Menu & Product Views
# --------------------------
@main.route('/menu/<int:page_num>', methods=['GET', 'POST'])
@login_required
def menu(page_num=1):
    store_id = session.get('store_id')
    store = Store.query.get_or_404(store_id)
    formpharm = Set_StoreForm()
    formpharm.store.choices = [(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
    form = CartlistForm()
    form2 = Search()

    products = Product.query.filter_by(store_id=store_id).all()
    start = (page_num - 1) * PRODUCTS_PER_PAGE
    end = start + PRODUCTS_PER_PAGE
    current_products = products[start:end]
    total_pages = (len(products) // PRODUCTS_PER_PAGE) + (1 if len(products) % PRODUCTS_PER_PAGE else 0)

    item_picture = url_for('static', filename='css/images/default.jpg')
    total_count = 0
    cart = Cart.query.filter_by(user_id=current_user.id, store_id=store_id).first()
    if cart:
        total_count = sum(item.quantity for item in cart.cart_items)

    return render_template(
        'customer/updated_menu.html',
        form=form,
        form2=form2,
        formpharm=formpharm,
        products=current_products,
        total_pages=total_pages,
        page_num=page_num,
        total_count=total_count,
        item_picture=item_picture,
        store=store,
        user=current_user
    )


@main.route('/viewproduct/<int:product_id>', methods=['GET'])
@login_required
def viewproduct(product_id):
    product = Product.query.get_or_404(product_id)
    store_id = session.get('store_id')
    store = Store.query.get_or_404(store_id)
    formpharm = Set_StoreForm()
    formpharm.store.choices = [(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
    form = CartlistForm()
    item_picture = url_for('static', filename=f'css/images/products/{product.pictures}') if product.pictures else url_for('static', filename='css/images/default.jpg')

    return render_template(
        'customer/updated_productview.html',
        product=product,
        store=store,
        form=form,
        formpharm=formpharm,
        item_picture=item_picture
    )


# --------------------------
# Cart Routes & AJAX
# --------------------------
@main.route('/cartlist', methods=['GET', 'POST'])
@login_required
def cart():
    store_id = session.get('store_id')
    if not store_id:
        flash('Please select a store first.')
        return redirect(url_for('main.home'))

    form = CartlistForm()
    form2 = removefromcart()
    form3 = confirmpurchase()
    formpharm = Set_StoreForm()
    formpharm.store.choices = [(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]

    cart = Cart.query.filter_by(user_id=current_user.id, store_id=store_id).first()
    total_amount = sum(item.product.price * item.quantity for item in cart.cart_items) if cart else 0.0
    total_count = sum(item.quantity for item in cart.cart_items) if cart else 0

    return render_template(
        'customer/updated_cartlist.html',
        cart=cart,
        user=current_user,
        total_amount=total_amount,
        total_count=total_count,
        form=form,
        form2=form2,
        form3=form3,
        formpharm=formpharm,
        store=Store.query.get_or_404(store_id)
    )


@main.route("/add_to_cart_ajax", methods=["POST"])
@login_required
def add_to_cart_ajax():
    data = request.get_json() or {}
    product_id = data.get("product_id")
    if not product_id:
        return jsonify(success=False, error="missing_product_id"), 400

    product = Product.query.get_or_404(product_id)
    store_id = session.get("store_id") or product.store_id

    # get or create cart
    cart = Cart.query.filter_by(user_id=current_user.id, store_id=store_id).first()
    if not cart:
        cart = Cart(user_id=current_user.id, store_id=store_id)
        db.session.add(cart)
        db.session.commit()

    cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = CartItem(cart_id=cart.id, product_id=product.id, quantity=1)
        db.session.add(cart_item)

    db.session.commit()

    cart_count = cart.total_items()
    cart_total = cart.total_amount()

    try:
        socketio.emit("cart_updated", {"cart_count": cart_count, "cart_total": cart_total}, room=str(current_user.id))
    except Exception as e:
        current_app.logger.debug(f"socketio emit failed: {e}")

    cart_cache.set(current_user.id, "total_count", cart_count)
    cart_cache.set(current_user.id, "total_amount", cart_total)

    return jsonify(success=True, cart_count=cart_count, cart_total=cart_total)


@main.route("/remove_from_cart_ajax/<int:item_id>", methods=["POST"])
@login_required
def remove_from_cart_ajax(item_id):
    item = CartItem.query.get_or_404(item_id)
    cart = Cart.query.get(item.cart_id)
    if not cart or cart.user_id != current_user.id:
        return jsonify(success=False, error="forbidden"), 403

    db.session.delete(item)
    db.session.commit()

    cart_count = cart.total_items() if cart else 0
    cart_total = cart.total_amount() if cart else 0.0

    try:
        socketio.emit("cart_updated", {"cart_count": cart_count, "cart_total": cart_total}, room=str(current_user.id))
    except Exception as e:
        current_app.logger.debug(f"socketio emit failed: {e}")

    cart_cache.set(current_user.id, "total_count", cart_count)
    cart_cache.set(current_user.id, "total_amount", cart_total)

    return jsonify(success=True, cart_count=cart_count, cart_total=cart_total)


# --------------------------
# Add order
# --------------------------
@main.route("/addorder/<int:total_amount>", methods=["POST", "GET"])
@login_required
def addorder(total_amount):
    form = confirmpurchase()
    store_id = session.get('store_id')
    store = Store.query.get_or_404(store_id)
    cart = Cart.query.filter_by(user_id=current_user.id, store_id=store_id).first()
    if not cart:
        flash("No items in cart.")
        return redirect(url_for('main.cart'))

    existing_order = Order.query.filter_by(user_id=current_user.id, status="Pending", store_id=store_id).first()
    if existing_order:
        flash("You have a pending order. Wait for admin approval.", "unsuccessful")
        return redirect(url_for('main.myorders'))

    if not form.validate_on_submit():
        flash("Form validation failed.", "danger")
        return redirect(url_for('main.cart'))

    # Create order
    new_order = Order(
        user_id=current_user.id,
        payment=form.payment.data,
        user_email=current_user.email,
        store_id=store.id,
        source_store=store.name,
        location=form.drop_address.data if form.deliverymethod.data != 'pickup' else 'pickup',
        screenshot=None,
        transactionID='None'
    )

    file = form.payment_screenshot.data
    if not file:
        flash("Payment proof missing.")
        return redirect(url_for('main.cart'))

    if current_app.config['USE_CLOUDINARY']:
        new_order.screenshot = upload_to_cloudinary(file)['secure_url']
    else:
        new_order.screenshot = save_product_picture(file)

    db.session.add(new_order)
    db.session.commit()

    # Create OrderItems & Sales
    order_items = []
    sales_entries = []
    total_amount = 0
    for item in cart.cart_items:
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=item.product.id,
            product_name=item.product.productname,
            product_price=item.product.price,
            quantity=item.quantity
        )
        total_amount += item.product.price * item.quantity
        order_items.append(order_item)

        sale = Sales(
            order_id=new_order.id,
            product_id=item.product.id,
            product_name=item.product.productname,
            price=item.product.price,
            quantity=item.quantity,
            user_id=new_order.user_id,
            date_=new_order.create_at,
            store_id=store.id
        )
        sales_entries.append(sale)

    db.session.add_all(order_items + sales_entries)

    # Clear cart
    CartItem.query.filter_by(cart_id=cart.id).delete()
    cart.redeemed = False
    db.session.commit()

    # Clear user's cart cache
    cart_cache.clear_cache(current_user.id)

    # Notify store
    try:
        notify_store(store_id=store.id)
        send_sound(store_id, sound_name="new_order")
    except Exception:
        current_app.logger.debug("Store notification failed.")

    flash("Order successfully placed! Payment will be verified shortly.", "success")
    return redirect(url_for('main.myorders', total_amount=total_amount))


# --------------------------
# Account
# --------------------------
@main.route("/account", methods=["GET", "POST"])
@login_required
def account():
    form = UpdateForm()
    formpharm = Set_StoreForm()
    formpharm.store.choices = [(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
    user = current_user

    if form.validate_on_submit():
        if form.picture.data:
            user.image_file = save_update_profile_picture(form.picture.data)

        user.email = form.Email.data
        user.phonenumber = form.phonenumber.data
        user.lastname = form.lastName.data
        user.username = form.username.data
        db.session.commit()
        flash("Account updated successfully.", "success")
        return redirect(url_for('main.account'))

    image_file = url_for('static', filename=f'css/images/profiles/{user.image_file}') if user.image_file else url_for('static', filename='css/images/default.jpg')

    return render_template(
        'customer/updated_acc.html',
        user=user,
        form=form,
        formpharm=formpharm,
        store=Store.query.get(session.get('store_id')),
        image_file=image_file
    )


@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have successfully logged out.', 'success')
    return redirect(url_for('main.landing'))

@main.route('/deactivate account/<int:user_id>')
@login_required
def deactivate_Account(user_id):
    user = User.query.get_or_404(user_id)
    if not user:
        flash('Failed to get user')
        return redirect(url_for('main.account'))
    db.session.delete(user)
    try:
        db.session.commit()
        logout_user()
        session.pop('store_id', None)
        flash('Account successfully deleted.')
    except IntegrityError:
        flash('Error deleting account')
        db.session.rollback() 
        return redirect(url_for('main.account'))
    return redirect(url_for('auth.newlogin'))   


@main.route('/set_store', methods=['POST', 'GET'])
@login_required
def set_store():
    formpharm = Set_StoreForm()
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
    if formpharm.validate_on_submit():
        session['store_id'] = formpharm.store.data
        return redirect(url_for('main.home', store_id=formpharm.store.data))
    elif formpharm.errors:
        print(formpharm.errors)
        return formpharm.errors
    else:
        flash(f'{current_user.id} had a problem selecting your store, please try again later')
        return redirect(url_for('main.home'))
    
@main.route('/set_store/<int:store_id>', methods=['POST', 'GET'])
@login_required
def set_storee(store_id):
    store = Store.query.get_or_404(store_id)
    if store:
        session['store_id'] = store.id
        flash(f'You are now viewing {store.name}', 'success')
        return redirect(url_for('main.home', store_id=store.id))
    else:
        flash('Store not found', 'danger')
        return redirect(url_for('main.home'))

@main.route('/restuarants', methods=['POST', 'GET'])
def restuarants():
    formpharm = Set_StoreForm()
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
    stores = Store.query.all()
    return render_template('customer/restuarants.html', stores=stores, formpharm=formpharm)

    
