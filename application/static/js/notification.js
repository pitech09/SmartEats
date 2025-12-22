// Replace with your VAPID public key
const publicVapidKey = "YOUR_PUBLIC_VAPID_KEY";

// Subscribe the user to push notifications
async function subscribeUser() {
    if (!("serviceWorker" in navigator)) {
        console.error("Service workers not supported in this browser.");
        return;
    }

    try {
        // 1. Register the service worker
        const register = await navigator.serviceWorker.register('/static/sw.js', { scope: '/' });

        // 2. Request notification permission
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
            console.log("Notification permission denied.");
            return;
        }

        // 3. Subscribe user
        const subscription = await register.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(publicVapidKey)
        });

        // 4. Send subscription to backend
        await fetch('/subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(subscription)
        });

        console.log("User successfully subscribed for push notifications.");
    } catch (err) {
        console.error("Error during subscription:", err);
    }
}

// Helper function to convert VAPID key
function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    return Uint8Array.from([...rawData].map(c => c.charCodeAt(0)));
}

// Automatically subscribe user on page load
window.addEventListener('load', () => {
    subscribeUser();
});

