from application import db
from application.models import User
from sqlalchemy.exc import IntegrityError
from manage import app

app.app_context().push()

users = User.query.filter(User.district == None, User.town == None).all()
for i in users:
	i.district = "Leribe"
	i.town = "Maputsoe, Ha Maqele"
	print("Done with User", i.id)

try:
	db.session.commit()
	for i in users:
		print(i.district)
	print("successfully updated existing users")
except IntegrityError:
	db.session.rollback()
	print("Failed")

