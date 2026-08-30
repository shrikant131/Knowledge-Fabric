"""Start Knowledge Fabric locally without Docker."""
from admin.app import app
if __name__ == "__main__":
    import os
    app.run(host=os.getenv("KF_HOST","127.0.0.1"), port=int(os.getenv("KF_PORT","5050")), debug=False)
