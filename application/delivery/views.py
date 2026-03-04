import os, secrets
from datetime import datetime, timedelta
from PIL import Image
from flask import (
    abort, render_template, redirect, url_for, flash, session, request, current_app, jsonify
)
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from . import delivery
from ..forms import *
from ..models import *
from application.notification import notify_customer, notify_store
from application.utils.notification import create_notification
import flask_bcrypt
import cloudinary
from cloudinary.uploader import upload


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


def upload_to_cloudinary(file, folder='delivery_proofs'):
    result = upload(
        file,
        folder=folder,
        use_filename=True,
        unique_filename=True,
        resource_type='image',
        transformation=[{'width': 300, 'height': 300, 'crop': 'fill'}, {'quality': 'auto'}]
    )
    return result


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
        print(f"Error saving image: {e}")
        return None


# ---------------- DASHBOARD ----------------
@delivery.route('/dashboard', methods=["GET", "POST"])
@login_required
def dashboard():
    store = Store.query.get(session.get('store_id'))
    formpharm = Set_StoreForm()
    formpharm.store.choices = [(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.filter_by(is_active=True).all()]

    # Optional date filter
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
    else:
        start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)

    deliveries = Delivery.query.filter(Delivery.delivery_guy_id == current_user.id).all()
    total = len(deliveries)
    delivered = [d for d in deliveries if d.status == 'Delivered']
    cancelled = [d for d in deliveries if d.status == 'Cancelled']
    in_progress = [d for d in deliveries if d.status not in ['Delivered', 'Cancelled']]

    # Revenue
    revenue = sum(d.order.deliveryfee or 0 for d in delivered)
    daily_revenue = sum(
        d.order.deliveryfee or 0
        for d in deliveries
        if d.status == "Delivered" and start_date <= (d.end_time or datetime.utcnow()) < end_date
    )

    start_of_week = start_date - timedelta(days=start_date.weekday())
    end_of_week = start_of_week + timedelta(days=7)
    weekly_revenue = sum(
        d.order.deliveryfee or 0
        for d in deliveries
        if d.status == "Delivered" and start_of_week <= (d.end_time or datetime.utcnow()) < end_of_week
    )

    success_rate = (len(delivered) / total * 100) if total else 0

    return render_template(
        'delivery/deliverystats.html',
        total=total,
        delivered=len(delivered),
        in_progress=len(in_progress),
        cancelled=len(cancelled),
        store=store,
        revenue=revenue,
        daily_revenue=daily_revenue,
        weekly_revenue=weekly_revenue,
        success_rate=round(success_rate, 2),
        formpharm=formpharm,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=(end_date - timedelta(days=1)).strftime("%Y-%m-%d")
    )


# ---------------- TAKE ORDER ----------------
@delivery.route('/takeorder/<int:order_id>', methods=["GET", "POST"])
@login_required
def takeorder(order_id):
    order = Order.query.filter(
        Order.id == order_id,
        Order.store_id == session.get('store_id')
    ).first()
    if not order:
        flash("Order not found.")
        return redirect(url_for("delivery.dashboard"))

    if order.delivery:
        flash("This order has already been taken.")
        return redirect(url_for("delivery.dashboard"))

    active_count = Delivery.query.filter_by(
        delivery_guy_id=current_user.id,
        status="Out for Delivery"
    ).count()

    if active_count >= 5:
        flash("Cannot take more than 5 active orders.")
        return redirect(url_for("delivery.dashboard"))

    user = User.query.get(order.user_id)
    new_delivery = Delivery(
        customer_name=user.lastname if user else "Customer",
        address=order.location,
        status="Out for Delivery",
        order_id=order.id,
        delivery_guy_id=current_user.id,
        deliveryfee=order.deliveryfee
    )

    order.status = "Out for Delivery"
    order.deliveryguy = current_user.names

    db.session.add(new_delivery)
    try:
        db.session.commit()
        flash("Order taken successfully.")
    except IntegrityError:
        db.session.rollback()
        flash("This order was taken by someone else.")

    return redirect(url_for("delivery.dashboard"))


# ---------------- API DELIVERY STATUS ----------------
@delivery.route('/api/delivery/<int:order_id>', methods=['GET'])
@login_required
def get_delivery_status(order_id):
    delivery_obj = Delivery.query.filter_by(order_id=order_id).first()
    if delivery_obj:
        return jsonify(delivery_obj.to_dict())
    return jsonify({"error": "Delivery not found"}), 404


# ---------------- READY ORDERS ----------------
@delivery.route('/ready_orders', methods=["GET"])
@login_required
def ready_orders():
    store = Store.query.get_or_404(session.get('store_id'))
    myform = updatedeliveryform()
    delivery_update = updatedeliveryform()
    formpharm = Set_StoreForm()
    formpharm.store.choices = [(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.filter_by(is_active=True).all()]
    ready = Order.query.filter(
        Order.status == "Ready",
        Order.location != "pickup",
        Order.store_id == session.get('store_id')
    ).all()
    return render_template(
        'delivery/deliverydashboard.html',
        ready_orders=ready,
        myform=myform,
        delivery_update=delivery_update,
        store=store,
        formpharm=formpharm
    )


# ---------------- MY DELIVERIES ----------------
@delivery.route('/mydeliveries', methods=["GET", "POST"])
@login_required
def mydeliveries():
    store = Store.query.get_or_404(session.get('store_id'))
    myform = updatedeliveryform()
    delivery_update = updatedeliveryform()
    deliveries = Delivery.query.filter(
        Delivery.delivery_guy_id == current_user.id,
        Delivery.status == "Out for Delivery"
    ).all()
    formpharm = Set_StoreForm()
    formpharm.store.choices = [(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.filter_by(is_active=True).all()]
    return render_template(
        'delivery/ActiveOrder.html',
        myform=myform,
        store=store,
        deliveries=deliveries,
        delivery_update=delivery_update,
        formpharm=formpharm
    )


# ---------------- UPDATE DELIVERY ----------------
@delivery.route('/update_delivery/<int:delivery_id>', methods=["POST"])
@login_required
def update_delivery(delivery_id):
    form = updatedeliveryform()
    delivery_obj = Delivery.query.get_or_404(delivery_id)

    if delivery_obj.delivery_guy_id != current_user.id:
        abort(403, "Not authorised")

    if not form.validate_on_submit():
        flash("Form failed to validate.")
        return redirect(url_for('delivery.mydeliveries'))

    old_status = delivery_obj.status
    new_status = form.status.data
    if old_status == new_status:
        flash('Status is already up to date.')
        return redirect(url_for('delivery.mydeliveries'))

    delivery_obj.status = new_status
    order = Order.query.get_or_404(delivery_obj.order_id)
    order.status = new_status

    if new_status in ["Delivered", "Completed"]:
        delivery_obj.end_time = datetime.utcnow()
        duration = int((delivery_obj.end_time - delivery_obj.timestamp).total_seconds() // 60)
        flash(f"Delivery took {duration} minutes")

    # Proof upload
    if form.delivery_prove.data:
        if current_app.config.get('USE_CLOUDINARY', False):
            image = upload_to_cloudinary(form.delivery_prove.data)
            delivery_obj.customer_pic = image['secure_url']
        else:
            delivery_obj.customer_pic = save_product_picture(form.delivery_prove.data)

    try:
        db.session.commit()
        message = f"Delivery #{delivery_obj.id} status changed from {old_status} to {new_status}"
        create_notification('customer', order.user_id, message)
        create_notification('store', order.store_id, message)
        notify_customer(order.user_id)
        notify_store(order.store_id)
        flash('Delivery status successfully updated.')
    except IntegrityError:
        db.session.rollback()
        flash('Error updating delivery. Please try again.')

    return redirect(url_for('delivery.mydeliveries'))