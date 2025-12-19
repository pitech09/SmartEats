from flask import url_for
from manage import app
with app.test_request_context():
    print(url_for('main.myorders'))
