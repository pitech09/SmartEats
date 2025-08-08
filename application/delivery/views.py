import os
from datetime import datetime, timedelta
from PIL import Image
from flask import render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user, logout_user  # type: ignore
from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError

from application.utils.notification import create_notification
from . import delivery
from ..forms import *
from ..models import *
import cloudinary
from cloudinary.uploader import upload  # type: ignore

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
def upload_to_cloudinary(file, folder='products'):
    result = upload(
        file,
        folder=folder,
        use_filename=True,
        unique_filename=True,
        resource_type='image'
    )
    return result


@delivery.route('/dashboard', methods=["GET", "POST"])
@login_required
def dashboard():
    store = Store.query.get(session.get('store_id'))
    formpharm = Set_StoreForm()
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
    deliveries = Delivery.query.filter_by(delivery_guy_id=current_user.id).all()
    total = len(deliveries)
    delivered = [d for d in deliveries if d.status == 'Delivered']
    revenue=len(delivered) * 10
    cancelled = [d for d in deliveries if d.status == 'Cancelled']
    in_progress = [d for d in deliveries if d.status not in ['Delivered', 'Cancelled']]

    success_rate = (len(delivered) / total * 100) if total !=0 else 0
    today = datetime.utcnow()
    start_of_day = today.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    # Daily Statistics
    deliveries_today = db.session.query(Delivery).filter(
        Delivery.end_time >= start_of_day,
        Delivery.end_time < end_of_day,
        Delivery.status == "Delivered"
    ).all()
    daily_revenue = len(deliveries_today)*10
    print(daily_revenue)

    start_of_week = start_of_day - timedelta(days=start_of_day.weekday())
    end_of_week = start_of_week + timedelta(weeks=1)

    weekly_count = db.session.query(Delivery).filter(
        Delivery.end_time >= start_of_week,
        Delivery.end_time < end_of_week,
        Delivery.status == "Delivered"
    ).all()

    weekly_revenue = len(weekly_count)*10
    print(weekly_revenue)


    return render_template('delivery/deliverystats.html',
                           total=total,
                           weekly_revenue=weekly_revenue,
                           daily_revenue=daily_revenue,
                           delivered=len(delivered),
                           in_progress=len(in_progress),
                           cancelled=len(cancelled),
                           store=store,
                           revenue=revenue,
                           formpharm=formpharm,
                           success_rate=round(success_rate, 2),
                          )
@delivery.route('/takeorder/<int:order_id>', methods=["GET", "POST"])
@login_required
def takeorder(order_id):
    order = Order.query.filter(Order.id==order_id, Order.store_id==session.get('store_id')).first()
    existing_deliveries_count = db.session.query(Delivery).join(Order).filter(Delivery.delivery_guy_id == current_user.id, Order.status == "Out for Delivery").count()
    if existing_deliveries_count >= 5:
        flash('You cannot take more than 5 orders at a time.')
        return redirect(url_for('delivery.dashboard'))
    user = User.query.get_or_404(order.user_id)
    cust_names= user.lastname
    new_delivery = Delivery(customer_name = cust_names,
        address=order.location,
        delivery_guy_id=current_user.id,
        order_id=order.order_id,
        status="Out for Delivery")
    order.status = "Out for Delivery"
    order.deliveryguy = current_user.names
    order.taken_by = current_user.id
    db.session.add(order)
    db.session.add(new_delivery)
    try:
        db.session.commit()
        flash('Order taken successfully.')
    except IntegrityError:
        db.session.rollback()
        flash('An integrity error occurred.')
        return redirect(url_for('delivery.dashboard'))

    return redirect(url_for('delivery.dashboard'))


from flask import jsonify

@delivery.route('/api/delivery/<order_id>', methods=['GET'])
@login_required
def get_delivery_status(order_id):
    delivery = Delivery.query.filter_by(order_id=order_id).first()
    if delivery:
        return jsonify(delivery.to_dict())
    return jsonify({"error": "Delivery not found"}), 404



@delivery.route('/mydeliveries', methods=["POST", "GET"])
@login_required
def mydeliveries():
    store = Store.query.get_or_404(session.get('store_id'))
    myform = updatedeliveryform()
    delivery_update = updatedeliveryform()
    deliveries = Delivery.query.filter(
        Delivery.delivery_guy_id == current_user.id,
        Delivery.status == "Out for Delivery"
    ).all()
    formpharm=Set_StoreForm()
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
  
    return render_template('delivery/ActiveOrder.html', myform=myform, store=store,
                           deliveries=deliveries, delivery_update=delivery_update,formpharm=formpharm)

@delivery.route('/ready orders')
@login_required
def ready_orders():
    store = Store.query.get_or_404(session.get('store_id'))
    myform = updatedeliveryform()
    delivery_update = updatedeliveryform()
    formpharm=Set_StoreForm()
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
    ready = Order.query.filter(Order.status == "Ready ", Order.store_id == session.get('store_id')).all()
    return render_template('delivery/deliverydashboard.html', ready_orders=ready, myform=myform, store=store,
                           delivery_update=delivery_update,formpharm=formpharm)


@delivery.route('/update_delivery/<int:delivery_id>', methods=["GET", "POST"])
@login_required
def update_delivery(delivery_id):
    form = updatedeliveryform()
    delivery = Delivery.query.get_or_404(delivery_id)
    if form.validate_on_submit():
        new_status = form.status.data
        old_status = delivery.status

        if old_status == new_status:
            flash('Status is already up to date.')
            return redirect(url_for('delivery.mydeliveries'))

        delivery.status = new_status
        order = Order.query.filter(Order.order_id == delivery.order_id).first()
        order.status = form.status.data
        delivery.end_time = datetime.utcnow()
        if form.delivery_prove.data:
            image_filename = upload_to_cloudinary(form.delivery_prove.data)
            delivery.customer_pic = image_filename

        db.session.add(delivery)
        db.session.add(order)
        try:
            db.session.commit()
            flash(f" End time{delivery.end_time}, Start time{delivery.timestamp}")
            # 🔔 Message
            message = f"Delivery #{delivery.id} status changed from {old_status} to {new_status}"

            create_notification(user_type='customer', user_id=order.user_id, message=message)

            # 🔔 Notify store & emit event

            create_notification(user_type='store', user_id=order.store_id, message=message)

            flash('Delivery status successfully updated.')

        except IntegrityError:
            db.session.rollback()
            flash('An error occurred while updating the delivery. Please try again.')

        return redirect(url_for('delivery.mydeliveries'))

    flash("Form failed to validate.")
    return redirect(url_for('delivery.mydeliveries'))


@delivery.route('/deliverylayout', methods=["POST", "GET"])
def deliverylayout():
    formpharm = Set_StoreForm()
    pharmacies = Store.query.all()
    total_count = 0
    store = Store.query.get_or_404(session.get('store_id'))
    total_count = Order.query.filter(Order.store_id == session.get('store_id'), Order.status == "Ready").all().count()
    formpharm.store.choices = [(p.id, p.name) for p in pharmacies]
    return render_template('deliverylayout.html', formpharm=formpharm, total_count=total_count,
                           store=store)

@delivery.route('/set_pharmacy', methods=['POST', 'GET'])
def set_pharmacy():
    formpharm = Set_StoreForm()
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
    if formpharm.validate_on_submit():
        session['store_id'] = formpharm.store.data
        return redirect(url_for('delivery.dashboard', store_id=formpharm.store.data))
    elif formpharm.errors:
        print(formpharm.errors)
        return formpharm.errors
    else:
        flash(f'{current_user.id} had a problem selecting your store, please try again later')
        return redirect(url_for('delivery.dashboard'))

