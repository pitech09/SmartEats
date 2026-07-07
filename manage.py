import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent
_venv_python = _project_root / "venv" / "bin" / "python"

# Re-exec through the project venv so we do not pick up broken user-site packages.
if Path(sys.executable).as_posix() != _venv_python.as_posix() and _venv_python.exists():
    os.execv(str(_venv_python), [str(_venv_python), *sys.argv])

import eventlet

eventlet.monkey_patch()

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

# Development only
if __name__ == "__main__":
    #app.run('0.0.0.0', port=5000, debug=True)
    socketio.run(
       app,
        host="0.0.0.0",
       port=5000,
       debug=True,
       use_reloader=False
    )
