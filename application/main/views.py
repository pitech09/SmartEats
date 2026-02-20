import os
import secrets
import re
from datetime import datetime
from typing import Self
from flask import render_template, redirect, url_for, flash, session, jsonify, request, current_app
from flask_login import login_required, current_user, logout_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy import desc, func, or_, case
from PIL import Image
import cloudinary
from cloudinary.uploader import upload
from dateutil.relativedelta import relativedelta
from math import radians, cos, sin, asin, sqrt

from . import main  # Blueprint is fine to import at top
from ..forms import *
from ..models import *
from sqlalchemy.orm import joinedload
from application.notification import *
from application.auth.views import send_sound
from application.utils.cache import *
from application import socketio, db
from flask_socketio import join_room
PRODUCTS_PER_PAGE = 9

# --------------------- USER LOADER ---------------------
def init_login_manager(login_manager):
    @login_manager.user_loader
    def load_user(user_id):
        user_type = session.get('user_type')
        if user_type == 'store':
            return Store.query.get(int(user_id)) or Staff.query.get(int(user_id))
        elif user_type == 'customer':
            return User.query.get(int(user_id))
        elif user_type == 'delivery_guy':
            return DeliveryGuy.query.get(int(user_id))
        elif user_type == 'administrator':
            return Administrater.query.get(int(user_id))
        return None
# --------------------- UTILITIES ---------------------

def update_product_status(Product):
    for item in Product:
        if item.quantity < 10:
            item.warning = "Low Stock"
            db.session.commit()
        elif item.quantity <= 0:
            db.session.delete(item)
            db.session.commit()

def calculate_loyalty_points(user, sale_amount):
    points_earned = int(sale_amount // 10)
    user.loyalty_points = points_earned + int(user.loyalty_points or 0)
    db.session.commit()
    return points_earned


from math import radians, sin, cos, sqrt, atan2

def haversine_meters(lat1, lon1, lat2, lon2):
    """
    Calculate great-circle distance in meters
    """
    R = 6371000  # Earth radius in meters

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def calculate_delivery_fee(store_lat, store_lng, cust_lat, cust_lng,
                           rate_per_km=5,
                           min_fee=10,
                           free_radius_m=500):
    """
    Fair delivery calculation:
    - Base minimum fee
    - First 500m included
    - M5 per km after that
    """
    distance_m = haversine_meters(store_lat, store_lng, cust_lat, cust_lng)

    fee = min_fee

    if distance_m > free_radius_m:
        extra_km = (distance_m - free_radius_m) / 1000
        fee += extra_km * rate_per_km

    return round(fee, 2)



def is_store_open(opening_hours):
    """
    Returns True if store is open, False otherwise.
    Handles messy formats like:
    - "Orders from 8am - 10pm"
    - "8am - 10pm"
    - "08:00 to 21:00"
    - "24/7"
    """
    print(f"[DEBUG] Checking opening hours: {opening_hours}")

    if not opening_hours:
        print("[DEBUG] No opening hours → Closed")
        return False

    opening_hours = opening_hours.lower()

    # Handle "24/7" explicitly
    if "24/7" in opening_hours:
        print("[DEBUG] 24/7 store → Open")
        return True

    # Regex to extract two times (HH:MM or H[H]?am/pm)
    time_matches = re.findall(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', opening_hours)
    print(f"[DEBUG] Extracted times: {time_matches}")

    if len(time_matches) != 2:
        print("[DEBUG] Could not find exactly 2 times → Closed")
        return False

    open_str, close_str = time_matches
    now = datetime.now().time()
    print(f"[DEBUG] Current time: {now}")

    # Try possible formats
    for fmt in ("%H:%M", "%I%p", "%I:%M%p"):
        try:
            open_time = datetime.strptime(open_str.strip(), fmt).time()
            close_time = datetime.strptime(close_str.strip(), fmt).time()
            print(f"[DEBUG] Parsed with format {fmt}: Open={open_time}, Close={close_time}")
            break
        except ValueError:
            continue
    else:
        print("[DEBUG] Could not parse times → Closed")
        return False

    # Check if store is open
    if open_time < close_time:
        is_open = open_time <= now <= close_time
        print(f"[DEBUG] Regular hours → is_open: {is_open}")
        return is_open
    else:
        is_open = now >= open_time or now <= close_time
        print(f"[DEBUG] Overnight hours → is_open: {is_open}")
        return is_open

def upload_to_cloudinary(file, folder='payment_proofs'):
    result = upload(
        file,
        folder=folder,
        use_filename=True,
        unique_filename=True,
        resource_type='image',
        transformation=[{'width': 300, 'height': 300, 'crop': 'fill'}, {'quality': 'auto'}]
    )
    return result

def human_duration(start_date, end_date=None):
    if not start_date:
        return "Unknown"
    if end_date is None:
        end_date = datetime.utcnow()
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
    _, f_ex = os.path.splitext(file.filename)
    post_img_fn = random_hex + f_ex
    post_image_path = os.path.join(current_app.root_path, current_app.config['UPLOAD_PRODUCTS'], post_img_fn)
    try:
        img = Image.open(file)
        img.thumbnail(size)
        img.save(post_image_path)
        return post_img_fn
    except Exception as e:
        print(f"Error saving image: {e}")
        return None

def save_update_profile_picture(form_picture):
    random_hex = secrets.token_hex(9)
    _, f_ex = os.path.splitext(form_picture.filename)
    post_img_fn = random_hex + f_ex
    post_image_path = os.path.join(current_app.root_path, current_app.config['UPLOAD_PATH'], post_img_fn)
    form_picture.save(post_image_path)
    return post_img_fn


@socketio.on("join")
def handle_join(data):
    join_room(data["room"])
    print(f"User joined room: {data['room']}")
# --------------------- ROUTES ---------------------
@main.route('/subscribe', methods=['POST'])
@login_required
def subscribe():
    data = request.get_json()
    existing = PushSubscription.query.filter_by(user_id=current_user.id).first()
    if existing:
        existing.subscription_info = data
    else:
        new_sub = PushSubscription(user_id=current_user.id, subscription_info=data)
        db.session.add(new_sub)
    db.session.commit()
    return jsonify({"success": True})

@main.route('/unsubscribe', methods=['POST'])
@login_required
def unsubscribe():
    sub = PushSubscription.query.filter_by(user_id=current_user.id).first() # type: ignore
    if sub:
        db.session.delete(sub)
        db.session.commit()
    return jsonify({"success": True})


# ---------------- HOME ----------------
@main.route('/home', methods=["POST", "GET"])
@login_required
def home():
    formpharm = Set_StoreForm()
    pharmacies = Store.query.all()
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in pharmacies]
    store_id = session.get('store_id')
    cart = Cart.query.filter(Cart.user_id==current_user.id, Cart.store_id == store_id).first()
    total_amount = cart.total_amount() if cart else 0.0
    total_count = cart.total_items() if cart else 0
    ads = Ad.query.all()
    return render_template("customer/home.html", user=current_user, total_count=total_count,
                           total_amount=total_amount, ads=ads, pharmacies=pharmacies, formpharm=formpharm)

@main.route("/", methods=["POST", "GET"])
def landing():
    ads = Ad.query.all()
    
    meals = (
        Product.query
        .filter_by(is_active=True)
        .order_by(func.random())
        .all()
    )

    return render_template('customer/landingpage.html', ads=ads, meals=meals)

# ---------------- CART ----------------
@main.route('/cartlist', methods=['GET', 'POST'])
@login_required
def cart():
    store_id = session.get('store_id')
    if not store_id:
        flash('Please select a store first.')
        return redirect(url_for("main.restuarants"))

    form = CartlistForm()
    form2 = removefromcart()
    form3 = confirmpurchase()
    formpharm = Set_StoreForm()
    formpharm.store.choices = [(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]

    user = current_user
    cart = Cart.query.filter_by(user_id=user.id, store_id=store_id).first()
    total_amount = 0.0
    total_count = 0
    if cart:
        total_amount = cart.total_amount()

        total_count = sum(item.quantity for item in cart.cart_items)

    return render_template('customer/updated_cartlist.html', form=form, form2=form2, form3=form3,
                           cart=cart, user=user, formpharm=formpharm, store=Store.query.get(store_id),
                           total_amount=total_amount, total_count=total_count, is_store_open=is_store_open)
@main.route("/go-to-store/<int:store_id>")
def go_to_store(store_id):
    session["store_id"] = store_id
    return redirect(url_for("main.menu", page_num=1))


# ---------------- MENU ----------------
@main.route("/menu/<int:page_num>", methods=["POST", "GET"])
@login_required
def menu(page_num=1):
    formpharm = Set_StoreForm()
    store_id = session.get("store_id")
    if not store_id:
        flash("Please select a store first", "warning")
        return redirect(url_for("main.restuarants"))

    mystore = Store.query.get_or_404(store_id)

    # Populate store choices
    formpharm.store.choices = [(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]

    # Forms
    form = CartlistForm()
    form2 = Search()

    # Get all active categories for this store
    categories = Category.query.filter_by(store_id=mystore.id, is_active=True).all()

    # Get selected category from query params (optional)
    selected_category_id = request.args.get("category", type=int)

    # Query products
    query = Product.query.filter_by(store_id=mystore.id, is_active=True)
    if selected_category_id:
        query = query.filter_by(category_id=selected_category_id)

    products = query.all()

    # Pagination
    start = (page_num - 1) * PRODUCTS_PER_PAGE
    end = start + PRODUCTS_PER_PAGE
    current_products = products[start:end]
    total_pages = (len(products) // PRODUCTS_PER_PAGE) + (1 if len(products) % PRODUCTS_PER_PAGE > 0 else 0)

    # Cart count
    cart = Cart.query.filter_by(user_id=current_user.id, store_id=mystore.id).first()
    total_count = sum(item.quantity for item in cart.cart_items) if cart else 0

    return render_template(
        "customer/updated_menu.html",
        form=form,
        formpharm=formpharm,
        form2=form2,
        products=current_products,
        categories=categories,
        selected_category_id=selected_category_id,
        page_num=page_num,
        total_pages=total_pages,
        total_count=total_count,
        user=current_user,
        store=mystore
    )

# ---------------- CUSTOM MEAL ----------------
@main.route("/custom_meal/<int:store_id>", methods=["GET", "POST"])
@login_required
def custom_meal(store_id):
    store = Store.query.get_or_404(store_id)
    ingredients = Ingredient.query.filter_by(store_id=store_id).all()

    if request.method == "POST":
        data = request.get_json()
        selected = data.get("ingredients", [])

        if not selected:
            return jsonify({"success": False, "message": "No ingredients selected"}), 400

        # ---------------- ENSURE CART ----------------
        cart = Cart.query.filter_by(
            user_id=current_user.id,
            store_id=store_id
        ).first()

        if not cart:
            cart = Cart(user_id=current_user.id, store_id=store_id)
            db.session.add(cart)
            db.session.flush()

        # ---------------- CREATE CUSTOM MEAL ----------------
        custom_meal = CustomMeal(
            name="Custom Meal",
            base_price=0,
            total_price=0,
            user_id=current_user.id
        )
        db.session.add(custom_meal)
        db.session.flush()

        # ---------------- INGREDIENTS ----------------
        total_price = 0

        for item in selected:
            ing = Ingredient.query.filter_by(
                id=int(item.get("id")),
                store_id=store_id
            ).first()

            if not ing:
                continue

            qty = max(1, int(item.get("quantity", 1)))
            total_price += ing.price * qty

            db.session.add(
                CustomMealIngredient(
                    custom_meal_id=custom_meal.id,
                    ingredient_name=ing.name,
                    ingredient_price=ing.price,
                    quantity=qty
                )
            )

        custom_meal.total_price = total_price
        db.session.flush()

        # ---------------- ADD TO CART ----------------
        cart_item = CartItem(
            cart_id=cart.id,
            custom_meal_id=custom_meal.id,
            quantity=1
        )
        db.session.add(cart_item)

        db.session.commit()

        return jsonify({
            "success": True,
            "custom_meal_id": custom_meal.id,
            "total": round(total_price, 2)
        })

    return render_template(
        "customer/custom_meal.html",
        store=store,
        ingredients=ingredients
    )

@main.route('/addorder', methods=['POST'])
@login_required
def addorder():
    form = confirmpurchase()

    store_id = session.get('store_id')
    store = Store.query.get_or_404(store_id)

    # Get cart
    cart = Cart.query.filter_by(
        user_id=current_user.id,
        store_id=store_id
    ).first()

    if not cart or not cart.cart_items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for('main.menu', page_num=1))

    # Prevent multiple pending orders
    existing_order = Order.query.filter_by(
        user_id=current_user.id,
        store_id=store_id,
        status='Pending'
    ).first()

    if existing_order:
        flash("You still have a pending order.", "warning")
        return redirect(url_for('main.myorders'))

    if not form.validate_on_submit():
        flash("Invalid submission.", "warning")
        return redirect(url_for('main.cart'))

    # -----------------------------
    # Get customer coordinates
    # -----------------------------
    try:
        customer_lat = float(request.form.get('latitude')) if request.form.get('latitude') else None
        customer_lng = float(request.form.get('longitude')) if request.form.get('longitude') else None
    except ValueError:
        customer_lat = None
        customer_lng = None

    # -----------------------------
    # Create Order
    # -----------------------------
    neworder = Order(
        user_id=current_user.id,
        user_email=current_user.email,
        store_id=store.id,
        payment=form.payment.data,
        status="Pending",
        customer_lat=customer_lat,
        customer_lng=customer_lng
    )

    # Delivery location
    if form.deliverymethod.data == 'pickup':
        neworder.location = 'pickup'
    else:
        if not form.drop_address.data:
            flash("Delivery address is required.", "warning")
            return redirect(url_for('main.cart'))
        neworder.location = form.drop_address.data

    # -----------------------------
    # Payment Screenshot
    # -----------------------------
    file = form.payment_screenshot.data
    if not file:
        flash("Payment proof is required.", "warning")
        return redirect(url_for('main.cart'))

    if current_app.config.get('USE_CLOUDINARY'):
        neworder.screenshot = upload_to_cloudinary(file)['secure_url']
    else:
        neworder.screenshot = save_product_picture(file)

    # -----------------------------
    # Distance + Delivery Fee
    # -----------------------------
    delivery_fee = 0
    distance_km = 0

    if form.deliverymethod.data == 'agent':
        if not all([customer_lat, customer_lng, store.latitude, store.longitude]):
            flash("Location access required for delivery.", "warning")
            return redirect(url_for('main.cart'))

        from math import radians, sin, cos, sqrt, atan2


        distance_km = haversine(
            store.latitude,
            store.longitude,
            customer_lat,
            customer_lng
        )

        BASE_FEE = 10
        PER_KM = 5

        delivery_fee = round(BASE_FEE + (distance_km * PER_KM), 2)

    neworder.delivery_fee = delivery_fee
    neworder.distance_km = round(distance_km, 2)

    db.session.add(neworder)
    db.session.commit()

    # -----------------------------
    # Process Cart Items
    # -----------------------------
    total_amount = 0

    for item in cart.cart_items:
        if item.product:
            order_item = OrderItem(
                order_id=neworder.id,
                product_id=item.product.id,
                product_name=item.product.productname,
                product_price=item.product.price,
                quantity=item.quantity
            )
            db.session.add(order_item)

            item_total = item.product.price * item.quantity
            total_amount += item_total

            sale = Sales(
                order_id=neworder.id,
                user_id=current_user.id,
                product_id=item.product.id,
                product_name=item.product.productname,
                price=item.product.price,
                quantity=item.quantity,
                store_id=store.id
            )
            db.session.add(sale)

        elif item.custom_meal:
            item.custom_meal.order_id = neworder.id
            total_amount += item.custom_meal.total_price

            sale = Sales(
                order_id=neworder.id,
                user_id=current_user.id,
                product_id=None,
                product_name=item.custom_meal.name,
                price=item.custom_meal.total_price,
                quantity=1,
                store_id=store.id
            )
            db.session.add(sale)

    total_amount += delivery_fee
    neworder.total_amount = round(total_amount, 2)

    # -----------------------------
    # Clear Cart
    # -----------------------------
    CartItem.query.filter_by(cart_id=cart.id).delete()
    db.session.commit()

    cart_cache.clear_cache(current_user.id)

    # -----------------------------
    # Notify Store (SocketIO)
    # -----------------------------
    socketio.emit(
        'new_order',
        {
            'order_id': neworder.id,
            'customer_email': current_user.email,
            'total_amount': neworder.total_amount,
            'delivery_fee': delivery_fee,
            'distance_km': neworder.distance_km,
            'delivery_method': form.deliverymethod.data,
            'location': neworder.location,
            'created_at': neworder.create_at.strftime('%Y-%m-%d %H:%M')
        },
        room=f'store_{store.id}'
    )

    flash("Order successfully placed.", "success")
    return redirect(url_for('main.myorders'))




@main.route('/myorders')
@login_required
def myorders():
    store_id = session.get('store_id')
    if not store_id:
        flash("Please select a store first.")
        return redirect(url_for('main.home'))

    # Fetch active/pending orders with their items
    orders = (
        Order.query
        .filter_by(user_id=current_user.id, store_id=store_id)
        .filter(Order.status.in_(["Pending", "Processing", "Accepted"]))
        .options(joinedload(Order.order_items))  # <-- load items
        .order_by(Order.create_at.desc())
        .all()
    )

    return render_template('customer/myorder.html', order=orders)

@main.route('/complete_orders')
@login_required
def completed_order():
    # Fetch all orders for current user where status is "Completed"
    completed_orders = Order.query.filter_by(user_id=current_user.id, status='Completed')\
                                  .order_by(Order.create_at.desc()).all()
    
    return render_template(
        'customer/updated_complete.html',
        completed_orders=completed_orders
    )


@main.route('/cancelled_orders')
@login_required
def cancelled_orders():
    cancelled_orders = Order.query.filter_by(user_id=current_user.id, status='Cancelled')\
                                  .order_by(Order.create_at.desc()).all()
    return render_template(
        'customer/updated_cancelled.html',
        orders=cancelled_orders,
        title="Cancelled Orders"
    )

# ---------------- AJAX ----------------
@main.route("/add_to_cart_ajax", methods=["POST"])
@login_required
def add_to_cart_ajax():
    data = request.get_json() or {}

    product_id = data.get("product_id")
    custom_meal_id = data.get("custom_meal_id")

    if not product_id and not custom_meal_id:
        return jsonify(success=False, error="nothing_to_add"), 400

    # Resolve store
    if product_id:
        product = Product.query.get_or_404(product_id)
        store_id = product.store_id
    else:
        custom_meal = CustomMeal.query.get_or_404(custom_meal_id)
        store_id = session.get("store_id")

    # Ensure cart exists
    cart = Cart.query.filter_by(
        user_id=current_user.id,
        store_id=store_id
    ).first()

    if not cart:
        cart = Cart(user_id=current_user.id, store_id=store_id)
        db.session.add(cart)
        db.session.flush()

    # ---- PRODUCT ----
    if product_id:
        cart_item = CartItem.query.filter_by(
            cart_id=cart.id,
            product_id=product_id
        ).first()

        if cart_item:
            cart_item.quantity += 1
        else:
            cart_item = CartItem(
                cart_id=cart.id,
                product_id=product_id,
                quantity=1
            )
            db.session.add(cart_item)

    # ---- CUSTOM MEAL ----
    if custom_meal_id:
        cart_item = CartItem.query.filter_by(
            cart_id=cart.id,
            custom_meal_id=custom_meal_id
        ).first()

        if cart_item:
            cart_item.quantity += 1
        else:
            cart_item = CartItem(
                cart_id=cart.id,
                custom_meal_id=custom_meal_id,
                quantity=1
            )
            db.session.add(cart_item)

    db.session.commit()

    # Recalculate totals
    cart_count = cart.total_items()
    cart_total = cart.total_amount()

    try:
        socketio.emit(
            "cart_updated",
            {"cart_count": cart_count, "cart_total": cart_total},
            room=str(current_user.id)
        )
    except Exception:
        pass

    return jsonify(
        success=True,
        cart_count=cart_count,
        cart_total=cart_total
    )

# ---------------- REMOVE CART ITEM AJAX ----------------
@main.route("/remove_from_cart_ajax/<int:item_id>", methods=["POST"])
@login_required
def remove_from_cart_ajax(item_id):
    item = CartItem.query.get_or_404(item_id)
    cart = Cart.query.get(item.cart_id)
    if not cart or cart.user_id != current_user.id:
        return jsonify(success=False, error="forbidden"), 403
    db.session.delete(item)
    db.session.commit()
    cart = Cart.query.filter_by(user_id=current_user.id, store_id=cart.store_id).first()
    if not cart:
        cart_count = 0
        cart_total = 0.0
    else:
        cart_count = sum(i.quantity for i in cart.cart_items)
        cart_total = sum(i.product.price * i.quantity for i in cart.cart_items)
    try:
        socketio.emit("cart_updated", {"cart_count": cart_count, "cart_total": cart_total}, room=str(current_user.id))
    except Exception as e:
        current_app.logger.debug(f"socketio emit failed: {e}")
    return jsonify(success=True, cart_count=cart_count, cart_total=cart_total)

# ---------------- CART STATUS ----------------
@main.route("/cart_status", methods=["GET"])
@login_required
def cart_status():
    store_id = session.get("store_id")
    cart = Cart.query.filter_by(user_id=current_user.id, store_id=store_id).first()
    if not cart:
        return jsonify(success=True, cart_count=0, cart_total=0.0)
    return jsonify(success=True, cart_count=sum(i.quantity for i in cart.cart_items),
                   cart_total=sum(i.product.price * i.quantity for i in cart.cart_items))

# ---------------- ACCOUNT ----------------
@main.route("/account", methods=["GET", "POST"])
@login_required
def account():
    form = UpdateForm()

    user = current_user

    if form.validate_on_submit():
        print(request.form)

        # Handle profile picture
        if form.picture.data:
            image_file = save_product_picture(form.picture.data)
            current_user.image_file = image_file

        # Update user info
        current_user.email = form.Email.data.strip()
        current_user.lastname = form.lastName.data.strip()
        current_user.username = form.username.data.strip()
        current_user.district = form.district.data.strip()
        current_user.town = form.town.data.strip()

        db.session.commit()
        flash("Account Details Updated Successfully.", "success")
        return redirect(url_for('main.home'))

    image_file = url_for('static', filename='images/profiles/' + user.image_file)

    return render_template(
        'customer/updated_acc.html',
        user=user,
        store=session.get('store_id'),
        image_file=image_file,
        form=form
    )

# ---------------- LOGOUT ----------------
@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have successfully logged out.', 'success')
    return redirect(url_for('main.landing'))

# ---------------- DEACTIVATE ACCOUNT ----------------
@main.route('/deactivate account/<int:user_id>')
@login_required
def deactivate_Account(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    try:
        db.session.commit()
        logout_user()
        session.pop('store_id', None)
        flash('Account successfully deleted.')
    except IntegrityError:
        db.session.rollback()
        flash('Error deleting account')
    return redirect(url_for('auth.newlogin'))

# ---------------- STORE ----------------
@main.route('/set_store', methods=['POST', 'GET'])
@login_required
def set_store():
    formpharm = Set_StoreForm()
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
    if formpharm.validate_on_submit():
        session['store_id'] = formpharm.store.data
        return redirect(url_for('main.home', store_id=formpharm.store.data))
    flash(f'{current_user.id} had a problem selecting your store, please try again later')
    return redirect(url_for('main.home'))

@main.route('/set_store/<int:store_id>', methods=['POST', 'GET'])
@login_required
def set_storee(store_id):
    store = Store.query.get_or_404(store_id)
    session['store_id'] = store.id
    flash(f'You are now viewing {store.name}', 'success')
    return redirect(url_for('main.menu', page_num=1))

@main.route('/stores')
def restuarants():
    form2 = Search()
    user_district = current_user.district
    user_town = current_user.town

    rank_case = case(
        (Store.town == user_town, 0),
        (Store.district == user_district, 1),
        else_=2
    )

    stores = Store.query.filter(
        Store.is_active == True
    ).order_by(
        rank_case,  # prioritize rank
        Store.name.asc()  # then alphabetical by name
    ).all()

    return render_template('customer/restuarants.html', stores=stores, form2=form2, is_store_open=is_store_open)

@main.route("/store/<int:store_id>")
@login_required
def store_details(store_id):
    restuarant = Store.query.get_or_404(store_id)
    registered_for = human_duration(restuarant.registered_on)
    # Forms used in navbar or page
    formpharm = Set_StoreForm()
    formpharm.store.choices = [(-1, "Select a Store")] + [
        (p.id, p.name) for p in Store.query.all()
    ]

    # Cart summary (if user already browsing this store)
    cart = Cart.query.filter_by(
        user_id=current_user.id,
        store_id=restuarant.id
    ).first()

    total_count = sum(i.quantity for i in cart.cart_items) if cart else 0
    total_amount = sum(i.product.price * i.quantity for i in cart.cart_items) if cart else 0.0

    return render_template(
        "customer/restuarantdetails.html",
        restuarant=restuarant,
        total_count=total_count,
        total_amount=total_amount,
        formpharm=formpharm,
        registered_for=registered_for
    )

# ---------------- VIEW PRODUCT ----------------
@main.route('/viewproduct/<int:product_id>')
@login_required
def viewproduct(product_id):
    store_id = session.get('store_id')
    store = Store.query.get_or_404(store_id)
    if not store:
        flash('Please select a store first.', 'warning')
        return redirect(url_for('main.restuarants'))
    
    product = Product.query.get_or_404(product_id)
    return render_template('customer/updated_productview.html', product=product, store=store)

# ---------------- SEARCH ----------------
@main.route("/search/<int:page_num>", methods=["POST", "GET"])
@login_required
def search(page_num=1):
    form2 = Search()

    if form2.validate_on_submit():
        search_term = form2.keyword.data.strip()

        products = Product.query.filter(
            or_(
                Product.productname.ilike(f"%{search_term}%"),
                Product.description.ilike(f"%{search_term}%")
            )
        ).all()

        start = (page_num - 1) * PRODUCTS_PER_PAGE
        end = start + PRODUCTS_PER_PAGE
        current_products = products[start:end]

        total_pages = (
            len(products) // PRODUCTS_PER_PAGE
            + (1 if len(products) % PRODUCTS_PER_PAGE > 0 else 0)
        )

        store = Store.query.get_or_404(session.get("store_id"))

        return render_template(
            "customer/updated_menu.html",
            products=current_products,
            form2=form2,
            page_num=page_num,
            store=store,
            total_pages=total_pages
        )

    return redirect(url_for("main.menu", page_num=1))

@main.route("/search/store/<int:page_num>", methods=["POST", "GET"])
def searcher(page_num=1):
    form2 = Search()
    current_stores = []

    if form2.validate_on_submit():
        search_term = form2.keyword.data.strip()

        # Filter stores by name, district, or town
        stores = Store.query.filter(
            Store.is_active == True,
            or_(
                Store.district.ilike(f"%{search_term}%"),
                Store.town.ilike(f"%{search_term}%"),
                Store.name.ilike(f"%{search_term}%")
            )
        ).all()

        # Pagination
        start = (page_num - 1) * PRODUCTS_PER_PAGE
        end = start + PRODUCTS_PER_PAGE
        current_stores = stores[start:end]

        total_pages = (len(stores) // PRODUCTS_PER_PAGE) + (1 if len(stores) % PRODUCTS_PER_PAGE > 0 else 0)

        return render_template(
            "customer/restuarants.html",
            stores=current_stores,
            form2=form2,
            page_num=page_num,
            total_pages=total_pages,
            search_term=search_term
        )

    # GET request or empty search: just show all stores
    all_stores = Store.query.filter_by(is_active=True).all()
    start = (page_num - 1) * PRODUCTS_PER_PAGE
    end = start + PRODUCTS_PER_PAGE
    current_stores = all_stores[start:end]

    total_pages = (len(all_stores) // PRODUCTS_PER_PAGE) + (1 if len(all_stores) % PRODUCTS_PER_PAGE > 0 else 0)

    return render_template(
        "customer/restuarants.html",
        stores=current_stores,
        form2=form2,
        page_num=page_num,
        total_pages=total_pages
    )

@main.route('/terms')
def terms_conditions():
    return render_template("customer/terms.html")

@main.route('/privacy policy')
def privacy_policy():
    return render_template('customer/policy.html')

@main.route('/decrement_cart_item/<int:item_id>', methods=['POST'])
@login_required
def decrement_cart_item(item_id):
    item = CartItem.query.get_or_404(item_id)

    # Make sure this item belongs to the current user's cart
    cart = Cart.query.get(item.cart_id)
    if not cart or cart.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Forbidden'}), 403

    # Decrement or remove item
    if item.quantity > 1:
        item.quantity -= 1
        db.session.commit()
    else:
        db.session.delete(item)
        db.session.commit()
        item.quantity = 0  # ensure front-end knows quantity is 0

    # Optional: calculate new cart total
    cart_items = CartItem.query.filter_by(cart_id=cart.id).all()
    cart_total = sum(i.quantity * i.product.price for i in cart_items)

    return jsonify({
        'success': True,
        'new_quantity': item.quantity,
        'cart_total': cart_total
    })

# ---------------- CONTACT / ABOUT / HEALTH ----------------
@main.route("/about")
def about():
    return render_template("customer/aboutme.html")

@main.route("/contact")
def contact():
    return render_template("customer/contact.html")

@main.route("/ping")
def ping():
    return "pong"

@main.route("/health")
def health():
    return "ok"
