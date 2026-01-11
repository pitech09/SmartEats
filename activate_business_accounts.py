from sqlalchemy.exc import IntegrityError
from application.models import Store
from manage import app
from application import db
app.app_context().push()

accounts = Store.query.all()
if not accounts:
	print("no accounts registered")
for account in accounts:
	print(f"Stores: {account.name}")
	print(f"Verified: {account.verified} ")
	print(f"Confirmed Email: {account.confirmed}")
	if account.confirmed and account.verified:
		print(f"Account for {account.name} is verified and email confirmed")
	else:
		print('No Active accounts found.')

		account.confirmed = True
		
		db.session.add(account)
		try:
			db.session.commit()
			print(f"Stores: {account.name}")
			print(f"Verified: {account.verified} ")
			print(f"Confirmed Email: {account.confirmed}")
			print(f"Account for {account.name} activated and confirmed.")
		except IntegrityError:
			db.session.rollback()
		
			print("Account exists. Rolling database back.")

print("Adding accounts done.")
