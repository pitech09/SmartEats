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
        stores = [
            {
                "name": "Main Street Store",
                "address": "123 Main St, Cityville",
                "email": "mainstreet@smarteats.com",
                "password": "StorePass123",
                "openinghours": "8am - 10pm",
                "phone": "123-456-7890"
            }
        ]

        for store_data in stores:
            # Check if already exists
            existing_store = Store.query.filter_by(email=store_data["email"]).first()
            if existing_store:
                print(f"⚠️ Store {store_data['email']} already exists. Skipping.")
                continue

            hashed_pw = bcrypt.generate_password_hash(store_data["password"]).decode("utf-8")
            new_store = Store(
                name=store_data["name"],
                address=store_data["address"],
                email=store_data["email"],
                password=hashed_pw,
                openinghours=store_data["openinghours"],
                phone=store_data["phone"]
            )

            db.session.add(new_store)
            print(f"✅ Created store: {store_data['email']}")

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



if __name__ == "__main__":
    create_admin_accounts()
