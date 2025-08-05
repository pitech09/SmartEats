
import pytz
from flask_login import UserMixin  # type: ignore
from itsdangerous import TimedSerializer
from flask import current_app

from . import login_manager, db
from zoneinfo import ZoneInfo
import secrets
from datetime import datetime
from flask_migrate import Migrate  # type: ignore



def get_localTime(self):
    tz = pytz.timezone("Africa/Johannesburg")
    return datetime.now(tz)

def get_orderid():
    return "ORD-"+ secrets.token_hex(5).upper()




class Store(UserMixin, db.Model):
    __tablename__ = "store"
    __searchable__ = ['name', 'address']
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    address = db.Column(db.String(200))
    openinghours = db.Column(db.String(100), nullable=False, default='09:00 to 18:30')
    registered_on = db.Column(db.DateTime, server_default=db.func.now())
    password = db.Column(db.String(200), nullable = False)
 

    #mpesa
    mpesa_shortcode = db.Column(db.String(100), nullable=False, default="None")
    ecocash_short_code = db.Column(db.String(100), nullable=False, default="None")
    
    registered_on = db.Column(db.DateTime, server_default=db.func.now())
    users = db.relationship('User', backref='store', lazy=True)  # a user will be tied to a store store they create
    products = db.relationship('Product', backref='store', lazy=True)
    orders = db.relationship('Order', backref='store', lazy=True)
    sales = db.relationship('Sales', backref='store', lazy=True)
    users = db.relationship('User', back_populates='store')
    confirmed = db.Column(db.Boolean, nullable=False, default=False)
    verified = db.Column(db.Boolean, default=False)

    def __init__(self, name, password, email, phone, address, openinghours):
        self.name = name
        self.email = email
        self.phone = phone
        self.address = address
        self.openinghours = openinghours
        self.password = password


class Product(db.Model):
    __searchable__ = ['productname', 'description', 'category']
    id = db.Column(db.Integer, primary_key=True)
    productname = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Float, nullable=False)
    pictures = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer)
    description = db.Column(db.String(100), nullable=False)
    cart_items = db.relationship('CartItem', backref='product', lazy=True)
    order_items = db.relationship('OrderItem', backref='product', lazy=True)
    warning = db.Column(db.String(50), default='Quantity Good')
    category = db.Column(db.String(50), nullable=True, default='Uncategorized')
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'))

class Sales(db.Model):
    __searchable__ = ['order_id', 'date_', 'user_id']
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_user_id'), nullable=False)
    product_name = db.Column(db.String(30), nullable=False)
    product_id = db.Column(db.Integer, nullable=False)
    date_ = db.Column(db.DateTime, nullable=False, default=get_localTime)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id', name='fk_store_id'), nullable=False)

class User(UserMixin, db.Model):
    __searchable__ = ['username', 'firstname', 'email', 'lastname']
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(18), nullable=False, unique=True)
    lastname = db.Column(db.String(40), nullable=False)
    email = db.Column(db.String(30), unique=True, nullable=False)
    image_file = db.Column(db.String(140), nullable=True, default="account.png")
    password = db.Column(db.String(40), nullable=False, unique=False)
    carts = db.relationship('Cart', backref='user', lazy=True)
    orders = db.relationship('Order', backref='user', lazy=True)
    confirmed = db.Column(db.Boolean, nullable=False, default=False)
    loyalty_points = db.Column(db.Integer, default=0)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'))
    store = db.relationship('Store', back_populates='users')

    def generate_confirmation_token(self, expiration=4600):
        s = TimedSerializer(current_app.config['SECRET_KEY'], expiration)
#       serializer = TimedSerializer('your_secret_key', expires_in=3600)
        return s.dumps({'confirm': self.id})

    def confirm(self, token):
        s = TimedSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('confirm') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        return True

    def __init__(self, username, lastname, email, password):
        self.username = username
        self.lastname = lastname
        self.email = email
        self.password = password


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.ForeignKey('cart.id'), nullable=False)
    product_id = db.Column(db.ForeignKey('product.id', name='fk_prod_id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

class Order(db.Model):
    __searchable__ = ['order_id', 'location', 'user_id', 'status', 'payment', 'user_email']
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(10), nullable=False, default=get_orderid)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_userid_order'), nullable=False)
    create_at = db.Column(db.DateTime, default=get_localTime)
    location = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(40), nullable=False, default='Pending')
    payment = db.Column(db.String(40), nullable=False, default='None')
    transactionID = db.Column(db.String(90), default='Cash')
    user_email = db.Column(db.String(30), nullable=False)
    order_items = db.relationship('OrderItem', backref='order', lazy=True)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id', name='fk_store_order'), nullable=False)
    source_store = db.Column(db.String(120))
    taken_by = db.Column(db.Integer, db.ForeignKey('deliveryguy.id', name='fk_store_order_deliver'))
    deliveryguy = db.Column(db.String(50), default="Not Taken")
    screenshot = db.Column(db.String(120))
    #prescription = db.Column(db.String(120))

    def get_localTime(self):
        return self.create_at.astimezone(ZoneInfo("Africa/Johannesburg"))

    def getstorename(self, store_id):
        return Pharmacy.query.get_or_404(store_id)


class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('user.id', name='fk_cartuser'), nullable=False)
    date_created = db.Column(db.DateTime, default=get_localTime)
    cart_items = db.relationship('CartItem', backref='cart', lazy=True)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id', name='fk_store_order'), nullable=False)
    total_amount = db.Column(db.Float, default=0.0)
    def calculate_total(self):
       return sum(item.product.price * item.quantity for item in self.cart_items)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.ForeignKey('order.id', name='fk_order_item'), nullable=False)
    product_id = db.Column(db.ForeignKey('product.id', name='fk_prod_item'), nullable=False)
    product_name = db.Column(db.String(20), nullable=False)
    product_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

class DeliveryGuy(db.Model, UserMixin):
    __tablename__ = 'deliveryguy'
    id = db.Column(db.Integer, primary_key=True)
    names = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(30), unique=True, nullable=False)
    image_file = db.Column(db.String(140), nullable=True, default="account.png")
    password = db.Column(db.String(40), nullable=False, unique=False)
    deliveries = db.relationship('Delivery', back_populates='delivery_guy',overlaps='delivery_guy', lazy=True) 
    isfree = db.Column(db.Boolean, default=True)  

class Delivery(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    customer_name = db.Column(db.String(120))
    address = db.Column(db.String(100))
    status = db.Column(db.String(50), default='Out for delivery')
    end_time = db.Column(db.DateTime, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    order_id = db.Column(db.String(30), db.ForeignKey('order.id', name='fk_delivery_order'))
    orders = db.relationship('Order', backref='delivery', lazy=True)
    delivery_guy_id = db.Column(db.Integer, db.ForeignKey('deliveryguy.id', name='fk_delivery_guy'))
    delivery_guy = db.relationship('DeliveryGuy', back_populates='deliveries', overlaps='deliveries', lazy=True)

    def to_dict(self):
        return {
        "id": self.id,
        "customer_name": self.customer_name,
        "address": self.address,
        "status": self.status,
        "order_id": self.order_id
    }

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_type = db.Column(db.String(20))  
    user_id = db.Column(db.Integer)       
    message = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

class Staff(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    names = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(30), unique=True, nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'))
    role = db.Column(db.String(120))
    password = db.Column(db.String(100), nullable=False)
    store = db.relationship('Store', backref='Staff_members')

    def __init__(self, names, email, role, password, store):
        self.names = names
        self.email = email
        self.role = role
        self.password = password
        self.store = store