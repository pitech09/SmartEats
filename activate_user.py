from application import db
from manage import app

from application.models import *

app.app_context().push()

user=input("user email")
find_user = User.query.filter(User.email==user).first()
if not find_user:
	print("no user found")
else:
	find_user.confirmed=True
	print("user confirmed")
	db.session.add(find_user)
	db.session.commit()

