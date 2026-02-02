from flask import Flask
from flask_login import LoginManager, current_user
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///smarteats.db"

db = SQLAlchemy(app)
login_manager = LoginManager(app)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet",
    ping_interval=25,
    ping_timeout=60
)

# ======================
# SOCKET EVENTS
# ======================

@socketio.on("connect")
def on_connect(auth=None):
    if not current_user.is_authenticated:
        return False  

    user_room = f"user_{current_user.id}"
    join_room(user_room)

    emit("connected", {"message": "Socket connected"})
    print(f"User {current_user.id} connected")


@socketio.on("join_store")
def join_store(data):
    store_id = data.get("store_id")
    if store_id:
        join_room(f"store_{store_id}")
        emit("joined_store", {"store_id": store_id})


@socketio.on("ping_server")
def ping_server():
    emit("pong")


# ======================
# HELPER EMIT FUNCTIONS
# ======================

def notify_new_order(store_id):
    socketio.emit(
        "play_sound",
        {"sound": "new_order"},
        room=f"store_{store_id}"
    )


def notify_order_update(user_id):
    socketio.emit(
        "play_sound",
        {"sound": "order_update"},
        room=f"user_{user_id}"
    )


def notify_order_ready(user_id, store_id):
    socketio.emit(
        "play_sound",
        {"sound": "order_ready"},
        room=f"user_{user_id}"
    )
    socketio.emit(
        "order_ready",
        {},
        room=f"store_{store_id}"
    )


def update_cart_count(user_id, count):
    socketio.emit(
        "cart_updated",
        {"cart_count": count},
        room=f"user_{user_id}"
    )


# ======================
# RUN APP
# ======================
if __name__ == "__main__":
    socketio.run(app, debug=True)
