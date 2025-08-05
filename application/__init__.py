from flask import Flask
from flask_sqlalchemy import SQLAlchemy # type: ignore
from flask_login import LoginManager  # type: ignore
from config import *
from flask_mail import Mail   # type: ignore
#from flask_socketio import SocketIO, emit

db = SQLAlchemy()
#socketio = SocketIO()

login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = "auth.newlogin"


def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    UPLOAD_PATH = 'static/css/images/profiles/'
    UPLOAD_PRODUCTS = 'static/css/images/products/'
    UPLOAD_PAYMENT_PROOF = 'static/css/images/payments/'
    login_manager.init_app(app)
    app.config['UPLOAD_PATH'] = UPLOAD_PATH
    app.config['UPLOAD_PRODUCTS'] = UPLOAD_PRODUCTS
    app.config['UPLOAD_PAYMENT_PROOF'] = UPLOAD_PAYMENT_PROOF

    db.init_app(app)

    mail = Mail(app)
    mail.init_app(app)

    #routes will go here
    #blueprint registration

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from .store import store as pharmscy_blueprint
    app.register_blueprint(pharmscy_blueprint, url_prefix='/store')
    
    from .delivery import delivery as delivery_blueprint
    app.register_blueprint(delivery_blueprint, url_prefix='/delivery')
#
  #      from application.models import Pharmacy # type: ignore
   #     pharmacies = Pharmacy.query.all()
    #    return dict(pharmacies=pharmacies)

    return app
