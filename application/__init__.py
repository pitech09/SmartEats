from flask import Flask
from flask_sqlalchemy import SQLAlchemy  # type: ignore
from flask_login import LoginManager  # type: ignore
from flask_mail import Mail  # type: ignore
from flask_caching import Cache  # type: ignore
from flask_profiler import Profiler  # type: ignore
from flask_compress import Compress  # type: ignore
from config import config

# Initialize extensions
db = SQLAlchemy()
mail = Mail()
cache = Cache()
compress = Compress()
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = "auth.newlogin"


def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # Upload paths
    app.config['UPLOAD_PATH'] = 'static/css/images/profiles/'
    app.config['UPLOAD_PRODUCTS'] = 'static/css/images/products/'
    app.config['UPLOAD_PAYMENT_PROOF'] = 'static/css/images/payments/'

    # Initialize extensions
    db.init_app(app)
    mail.init_app(app)
    cache.init_app(app)
    compress.init_app(app)

    # Flask-Profiler (enabled only in development unless needed)
    if app.config.get("ENABLE_PROFILER", False):
        Profiler(app)

    login_manager.init_app(app)

    # Register blueprints
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from .store import store as store_blueprint
    app.register_blueprint(store_blueprint, url_prefix='/store')

    from .delivery import delivery as delivery_blueprint
    app.register_blueprint(delivery_blueprint, url_prefix='/delivery')

    return app
