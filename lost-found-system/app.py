import os
import webbrowser
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from bson import ObjectId
from werkzeug.utils import secure_filename
from db import init_db, lost_claims, found_items, notifications, audit_logs, users

from auth import register_user, login_user, logout_user, login_required, admin_required

# Setup Flask with custom frontend folder paths
app = Flask(__name__, template_folder="../frontend/templates", static_folder="../frontend/static")
app.secret_key = os.getenv("SECRET_KEY", "dev_key_fallback")

# Configure file uploads for found items
UPLOAD_FOLDER = os.path.abspath(os.path.join(app.static_folder, 'uploads'))
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
# Initialize DB indexes on startup
with app.app_context():
    init_db()


def _normalise_match_text(value):
    return " ".join((value or "").casefold().split())


def _is_potential_match(claim, item):
    claim_name = _normalise_match_text(claim.get("item_name"))
    found_name = _normalise_match_text(item.get("item_name"))
    return (
        bool(claim_name and found_name)
        and (claim_name in found_name or found_name in claim_name)
        and _normalise_match_text(claim.get("color"))
        == _normalise_match_text(item.get("color"))
    )


# --- AUTH ROUTES ---
@app.route("/")
def index():
    stats = {
        "students_helped": len(
            lost_claims.distinct("user_id", {"status": {"$in": ["resolved", "returned"]}})
        ),
        "items_reported": lost_claims.count_documents({}) + found_items.count_documents({}),
        "items_recovered": found_items.count_documents({"status": "returned"}),
    }
    return render_template("index.html", stats=stats)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        success, msg = login_user(email, password)
        if success:
            return redirect(url_for("admin_dashboard") if session["role"] == "admin" else url_for("dashboard"))
        flash(msg, "danger")
    return render_template("login.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        success, msg = login_user(
            request.form.get("email"),
            request.form.get("password"),
        )
        if success and session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        if success:
            logout_user()
            flash("This sign-in is restricted to campus security staff.", "danger")
        else:
            flash(msg, "danger")
    return render_template("admin_login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        student_id = request.form.get("student_id")
        success, msg = register_user(username, email, password, student_id=student_id)
        if success:
            flash(msg, "success")
            return redirect(url_for("login"))
        flash(msg, "danger")
    return render_template("register.html")

@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    if request.method != "POST":
        return redirect(url_for("index"))
    logout_user()
    flash("Successfully logged out.", "success")
    return redirect(url_for("index"))

# --- STUDENT ROUTES ---
@app.route("/dashboard")
@login_required
def dashboard():
    # Get user's recent claims (limit 5 for dashboard)
    user_claims = list(lost_claims.find({"user_id": ObjectId(session["user_id"])}).sort("created_at", -1).limit(5))
    return render_template("dashboard.html", claims=user_claims)

@app.route("/claim", methods=["GET", "POST"])
@login_required
def claim_item():
    if request.method == "POST":
        item_name = request.form.get("item_name")
        color = request.form.get("color")
        date_lost_str = request.form.get("date_lost")
        
        # 1. Validation
        if not item_name or not color or not date_lost_str:
            flash("Item name, color, and date lost are required.", "danger")
            return redirect(url_for("claim_item"))
        try:
            date_lost = datetime.strptime(date_lost_str, "%Y-%m-%d")
        except ValueError:
            flash("Enter a valid date lost.", "danger")
            return redirect(url_for("claim_item"))
        
        # 2. Auto-register the claim
        claim_doc = {
            "claim_id": f"LOST-{int(datetime.utcnow().timestamp())}",
            "user_id": ObjectId(session["user_id"]),
            "item_name": item_name,
            "color": color,
            "date_lost": date_lost,
            "location": request.form.get("location", ""),
            "description": request.form.get("description", ""),
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        lost_claims.insert_one(claim_doc)
        
        # 3. Create notification for Admin
        notifications.insert_one({
            "recipient_id": "admin", 
            "message": f"New lost claim submitted: {item_name} ({color})",
            "type": "new_claim",
            "read": False,
            "created_at": datetime.utcnow()
        })
        
        flash("Lost item claim registered successfully!", "success")
        return redirect(url_for("my_claims"))
        
    return render_template("claim_form.html")

@app.route("/my_claims")
@login_required
def my_claims():
    claims = list(lost_claims.find({"user_id": ObjectId(session["user_id"])}).sort("created_at", -1))
    return render_template("my_claim.html", claims=claims)

@app.route("/notifications")
@login_required
def view_notifications():
    recipient = session["user_id"] if session["role"] != "admin" else "admin"
    notifications.update_many(
        {"recipient_id": recipient, "read": False},
        {"$set": {"read": True}},
    )
    notifs = list(notifications.find({"recipient_id": recipient}).sort("created_at", -1))
    return render_template("notifications.html", notifications=notifs)

# --- ADMIN ROUTES ---
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    # Efficient MongoDB Aggregations for Stats
    stats = {
        "total_claims": lost_claims.count_documents({}),
        "total_found": found_items.count_documents({}),
        "pending_claims": lost_claims.count_documents({"status": "pending"}),
        "stored_items": found_items.count_documents({"status": "stored"}),
        "returned_items": found_items.count_documents({"status": "returned"})
    }
    return render_template("admin_dashboard.html", stats=stats)

@app.route("/admin/found", methods=["GET", "POST"])
@admin_required
def admin_found():
    if request.method == "POST":
        item_name = request.form.get("item_name")
        color = request.form.get("color")
        date_received_str = request.form.get("date_received")
        
        if not item_name or not color or not date_received_str:
            flash("Item name, color, and date received are required.", "danger")
            return redirect(url_for("admin_found"))
        try:
            date_received = datetime.strptime(date_received_str, "%Y-%m-%d")
        except ValueError:
            flash("Enter a valid date received.", "danger")
            return redirect(url_for("admin_found"))
        
        # Handle Photo Upload
        photo_path = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                photo_path = f"uploads/{filename}"
                
        found_doc = {
            "recovered_id": f"FOUND-{int(datetime.utcnow().timestamp())}",
            "item_name": item_name,
            "color": color,
            "date_received": date_received,
            "location_found": request.form.get("location_found", ""),
            "description": request.form.get("description", ""),
            "handover_name": request.form.get("handover_name", ""),
            "handover_contact": request.form.get("handover_contact", ""),
            "photo_path": photo_path,
            "registered_by": ObjectId(session["user_id"]),
            "status": "stored",
            "created_at": datetime.utcnow()
        }
        inserted_item = found_items.insert_one(found_doc)

        for claim in lost_claims.find({"status": "pending"}):
            if _is_potential_match(claim, found_doc):
                notifications.insert_one({
                    "recipient_id": str(claim["user_id"]),
                    "message": f"Campus security registered a found item that may match your {claim['item_name']}. Staff are reviewing it.",
                    "type": "possible_match",
                    "found_item_id": inserted_item.inserted_id,
                    "read": False,
                    "created_at": datetime.utcnow(),
                })

        # Log action
        audit_logs.insert_one({
            "admin_id": ObjectId(session["user_id"]),
            "action": "REGISTER_FOUND_ITEM",
            "target": item_name,
            "created_at": datetime.utcnow()
        })
        
        flash("Recovered item successfully registered.", "success")
        return redirect(url_for("admin_dashboard"))
        
    return render_template("admin_found_form.html")

@app.route("/admin/claims")
@admin_required
def admin_claims():
    claims = list(lost_claims.find().sort("created_at", -1))
    found_items_list = list(found_items.find({"status": "stored"}))
    
    for claim in claims:
        claim['suggested_matches'] = []
        student = users.find_one({"_id": claim["user_id"]}, {"username": 1, "student_id": 1})
        claim["student_username"] = student.get("username", "Student") if student else "Student"
        claim["student_id"] = student.get("student_id", "") if student else ""
        for item in found_items_list:
            if claim["status"] == "pending" and _is_potential_match(claim, item):
                claim['suggested_matches'].append(item)
        if claim.get("matched_found_id"):
            claim["matched_item"] = found_items.find_one(
                {"_id": claim["matched_found_id"]}
            )
                
    return render_template("admin_claims.html", claims=claims)

@app.route("/admin/match/<claim_id>/<found_id>", methods=["POST"])
@admin_required
def confirm_match(claim_id, found_id):
    if not ObjectId.is_valid(claim_id) or not ObjectId.is_valid(found_id):
        flash("The selected claim or item is invalid.", "danger")
        return redirect(url_for("admin_claims"))

    claim_object_id = ObjectId(claim_id)
    found_object_id = ObjectId(found_id)
    claim = lost_claims.find_one({"_id": claim_object_id, "status": "pending"})
    found = found_items.find_one({"_id": found_object_id, "status": "stored"})
    if not claim or not found:
        flash("This claim or found item is no longer available for matching.", "warning")
        return redirect(url_for("admin_claims"))

    claim_result = lost_claims.update_one(
        {"_id": claim_object_id, "status": "pending"},
        {"$set": {
            "status": "matched",
            "matched_found_id": found_object_id,
            "updated_at": datetime.utcnow(),
        }},
    )
    if claim_result.modified_count != 1:
        flash("This claim has already been updated.", "warning")
        return redirect(url_for("admin_claims"))

    found_result = found_items.update_one(
        {"_id": found_object_id, "status": "stored"},
        {"$set": {"status": "reserved_for_verification"}},
    )
    if found_result.modified_count != 1:
        lost_claims.update_one(
            {"_id": claim_object_id, "status": "matched", "matched_found_id": found_object_id},
            {"$set": {"status": "pending"}, "$unset": {"matched_found_id": ""}},
        )
        flash("This found item is no longer available for matching.", "warning")
        return redirect(url_for("admin_claims"))

    notifications.insert_one({
        "recipient_id": str(claim["user_id"]),
        "message": f"A possible match was found for your {claim['item_name']}. Please check your claim status.",
        "type": "possible_match",
        "read": False,
        "created_at": datetime.utcnow(),
    })
    flash("Match confirmed. Item reserved for verification.", "success")
    return redirect(url_for("admin_claims"))


@app.route("/admin/return/<claim_id>/<found_id>", methods=["POST"])
@admin_required
def return_item(claim_id, found_id):
    if request.form.get("ownership_verified") != "yes":
        flash("Confirm that identity and ownership were verified before recording a handover.", "warning")
        return redirect(url_for("admin_claims"))
    if not ObjectId.is_valid(claim_id) or not ObjectId.is_valid(found_id):
        flash("The selected claim or item is invalid.", "danger")
        return redirect(url_for("admin_claims"))

    claim_object_id = ObjectId(claim_id)
    found_object_id = ObjectId(found_id)
    claim = lost_claims.find_one({
        "_id": claim_object_id,
        "status": "matched",
        "matched_found_id": found_object_id,
    })
    found = found_items.find_one({
        "_id": found_object_id,
        "status": "reserved_for_verification",
    })
    if not claim or not found:
        flash("This matched item is no longer awaiting handover.", "warning")
        return redirect(url_for("admin_claims"))

    student = users.find_one({"_id": claim["user_id"]}, {"username": 1})
    if not student:
        flash("The student account for this claim could not be found.", "danger")
        return redirect(url_for("admin_claims"))

    returned_at = datetime.utcnow()
    claim_result = lost_claims.update_one(
        {"_id": claim_object_id, "status": "matched", "matched_found_id": found_object_id},
        {"$set": {
            "status": "resolved",
            "returned_at": returned_at,
            "updated_at": returned_at,
        }},
    )
    if claim_result.modified_count != 1:
        flash("This claim has already been updated.", "warning")
        return redirect(url_for("admin_claims"))

    found_result = found_items.update_one(
        {"_id": found_object_id, "status": "reserved_for_verification"},
        {"$set": {
            "status": "returned",
            "returned_to_id": claim["user_id"],
            "returned_to_username": student["username"],
            "returned_by": ObjectId(session["user_id"]),
            "returned_at": returned_at,
        }},
    )
    if found_result.modified_count != 1:
        lost_claims.update_one(
            {"_id": claim_object_id, "status": "resolved"},
            {"$set": {"status": "matched"}, "$unset": {"returned_at": ""}},
        )
        flash("The item status changed before the handover could be recorded.", "warning")
        return redirect(url_for("admin_claims"))

    audit_logs.insert_one({
        "admin_id": ObjectId(session["user_id"]),
        "action": "RETURN_FOUND_ITEM",
        "target": found["item_name"],
        "student_id": claim["user_id"],
        "created_at": returned_at,
    })
    notifications.insert_one({
        "recipient_id": str(claim["user_id"]),
        "message": f"Your {claim['item_name']} was marked as returned by campus security.",
        "type": "item_returned",
        "read": False,
        "created_at": returned_at,
    })
    flash("Handover recorded and item marked as returned.", "success")
    return redirect(url_for("admin_claims"))

if __name__ == "__main__":
    webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True)