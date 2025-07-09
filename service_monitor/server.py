from app import app, init_app

if init_app():
    print("App initialized successfully.")
else:
    print("App failed to initialize.")
