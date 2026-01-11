from application import db
from manage import app
app.app_context().push()
db.drop_all()
print("database cleared")
db.create_all()
print("created tables")
