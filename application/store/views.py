import os
import secrets
from datetime import datetime, timedelta

import plotly.graph_objs as go # type: ignore
import plotly.offline as plot #type: ignore
from PIL import Image
from flask import current_app # type: ignore
from flask import render_template, redirect, url_for, session, request, flash
from flask_bcrypt import Bcrypt
from flask_login import login_required, current_user, logout_user, LoginManager # type: ignore
from sqlalchemy import func, extract, case,and_
from sqlalchemy.exc import IntegrityError

from datetime import datetime, timedelta
import plotly.graph_objs as go
import plotly.io as pio

import cloudinary
from cloudinary.uploader import upload

from . import store
from ..forms import addmore, removefromcart, ProductForm, \
    updatestatusform, update, CartlistForm, Search, addstaffform, Set_StoreForm, UpdatePharmacyForm, updateorderpickup, deliveryregistrationform
from ..models import (User, Product, Sales, DeliveryGuy,
                      Order, Cart, OrderItem, db, Store,
                      Notification, Staff, Administrater)
from ..utils.notification import create_notification
from application import cache
from datetime import datetime
from application.notification import notify_customer
from application.auth.views import send_sound
mypharmacy_product = Store.products
mypharmacy_orders = Store.orders
bcrypt = Bcrypt()



def save_product_picture(file):
    # Set the desired size for resizing
    size = (300, 300)

    # Generate a random hex string for the filename
    random_hex = secrets.token_hex(9)

    # Get the file extension
    _, f_ex = os.path.splitext(file.filename)

    # Generate the final filename (random + extension)
    post_img_fn = random_hex + f_ex

    # Define the path to save the file (UPLOAD_PRODUCTS should be configured in your Flask app)
    post_image_path = os.path.join(current_app.root_path, current_app.config['UPLOAD_PRODUCTS'], post_img_fn)

    try:
        # Open the image
        img = Image.open(file)

        # Resize the image to fit within the size (thumbnail)
        img.thumbnail(size)

        # Save the resized image
        img.save(post_image_path)

        return post_img_fn  # Return the filename to store in the database
    except Exception as e:
        # If an error occurs during image processing, handle it
        print(f"Error saving image: {e}")
        return None

def upload_to_cloudinary(file, folder='products'):
    result = upload(
        file,
        folder=folder,
        use_filename=True,
        unique_filename=True,
        resource_type='image',
        transformation=[
            {'width': 200, 'height': 200, 'crop': 'fill'}
            ]
    )
    return result


login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'auth.newlogin'



@login_manager.user_loader
def load_user(user_id):
    user_type = session.get('user_type')
    if user_type == 'store':
        if Store.query.get(int(user_id)):
            return Store.query.get(int(user_id))
        else:
            return Staff.query.get(int(user_id))
    elif user_type == 'customer':
        return User.query.get(int(user_id))
    elif user_type == 'delivery_guy':
        return DeliveryGuy.query.get(int(user_id))
    elif user_type == 'administrator':
        return Administrater.query.get(int(user_id))
    return None



@store.route('/adminpage', methods=["POST", "GET"])
@login_required
def adminpage():
    if current_user.email != session.get('email'):
        flash('You are not authorised to see contents on this page.')
        logout_user()
        return redirect(url_for('main.newlogin'))

    mypharmacy = Store.query.get_or_404(current_user.id)

    # Notifications
    unread_notifications = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).all()

    count = len(unread_notifications)

    today = datetime.today()
    current_month, current_year = today.month, today.year

    start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
    end_of_month = next_month - timedelta(seconds=1)
    start_of_year = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    end_of_year = today.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)

    store_id = session.get('store_id')

    # Aggregate sales
    sales_query = db.session.query(
        func.sum(case((func.date(Sales.date_) == today.date(), Sales.price * Sales.quantity), else_=0)).label('daily'),
        func.sum(case(
            ((Sales.date_ >= start_of_month) & (Sales.date_ <= end_of_month), Sales.price * Sales.quantity),
            else_=0
        )).label('monthly'),
        func.sum(case(
            ((Sales.date_ >= start_of_year) & (Sales.date_ <= end_of_year), Sales.price * Sales.quantity),
            else_=0
        )).label('annual')
    ).filter(Sales.store_id == store_id).first()

    total_daily_sales = float(sales_query.daily or 0)
    total_monthly_sales = float(sales_query.monthly or 0)
    total_annual_sales = float(sales_query.annual or 0)

    # Pending orders
    pending_orders = Order.query.filter(
        extract('month', Order.create_at) == current_month,
        extract('year', Order.create_at) == current_year,
        Order.status == "Pending",
        Order.store_id == mypharmacy.id
    ).count()

    # FIXED DAILY DATA FOR CHART
    daily_dates = []
    daily_totals = []

    # Loop through each day of the current month
    current_day = start_of_month
    while current_day <= today:
        next_day = current_day + timedelta(days=1)

        total = db.session.query(
            func.sum(Sales.price * Sales.quantity)
        ).filter(
            Sales.store_id == store_id,
            Sales.date_ >= current_day,
            Sales.date_ < next_day
        ).scalar() or 0

        daily_dates.append(current_day.strftime("%Y-%m-%d"))
        daily_totals.append(float(total))

        current_day = next_day

    daily_data = {
        "dates": daily_dates,
        "totals": daily_totals
    }

    return render_template(
        'store/updated_dashboard.html',
        total_sales=total_monthly_sales,
        total_annual_sales=total_annual_sales,
        total_daily_sales=total_daily_sales,
        total_monthly_sales=total_monthly_sales,
        store=mypharmacy,
        pending_orders=pending_orders,
        unread_notifications=unread_notifications,
        count=count,
        daily_data=daily_data     # <-- FIXED
    )



@store.route('/search', methods=['POST', 'GET'])
@login_required
#@role_required('Store')
def search():
    mypharmacy = Store.query.get(current_user.id)
    form = CartlistForm()
    form1 = updateorderpickup()
    form2 = Search()
    keyword = form2.keyword.data
    item_picture = 'dfdfdf.jpg'
    total_count = 0
    count = Cart.query.filter_by(user_id=current_user.id).first()
    if count:
        total_count = sum(item.quantity for item in count.cart_items)
    products = Order.query.filter(Order.store_id == mypharmacy.id,
        Order.order_id.like(f'%{keyword}%')|
        Order.location.like(f'%{keyword}%') |
        Order.user_id.like(f'%{keyword}%') |
        Order.payment.like(f'%{keyword}%') |
        Order.user_email.like(f'%{keyword}%')
                            ).all()

    return render_template('store/updated_orders.html', form=form, item_picture=item_picture,
                           total_count=total_count, products=products, form2=form2, form1=form1)

@store.route('/updateproduct/<int:item_id>', methods=['GET', 'POST'])
@login_required
#@role_required('Store')
def updateproduct(item_id):
    mypharmacy = Store.query.get_or_404(current_user.id)
    unread_notifications = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).all()
    count = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).count()

    form = update()
    if form.validate_on_submit():

        product = Product.query.filter_by(id=item_id, store_id=mypharmacy.id).first()
        if product:
            product.productname = form.newname.data
            product.description = form.newdescription.data
            product.category = form.category.data
            product.price = form.newprice.data

        try:
            db.session.commit()
            return redirect(url_for('store.products'))
        except IntegrityError:
            db.session.rollback()

            return redirect(url_for('store.products'))
    store_id = session.get('store_id')

    return render_template('store/updated_updateproduct.html', form=form, item_id=item_id,
                           count=count, unread_notifications=unread_notifications, store=store)

@store.route('/ready_orders')
@login_required
def ready_orders():
    form1 = updateorderpickup()
    mypharmacy = Store.query.get_or_404(current_user.id)
    unread_notifications = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).all()
    count = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).count()

    form = updatestatusform()
    readyorders = Order.query.filter(Order.status=="Ready ", Order.store_id == current_user.id).all()
    return render_template('store/readyorder.html',form=form, readyorders=readyorders, store=mypharmacy,
                        unread_notifications=unread_notifications, count=count, form1=form1)

@store.route('/Orders on Delivery')
@login_required
def orders_on_delivery():
    mypharmacy = Store.query.get_or_404(current_user.id)
    unread_notifications = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).all()
    count = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).count()

    form = updatestatusform()
    ondelivery = Order.query.filter(Order.status == "Out for Delivery", Order.store_id == current_user.id).all()
    return render_template('store/ondelivery.html', form=form, count=count, ondelivery=ondelivery,
                           store=mypharmacy, unread_notifications=unread_notifications)

@cache.memoize(timeout=120)
@store.route('/ActiveOrders')
@login_required
def ActiveOrders():
    mypharmacy = Store.query.get_or_404(current_user.id)
    unread_notifications = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).all()
    count = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).count()

    form = updatestatusform()
    form1 = updateorderpickup()
    orders = Order.query.filter(Order.status=="Pending", Order.store_id == current_user.id).all()
    approved_order = Order.query.filter(Order.status=="Approved", Order.store_id == current_user.id).all()
    store_id = session.get('store_id')
    readyorder = Order.query.filter(Order.status=="Ready ", Order.store_id == current_user.id).all()

    return render_template("store/updated_orders.html", readyorder=readyorder,
                           form=form, orders=orders, approved_order=approved_order,
                           unread_notifications=unread_notifications, store=store, count=count, form1=form1)


@store.route('/delivered')
@login_required
def delivered_orders():
    mypharmacy = Store.query.get_or_404(current_user.id)
    # Notifications
    unread_notifications = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).all()
    
    count = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).count()

    store_id = session.get('store_id')
    store = Store.query.get_or_404(store_id)    
    form = updatestatusform()

    # Fetch Delivered or Collected orders
    orders = Order.query.filter(
        Order.status.in_(["Delivered", "Collected"]),
        Order.store_id == current_user.id
    ).order_by(Order.create_at.desc()).all()

    return render_template(
        "store/updated_Delivered.html",
        form=form,
        orders=orders,
        unread_notifications=unread_notifications,
        store=store,
        count=count
    )

@store.route('/cancelled')
@login_required
#@role_required('Store')
def cancelled_orders():
    store_id = session.get('store_id')
    store = Store.query.get_or_404(store_id)
    mypharmacy = Store.query.get_or_404(current_user.id)
    unread_notifications = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).all()
    count = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).count()

    form = updatestatusform()
    orders = Order.query.filter(Order.status=="Cancelled", Order.store_id == current_user.id).all()
    #total = sum(item.product.price * item.quantity for item in orders.order_items)
    return render_template("store/updated_cancelled.html", form=form, orders=orders,
                           unread_notifications=unread_notifications,store=store, count=count)


@store.route('updatestore', methods=["POST", "GET"])
@login_required
def updatestore():
    mypharmacy = Store.query.get_or_404(current_user.id)
    unread_notifications = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).all()
    count = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).count()

    updateForm = UpdatePharmacyForm()
    store_id = session.get('store_id')
    store = Store.query.get_or_404(store_id)
    if updateForm.validate_on_submit():
        store = Store.query.get_or_404(current_user.id)
        store.ecocash_short_code = updateForm.ecocashcode.data
        store.mpesa_shortcode = updateForm.mpesacode.data
        db.session.commit()
        flash('Store Details added...')
        return redirect(url_for('store.adminpage'))
    else:
        flash('')

    return render_template('store/updatedetails.html', form=updateForm,
                           unread_notifications=unread_notifications, count=count, store=store)


@store.route('/orders/updatestatus/<int:order_id>', methods=['POST'])
@login_required
def updatestatus(order_id):
    form = updatestatusform(request.form)
    form1 = updateorderpickup(request.form)  # explicitly use form from request
    if form.validate_on_submit() or form1.validate_on_submit():
        order = Order.query.get_or_404(order_id)
        if order.location == "pickup":
            old_status = order.status
            new_status = form1.status.data
        else:    
            old_status = order.status
            new_status = form.status.data

        if old_status == new_status:
            flash('Status is already set to this value.')
            return redirect(url_for('store.ActiveOrders'))

        order.status = new_status

        try:
            db.session.commit()
            # 🔔 Notifications
            message = f"Order #{order.order_id} status changed from {old_status} to {new_status}"
            # Notify customer
            create_notification(user_type='customer', user_id=order.user_id, message=message)
            try:
                notify_customer(order.user_id)
            except Exception:
                current_app.logger.debug("notify_customer failed during login (admin).")
            send_sound(order.user_id, sound_name="update_order")

            # Also notify store dashboard if needed
            create_notification(user_type='store', user_id=order.store_id, message=message)

            flash('Order status updated successfully')
            return redirect(url_for('store.ActiveOrders'))

        except IntegrityError:
            db.session.rollback()
            flash("Failed to update Order Status.")
            return redirect(url_for('store.ActiveOrders'))

    flash("Invalid status update form.")
    return redirect(url_for('store.ActiveOrders'))


@store.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('auth.newlogin'))


@cache.memoize(timeout=300)
@store.route('/addproducts', methods=["POST", "GET"])
@login_required
#@role_required('Store')
def addproducts():
    form = ProductForm()
    mypharmacy = Store.query.get_or_404(current_user.id)
    unread_notifications = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).all()
    count = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).count()

    if request.method == 'POST':
        if form.is_submitted():
            if form.validate_on_submit:
                product = Product(productname=form.product_name.data, price=form.product_price.data,
                                  description=form.product_description.data
                                  )
                file = form.product_pictures.data
                print(current_app.config['USE_CLOUDINARY'])
                if current_app.config['USE_CLOUDINARY']:
                    print("SAving to cloudinary.")
                    upload_result = upload_to_cloudinary(file)
                    image_url = upload_result['secure_url'] 
                    product.pictures = image_url
                else: 
                    print('Saving picture to sqlite db') 
                    _image = save_product_picture(file)
                    product.pictures = _image

                product.store_id = mypharmacy.id
                db.session.add(product)
                try:
                    db.session.commit()
                    cache.clear()
                    return redirect(url_for("store.products"))
                except IntegrityError:
                    flash('intergrity error', 'danger')
                    return redirect(url_for('store.addproducts'))
            else:
                flash("An error occurred")
        else:
            flash('form was not submitted successfully.try again later.')
    store_id = session.get('store_id')
    store = Store.query.get_or_404(store_id)    
    return render_template("store/updated_addProduct.html", form=form,
                            unread_notifications=unread_notifications, count=count, store=store)

@cache.memoize(timeout=300)
@store.route('/userorders/<int:order_id>', methods=['post', 'get'])
@login_required
#@role_required('Store')
def userorders(order_id):
    mypharmacy = Store.query.get_or_404(current_user.id)
    unread_notifications = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).all()
    count = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).count()

    store_id = session.get('store_id')
    store = Store.query.get_or_404(store_id) 
    cart = Cart.query.filter_by(user_id=current_user.id, store_id=current_user.id).first()
    user_order = Order.query.filter(Order.id==order_id, Order.store_id==store_id).first()
    total = 0.00
    if user_order:
        gross_total = sum(item.product.price * item.quantity for item in user_order.order_items)
        total=gross_total
    else:
        flash('Cant view details')
        return redirect(url_for('store.ActiveOrders'))
  
    return render_template('store/updated_vieworders.html', store=store, user_order=user_order,
                           unread_notifications=unread_notifications,total=total, count=count)


@cache.memoize(timeout=300)
@store.route('/products')
@login_required
def products():
    mypharmacy = Store.query.get(current_user.id)
    unread_notifications = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).all()
    count = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).count()

    form2 = removefromcart()
    form4 = Search()
    form3 = addmore()
    form = update()
    product = Product.query.filter(Product.store_id==mypharmacy.id).all()
    store_id = session.get('store_id')
    store = Store.query.get_or_404(store_id)
    return render_template('store/updated_products.html', product=product, form4=form4, form=form, 
                           store=store, count=count, form2=form2, unread_notifications=unread_notifications,form3=form3)


@cache.memoize(timeout=300)
@store.route('/remove_from_products/<int:item_id>', methods=['POST', 'GET'])
@login_required
def remove_product(item_id):
    product = Product.query.get_or_404(item_id)
    try:
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully.', 'success')
    except IntegrityError as e:
        db.session.rollback()
        flash('Cannot delete product: it is referenced in existing orders.', 'danger')

    return redirect(url_for('store.products'))



@store.route('/notifications/read/<int:notification_id>', methods=['POST','GET'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    notification.is_read = True
    db.session.commit()
    return redirect(url_for('store.adminpage'))

@store.route('/addstaff', methods=["post", "get"])
@login_required
def addstaff():
    form = addstaffform()
    store = Store.query.get_or_404(session.get('store_id'))

    unread_notifications = Notification.query.filter_by(
        user_type='store', user_id=store.id, is_read=False
    ).order_by(Notification.timestamp.desc()).all()
    count = Notification.query.filter_by(
        user_type='store', user_id=store.id, is_read=False
    ).order_by(Notification.timestamp.desc()).count()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        newstuff = Staff(names=form.names.data, email=form.email.data, role=form.role.data, password=hashed_password,
                         store=store)
        if newstuff:
            try:
                db.session.add(newstuff)
                db.session.commit()
                flash('New staff added successfully')
                return redirect(url_for('store.adminpage'))
            except IntegrityError:
                flash('There were some conflicts.')
                db.session.rollback()
                return redirect(url_for('store.addstaff'))
        else:
            flash('Could not add stuff member')
    return render_template('store/addstaff.html',
                           store=store,form=form, count=count, unread_notifications=unread_notifications)

@store.route('/register delivery', methods=["POST", "GET"])
@login_required
def register_delivery():
    form = deliveryregistrationform()  
    if request.method == "POST":
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        new_delivery = DeliveryGuy(names=form.names.data, email=form.email.data,
                                    password=hashed_password)
        db.session.add(new_delivery)
        try:
            db.session.commit()
            flash('Delivery agent registered successfully.')
            return redirect(url_for('store.adminpage'))
        except IntegrityError:
            db.session.rollback()
            flash('An integrity error occurred.')
            return redirect(url_for('store.register_delivery'))   
    return render_template('store/add_delivery.html', form=form)

@store.route('/vendor/analytics')
@login_required
def vendor_analytics():
    store_id = session.get('store_id')
    store = Store.query.get_or_404(store_id)
    if store.id != current_user.id:
        return "Unauthorized", 403

    # Date filters (defaults to last 7 days)
    end_date = request.args.get('end_date', datetime.utcnow().date())
    start_date = request.args.get('start_date', (datetime.utcnow() - timedelta(days=7)).date())

    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    period_length = (end_date - start_date).days or 1
    prev_start = start_date - timedelta(days=period_length)
    prev_end = start_date

    def sales_query(start, end):
        return db.session.query(func.sum(Sales.price * Sales.quantity))\
            .filter(Sales.store_id == store_id)\
            .filter(func.date(Sales.date_).between(start, end))\
            .scalar() or 0

    total_sales = sales_query(start_date, end_date)
    prev_sales = sales_query(prev_start, prev_end)
    sales_change = round(((total_sales - prev_sales) / prev_sales * 100), 2) if prev_sales else 100

    total_orders = db.session.query(func.count(Sales.order_id.distinct()))\
        .filter(Sales.store_id == store_id)\
        .filter(func.date(Sales.date_).between(start_date, end_date))\
        .scalar() or 1
    avg_order_value = total_sales / total_orders

    prev_orders = db.session.query(func.count(Sales.order_id.distinct()))\
        .filter(Sales.store_id == store_id)\
        .filter(func.date(Sales.date_).between(prev_start, prev_end))\
        .scalar() or 1
    prev_aov = prev_sales / prev_orders if prev_orders else 0
    aov_change = round(((avg_order_value - prev_aov) / prev_aov * 100), 2) if prev_aov else 100

    # ------------------ Sales Trend ------------------
    sales_trend = (
        db.session.query(func.date(Sales.date_), func.sum(Sales.price * Sales.quantity))
        .filter(Sales.store_id == store_id)
        .filter(func.date(Sales.date_).between(start_date, end_date))
        .group_by(func.date(Sales.date_))
        .order_by(func.date(Sales.date_))
        .all()
    )

    dates, revenues = zip(*sales_trend) if sales_trend else ([], [])
    # Fix: convert to strings if necessary
    dates = [d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d) for d in dates]

    # ------------------ Product and Category ------------------
    product_sales = (
        db.session.query(Product.productname, func.sum(Sales.price * Sales.quantity))
        .join(Sales, Sales.product_id == Product.id)
        .filter(Sales.store_id == store_id)
        .filter(func.date(Sales.date_).between(start_date, end_date))
        .group_by(Product.productname)
        .order_by(func.sum(Sales.price * Sales.quantity).desc())
        .limit(5)
    )
    prod_names, prod_revenues = zip(*product_sales) if product_sales else ([], [])

    category_sales = (
        db.session.query(Product.category, func.sum(Sales.price * Sales.quantity))
        .join(Sales, Sales.product_id == Product.id)
        .filter(Sales.store_id == store_id)
        .filter(func.date(Sales.date_).between(start_date, end_date))
        .group_by(Product.category)
        .all()
    )
    categories, cat_revenue = zip(*category_sales) if category_sales else ([], [])

    # ------------------ Top Customers ------------------
    top_customers = (
        db.session.query(User.username, func.sum(Sales.price * Sales.quantity).label('spent'))
        .join(Sales, Sales.user_id == User.id)
        .filter(Sales.store_id == store_id)
        .filter(func.date(Sales.date_).between(start_date, end_date))
        .group_by(User.username)
        .order_by(func.sum(Sales.price * Sales.quantity).desc())
        .limit(5)
        .all()
    )

    # ------------------ Plotly Charts ------------------
    import plotly.graph_objs as go
    import plotly.io as pio

    trend_fig = go.Figure([go.Scatter(x=dates, y=revenues, mode='lines+markers', name='Revenue')])
    trend_fig.update_layout(title='Sales Over Time', xaxis_title='Date', yaxis_title='Revenue (M)', template='plotly_white')

    prod_fig = go.Figure([go.Bar(x=prod_names, y=prod_revenues, marker_color='green')])
    prod_fig.update_layout(title='Top 5 Products by Revenue', xaxis_title='Product', yaxis_title='Revenue (M)', template='plotly_white')

    cat_fig = go.Figure([go.Pie(labels=categories, values=cat_revenue)])
    cat_fig.update_layout(title='Sales by Category', template='plotly_white')

    # ------------------ Hourly, Weekday, Monthly ------------------
    hourly_sales = (
        db.session.query(func.extract('hour', Sales.date_), func.sum(Sales.price * Sales.quantity))
        .filter(Sales.store_id == store_id)
        .filter(func.date(Sales.date_).between(start_date, end_date))
        .group_by(func.extract('hour', Sales.date_))
        .order_by(func.extract('hour', Sales.date_))
        .all()
    )

    weekday_sales = (
        db.session.query(func.extract('dow', Sales.date_), func.sum(Sales.price * Sales.quantity))
        .filter(Sales.store_id == store_id)
        .filter(func.date(Sales.date_).between(start_date, end_date))
        .group_by(func.extract('dow', Sales.date_))
        .order_by(func.extract('dow', Sales.date_))
        .all()
    )

    monthly_sales = (
        db.session.query(func.extract('month', Sales.date_), func.sum(Sales.price * Sales.quantity))
        .filter(Sales.store_id == store_id)
        .group_by(func.extract('month', Sales.date_))
        .order_by(func.extract('month', Sales.date_))
        .all()
    )

    hourly_fig = go.Figure([go.Bar(x=[int(h) for h, _ in hourly_sales], y=[r for _, r in hourly_sales])])
    hourly_fig.update_layout(title='Hourly Sales Distribution', xaxis_title='Hour', yaxis_title='Revenue', template='plotly_white')

    weekday_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    weekday_fig = go.Figure([go.Bar(
        x=[weekday_names[int(w)] for w, _ in weekday_sales],
        y=[r for _, r in weekday_sales],
        marker_color='orange'
    )])
    weekday_fig.update_layout(title='Sales by Weekday', xaxis_title='Day', yaxis_title='Revenue', template='plotly_white')

    monthly_fig = go.Figure([go.Scatter(
        x=[int(m) for m, _ in monthly_sales],
        y=[r for _, r in monthly_sales],
        mode='lines+markers',
        line=dict(color='purple')
    )])
    monthly_fig.update_layout(title='Monthly Sales Trend', xaxis_title='Month', yaxis_title='Revenue', template='plotly_white')

    # ------------------ Customer Behavior ------------------
    repeat_customers = (
        db.session.query(User.username, func.count(Sales.order_id.distinct()).label('orders'))
        .join(Sales, Sales.user_id == User.id)
        .filter(Sales.store_id == store_id)
        .group_by(User.username)
        .having(func.count(Sales.order_id.distinct()) > 1)
        .order_by(func.count(Sales.order_id.distinct()).desc())
        .all()
    )

    total_customers = db.session.query(func.count(User.id.distinct()))\
        .join(Sales, Sales.user_id == User.id)\
        .filter(Sales.store_id == store_id)\
        .scalar() or 1

    repeat_customer_count = len(repeat_customers)
    repeat_rate = round((repeat_customer_count / total_customers) * 100, 2)

    # ------------------ Product Performance ------------------
    product_contribution = (
        db.session.query(Product.productname, func.sum(Sales.price * Sales.quantity))
        .join(Sales, Sales.product_id == Product.id)
        .filter(Sales.store_id == store_id)
        .group_by(Product.productname)
        .order_by(func.sum(Sales.price * Sales.quantity).desc())
        .all()
    )

    # ------------------ Inventory Analytics ------------------
    total_sold = db.session.query(func.sum(Sales.quantity))\
        .filter(Sales.store_id == store_id)\
        .scalar() or 0
    total_stock = db.session.query(func.sum(Product.quantity))\
        .filter(Product.store_id == store_id)\
        .scalar() or 1
    stock_turnover_rate = round(total_sold / total_stock, 2)

    days = max(1, (end_date - start_date).days)
    avg_daily_sales = total_sold / days
    days_left = round(total_stock / avg_daily_sales, 1) if avg_daily_sales > 0 else "N/A"

    # ------------------ Render ------------------
    return render_template(
        'store/vendor_analystics.html',
        store=store,
        trend_graph=pio.to_html(trend_fig, full_html=False),
        product_graph=pio.to_html(prod_fig, full_html=False),
        category_graph=pio.to_html(cat_fig, full_html=False),
        hourly_graph=pio.to_html(hourly_fig, full_html=False),
        weekday_graph=pio.to_html(weekday_fig, full_html=False),
        monthly_graph=pio.to_html(monthly_fig, full_html=False),
        total_sales=total_sales,
        avg_order_value=round(avg_order_value, 2),
        sales_change=sales_change,
        aov_change=aov_change,
        repeat_rate=repeat_rate,
        repeat_customers=repeat_customers,
        product_contribution=product_contribution,
        stock_turnover_rate=stock_turnover_rate,
        days_left=days_left,
        start_date=start_date,
        end_date=end_date,
        top_customers=top_customers
    )

