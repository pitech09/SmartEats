from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_mail import Mail
from flask_caching import Cache
from flask_compress import Compress
from flask_socketio import SocketIO, join_room
from config import config

# Extensions
db = SQLAlchemy()
mail = Mail()
cache = Cache()
compress = Compress()

login_manager = LoginManager()
login_manager.session_protection = "strong"
login_manager.login_view = "auth.newlogin"

socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode="eventlet",
    ping_timeout=20,
    ping_interval=25
)

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # Init extensions
    db.init_app(app)
    mail.init_app(app)
    cache.init_app(app)
    compress.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)

    # Upload paths
    app.config["UPLOAD_PATH"] = "static/css/images/profiles/"
    app.config["UPLOAD_PRODUCTS"] = "static/css/images/products/"
    app.config["UPLOAD_PAYMENT_PROOF"] = "static/css/images/payments/"

    # Blueprints
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix="/auth")

    from .store import store as store_blueprint
    app.register_blueprint(store_blueprint, url_prefix="/store")

    from .delivery import delivery as delivery_blueprint
    app.register_blueprint(delivery_blueprint, url_prefix="/delivery")

    from .admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix="/admin")

    # Socket.IO events
    @socketio.on("connect")
    def handle_connect(auth):
        if current_user.is_authenticated:
            join_room(str(current_user.id))
            print(f"User {current_user.id} joined room")

    return app
