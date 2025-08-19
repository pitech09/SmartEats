import os
from application import create_app, db
from flask_migrate import Migrate  # type: ignore


# Create the Flask app instance
app = create_app(os.getenv('FLASK_CONFIG') or 'default')
migrate = Migrate(app, db)


def make_shell_context():
    return dict(app=app, db=db)
app.shell_context_processor(make_shell_context)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)

