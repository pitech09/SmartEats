import os
from application import create_app, db, socketio
from flask_migrate import Migrate  # type: ignore
from application.models import Product
from application.utils.cache import products_cache

# Create the Flask app instance
app = create_app(os.getenv('FLASK_CONFIG') or 'default')
migrate = Migrate(app, db)


def make_shell_context():
    return dict(app=app, db=db)
app.shell_context_processor(make_shell_context)

if __name__ == "__main__":
    if products_cache is None:
        #On preload, load all products to memory
        products_cache.set()

    socketio.run(app, host="0.0.0.0", port=5000)
    

