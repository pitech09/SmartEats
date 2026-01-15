import secrets
import pytz
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app
from flask_login import UserMixin
from itsdangerous import TimedSerializer
from sqlalchemy.dialects.postgresql import JSON
from . import db, login_manager

# ----------------- Utilities -----------------
def get_localTime():
    tz = pytz.timezone("Africa/Johannesburg")
    return datetime.now(tz)


def get_orderid():
    return "ORD-" + secrets.token_hex(4).upper()


# ----------------- Store -----------------
class Store(UserMixin, db.Model):
    __tablename__ = "store"
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(50), nullable=False)

    openinghours = db.Column(db.String(100), default="09:00 to 18:30")
    password = db.Column(db.String(200), nullable=False)

    mpesa_shortcode = db.Column(db.String(100), default="None")
    ecocash_short_code = db.Column(db.String(100), default="None")

    confirmed = db.Column(db.Boolean, default=False)
    verified = db.Column(db.Boolean, default=False)

    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    registered_on = db.Column(db.DateTime, server_default=db.func.now())

    users = db.relationship("User", back_populates="store")
    products = db.relationship("Product", backref="store", lazy=True)
    orders = db.relationship("Order", back_populates="store")
    sales = db.relationship("Sales", back_populates="store")
    ingredients = db.relationship("Ingredient", backref="store")
    staff_members = db.relationship("Staff", back_populates="store", lazy=True)

# ----------------- Product -----------------
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    productname = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Float, nullable=False)
    pictures = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Integer)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), default="Uncategorized")
    warning = db.Column(db.String(100), default="Quantity Good")
    is_active = db.Column(db.Boolean, default=True)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"))
    # Relationships
    cart_items = db.relationship("CartItem", backref="product", lazy=True)
    order_items = db.relationship("OrderItem", backref="product", lazy=True)


# ----------------- Ingredient -----------------
class Ingredient(db.Model):
    __tablename__ = "ingredient"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100), default="General")

    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False)


# ----------------- User -----------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(50), unique=True, nullable=False)
    lastname = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    image_file = db.Column(db.Text, default="account.png")
    password = db.Column(db.String(200), nullable=False)


    confirmed = db.Column(db.Boolean, default=False)
    loyalty_points = db.Column(db.Integer, default=0)

    store_id = db.Column(db.Integer, db.ForeignKey("store.id"))

    # Relationships
    store = db.relationship("Store", back_populates="users")
    carts = db.relationship("Cart", backref="user", lazy=True)
    orders = db.relationship("Order", back_populates="user", lazy=True)

    def generate_confirmation_token(self, expiration=3600):
        s = TimedSerializer(current_app.config["SECRET_KEY"], expiration)
        return s.dumps({"confirm": self.id})

    def confirm(self, token):
        s = TimedSerializer(current_app.config["SECRET_KEY"])
        try:
            data = s.loads(token)
        except Exception:
            return False
        if data.get("confirm") != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        return True


# ----------------- Cart & CartItem -----------------
class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False)

    date_created = db.Column(db.DateTime, default=get_localTime)

    cart_items = db.relationship("CartItem", backref="cart", lazy=True)

    def total_items(self):
        return sum(item.quantity for item in self.cart_items)

    def total_amount(self):
        total = 0
        for item in self.cart_items:
            if item.product:
                total += item.product.price * item.quantity
            elif item.custom_meal:
                total += item.custom_meal.total_price * item.quantity
        return total


class CartItem(db.Model):
    __tablename__ = "cart_item"
    id = db.Column(db.Integer, primary_key=True)

    cart_id = db.Column(db.Integer, db.ForeignKey("cart.id"), nullable=False)

    # Either product or custom meal
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True)
    custom_meal_id = db.Column(db.Integer, db.ForeignKey("custom_meal.id"), nullable=True)

    quantity = db.Column(db.Integer, nullable=False, default=1)

    # Relationships
    custom_meal = db.relationship("CustomMeal", backref="cart_items_custom", lazy=True)

    def get_name(self):
        if self.product:
            return self.product.productname
        elif self.custom_meal:
            return self.custom_meal.name
        return "Unknown Item"

    def get_price(self):
        if self.product:
            return self.product.price
        elif self.custom_meal:
            return self.custom_meal.total_price
        return 0.0

    def get_total(self):
        return self.get_price() * self.quantity


# ----------------- Order & OrderItem -----------------
class Order(db.Model):
    __tablename__ = "order"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(200), default=get_orderid)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False)

    create_at = db.Column(db.DateTime, default=get_localTime)
    location = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(40), default="Pending")
    payment = db.Column(db.String(40), default="Cash")
    transactionID = db.Column(db.String(90), default="None")
    user_email = db.Column(db.String(120), nullable=False)

    customer_lat = db.Column(db.Float)
    customer_lng = db.Column(db.Float)


    deliveryguy = db.Column(db.String(50), default="Not Taken")
    screenshot = db.Column(db.Text)
    is_pos = db.Column(db.Boolean, default=False)
    user = db.relationship("User", back_populates="orders")
    store = db.relationship("Store", back_populates="orders")
    order_items = db.relationship("OrderItem", back_populates="order", lazy=True, cascade="all, delete-orphan")
    custom_meals = db.relationship("CustomMeal", backref="order", lazy=True)

    def local_time(self):
        return self.create_at.astimezone(ZoneInfo("Africa/Johannesburg"))


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)

    product_name = db.Column(db.String(50), nullable=False)
    product_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    order = db.relationship("Order", back_populates="order_items")


# ----------------- CustomMeal -----------------
class CustomMeal(db.Model):
    __tablename__ = "custom_meal"
    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(db.Integer, db.ForeignKey("order.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    name = db.Column(db.String(120), default="Custom Meal")
    base_price = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, nullable=False)

    ingredients = db.relationship(
        "CustomMealIngredient",
        back_populates="custom_meal",
        cascade="all, delete-orphan",
        lazy=True
    )


class CustomMealIngredient(db.Model):
    __tablename__ = "custom_meal_ingredient"
    id = db.Column(db.Integer, primary_key=True)

    custom_meal_id = db.Column(db.Integer, db.ForeignKey("custom_meal.id"), nullable=False)
    ingredient_name = db.Column(db.String(120), nullable=False)
    ingredient_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=1)

    custom_meal = db.relationship("CustomMeal", back_populates="ingredients")


# ----------------- Delivery & DeliveryGuy -----------------
class DeliveryGuy(UserMixin, db.Model):
    __tablename__ = "deliveryguy"
    id = db.Column(db.Integer, primary_key=True)
    names = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(30), unique=True, nullable=False)
    image_file = db.Column(db.String(140), default="account.png")
    password = db.Column(db.String(100), nullable=False)
    isfree = db.Column(db.Boolean, default=True)


class Delivery(db.Model):
    __tablename__ = "delivery"

    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(120))
    address = db.Column(db.String(100))
    status = db.Column(db.String(50))

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("order.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    delivery_guy_id = db.Column(db.Integer, db.ForeignKey("deliveryguy.id"))
    customer_pic = db.Column(db.Text)

    order = db.relationship(
        "Order",
        backref=db.backref("delivery", uselist=False),
        lazy=True
    )

# ----------------- Sales -----------------
class Sales(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    product_name = db.Column(db.String(50), nullable=False)
    product_id = db.Column(db.Integer, nullable=False)

    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    date_ = db.Column(db.DateTime, default=get_localTime)

    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False)
    store = db.relationship("Store", back_populates="sales")


# ----------------- Notifications -----------------
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_type = db.Column(db.String(20))
    user_id = db.Column(db.Integer)
    message = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)


# ----------------- Staff -----------------
class Staff(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    names = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(30), unique=True, nullable=False)
    role = db.Column(db.String(120))
    password = db.Column(db.String(100), nullable=False)

    store_id = db.Column(db.Integer, db.ForeignKey("store.id"))
    store = db.relationship("Store", back_populates="staff_members")


# ----------------- Administrater -----------------
class Administrater(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    password = db.Column(db.Text, nullable=False)


# ----------------- Ad -----------------
class Ad(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(120), nullable=False)
    image = db.Column(db.Text, nullable=False)

    # Where the ad points to
    link_type = db.Column(db.String(20))  # "product", "store", "external"
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=True)
    external_url = db.Column(db.String(255), nullable=True)

    is_active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.Integer, default=0)  # higher = shows first

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    store = db.relationship('Store', backref='ads_Store', lazy=True)
    product = db.relationship('Product', backref='ads_Product', lazy=True)

    class PushSubscription(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, nullable=False)  # link to your User table
        subscription_info = db.Column(JSON, nullable=False)