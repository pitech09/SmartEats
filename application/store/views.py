import os
import secrets
from datetime import datetime, timedelta

from flask import (
    current_app, render_template, redirect, url_for,
    session, request, flash
)
from flask_bcrypt import Bcrypt
from flask_login import (
    login_required, current_user, logout_user, LoginManager
)
from sqlalchemy import func, extract, case
from sqlalchemy.exc import IntegrityError
from PIL import Image
import plotly.graph_objs as go
import plotly.io as pio
from cloudinary.uploader import upload

from . import store
from ..forms import (
    addmore, removefromcart, ProductForm, updatestatusform, update,
    CartlistForm, Search, addstaffform, UpdatePharmacyForm,
    updateorderpickup, deliveryregistrationform
)
from ..models import (
    User, Product, Sales, DeliveryGuy, Order, Cart,
    Store, Notification, Staff, Administrater, db
)
from ..utils.notification import create_notification
from application import cache
from application.notification import notify_customer
from application.auth.views import send_sound

bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'auth.newlogin'


# -------------------- Helper Functions -------------------- #

def save_product_picture(file, size=(300, 300)):
    """Save a product picture locally and return its filename."""
    try:
        random_hex = secrets.token_hex(9)
        _, f_ext = os.path.splitext(file.filename)
        filename = random_hex + f_ext
        path = os.path.join(current_app.root_path, current_app.config['UPLOAD_PRODUCTS'], filename)

        img = Image.open(file)
        img.thumbnail(size)
        img.save(path)
        return filename
    except Exception as e:
        print(f"Error saving image: {e}")
        return None


def upload_to_cloudinary(file, folder='products'):
    """Upload image to Cloudinary and return result dict."""
    result = upload(
        file,
        folder=folder,
        use_filename=True,
        unique_filename=True,
        resource_type='image',
        transformation=[{'width': 200, 'height': 200, 'crop': 'fill'}]
    )
    return result


def get_unread_notifications(user_type, user_id):
    """Fetch unread notifications for a user."""
    notifications = Notification.query.filter_by(
        user_type=user_type, user_id=user_id, is_read=False
    ).order_by(Notification.timestamp.desc()).all()
    return notifications, len(notifications)


def get_store():
    """Return the current user's store object."""
    store_id = session.get('store_id')
    return Store.query.get_or_404(store_id)


# -------------------- User Loader -------------------- #

@login_manager.user_loader
def load_user(user_id):
    user_type = session.get('user_type')
    if user_type == 'store':
        return Store.query.get(int(user_id)) or Staff.query.get(int(user_id))
    if user_type == 'customer':
        return User.query.get(int(user_id))
    if user_type == 'delivery_guy':
        return DeliveryGuy.query.get(int(user_id))
    if user_type == 'administrator':
        return Administrater.query.get(int(user_id))
    return None


# -------------------- Store Dashboard -------------------- #

@store.route('/adminpage', methods=["GET", "POST"])
@login_required
def adminpage():
    if current_user.email != session.get('email'):
        flash('Unauthorized access.')
        logout_user()
        return redirect(url_for('main.newlogin'))

    store_obj = get_store()
    notifications, notif_count = get_unread_notifications('store', store_obj.id)
    today = datetime.today()

    # Dates for sales calculations
    start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
    end_of_month = next_month - timedelta(seconds=1)
    start_of_year = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    end_of_year = today.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)

    # Aggregate sales
    sales_query = db.session.query(
        func.sum(case((func.date(Sales.date_) == today.date(), Sales.price * Sales.quantity), else_=0)).label('daily'),
        func.sum(case(((Sales.date_ >= start_of_month) & (Sales.date_ <= end_of_month), Sales.price * Sales.quantity), else_=0)).label('monthly'),
        func.sum(case(((Sales.date_ >= start_of_year) & (Sales.date_ <= end_of_year), Sales.price * Sales.quantity), else_=0)).label('annual')
    ).filter(Sales.store_id == store_obj.id).first()

    total_daily_sales = float(sales_query.daily or 0)
    total_monthly_sales = float(sales_query.monthly or 0)
    total_annual_sales = float(sales_query.annual or 0)

    # Pending orders this month
    pending_orders = Order.query.filter(
        extract('month', Order.create_at) == today.month,
        extract('year', Order.create_at) == today.year,
        Order.status == "Pending",
        Order.store_id == store_obj.id
    ).count()

    # Daily sales chart
    daily_dates, daily_totals = [], []
    current_day = start_of_month
    while current_day <= today:
        next_day = current_day + timedelta(days=1)
        total = db.session.query(func.sum(Sales.price * Sales.quantity)).filter(
            Sales.store_id == store_obj.id,
            Sales.date_ >= current_day,
            Sales.date_ < next_day
        ).scalar() or 0
        daily_dates.append(current_day.strftime("%Y-%m-%d"))
        daily_totals.append(float(total))
        current_day = next_day

    daily_data = {"dates": daily_dates, "totals": daily_totals}

    return render_template(
        'store/updated_dashboard.html',
        total_sales=total_monthly_sales,
        total_annual_sales=total_annual_sales,
        total_daily_sales=total_daily_sales,
        total_monthly_sales=total_monthly_sales,
        store=store_obj,
        pending_orders=pending_orders,
        unread_notifications=notifications,
        count=notif_count,
        daily_data=daily_data
    )


# -------------------- Product Routes -------------------- #

@cache.memoize(timeout=300)
@store.route('/products')
@login_required
def products():
    store_obj = get_store()
    notifications, notif_count = get_unread_notifications('store', store_obj.id)

    product_list = Product.query.filter_by(store_id=store_obj.id).all()
    form2, form3, form4, form = removefromcart(), addmore(), Search(), update()
    return render_template(
        'store/updated_products.html',
        product=product_list,
        form=form,
        form2=form2,
        form3=form3,
        form4=form4,
        store=store_obj,
        count=notif_count,
        unread_notifications=notifications
    )


@cache.memoize(timeout=300)
@store.route('/addproducts', methods=["POST", "GET"])
@login_required
def addproducts():
    store_obj = get_store()
    notifications, notif_count = get_unread_notifications('store', store_obj.id)
    form = ProductForm()

    if form.validate_on_submit():
        product = Product(
            productname=form.product_name.data,
            price=form.product_price.data,
            description=form.product_description.data,
            store_id=store_obj.id
        )
        file = form.product_pictures.data
        if current_app.config.get('USE_CLOUDINARY'):
            upload_result = upload_to_cloudinary(file)
            product.pictures = upload_result['secure_url']
        else:
            product.pictures = save_product_picture(file)

        db.session.add(product)
        try:
            db.session.commit()
            cache.clear()
            return redirect(url_for('store.products'))
        except IntegrityError:
            db.session.rollback()
            flash('Failed to add product.', 'danger')
            return redirect(url_for('store.addproducts'))

    return render_template('store/updated_addProduct.html', form=form, unread_notifications=notifications, count=notif_count, store=store_obj)


@store.route('/remove_from_products/<int:item_id>', methods=['POST', 'GET'])
@login_required
def remove_product(item_id):
    product = Product.query.get_or_404(item_id)
    try:
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Cannot delete product: referenced in existing orders.', 'danger')
    return redirect(url_for('store.products'))


# -------------------- Order Routes -------------------- #

def get_order_forms():
    return updatestatusform(), updateorderpickup()


@store.route('/ActiveOrders')
@login_required
@cache.memoize(timeout=120)
def ActiveOrders():
    store_obj = get_store()
    notifications, notif_count = get_unread_notifications('store', store_obj.id)
    form, form1 = get_order_forms()

    orders = Order.query.filter_by(store_id=store_obj.id, status="Pending").all()
    approved_orders = Order.query.filter_by(store_id=store_obj.id, status="Approved").all()
    ready_orders = Order.query.filter_by(store_id=store_obj.id, status="Ready ").all()

    return render_template(
        "store/updated_orders.html",
        readyorder=ready_orders,
        orders=orders,
        approved_order=approved_orders,
        unread_notifications=notifications,
        store=store_obj,
        count=notif_count,
        form=form,
        form1=form1
    )


@store.route('/orders/updatestatus/<int:order_id>', methods=['POST'])
@login_required
def updatestatus(order_id):
    form = updatestatusform(request.form)
    form1 = updateorderpickup(request.form)

    if form.validate_on_submit() or form1.validate_on_submit():
        order = Order.query.get_or_404(order_id)
        old_status = order.status
        new_status = form1.status.data if order.location == "pickup" else form.status.data

        if old_status == new_status:
            flash('Status already set.')
            return redirect(url_for('store.ActiveOrders'))

        order.status = new_status
        try:
            db.session.commit()
            message = f"Order #{order.order_id} status changed from {old_status} to {new_status}"
            create_notification('customer', order.user_id, message)
            create_notification('store', order.store_id, message)
            try:
                notify_customer(order.user_id)
            except Exception:
                current_app.logger.debug("notify_customer failed")
            send_sound(order.user_id, "update_order")
            flash('Order status updated successfully')
        except IntegrityError:
            db.session.rollback()
            flash("Failed to update order status.")
    else:
        flash("Invalid form submission.")
    return redirect(url_for('store.ActiveOrders'))


@store.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('auth.newlogin'))


# -------------------- Staff Management -------------------- #

@store.route('/addstaff', methods=["POST", "GET"])
@login_required
def addstaff():
    store_obj = get_store()
    notifications, notif_count = get_unread_notifications('store', store_obj.id)
    form = addstaffform()

    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        new_staff = Staff(
            names=form.names.data,
            email=form.email.data,
            role=form.role.data,
            password=hashed_password,
            store=store_obj
        )
        try:
            db.session.add(new_staff)
            db.session.commit()
            flash('New staff added successfully')
            return redirect(url_for('store.adminpage'))
        except IntegrityError:
            db.session.rollback()
            flash('Conflict occurred while adding staff.')

    return render_template('store/addstaff.html', form=form, store=store_obj, count=notif_count, unread_notifications=notifications)


@store.route('/register delivery', methods=["POST", "GET"])
@login_required
def register_delivery():
    form = deliveryregistrationform()
    store_obj = get_store()

    if request.method == "POST" and form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        new_delivery = DeliveryGuy(
            names=form.names.data,
            email=form.email.data,
            password=hashed_password
        )
        db.session.add(new_delivery)
        try:
            db.session.commit()
            flash('Delivery agent registered successfully.')
            return redirect(url_for('store.adminpage'))
        except IntegrityError:
            db.session.rollback()
            flash('Integrity error occurred while registering delivery agent.')

    return render_template('store/add_delivery.html', form=form)


# -------------------- Analytics -------------------- #

@store.route('/vendor/analytics')
@login_required
def vendor_analytics():
    store_obj = get_store()
    if store_obj.id != current_user.id:
        return "Unauthorized", 403

    # Date range
    end_date = request.args.get('end_date', datetime.utcnow().date())
    start_date = request.args.get('start_date', (datetime.utcnow() - timedelta(days=7)).date())
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    # Helper query
    def sales_query(start, end):
        return db.session.query(func.sum(Sales.price * Sales.quantity)).filter(
            Sales.store_id == store_obj.id,
            func.date(Sales.date_).between(start, end)
        ).scalar() or 0

    # Metrics
    period_days = (end_date - start_date).days or 1
    prev_start = start_date - timedelta(days=period_days)
    prev_end = start_date

    total_sales = sales_query(start_date, end_date)
    prev_sales = sales_query(prev_start, prev_end)
    sales_change = round(((total_sales - prev_sales) / prev_sales * 100), 2) if prev_sales else 100

    total_orders = db.session.query(func.count(Sales.order_id.distinct())).filter(
        Sales.store_id == store_obj.id,
        func.date(Sales.date_).between(start_date, end_date)
    ).scalar() or 1
    avg_order_value = total_sales / total_orders

    prev_orders = db.session.query(func.count(Sales.order_id.distinct())).filter(
        Sales.store_id == store_obj.id,
        func.date(Sales.date_).between(prev_start, prev_end)
    ).scalar() or 1
    prev_aov = prev_sales / prev_orders if prev_orders else 0
    aov_change = round(((avg_order_value - prev_aov) / prev_aov * 100), 2) if prev_aov else 100

    # Sales trends
    sales_trend = db.session.query(func.date(Sales.date_), func.sum(Sales.price * Sales.quantity)).filter(
        Sales.store_id == store_obj.id,
        func.date(Sales.date_).between(start_date, end_date)
    ).group_by(func.date(Sales.date_)).order_by(func.date(Sales.date_)).all()

    dates, revenues = zip(*sales_trend) if sales_trend else ([], [])
    dates = [d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d) for d in dates]

    trend_fig = go.Figure([go.Scatter(x=dates, y=revenues, mode='lines+markers')])
    trend_fig.update_layout(title='Sales Over Time', xaxis_title='Date', yaxis_title='Revenue', template='plotly_white')

    return render_template(
        'store/vendor_analystics.html',
        store=store_obj,
        trend_graph=pio.to_html(trend_fig, full_html=False),
        total_sales=total_sales,
        avg_order_value=round(avg_order_value, 2),
        sales_change=sales_change,
        aov_change=aov_change,
        start_date=start_date,
        end_date=end_date
    )
