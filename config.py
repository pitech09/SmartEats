import os
basedir = os.path.abspath(os.path.dirname(__file__))
import cloudinary
import cloudinary.uploader
import cloudinary.api
from sqlalchemy.pool import NullPool, QueuePool



class Config:
    SECRET_KEY = '19fe4df09e28188141de802f9ae70a02'
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    ALLOWED_EXTENSIONS = {'png', 'jpeg', 'jpg', 'gif'}
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_NAME = 'smarteats_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 1800  # seconds
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,        # Checks if connection is alive before using
        "pool_recycle": 280,          # Reconnect before Supabase timeout
        "pool_size": 5,               # Number of connections in the pool
        "max_overflow": 10,           # Allow extra connections when needed
    }

    # Flask-Compress config
    COMPRESS_ALGORITHM = 'gzip'
    COMPRESS_LEVEL = 6
    COMPRESS_MIN_SIZE = 500
    COMPRESS_MIMETYPES = [
        'text/html', 'text/css', 'application/json', 'application/javascript'
    ]

    # Flask-Profiler config
    ENABLE_PROFILER = False
    FLASK_PROFILER = {
        "enabled": False,
        "storage": {"engine": "sqlite"},
        "basicAuth": {"enabled": False},
        "ignore": ["^/static/.*"]
    }

    @staticmethod
    def init_app(app):
        
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False

    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'pitechcorp7@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'rljm azij wply ihrp'
    USE_CLOUDINARY = False
    UPLOAD_PATH = os.path.join(basedir, 'static/css/images/profiles')
    UPLOAD_PRODUCTS = os.path.join(basedir, 'static/css/images/products')
    UPLOAD_DELIVERY = os.path.join(basedir, 'static/css/images/deliveries')

    SQLALCHEMY_DATABASE_URI = os.environ.get('MY_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data-dev.db')



    @staticmethod
    def init_app(app):
        # Ensure upload directories exist in development
        os.makedirs(DevelopmentConfig.UPLOAD_PATH, exist_ok=True)
        os.makedirs(DevelopmentConfig.UPLOAD_PRODUCTS, exist_ok=True)
        os.makedirs(DevelopmentConfig.UPLOAD_DELIVERY, exist_ok=True)


class ProductionConfig(Config):
    DEBUG = False
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    USE_CLOUDINARY = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'pitechcorp7@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'rljm azij wply ihrp'
    SQLALCHEMY_DATABASE_URI = (
    "postgresql://postgres.lqqhcvfotzowyitgnfgf:Boity%202003"
    "@aws-1-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require"
)

    # Configuration
    cloudinary.config(
        cloud_name = 'di9fnjxk5',
        api_key = '218793494492183',
        api_secret = 's4FgdXdoys3aBFWh_ZnXJHgye2U',
        secure = True
)


# Dict to map config names
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig
}
