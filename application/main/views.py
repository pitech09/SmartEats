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
from application.utils.sms import normalize_phone_number
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
                           store_radius=500,
                           inside_min_fee=10,
                           normal_min_fee=13,
                           rate_per_meter=0.01,
                           max_fee=10000):

    distance_m = haversine_meters(
        store_lat,
        store_lng,
        cust_lat,
        cust_lng
    )

    # Same logic as JS
    if distance_m <= store_radius:
        fee = inside_min_fee
    else:
        fee = max(distance_m * rate_per_meter, normal_min_fee)

    return round(min(fee, max_fee), 2)


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

@main.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"restaurants": [], "meals": []})

    # Search restaurants
    restaurants = Store.query.filter(
        Store.is_active == True,
        or_(
            Store.name.ilike(f"%{q}%"),
            Store.district.ilike(f"%{q}%"),
            Store.town.ilike(f"%{q}%")
        )
    ).limit(5).all()

    # Search meals
    meals = Product.query.filter(
        Product.is_active == True,
        or_(
            Product.productname.ilike(f"%{q}%"),
            Product.description.ilike(f"%{q}%")
        )
    ).limit(5).all()

    return jsonify({
        "restaurants": [{
            "id": r.id,
            "name": r.name,
            "district": r.district or "",
            "town": r.town or "",
            "url": url_for('main.store_details', store_id=r.id) if current_user.is_authenticated else url_for('auth.newlogin')
        } for r in restaurants],
        "meals": [{
            "id": m.id,
            "name": m.productname,
            "price": f"M{m.price:.2f}",
            "image": m.pictures or url_for('static', filename='css/images/default.png'),
            "store": m.store.name if m.store else "",
            "url": url_for('main.viewproduct', product_id=m.id) if current_user.is_authenticated else url_for('auth.newlogin')
        } for m in meals]
    })

@main.route("/robots.txt")
def robots_txt():
    """Serve robots.txt from the templates folder via direct rendering."""
    return current_app.response_class(
        render_template('robots.txt'),
        mimetype='text/plain'
    )

@main.route("/sitemap.xml")
def sitemap_xml():
    """Generate dynamic XML sitemap."""
    from xml.sax.saxutils import escape as xml_escape
    
    pages = []
    
    # Static pages
    base_url = url_for('main.landing', _external=True)
    pages.append({
        'loc': base_url,
        'changefreq': 'weekly',
        'priority': '1.0'
    })
    pages.append({
        'loc': url_for('main.restuarants', _external=True),
        'changefreq': 'daily',
        'priority': '0.9'
    })
    pages.append({
        'loc': url_for('main.about', _external=True),
        'changefreq': 'monthly',
        'priority': '0.5'
    })
    pages.append({
        'loc': url_for('main.privacy_policy', _external=True),
        'changefreq': 'monthly',
        'priority': '0.3'
    })
    pages.append({
        'loc': url_for('main.terms_conditions', _external=True),
        'changefreq': 'monthly',
        'priority': '0.3'
    })
    
    # Auth pages
    pages.append({
        'loc': url_for('auth.register', _external=True),
        'changefreq': 'monthly',
        'priority': '0.6'
    })
    pages.append({
        'loc': url_for('auth.newlogin', _external=True),
        'changefreq': 'monthly',
        'priority': '0.6'
    })
    pages.append({
        'loc': url_for('auth.registerstore', _external=True),
        'changefreq': 'monthly',
        'priority': '0.6'
    })
    
    # Active stores
    stores = Store.query.filter_by(is_active=True).all()
    for store in stores:
        pages.append({
            'loc': url_for('main.store_details', store_id=store.id, _external=True),
            'changefreq': 'daily',
            'priority': '0.8'
        })
    
    # Active meals
    meals = Product.query.filter_by(is_active=True).all()
    for meal in meals:
        pages.append({
            'loc': url_for('main.viewproduct', product_id=meal.id, _external=True),
            'changefreq': 'weekly',
            'priority': '0.7'
        })
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for page in pages:
        xml += '  <url>\n'
        xml += f'    <loc>{xml_escape(page["loc"])}</loc>\n'
        if page.get('lastmod'):
            xml += f'    <lastmod>{page["lastmod"]}</lastmod>\n'
        xml += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
        xml += f'    <priority>{page["priority"]}</priority>\n'
        xml += '  </url>\n'
    xml += '</urlset>'
    
    return current_app.response_class(xml, mimetype='application/xml')

@main.route("/", methods=["POST", "GET"])
def landing():
    ads = Ad.query.all()
    restaurants = Store.query.filter_by(is_active=True).order_by(func.random()).limit(6).all()
    meals = (
        Product.query
        .filter_by(is_active=True)
        .order_by(func.random())
        .all()
    )

    seo_defaults = {
        'title': 'SmartEats – Food Delivery in Maputsoe, Roma & Leribe | Lesotho',
        'description': 'SmartEats delivers fresh, hot meals from the best local restaurants in Maputsoe, Roma, and Leribe, Lesotho. Order online for fast food delivery to your door.',
        'keywords': 'food delivery Lesotho, online food ordering Maputsoe, restaurant delivery Roma, local food Leribe, pizza delivery Maputsoe, SmartEats, Lesotho food platform',
        'og_type': 'website',
        'canonical': url_for('main.landing', _external=True),
    }
    
    breadcrumbs = [
        {'name': 'Home', 'url': url_for('main.landing', _external=True)},
        {'name': 'SmartEats Lesotho – Food Delivery', 'url': url_for('main.landing', _external=True)},
    ]

    return render_template(
        'customer/landingpage.html',
        ads=ads,
        meals=meals,
        restaurants=restaurants,
        seo_defaults=seo_defaults,
        breadcrumbs=breadcrumbs,
        seo_organization=True
    )

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
    cart = Cart.query.filter_by(user_id=current_user.id, store_id=store_id).first()
    if not cart or not cart.cart_items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for('main.menu', page_num=1))

    # Prevent multiple pending orders
    existing_order = Order.query.filter_by(
        user_id=current_user.id, store_id=store_id, status='Pending'
    ).first()
    if existing_order:
        flash("You still have a pending order.", "warning")
        return redirect(url_for('main.myorders'))

    if not form.validate_on_submit():
        flash("Invalid submission.", "warning")
        return redirect(url_for('main.cart'))

    customer_phone = normalize_phone_number(form.payment_number.data)

    # -----------------------------
    # Delivery method handling
    # -----------------------------
    delivery_method = form.deliverymethod.data
    delivery_fee = 0
    customer_lat = None
    customer_lng = None
    location_accuracy = None

    if delivery_method == 'agent':
        # -----------------------------
        # Get customer coordinates & client fee (only for delivery)
        # -----------------------------
        try:
            customer_lat = float(request.form.get('latitude') or 0)
            customer_lng = float(request.form.get('longitude') or 0)
            client_fee = float(request.form.get('delivery_fee') or 0)
            location_accuracy = request.form.get('location_accuracy')
            location_accuracy = float(location_accuracy) if location_accuracy else None
        except (TypeError, ValueError):
            customer_lat = None
            customer_lng = None
            client_fee = 0

        if not customer_lat or not customer_lng:
            flash("Location access is required for delivery orders. Please enable location and try again.", "warning")
            return redirect(url_for('main.cart'))

        if not (-90 <= customer_lat <= 90 and -180 <= customer_lng <= 180):
            flash("Invalid map coordinates.", "warning")
            return redirect(url_for('main.cart'))

        if store.latitude is None or store.longitude is None:
            flash("This store has not set their delivery location yet. Please try pickup.", "warning")
            return redirect(url_for('main.cart'))

        if location_accuracy and location_accuracy > 1500:
            current_app.logger.warning(
                f"Low accuracy location | User:{current_user.id} Accuracy:{location_accuracy}m"
            )

        server_fee = calculate_delivery_fee(store.latitude, store.longitude, customer_lat, customer_lng)

        # Compare against client fee (allow small rounding diff)
        if abs(server_fee - client_fee) > 1:
            current_app.logger.warning(
                f"Fee mismatch | User:{current_user.id} Client:{client_fee} Server:{server_fee}"
            )
            flash("Delivery fee mismatch detected.", "danger")
            return redirect(url_for('main.cart'))

        delivery_fee = server_fee
        drop_location = form.drop_address.data or 'Delivery'
    else:
        drop_location = 'pickup'

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
        customer_lng=customer_lng,
        customer_phone=customer_phone,
        location_accuracy_m=location_accuracy,
        deliveryfee=delivery_fee,
        location=drop_location
    )

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

    db.session.add(neworder)
    db.session.flush()  # get neworder.id before commit

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
                quantity=item.quantity,
                notes=item.notes or ''
            )
            db.session.add(order_item)
            total_amount += item.product.price * item.quantity

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
    # NOTE: deliveryfee was already set at order creation (line 587) — do NOT overwrite with total
    print(f"[DEBUG] Total order amount (including delivery): {total_amount}")
    print(f"[DEBUG] Calculated delivery fee: {delivery_fee}")
    print(f"[DEBUG] Stored delivery fee on order: {neworder.deliveryfee}")

    # -----------------------------
    # Clear Cart
    # -----------------------------
    CartItem.query.filter_by(cart_id=cart.id).delete()
    db.session.commit()
    cart_cache.clear_cache(current_user.id)

    # -----------------------------
    # Notify Store via SocketIO
    # -----------------------------
    socketio.emit(
        'new_order',
        {
            'order_id': neworder.id,
            'customer_email': current_user.email,
            'delivery_fee': delivery_fee,
            'delivery_method': form.deliverymethod.data,
            'location': neworder.location,
            'created_at': neworder.create_at.strftime('%Y-%m-%d %H:%M')
        },
        room=f'store_{store.id}'
    )

    # Play sound notification for the store dashboard
    try:
        from application.notification import notify_store
        notify_store(store.id)
    except Exception:
        pass

    flash("Order successfully placed.", "success")
    return redirect(url_for('main.myorders'))


@main.route('/myorders')
@login_required
def myorders():
    # Show ALL active orders for this customer (across any store)
    ACTIVE_STATUSES = [
        "Pending", "Processing", "Accepted",
        "Approved", "Ready", "Out for Delivery"
    ]

    orders = (
        Order.query
        .filter_by(user_id=current_user.id)
        .filter(Order.status.in_(ACTIVE_STATUSES))
        .options(joinedload(Order.order_items))
        .order_by(Order.create_at.desc())
        .all()
    )

    return render_template('customer/myorder.html', order=orders)

@main.route('/order_history')
@login_required
def order_history():
    # Show ALL past orders (completed, delivered, collected, cancelled)
    FINAL_STATUSES = [
        "Completed", "Delivered", "Collected", "Cancelled"
    ]

    past_orders = (
        Order.query
        .filter_by(user_id=current_user.id)
        .filter(Order.status.in_(FINAL_STATUSES))
        .options(joinedload(Order.order_items))
        .order_by(Order.create_at.desc())
        .all()
    )

    return render_template(
        'customer/updated_orderhistory.html',
        past_orders=past_orders
    )


@main.route('/track_order/<int:order_id>')
@login_required
def track_order(order_id):
    """Customer live tracking page — shows progress bar and live map for Out for Delivery."""
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    return render_template('customer/track_order.html', order=order)


@main.route('/api/delivery/<int:order_id>')
def api_delivery_public(order_id):
    """Public API for customers to poll driver location."""
    delivery_obj = Delivery.query.filter_by(order_id=order_id).first()
    if delivery_obj:
        return jsonify(delivery_obj.to_dict())
    return jsonify({"error": "Delivery not found"}), 404


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
        cart_count = cart.total_items()
        cart_total = cart.total_amount()
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
    return jsonify(success=True, cart_count=cart.total_items(),
                   cart_total=cart.total_amount())

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
@main.route('/update_cart_item_notes', methods=['POST'])
@login_required
def update_cart_item_notes():
    """Save per-item notes/special instructions."""
    data = request.get_json() or {}
    item_id = data.get('item_id')
    notes = data.get('notes', '')

    if not item_id:
        return jsonify(success=False), 400

    item = CartItem.query.get(item_id)
    if not item:
        return jsonify(success=False, error='Item not found'), 404

    # Ensure item belongs to current user's cart
    cart = Cart.query.get(item.cart_id)
    if not cart or cart.user_id != current_user.id:
        return jsonify(success=False, error='Not authorized'), 403

    item.notes = notes
    db.session.commit()
    return jsonify(success=True)


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

@main.route("/api/delivery_fee")
@login_required
def api_delivery_fee():
    """Calculate delivery fee based on customer location and current store."""
    store_id = session.get('store_id')
    if not store_id:
        return jsonify({"error": "No store selected"}), 400

    store = Store.query.get(store_id)
    if not store:
        return jsonify({"error": "Store not found"}), 404

    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)

    if not lat or not lng:
        return jsonify({"fee": None, "message": "Location not available"})

    if store.latitude is None or store.longitude is None:
        return jsonify({"fee": None, "message": "Store location not set"})

    fee = calculate_delivery_fee(store.latitude, store.longitude, lat, lng)
    return jsonify({"fee": fee})


@main.route('/stores')
def restuarants():
    form2 = Search()
    selected_location = request.args.get('location', '').strip()
    open_now = request.args.get('open_now', '').strip()

    if current_user.is_authenticated:
        user_district = current_user.district
        user_town = current_user.town

        rank_case = case(
            (Store.town == user_town, 0),
            (Store.district == user_district, 1),
            else_=2
        )

        query = Store.query.filter(Store.is_active == True)

        # Filter by location (town or district)
        if selected_location:
            query = query.filter(
                or_(
                    Store.town.ilike(f"%{selected_location}%"),
                    Store.district.ilike(f"%{selected_location}%")
                )
            )

        stores = query.order_by(
            rank_case,
            Store.name.asc()
        ).all()
    else:
        query = Store.query.filter(Store.is_active == True)

        # Filter by location (town or district)
        if selected_location:
            query = query.filter(
                or_(
                    Store.town.ilike(f"%{selected_location}%"),
                    Store.district.ilike(f"%{selected_location}%")
                )
            )

        stores = query.order_by(Store.name.asc()).all()

    # Filter by open status
    if open_now == '1':
        stores = [s for s in stores if is_store_open(s.openinghours)]

    seo_defaults = {
        'title': f'Restaurants in {selected_location} – SmartEats Food Delivery Lesotho' if selected_location else 'Browse Restaurants – SmartEats Food Delivery Lesotho',
        'description': f'Discover the best local restaurants in {selected_location}, Lesotho. Order fresh meals online for fast delivery.' if selected_location else 'Browse all restaurants on SmartEats. Order from the best local food spots in Maputsoe, Roma, and Leribe, Lesotho.',
        'keywords': f'restaurants {selected_location}, food delivery {selected_location}, SmartEats' if selected_location else 'restaurants Lesotho, food delivery, local restaurants, SmartEats',
        'canonical': url_for('main.restuarants', location=selected_location if selected_location else None, open_now=open_now if open_now else None, _external=True),
    }
    
    breadcrumbs = [
        {'name': 'Home', 'url': url_for('main.landing', _external=True)},
        {'name': 'Restaurants', 'url': url_for('main.restuarants', _external=True)},
    ]
    if selected_location:
        breadcrumbs.append({'name': selected_location, 'url': url_for('main.restuarants', location=selected_location, _external=True)})

    return render_template('customer/restuarants.html', stores=stores, form2=form2,
                           is_store_open=is_store_open, selected_location=selected_location, open_now=open_now,
                           seo_defaults=seo_defaults, breadcrumbs=breadcrumbs)

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

    total_count = cart.total_items() if cart else 0
    total_amount = cart.total_amount() if cart else 0.0

    seo_defaults = {
        'title': f'{restuarant.name} – Restaurant in {restuarant.town or restuarant.district} | SmartEats Lesotho',
        'description': f'Order from {restuarant.name} in {restuarant.town or restuarant.district}, Lesotho. Browse their menu and get fresh food delivered fast.',
        'keywords': f'{restuarant.name}, restaurant {restuarant.town or restuarant.district}, food delivery, {restuarant.name} menu, SmartEats',
        'canonical': url_for('main.store_details', store_id=restuarant.id, _external=True),
    }
    
    breadcrumbs = [
        {'name': 'Home', 'url': url_for('main.landing', _external=True)},
        {'name': 'Restaurants', 'url': url_for('main.restuarants', _external=True)},
        {'name': restuarant.name, 'url': url_for('main.store_details', store_id=restuarant.id, _external=True)},
    ]

    return render_template(
        "customer/restuarantdetails.html",
        restuarant=restuarant,
        total_count=total_count,
        total_amount=total_amount,
        formpharm=formpharm,
        registered_for=registered_for,
        seo_defaults=seo_defaults,
        breadcrumbs=breadcrumbs
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
    
    seo_defaults = {
        'title': f'{product.productname} – {store.name} | SmartEats Lesotho',
        'description': f'Order {product.productname} from {store.name} in {store.town or store.district}, Lesotho. M{product.price:.2f}. Fresh, delicious food delivered fast.',
        'keywords': f'{product.productname}, {store.name}, food delivery, {product.productname} price, SmartEats',
        'og_type': 'product',
        'product_price': f'{product.price:.2f}',
        'image': product.pictures or url_for('static', filename='css/images/default.png', _external=True),
        'canonical': url_for('main.viewproduct', product_id=product.id, _external=True),
    }
    
    breadcrumbs = [
        {'name': 'Home', 'url': url_for('main.landing', _external=True)},
        {'name': 'Restaurants', 'url': url_for('main.restuarants', _external=True)},
        {'name': store.name, 'url': url_for('main.store_details', store_id=store.id, _external=True)},
        {'name': product.productname, 'url': url_for('main.viewproduct', product_id=product.id, _external=True)},
    ]

    return render_template('customer/updated_productview.html', product=product, store=store, seo_defaults=seo_defaults, breadcrumbs=breadcrumbs)

# ---------------- SEARCH ----------------
@main.route("/search/<int:page_num>", methods=["POST", "GET"])
@login_required
def search(page_num=1):
    form2 = Search()
    store_id = session.get("store_id")
    if not store_id:
        flash("Please select a store first", "warning")
        return redirect(url_for("main.restuarants"))

    mystore = Store.query.get_or_404(store_id)

    if form2.validate_on_submit():
        search_term = form2.keyword.data.strip()

        # Filter by current store AND search term
        products = Product.query.filter(
            Product.store_id == store_id,
            Product.is_active == True,
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

        # Get categories for the menu template
        categories = Category.query.filter_by(store_id=mystore.id, is_active=True).all()

        # Cart count
        cart = Cart.query.filter_by(user_id=current_user.id, store_id=mystore.id).first()
        total_count = sum(item.quantity for item in cart.cart_items) if cart else 0

        # Populate store choices for the form
        formpharm = Set_StoreForm()
        formpharm.store.choices = [(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]

        return render_template(
            "customer/updated_menu.html",
            products=current_products,
            form2=form2,
            formpharm=formpharm,
            form=CartlistForm(),
            page_num=page_num,
            store=mystore,
            total_pages=total_pages,
            categories=categories,
            selected_category_id=None,
            total_count=total_count,
            user=current_user,
            search_term=search_term
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
            search_term=search_term,
            is_store_open=is_store_open
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
        total_pages=total_pages,
        is_store_open=is_store_open
    )

@main.route('/terms')
def terms_conditions():
    return render_template("customer/terms.html")

@main.route('/privacy policy')
def privacy_policy():
    return render_template('customer/policy.html')

@main.route('/increment_cart_item/<int:item_id>', methods=['POST'])
@login_required
def increment_cart_item(item_id):
    item = CartItem.query.get_or_404(item_id)

    # Make sure this item belongs to the current user's cart
    cart = Cart.query.get(item.cart_id)
    if not cart or cart.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Forbidden'}), 403

    # Increment quantity
    item.quantity += 1
    db.session.commit()

    # Recalculate cart total using the model method (handles custom meals)
    cart_total = cart.total_amount()

    return jsonify({
        'success': True,
        'new_quantity': item.quantity,
        'cart_total': cart_total
    })


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

    # Recalculate cart total using the model method (handles custom meals)
    cart_total = cart.total_amount()

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
