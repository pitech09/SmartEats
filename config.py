import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = '17849dd2877c52dbb1009c50693c6eb5'
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    ALLOWED_EXTENSIONS = {'png', 'jpeg', 'jpg', 'gif'}
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 1800

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    MAIL_SERVER='smtp.gmail.com'
    MAIL_PORT=587
    MAIL_USE_TLS = True
    #MAIL_USE_SSL=True
    MAIL_USERNAME = 'pitechcorp7@gmail.com'
    MAIL_PASSWORD = 'rljm azij wply ihrp'
    UPLOAD_PATH = os.path.join(basedir, 'static/css/images/profiles')
    UPLOAD_PRODUCTS = os.path.join(basedir, 'static/css/images/products')

    UPLOAD_DELIVERY = os.path.join(basedir, 'static/css/images/deliveries')
    os.makedirs(UPLOAD_PRODUCTS, exist_ok=True)
    os.makedirs(UPLOAD_PATH, exist_ok=True)
    os.makedirs(UPLOAD_DELIVERY, exist_ok=True)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'data-dev.db')



class ProductionConfig(Config):
    MAIL_SERVER='smtp.gmail.com'
    MAIL_PORT=465
    MAIL_USE_TLS = False
    MAIL_USE_SSL=True
    MAIL_USERNAME = 'pitechcorp7@gmail.com'
    MAIL_PASSWORD = 'rljm azij wply ihrp'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'data.sqlite')


config = {
 'development': DevelopmentConfig,
 'production': ProductionConfig,
 'default': DevelopmentConfig
}
