import os
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-should-change-this'
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ALLOWED_EXTENSIONS = {'png', 'jpeg', 'jpg', 'gif'}
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_NAME = 'smarteats_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 1800  # seconds

    # Flask-Caching config
    CACHE_TYPE = 'SimpleCache'  # or "RedisCache"
    CACHE_DEFAULT_TIMEOUT = 300

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

    UPLOAD_PATH = os.path.join(basedir, 'static/css/images/profiles')
    UPLOAD_PRODUCTS = os.path.join(basedir, 'static/css/images/products')
    UPLOAD_DELIVERY = os.path.join(basedir, 'static/css/images/deliveries')

    SQLALCHEMY_DATABASE_URI = os.environ.get('MY_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data-dev.db')

    ENABLE_PROFILER = True
    FLASK_PROFILER = {
        "enabled": True,
        "storage": {"engine": "sqlite"},
        "basicAuth": {"enabled": False},
        "ignore": ["^/static/.*"]
    }

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
    MAIL_USE_TLS = False
    MAIL_USE_SSL = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or "postgresql://pitech:GG9IahwNPkHzuns2cdAYUqpMD3HyVyav@dpg-d28teh6r433s73bv0fg0-a.ohio-postgres.render.com/smarteats_nx5v"
        

    # Disable profiler in production
    ENABLE_PROFILER = False
    FLASK_PROFILER = {
        "enabled": False,
        "storage": {"engine": "sqlite"},
        "basicAuth": {"enabled": False},
        "ignore": ["^/static/.*"]
    }
    UPLOAD_PATH = os.path.join(basedir, 'static/css/images/profiles')
    UPLOAD_PRODUCTS = os.path.join(basedir, 'static/css/images/products')
    UPLOAD_DELIVERY = os.path.join(basedir, 'static/css/images/deliveries')

    @staticmethod
    def init_app(app):
        # Ensure upload directories exist in development
        os.makedirs(DevelopmentConfig.UPLOAD_PATH, exist_ok=True)
        os.makedirs(DevelopmentConfig.UPLOAD_PRODUCTS, exist_ok=True)
        os.makedirs(DevelopmentConfig.UPLOAD_DELIVERY, exist_ok=True)


# Dict to map config names
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig
}
