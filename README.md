SmartEats 🍔🚴‍♂️

SmartEats is a digital food ordering and delivery platform built with Flask, Supabase, and Cloudinary, focused on simplifying food ordering at Roma Campus.

Local restaurants can onboard, customers can place orders, and delivery riders can manage and update deliveries through a mobile-friendly interface.

🚀 Features

User Authentication – Customer, Store, Delivery, and Admin roles

Restaurant Management – Vendors manage menus, food images, and orders

Food Ordering – Customers browse menus, checkout, and track orders

Delivery Dashboard – Riders update delivery status and location

Admin Panel – Analytics (sales, top products, order activity)

Supabase Database – Orders, users, deliveries, notifications

Cloudinary Storage – Food images, logos, and proof-of-delivery uploads

📂 Project Structure
application/
│── admin/              # Admin blueprint
│── auth/               # Authentication (login, register, roles)
│── delivery/           # Delivery blueprint (driver interface)
│── main/               # Main/public routes (landing, homepage)
│── store/              # Store blueprint (restaurant UI)
│── static/             # Static assets (CSS, JS, vendor libs)
│   ├── css/
│   ├── js/
│   └── vendor/         # Bootstrap, jQuery, etc.
│── templates/          # Jinja2 templates (HTML views)
│── utils/              # Helpers (email, Cloudinary, forms, etc.)
│   ├── email.py
│   ├── forms.py
│   └── models.py       # Database models (Supabase)
│── migrations/         # DB migrations / schema references
│── config.py           # Flask app configuration


📊 Database (Supabase)

Tables:

users – Customer, store, delivery, and admin accounts

stores – Restaurant data (name, logo, contact info)

menus – Menu items with price & Cloudinary image URLs

orders – Orders with status (pending, accepted, delivered)

order_items – Items inside each order

delivery – Delivery assignments & location updates

notifications – Order & delivery notifications

🔒 RLS Policies: Each role (customer, store, delivery, admin) should only see their own data.

☁️ Storage (Cloudinary)

Used for:

Menu item images

Store logos

Proof-of-delivery photos

Example:
import cloudinary.uploader

upload_result = cloudinary.uploader.upload(
    "food.jpg",
    folder="smarteats/menus"
)
print(upload_result["secure_url"])

📌 Roadmap
Supabase Realtime for live order updates
Push Notifications (for delivery and customer updates)

👨‍💻 Author

Khauhelo Makara
BSc Computer Science, National University of Lesotho
GitHub: pitech09
