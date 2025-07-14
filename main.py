from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# Initialize Firebase
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

CHAR_REGEN_RATE = 100
MAX_CHAR_STORAGE = 200
BIN_CAPACITY = 50
BIN_LIFESPAN = 3

def get_user(uid):
    return db.collection("users").document(uid).get().to_dict()

def update_user(uid, data):
    db.collection("users").document(uid).update(data)

@app.route("/post", methods=["POST"])
def create_post():
    data = request.json
    uid = data["uid"]
    content = data["content"]
    links = data.get("links", [])
    images = data.get("images", [])
    video = data.get("video", None)

    user = get_user(uid)
    char_cost = len(content)

    # Apply media costs
    if links:
        char_cost += max(0, len(links) - 1) * 10
    if images:
        char_cost += 5 + max(0, len(images) - 1) * 20
    if video:
        char_cost += 15

    if user["char_balance"] < char_cost:
        return jsonify({"error": "Not enough characters"}), 403

    # Deduct characters and update post count
    new_balance = user["char_balance"] - char_cost
    post_count = user.get("post_count", 0) + 1

    update_user(uid, {
        "char_balance": new_balance,
        "post_count": post_count,
        "last_post": datetime.utcnow()
    })

    # Create post entry
    db.collection("posts").add({
        "uid": uid,
        "content": content,
        "timestamp": datetime.utcnow(),
        "media": {"links": links, "images": images, "video": video}
    })

    return jsonify({"success": True, "remaining_chars": new_balance})

@app.route("/regen", methods=["POST"])
def regenerate_chars():
    uid = request.json["uid"]
    user = get_user(uid)
    last_regen = user.get("last_regen", datetime.utcnow() - timedelta(hours=1))
    now = datetime.utcnow()

    hours_passed = int((now - last_regen).total_seconds() // 3600)
    if hours_passed < 1:
        return jsonify({"message": "Too soon to regenerate"}), 429

    regen_amount = min(MAX_CHAR_STORAGE, user["char_balance"] + hours_passed * CHAR_REGEN_RATE)
    update_user(uid, {
        "char_balance": regen_amount,
        "last_regen": now
    })

    return jsonify({"new_balance": regen_amount})
