# create_admins.py
from flask_bcrypt import Bcrypt
from application import create_app, db
from application.models import User, Administrater, Store  # Adjust path if your models file is elsewhere
from manage import app
def create_admin_accounts():
    bcrypt = Bcrypt(app) 

    with app.app_context():
        admins = [
            {
                "username": "AdminOne1",
                "email": "admin12@smarteats.com",
                "password": "AdminPass123",
            },

        ]
        customers = [
            {
                "username": "lekula",
                "lastname": "tsau",
                "email": "lekau@gmail.com",
                "password": "CustPass123",
            },
            {
                "username": "johanes",
                "lastname": "lekoae",
                "email": "tsau@gmail.com",
                "password": "CustPass123",
            },
        ]

        stores = [
            {
                "name": "Majezz Eatery",
                "address": "Maputsoe Ha Maqele",
                "email": "danielnteso5@gmail.com",
                "password": "MajezzNteso123",
                "phone":" +266 5786 3240",
                "opening_hours":"8:00 AM - 9:00 PM",
            }
        ]

        for store_data in stores:
            # Check if already exists
            existing = Store.query.filter_by(email=store_data["email"]).first()

            if existing:
                print(f"⚠️ {store_data['email']} already exists. Skipping.")
                continue

            hashed_pw = bcrypt.generate_password_hash(store_data["password"]).decode("utf-8")
            new_store = Store(
                name=store_data["name"],
                address=store_data["address"],
                email=store_data["email"],
                password=hashed_pw,  
                phone=store_data["phone"],
                openinghours=store_data["opening_hours"],
            )
            new_store.verified = True  # Mark as verified
            new_store.confirmed = True  # Mark as confirmed
            db.session.add(new_store)
            print(f"✅ Created store: {store_data['email']}")

        db.session.commit()
        print("🎉 All store accounts created successfully!"
              )
        for admin_data in admins:
            # Check if already exists
            existing = User.query.filter_by(email=admin_data["email"]).first()
            if existing:
                print(f"⚠️ {admin_data['email']} already exists. Skipping.")
                continue

            hashed_pw = bcrypt.generate_password_hash(admin_data["password"]).decode("utf-8")
            new_admin = Administrater(
                username=admin_data["username"],
                email=admin_data["email"],
                password=hashed_pw,  
                
            )

            db.session.add(new_admin)
            print(f"✅ Created admin: {admin_data['email']}")

        db.session.commit()
        print("🎉 All admin accounts created successfully!")


        for customer_data in customers:
            # Check if already exists
            existing = User.query.filter_by(email=customer_data["email"]).first()
            if existing:
                print(f"⚠️ {customer_data['email']} already exists. Skipping.")
                continue

            hashed_pw = bcrypt.generate_password_hash(admin_data["password"]).decode("utf-8")
            new_user = User(
                username=customer_data["username"],
                lastname=customer_data["lastname"],
                email=customer_data["email"],
                password=hashed_pw,  
            )

            db.session.add(new_user)
            print(f"✅ Created customer: {customer_data['email']}")

        db.session.commit()
        print("🎉 All customer accounts created successfully!")

if __name__ == "__main__":
    create_admin_accounts()
