from . import socketio

def notify_store(store_id):
    print("notifying store.")
    socketio.emit("play_sound", {"sound": "new_order"}, room=str(store_id))

def notify_customer(customer_id):
    print("notifying customer")
    socketio.emit("play_sound", {"sound": "order_update"}, room=str(customer_id))

def notify_delivery(delivery_id):
    print("notifying delivery")
    socketio.emit("play_sound", {"sound": "order_ready"}, room=str(delivery_id))

def notify_admin(admin_id):
    print("notify_admin")
    socketio.emit("play_sound", {"sound": "admin_alert"}, room=str(admin_id))