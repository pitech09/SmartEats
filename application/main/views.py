import os
from flask import render_template, redirect,  url_for, flash, session
from flask_login import login_required, current_user, logout_user # type: ignore
from sqlalchemy.exc import IntegrityError
from sqlalchemy import desc, or_
from . import main
from ..forms import *
from ..models import *
from application import cache
from PIL import Image
import cloudinary #type: ignore
from cloudinary.uploader import upload  # type: ignore

PRODUCTS_PER_PAGE = 9

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

def update_product_status(Product):
    for item in Product:
        if item.quantity < 10:
            item.warning == "Low Stock"
            db.session.commit()
        elif item.quantity <= 0:
            db.session.delete(item)
            db.sesion.commit()



def calculate_loyalty_points(user, sale_amount):
    points_earned = int(sale_amount // 10) #a point for each 10 spent
    user.loyalty_points = points_earned + int(user.loyalty_points or 0)

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

def save_update_profile_picture(form_picture):
    random_hex = secrets.token_hex(9)
    _, f_ex = os.path.splitext(form_picture.filename)
    post_img_Fn = random_hex + f_ex
    post_image_path = os.path.join(current_app.root_path, current_app.config['UPLOAD_PATH'], post_img_Fn)
    form_picture.save(post_image_path)
    return post_img_Fn



@main.route('/order_history')
@login_required
def order_history():
    formpharm= Set_StoreForm()
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
    orders = Order.query.filter_by(user_id=current_user.id, store_id=session.get('store_id')).all()
    return render_template('customer/orderhistory.html', formpharm=formpharm, orders=orders)

@main.route('/myorder', methods=['GET', 'POST'])
@login_required
def myorders():
    user_id = current_user.id
    form2 = Search()
    formpharm=Set_StoreForm()
    store = Store.query.get_or_404(session.get('store_id'))

    
    user = User.query.get_or_404(user_id)
    0.00
    total = 0.00
    orders = Order.query.filter(Order.user_id==current_user.id, or_(Order.status=="Pending", Order.status=="Approved", Order.status=="Out for Delivery")).order_by(desc(Order.create_at)).all()

    for o in orders:
        total_amount = sum(item.product.price * item.quantity for item in o.order_items)
        if total_amount >= 180:
            discount = 0.15*total_amount
            total = total_amount - discount

        else:
            total = total_amount
    return render_template('customer/myorder.html',  order=orders,
                           user=user, total=total, formpharm=formpharm, store=store, form2=form2)


@main.route('/completed_orders')
@login_required
def completed_order():
    user_id = current_user.id
    formpharm=Set_StoreForm()
    store = Store.query.get_or_404(session.get('store_id'))
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
    user = User.query.get_or_404(user_id)
    orders_completed = Order.query.filter(Order.user_id==current_user.id, Order.status=="Delivered").order_by(desc(Order.create_at)).all()
    return render_template('customer/updated_complete.html', user=user, formpharm=formpharm, store=store, orders_completed = orders_completed)


@main.route('/cancelled_orders', methods=['GET', 'POST'])
@login_required
def cancelled_orders():
    formpharm=Set_StoreForm()
    user_id = current_user.id
    store = Store.query.get_or_404(session.get('store_id'))
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
    user = User.query.get_or_404(user_id)
    discount=0.00
    total = 0.00
    order = Order.query.filter_by(user_id=current_user.id, status="Cancelled").all()
    return render_template('customer/updated_cancelled.html', order=order,store=store, formpharm=formpharm, user=user)
 
@main.route('/home', methods=["POST", "GET"])
def home():
    formpharm = Set_StoreForm()
    pharmacies = Store.query.all()
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
    store_id = session.get('store_id')
    count = Cart.query.filter(Cart.user_id==current_user.id, Cart.store_id == store_id).first()
    if count:
        count = sum(item.quantity for item in count.cart_items)

    return render_template("customer/home.html", user=current_user, total_count=count, pharmacies=pharmacies, formpharm=formpharm)


@main.route("/", methods=["POST", "GET"])
def landing():
    return render_template('customer/landingpage.html')

@cache.memoize(timeout=300)
@main.route('/cartlist', methods=['GET', 'POST'])
@login_required
def cart():
    form = CartlistForm()
    form2 = removefromcart()
    form3 = confirmpurchase()
    pres = upload_prescription()
    formpharm = Set_StoreForm()
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
    store_id = session.get('store_id')
    user_id = current_user.id
    store = Store.query.filter(Store.id == store_id).first()
    user = User.query.get_or_404(user_id)
    cart = Cart.query.filter(user_id==user.id, Cart.store_id == store_id).first()
    total_amount = 0.00
    total_count = 0
    count = Cart.query.filter(Cart.user_id==current_user.id, Cart.store_id == session.get('store_id')).first()
    if count:
        total_count = sum(item.quantity for item in count.cart_items)

    if cart:

        total_amount = sum(item.product.price * item.quantity for item in cart.cart_items)

    return render_template('customer/updated_cartlist.html', form=form, form3=form3, form2=form2,
                           cart=cart, user=user,formpharm=formpharm, store=store,
                           total_amount=total_amount, total_count=total_count, pres=pres)


@main.route('/about', methods=['POST', 'GET'])
def about():
    formpharm = Set_StoreForm()
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
    return render_template('about.html', formpharm=formpharm)


@main.route('/contact', methods=['POST', 'GET'])
def contact():
    formpharm = Set_StoreForm()
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]    
    return render_template('customer/contact.html')

@cache.memoize(timeout=300)
@main.route('/viewproduct/<int:product_id>', methods=['POST', 'GET'])
def viewproduct(product_id):
    formpharm = Set_StoreForm()
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]

    form = CartlistForm()
    product = Product.query.filter_by(id=product_id).first()
    store = Store.query.get_or_404(session.get('store_id'))
    item_picture = "dsdsqd"
    if product.pictures is not None:
        item_picture = url_for('static', filename=('css/images/products/' + product.pictures))
    return render_template('customer/updated_productview.html', product=product, store=store,
                           formpharm=formpharm, form=form, item_picture=item_picture)

@cache.memoize(timeout=300)
@main.route('/search/<int:page_num>', methods=['POST', 'GET'])
@login_required
def search(page_num):
    form = CartlistForm()
    form2 = Search()
    formpharm=Set_StoreForm()
    store = Store.query.get_or_404(session.get('store_id'))
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]
    keyword = form2.keyword.data
    products = Product.query.filter(
        Product.productname.like(f'%{keyword}%') |
        Product.description.like(f'%{keyword}%')  |
        Product.category.like(f'%{keyword}%'), 
        Product.store_id == session.get('store_id')
    ).all()
    start = (page_num - 1) * PRODUCTS_PER_PAGE
    end = start + PRODUCTS_PER_PAGE
    current_products = products[start:end]

    total_pages = (len(products) // PRODUCTS_PER_PAGE) + (1 if len(products) % PRODUCTS_PER_PAGE > 0 else 0)

    user_id = current_user.id
    user = User.query.get_or_404(user_id)
    item_picture = 'dfdfdf.jpg'
    total_count = 0
    count = Cart.query.filter_by(user_id=current_user.id).first()
    if count:
        total_count = sum(item.quantity for item in count.cart_items)

    for post in products:
        if post.pictures is not None:
            item_picture = url_for('static', filename=('css/images/products/' + post.pictures))
    return render_template('customer/updated_menu.html', form=form, item_picture=item_picture,
                           total_count=total_count, products=current_products, total_pages=total_pages,
                           page_num=page_num,formpharm=formpharm, form2=form2, store=store)


@cache.memoize(timeout=300)
@main.route('/addorder/<int:total_amount>', methods=['POST', 'GET'])
@login_required
def addorder(total_amount):
    form = confirmpurchase()
    formpharm = Set_StoreForm()
    pres =upload_prescription()
    store_id = session.get('store_id')
    pharm = Store.query.get_or_404(store_id)
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    tyt = total_amount

    user = User.query.filter_by(id = current_user.id).first()
    if not cart:
        return redirect(url_for('main.menu'))
    existing_order = Order.query.filter_by(user_id=current_user.id, status='Pending', store_id=store_id).first()
    if existing_order:
        flash("You still have a pending order, wait for admin to approve before placing another.", "unsuccessful")
        return redirect(url_for('main.myorders', order_id=existing_order.id))
    else:
        if form.validate_on_submit():
            neworder = Order(user_id=current_user.id, payment=form.payment.data,
                                user_email=current_user.email,store_id=pharm.id,
                                source_store=pharm.name)
            if form.deliverymethod.data == 'pickup' or form.deliverymethod == 'Customer pickup':
                neworder.location = 'pickup'
                flash('Order was placed as Pick up.')
            else:
                neworder.location = form.drop_address.data
                flash('Your order will be approved soon, and assined a delivery agent.')

            file = form.payment_screenshot.data
            if not form.payment_screenshot.data:
                flash("your are missing payment proof")
                return redirect(url_for('main.cart'))
            pics = upload_to_cloudinary(file)
            image_url = pics['secure_url'] 
            neworder.screenshot = image_url
        else:
            return redirect(url_for('main.cart'))
        
        #hashed_order = flask_bcrypt.generate_password_hash(neworder.id)
        if form.transid.data:
            print("form id found")
            neworder.transactionID = form.transid.data
        else:
            print("no id")
            neworder.transactionID ='None'
        db.session.add(neworder)
        try:
            print('committing...')
            db.session.commit()
            flash('Order successfully placed Order. Your payment will be verified shortly')
        except IntegrityError:
            db.session.rollback()
            flash('There was an error placing your order, make sure all the details were entered correctly.')
            print("integrity")
            return redirect(url_for('main.cart'))
        db.session.commit()
        
        total_amount = 0
        for item in cart.cart_items:
            order_item = OrderItem(order_id=neworder.id, product_id=item.product.id, product_name=item.product.productname,
                                   product_price=item.product.price, quantity=item.quantity)

            total_amount += item.product.price*item.quantity
            db.session.add(order_item)
            db.session.commit()
        for i in cart.cart_items:
            sale = Sales(order_id=neworder.id, product_id=i.product.id, product_name=i.product.productname,
            price=i.product.price, quantity=i.quantity, user_id=neworder.user_id, date_=neworder.create_at)
            sale.store_id = pharm.id
            product = Product.query.filter_by(id=i.product.id).first()
            db.session.add(sale)
        CartItem.query.filter_by(cart_id=cart.id).delete()
        cart.redeemed = False
        db.session.commit()
        cache.clear()
    return redirect(url_for('main.myorders', total_amount=total_amount))


@cache.memoize(timeout=300)
@main.route("/menu/<int:page_num>", methods=["POST", "GET"])
def menu(page_num=1):
    formpharm = Set_StoreForm()
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()]    
    form = CartlistForm()
    form2 = Search()
    products = Product.query.filter(Product.store_id == session.get('store_id')).all()
    start = (page_num - 1) * PRODUCTS_PER_PAGE
    end = start + PRODUCTS_PER_PAGE
    current_products = products[start:end]
    total_pages = (len(products) // PRODUCTS_PER_PAGE) + (1 if len(products) % PRODUCTS_PER_PAGE > 0 else 0)
    user_id = current_user.id
    user = User.query.get_or_404(user_id)
    item_picture = 'dfdfdf.jpg'
    total_count = 0
    count = Cart.query.filter(Cart.user_id==current_user.id, Cart.store_id == session.get('store_id')).first()
    if count:
        total_count = sum(item.quantity for item in count.cart_items)
    for post in products:
        if post.pictures is not None:
            item_picture = url_for('static', filename=('css/images/products/' + post.pictures))
    mystore = Store.query.get_or_404(session.get('store_id'))

    return render_template('customer/updated_menu.html', form=form, item_picture=item_picture,
                           total_count=total_count, form2=form2, formpharm=formpharm, products=current_products, 
                            total_pages=total_pages, page_num=page_num, user=user, store=mystore)


@main.route('/add_to_cart/<int:item_id>', methods=['POST','GET'])
def add_to_cart(item_id):
    form = CartlistForm()
    userid = current_user.id
    page_num = 1
    #print('starting...')
    product = Product.query.get_or_404(item_id)
    store_id = session.get('store_id')
    cart = Cart.query.filter(Cart.user_id==current_user.id, Cart.store_id==store_id).first()
    if not cart:
       # print('cart dont exist, creating one')
        cart = Cart(user_id=current_user.id, store_id=store_id)
       # print('creation done')
        db.session.add(cart)

   # print('checking cart item...')
    cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
    if cart_item:
        #print('product exists on cart and incremeted')
        cart_item.quantity+=1
    else:
        #print('adding product to cart')
        cart_item = CartItem(cart_id=cart.id, product_id=product.id, quantity=1)
        db.session.add(cart_item)
    total_amount = sum(item.product.price * item.quantity for item in cart.cart_items)
    try:
        db.session.commit()
        cache.clear()
        flash(f'{product.productname} added to cart.')
    except IntegrityError:
        return redirect(url_for('main.menu',page_num=1))
    #print('donee')
    return redirect(url_for('main.menu', user_id=current_user.id, form=form, page_num=page_num, total_amount=total_amount))


@main.route('/remove_from_cart/<int:item_id>', methods=['POST', 'GET'])
@login_required
def remove_from_cart(item_id):
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    #cart_ = CartItem.query.filter_by(cart_id=cart.id, product_id=item_id).first()
    product = CartItem.query.filter_by(id=item_id).first()
    if product:
        product.quantity -= 1
        db.session.add(product)
        if product.quantity <= 0:
            db.session.delete(product)
    db.session.commit()        #db.session.delete()
    cache.clear()
    return redirect(url_for('main.cart', user_id=current_user.id))


@main.route("/account", methods=["GET", "POST"])
@login_required
def account():
    form = UpdateForm()
    formpharm = Set_StoreForm()
    formpharm.store.choices=[(-1, "Select a Store")] + [(p.id, p.name) for p in Store.query.all()] 
    
    user = User.query.filter_by(id=current_user.id).first()

    if form.validate_on_submit():
        image_file = save_update_profile_picture(form.picture.data)
        current_user.image_file = image_file
        db.session.commit()
        flash("Account Details Updated Successfully.", "success")
        return redirect(url_for('main.account'))

    image_file = url_for('static', filename='static/images/profiles/ ' + user.image_file)
    store = session.get('store_id')
    return render_template('customer/updated_acc.html', user=user, formpharm=formpharm, store=store, image_file=image_file, form=form)


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
        flash('Errot deleting account')
        db.session.rollback() 

    return redirect(url_for('auth.newlogin'))   


@main.route('/set_store', methods=['POST', 'GET'])
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




    
