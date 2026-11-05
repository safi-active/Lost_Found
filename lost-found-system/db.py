import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Connect to MongoDB (using URI from .env or default local)
client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/lost_found"))
db = client.lost_found

# --- Collections ---
users = db.users
lost_claims = db.lost_claims
found_items = db.found_items
notifications = db.notifications
investigations = db.investigations
audit_logs = db.audit_logs

# --- Initialize Indexes ---
# Indexes make database searches faster (e.g., finding a user by email)
def init_db():
    # Users indexes (unique prevents duplicate accounts)
    users.create_index("email", unique=True)
    users.create_index("username", unique=True)
    for index_name, index in users.index_information().items():
        if (
            index.get("key") == [("student_id", 1)]
            and index.get("unique")
            and not index.get("sparse")
        ):
            users.drop_index(index_name)
    users.create_index("student_id", unique=True, sparse=True)

    # Lost Claims indexes
    lost_claims.create_index("status")
    lost_claims.create_index("user_id")
    lost_claims.create_index("item_name")
    lost_claims.create_index("created_at")

    # Found Items indexes
    found_items.create_index("status")
    found_items.create_index("item_name")
    found_items.create_index("created_at")

    # Notifications indexes
    notifications.create_index("recipient_id")
    notifications.create_index([("read", 1), ("created_at", -1)])

    # Audit logs
    audit_logs.create_index("admin_id")
    audit_logs.create_index("created_at")