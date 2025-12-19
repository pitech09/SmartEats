import os
from application import create_app, db, socketio
from flask_migrate import Migrate
from application.models import Product
from application.utils.cache import products_cache

# Create Flask app
app = create_app(os.getenv("FLASK_CONFIG", "default"))

# Setup migrations
migrate = Migrate(app, db)

# Shell context
@app.shell_context_processor
def make_shell_context():
    return {
        "app": app,
        "db": db,
        "Product": Product
    }

#