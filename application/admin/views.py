from itertools import product
from flask import render_template, redirect, url_for, request, flash, current_app, jsonify,session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, extract, or_
from ..models import *
from datetime import datetime,timedelta
import calendar
from flask_login import login_required, current_user, logout_user,  LoginManager # type: ignore
from . import admin
from ..forms import *
from ..models import db
import os
from application.auth import *
import secrets
from PIL import Image
from flask import current_app
import plotly.graph_objs as go # type: ignore
import plotly.offline as plot # type: ignore
import cloudinary
from cloudinary.uploader import upload



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


@admin.route('/users', methods=["GET", "POST"])
def reg_users():
    users = User.query.all()
    num_of_users = len(users)
    return render_template('admin/users.html', users=users, num_of_users=num_of_users)

@admin.route('/admindash', methods=["GET", "POST"])
def admindash():
    # Pending pharmacies
    pending_pharmacy = Store.query.filter(Store.verified == False).all()
    count = len(pending_pharmacy)

    today = datetime.today()
    current_month, current_year = today.month, today.year

    # Basic counts
    num_of_users = User.query.count()
    num_of_delivery = DeliveryGuy.query.count()
    num_of_stores = Store.query.count()

    # Date ranges
    start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
    end_of_month = next_month - timedelta(seconds=1)

    start_of_year = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    end_of_year = today.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)

    # Commission percentage for admin
    admin_commission = 0.10  # 10%

    # Total commission earned by admin
    total_sales = db.session.query(func.sum(Sales.price * Sales.quantity * admin_commission)).scalar() or 0.0

    # Daily commission breakdown
    daily_sales = db.session.query(
        func.date(Sales.date_).label('date'),
        func.sum(Sales.price * Sales.quantity * admin_commission).label('total')
    ).group_by(func.date(Sales.date_)).order_by(func.date(Sales.date_)).all() or []

    # Monthly commission
    total_monthly_sales = db.session.query(
        func.sum(Sales.price * Sales.quantity * admin_commission)
    ).filter(Sales.date_ >= start_of_month, Sales.date_ <= end_of_month).scalar() or 0.0

    # Annual commission
    total_annual_sales = db.session.query(
        func.sum(Sales.price * Sales.quantity * admin_commission)
    ).filter(Sales.date_ >= start_of_year, Sales.date_ <= end_of_year).scalar() or 0.0

    # Today's commission
    today_sales = db.session.query(
        func.sum(Sales.price * Sales.quantity * admin_commission)
    ).filter(func.date(Sales.date_) == today.date()).scalar() or 0.0

    return render_template(
        'admin/admindash.html',
        count=count,
        daily_sales=daily_sales,
        total_annual_sales=total_annual_sales,
        total_monthly_sales=total_monthly_sales,
        today_sales=today_sales,
        total_sales=total_sales,
        num_of_delivery=num_of_delivery,
        num_of_users=num_of_users,
        num_of_stores=num_of_stores
    )

@admin.route('/verify store/<int:pharmacy_id>', methods=["GET", "POST"])
def verifypharmacy(pharmacy_id):
    store = Store.query.get_or_404(pharmacy_id)
    if store:
        store.verified = True
        db.session.add(store)
    try:
        db.session.commit()
        flash('Store Verified.')
        return redirect(url_for('admin.pending_verification'))
    except IntegrityError:
        flash('Stores failed due to integrity.')
        return redirect(url_for('admin.pending_verification'))

@admin.route('/view_details/<int:pharmacy_id>')
def view_details(pharmacy_id):
    store = Store.query.get_or_404(pharmacy_id)
    return render_template('pharmacy_details.html', store=store)

@admin.route('/cancelled store/<int:pharmacy_id>')
def cancel_pharmacy(pharmacy_id):
    store = Store.query.get_or_404(pharmacy_id)
    if store:
        try:
            db.session.delete(store)
            db.session.commit()
            return redirect(url_for('admin.pending_verification'))
        except IntegrityError:
            flash('The Store has orders that have not been fulfiled.')
            return redirect(url_for('admin.pending_verification'))
    else:
        flash('Store could not be found')
        return redirect(url_for('admin.pending_verification'))

@admin.route('/registered stores')
def registered_stores():
    stores = Store.query.all()
    
    return render_template('admin/registereduser.html', stores=stores)

@admin.route('/register store')
def register_store():
    form = PharmacyRegistrationForm()
    return render_template('admin/registerstore.html', form=form)

@admin.route('/pending vefication')
def pending_verification():
    stores = Store.query.filter(Store.verified == False).all()
    return render_template('admin/pendingpharmacies.html', stores=stores)
@admin.route("/ads", methods=["GET", "POST"])
@login_required
def manage_ads():
    form = AdForm()

    # Populate product/store dropdowns
    form.product_id.choices = [(0, "-- Select Product --")] + [(p.id, p.name) for p in Product.query.all()]
    form.store_id.choices = [(0, "-- Select Store --")] + [(s.id, s.name) for s in Store.query.all()]

    if form.validate_on_submit():
        # Handle the selected IDs
        product_id = form.product_id.data if form.link_type.data == "product" and form.product_id.data != 0 else None
        store_id = form.store_id.data if form.link_type.data == "store" and form.store_id.data != 0 else None
        external_url = form.external_url.data if form.link_type.data == "external" else None

        # Upload image

        # Save ad
        ad = Ad(
            title=form.title.data,
            link_type=form.link_type.data,
            product_id=product_id,
            store_id=store_id,
            external_url=external_url
        )
        file = form.image_file.data
        print(current_app.config['USE_CLOUDINARY'])
        if current_app.config['USE_CLOUDINARY']:
            print("SAving to cloudinary.")
            upload_result = upload_to_cloudinary(file)
            image_url = upload_result['secure_url'] 
            ad.image = image_url
        else: 
            print('Saving picture to sqlite db') 
            _image = save_product_picture(file)
            ad.image = _image
        db.session.add(ad)
        db.session.commit()
        flash("Ad added successfully!", "success")
        return redirect(url_for("admin.manage_ads"))

    # GET request
    ads = Ad.query.all()
    products = Product.query.all()
    stores = Store.query.all()
    return render_template("admin/ads.html", form=form, ads=ads, products=products, stores=stores)

@admin.route("/ads/delete/<int:ad_id>", methods=["POST"])
@login_required
def delete_ad(ad_id):
    ad = Ad.query.get_or_404(ad_id)

    # Optional: Delete from Cloudinary
    try:
        # assuming you store public_id in image_file without extension
        public_id = ad.image_file.rsplit('.', 1)[0]
        #delete_from_cloudinary(public_id)  # your Cloudinary delete helper
    except Exception as e:
        print(f"Cloudinary delete failed: {e}")

    # Delete from database
    db.session.delete(ad)
    db.session.commit()
    flash("Ad deleted successfully!", "success")
    return redirect(url_for("admin.manage_ads"))
