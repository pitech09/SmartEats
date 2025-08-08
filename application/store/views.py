import os
import secrets
from datetime import datetime, timedelta

import plotly.graph_objs as go
import plotly.offline as plot
from PIL import Image
from flask import current_app
from flask import render_template, redirect, url_for, session, request, flash
from flask_bcrypt import Bcrypt
from flask_login import login_required, current_user, logout_user, LoginManager  # type: ignore
from sqlalchemy import func, extract
from sqlalchemy.exc import IntegrityError
import cloudinary
from cloudinary.uploader import upload

from . import store
from ..forms import addmore, removefromcart, ProductForm, \
    updatestatusform, update, CartlistForm, Search, addstaffform, Set_StoreForm, UpdatePharmacyForm, updateorderpickup
from ..models import (User, Product, Sales, DeliveryGuy,
                      Order, Cart, OrderItem, db, Store,
                      Notification, Staff)
from ..utils.notification import create_notification
from application import cache
mypharmacy_product = Store.products
mypharmacy_orders = Store.orders
bcrypt = Bcrypt()




def upload_to_cloudinary(file, folder='products'):
    result = upload(
        file,
        folder=folder,
        use_filename=True,
        unique_filename=True,
        resource_type='image'
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

    return None


@store.route('/adminpage', methods=["POST", "GET"])
@login_required
def adminpage():
    mypharmacy = Store.query.get_or_404(current_user.id)
    unread_notifications = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).all()
    count = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).count()

    today = datetime.today()
    current_month, current_year = today.month, today.year

    start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
    end_of_month = next_month - timedelta(seconds=1)
    start_of_year = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    end_of_year = today.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)

    store_id = session.get('store_id')

    # Daily sales
    daily_sales = db.session.query(
            func.date(Sales.date_).label('date'),
            func.sum(Sales.price * Sales.quantity).label('total')
        ).filter(Sales.store_id == store_id).group_by(func.date(Sales.date_)).order_by(
            func.date(Sales.date_)).all()

    daily_data = {
            "dates": [datetime.strptime(row.date, "%Y-%m-%d").strftime("%b %d") for row in daily_sales],
            "totals": [float(row.total) for row in daily_sales]
        }

    line = go.Scatter(x=daily_data["dates"], y=daily_data["totals"], mode='lines+markers', name='Daily Sales')
    line_layout = go.Layout(title="Daily Sales Trend")
    line_chart = plot.plot(go.Figure(data=[line], layout=line_layout), include_plotlyjs=True, output_type='div')

        # Total sales
    total_monthly_sales = db.session.query(func.sum(Sales.price * Sales.quantity)).filter(
            Sales.date_ >= start_of_month, Sales.date_ <= end_of_month,
            Sales.store_id == store_id
        ).scalar() or 0.0

    total_annual_sales = db.session.query(func.sum(Sales.price * Sales.quantity)).filter(
            Sales.date_ >= start_of_year, Sales.date_ <= end_of_year,
            Sales.store_id == store_id
        ).scalar() or 0.0

    today_sales = db.session.query(func.sum(Sales.price * Sales.quantity)).filter(
            func.date(Sales.date_) == today.date(),
            Sales.store_id == store_id
        ).scalar() or 0.0

        # Top 10 products
    top_products = db.session.query(
            Product.productname,
            func.sum(OrderItem.quantity * OrderItem.product_price).label('revenue')
        ).join(OrderItem, Product.id == OrderItem.product_id
               ).filter(Product.store_id == store_id
                        ).group_by(Product.productname
                                   ).order_by(func.sum(OrderItem.quantity * OrderItem.product_price).desc()
                                              ).limit(10).all()

    top_bar = go.Bar(
            x=[p[0] for p in top_products],
            y=[float(p[1]) for p in top_products],
            text=[f"{float(p[1]):.2f}" for p in top_products],
            textposition='auto'
        )
    top_layout = go.Layout(title="Top 10 Selling Products")
    top_chart = plot.plot(go.Figure(data=[top_bar], layout=top_layout), include_plotlyjs=True, output_type='div')

    pending_orders = len(Order.query.filter(
        extract('month', Order.create_at) == current_month,
        extract('year', Order.create_at) == current_year,
        (Order.status == "Pending"), (Order.store_id==mypharmacy.id)).all())
    if not pending_orders:
        pending_orders = 0

    return render_template(
            'store/updated_dashboard.html',
            chart1=line_chart,
            chart2=top_chart,
            total_sales=total_monthly_sales,
            total_annual_sales=total_annual_sales,
            total_daily_sales=today_sales,
            total_monthly_sales=total_monthly_sales,
            store=mypharmacy,
            pending_orders=pending_orders,
            unread_notifications=unread_notifications,
            count=count
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
#@role_required('Store')
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


@cache.memoize(timeout=300)
@store.route('/delivered')
@login_required
#@role_required('Store')
def delivered_orders():
    mypharmacy = Store.query.get_or_404(current_user.id)
    unread_notifications = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).all()
    count = Notification.query.filter_by(
        user_type='store', user_id=mypharmacy.id, is_read=False
    ).order_by(Notification.timestamp.desc()).count()

    store_id = session.get('store_id')
    store = Store.query.get_or_404(store_id)    
    form = updatestatusform()
    orders = Order.query.filter(Order.status=="Delivered", Order.store_id == current_user.id).all()
    #total = sum(item.product.price * item.quantity for item in orders.order_items)
    return render_template("store/updated_Delivered.html", form=form, orders=orders,
                           unread_notifications=unread_notifications,store=store, count=count)

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
                
                upload_result = upload_to_cloudinary(file)
                image_url = upload_result['secure_url'] 
              
                product.store_id = mypharmacy.id
                
                product.pictures = image_url

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
#@role_required('Store')
def remove_from_products(item_id):
    product = Product.query.filter_by(id=item_id).first()
    if product:
        db.session.delete(product)
        db.session.commit()
        cache.clear()
    return redirect(url_for('store.products'))

@cache.memoize(timeout=300)   
@store.route('/decrement/<int:item_id>', methods=['POST', 'GET'])
@login_required
#@role_required('Store')
def decrement_product(item_id):
    product = Product.query.filter_by(id=item_id).first()
    if product.quantity > 0:
        product.quantity -= 1
        if product.quantity <=10:
            product.warning = "Low on Stock"
        db.session.add(product)
    else:
        try:
            flash('Product depleted, removing from product list.')
            db.session.delete(product)
        except IntegrityError:
            flash('Integrity error.')
            db.session.rollback()
    db.session.commit()
    cache.clear()
    return redirect(url_for('store.products'))


@store.route('/add_products/<int:item_id>', methods=['POST', 'GET'])
@login_required
#@role_required('Store')
def add_products(item_id):
    product = Product.query.filter_by(id=item_id).first()
    product.quantity = product.quantity+1
    if product.quantity > 10:
        product.warning = "Quantity Good"
        db.session.add(product)
        print(f'updated quantity {product.warning}')

    db.session.commit()
    flash('Product count incremented successfully.')
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



