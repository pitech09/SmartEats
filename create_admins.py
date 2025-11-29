# create_admins.py
from flask_bcrypt import Bcrypt
from application import create_app, db
from application.models import User, Administrater  # Adjust path if your models file is elsewhere
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
            {
                "username": "AdminTwo2",
                "email": "admin22@smarteats.com",
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
