import os
basedir = os.path.abspath(os.path.dirname(__file__))
import cloudinary
import cloudinary.uploader
import cloudinary.api
from sqlalchemy.pool import NullPool, QueuePool

class Config:
    SECRET_KEY = '19fe4df09e28188141de802f9ae70a02'
    SQLALCHEMY_COMMIT_ON_TEARDOWN = False
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    ALLOWED_EXTENSIONS = {'png', 'jpeg', 'jpg', 'gif'}
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_NAME = 'smarteats_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 1800  # seconds
    WTF_CSRF_ENABLED = True
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": 5,
        "max_overflow": 10,
    }

    # Flask-Compress
    COMPRESS_ALGORITHM = 'gzip'
    COMPRESS_LEVEL = 6
    COMPRESS_MIN_SIZE = 500
    COMPRESS_MIMETYPES = [
        'text/html', 'text/css', 'application/json', 'application/javascript'
    ]

    # Flask-Profiler
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

    # Email (Gmail)
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = 'khauhelo872@gmail.com'
    MAIL_PASSWORD = 'gvzi kwcq vgzg xawr'
    MAIL_DEBUG = True
    MAIL_DEFAULT_SENDER = 'khauhelo872@gmail.com'

    # SendGrid (if needed later)
    SENDGRID_API_KEY = 'SG.INSERT_YOUR_KEY_HERE'
    SENDGRID_FROM_EMAIL = 'noreply@smarteats.com'

    USE_CLOUDINARY = False

    # Upload paths
    UPLOAD_PATH = os.path.join(basedir, 'static/css/images/profiles')
    UPLOAD_PRODUCTS = os.path.join(basedir, 'static/css/images/products')
    UPLOAD_DELIVERY = os.path.join(basedir, 'static/css/images/deliveries')

    # Database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'data-dev.db')

    @staticmethod
    def init_app(app):
        os.makedirs(DevelopmentConfig.UPLOAD_PATH, exist_ok=True)
        os.makedirs(DevelopmentConfig.UPLOAD_PRODUCTS, exist_ok=True)
        os.makedirs(DevelopmentConfig.UPLOAD_DELIVERY, exist_ok=True)


class ProductionConfig(Config):
    DEBUG = False

    # Email (Gmail)
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = 'khauhelo872@gmail.com'
    MAIL_PASSWORD = 'gvzi kwcq vgzg xawr'
    MAIL_DEFAULT_SENDER = 'khauhelo872@gmail.com'

    USE_CLOUDINARY = True

    # Database (Supabase)
    SQLALCHEMY_DATABASE_URI = (
        "postgresql://postgres.lqqhcvfotzowyitgnfgf:Boity%202003"
        "@aws-1-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require"
    )

    # Cloudinary config
    cloudinary.config(
        cloud_name='di9fnjxk5',
        api_key='218793494492183',
        api_secret='s4FgdXdoys3aBFWh_ZnXJHgye2U',
        secure=True
    )

    @staticmethod
    def init_app(app):
        pass


# Config dict
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig
}
