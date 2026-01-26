from application import db
from application.models import Store
from sqlalchemy.exc import IntegrityError
from manage import app

app.app_context().push()

store = Store.query.all()
for i in store:
	i.district = "Leribe"
	i.town = "Maputsoe, Ha Maqele"
	print("Done with Store", i.id)

try:
	db.session.commit()
	for i in store:
		print(i.district)
except IntegrityError:
	db.session.rollback()
	print("Failed")
