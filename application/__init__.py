from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_mail import Mail
from flask_caching import Cache
from flask_profiler import Profiler
from flask_compress import Compress
from config import config
from flask_socketio import SocketIO, join_room

db = SQLAlchemy()
mail = Mail()
cache = Cache()
compress = Compress()
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = "auth.newlogin"

socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode="eventlet",
    serve_static=False,        # 🔥 Fixes BrokenPipeError
    always_connect=True,
    ping_timeout=20,
    ping_interval=10
)

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    socketio.init_app(app)

    # Upload paths
    app.config['UPLOAD_PATH'] = 'static/css/images/profiles/'
    app.config['UPLOAD_PRODUCTS'] = 'static/css/images/products/'
    app.config['UPLOAD_PAYMENT_PROOF'] = 'static/css/images/payments/'

    db.init_app(app)
    mail.init_app(app)
    cache.init_app(app)
    compress.init_app(app)
    login_manager.init_app(app)

    # Blueprints
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from .store import store as store_blueprint
    app.register_blueprint(store_blueprint, url_prefix='/store')

    from .delivery import delivery as delivery_blueprint
    app.register_blueprint(delivery_blueprint, url_prefix='/delivery')

    from .admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')

    @socketio.on("connect")
    def handle_connect(auth):
        if current_user.is_authenticated:
            join_room(str(current_user.id))
            print("User joined room:", current_user.id)

    return app
