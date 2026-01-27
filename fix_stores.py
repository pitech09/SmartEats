from application import db
from sqlalchemy.exc import IntegrityError
from manage import app
from application.models import Store

app.app_context().push()

stores = Store.query.all()
for i in stores:
	i.district = "Leribe"
	i.town = "Maputsoe, Mohalalitoe"
	print(i.is_active)
	i.is_active = True
	print(f"done with store {i.id}")
try:
	db.session.commit()
	print("successfully committed")
except IntegrityError:
	db.session.rollback()
