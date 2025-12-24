# create_admins.py
from flask_bcrypt import Bcrypt
from application import create_app, db
from application.models import User, Administrater, Store, DeliveryGuy  # Ensure DeliveryGuy is imported correctly
from manage import app

def create_admin_accounts():
    bcrypt = Bcrypt(app) 

    with app.app_context():
        # Admins
        admins = [
            {
                "username": "AdminOne1",
                "email": "admin12@smarteats.com",
                "password": "AdminPass123",
            },
        ]
        customers = [
            {
                "username": "Skhau",
                "lastname": "Makara",
                "email": "customer1@smarteats.com",
                "password": "CustomerPass123",
            }
        ]
        # Stores
        stores = [
            {
                "name": "SmartEat",
                "address": "Remote",
                "email": "smarteats200@gmail.com",
                "password": "StorePass123",
                "openinghours": "8am - 10pm",
                "phone": "266 5853 8173"
            },
            {
                "name": "Spicy Noodles Ls",
                "address": "Maputsoe Pela borderGate",
                "email": "spicynoodles@gmail.com",
                "password": "SpicyLsPass123",
                "openinghours": "24/7 Orders from 8am - 10pm",
                "phone": "+26657130629"
            }
        ]

        # Delivery Agents
        delivery_agents = [
            {
                "name": "DeliveryGuyOne",
                "email": "delivery1@smarteats.com",
                "password": "DeliveryPass123"
            },
            {
                "name": "DeliveryGuyTwo",
                "email": "delivery2@smarteats.com",
                "password": "DeliveryPass123"
            }
        ]

        # Create Stores
        for store_data in stores:
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

        # Create Customers
        for customer_data in customers:
            existing_customer = User.query.filter_by(email=customer_data["email"]).first()
            if existing_customer:
                print(f"⚠️ Customer {customer_data['email']} already exists. Skipping.")
                continue

            hashed_pw = bcrypt.generate_password_hash(customer_data["password"]).decode("utf-8")
            new_customer = User(
                username=customer_data["username"],
                lastname=customer_data["lastname"],
                email=customer_data["email"],
                password=hashed_pw,
            )
            db.session.add(new_customer)
            print(f"✅ Created customer: {customer_data['email']}")

        # Create Admins
        for admin_data in admins:
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

        # Create Delivery Agents
        for agent in delivery_agents:
            existing_agent = DeliveryGuy.query.filter_by(email=agent["email"]).first()
            if existing_agent:
                print(f"⚠️ Delivery agent {agent['email']} already exists. Skipping.")
                continue

            hashed_pw = bcrypt.generate_password_hash(agent["password"]).decode("utf-8")
            new_agent = DeliveryGuy(
                names=agent["name"],
                email=agent["email"],
                password=hashed_pw
            )
            db.session.add(new_agent)
            print(f"✅ Created delivery agent: {agent['email']}")

        db.session.commit()
        print("🎉 All admin and delivery agent accounts created successfully!")


if __name__ == "__main__":
    create_admin_accounts()
