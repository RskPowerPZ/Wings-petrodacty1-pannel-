from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# MongoDB connection
MONGO_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["review_rise"]

submissions_col = db["submissions"]
settings_col = db["settings"]

# Initialize DB with default settings
def init_db():
    if settings_col.count_documents({}) == 0:
        settings_col.insert_many([
            {"key": "mapLink", "value": "https://maps.google.com/?q=Review+Rise+Office", "updated_at": datetime.utcnow()},
            {"key": "youtubeLink", "value": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "updated_at": datetime.utcnow()}
        ])

# Helper to serialize MongoDB ObjectId
def serialize_submission(sub):
    return {
        "id": str(sub["_id"]),
        "fullName": sub["full_name"],
        "upiId": sub["upi_id"],
        "screenshot": sub["screenshot"],
        "status": sub.get("status", "pending"),
        "createdAt": sub.get("created_at"),
        "updatedAt": sub.get("updated_at")
    }

# API Routes
@app.route('/api/submit', methods=['POST'])
def submit_review():
    try:
        data = request.json
        full_name = data.get('fullName')
        upi_id = data.get('upiId')
        screenshot = data.get('screenshot')

        if not all([full_name, upi_id, screenshot]):
            return jsonify({'error': 'All fields are required'}), 400

        submission = {
            "full_name": full_name,
            "upi_id": upi_id,
            "screenshot": screenshot,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        submissions_col.insert_one(submission)

        return jsonify({'message': 'Submission successful', 'status': 'success'}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/submissions', methods=['GET'])
def get_submissions():
    try:
        submissions = submissions_col.find().sort("created_at", -1)
        return jsonify([serialize_submission(s) for s in submissions]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/submissions/<submission_id>/<action>', methods=['POST'])
def update_submission(submission_id, action):
    try:
        valid_actions = ['approve', 'reject', 'paid', 'delete']
        if action not in valid_actions:
            return jsonify({'error': 'Invalid action'}), 400

        if action == 'delete':
            submissions_col.delete_one({"_id": ObjectId(submission_id)})
        else:
            status_map = {'approve': 'approved', 'reject': 'rejected', 'paid': 'paid'}
            new_status = status_map[action]
            submissions_col.update_one(
                {"_id": ObjectId(submission_id)},
                {"$set": {"status": new_status, "updated_at": datetime.utcnow()}}
            )

        return jsonify({'message': f'Submission {action}d successfully'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/<key>', methods=['GET', 'POST'])
def handle_settings(key):
    try:
        if request.method == 'GET':
            setting = settings_col.find_one({"key": key})
            if setting:
                return jsonify({'value': setting["value"]}), 200
            else:
                return jsonify({'error': 'Setting not found'}), 404

        elif request.method == 'POST':
            data = request.json
            value = data.get('value')
            if not value:
                return jsonify({'error': 'Value is required'}), 400

            settings_col.update_one(
                {"key": key},
                {"$set": {"value": value, "updated_at": datetime.utcnow()}},
                upsert=True
            )
            return jsonify({'message': 'Setting updated successfully'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        total = submissions_col.count_documents({})
        approved = submissions_col.count_documents({"status": "approved"})
        rejected = submissions_col.count_documents({"status": "rejected"})
        paid = submissions_col.count_documents({"status": "paid"})
        pending = submissions_col.count_documents({"status": "pending"})

        return jsonify({
            'total': total,
            'approved': approved,
            'rejected': rejected,
            'paid': paid,
            'pending': pending
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Serve static files
@app.route('/')
def serve_index():
    with open('static/index.html', 'r') as f:
        return f.read()

@app.route('/admin')
def serve_admin():
    with open('static/admin.html', 'r') as f:
        return f.read()

if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
