import os
from application import create_app, db
from flask_migrate import Migrate  # type: ignore
from gunicorn.app.wsgiapp import WSGIApplication
import sys

# Create the Flask app instance
app = create_app(os.getenv('FLASK_CONFIG') or 'default')
migrate = Migrate(app, db)

# Optional: Define the shell context
def make_shell_context():
    return dict(app=app, db=db)

if __name__ == '__main__':
    # Added a condition to run the app only when needed
    #if len(sys.argv) == 1:
    
     #   sys.argv += ['manage:app', '--bind=0.0.0.0:8000', '--workers=12', '--threads=4']
    #sys.exit(WSGIApplication("%(prog)s [OPTIONS] [APP_MODULE]").run())
    #app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))