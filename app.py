from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import sqlite3
import base64
import os
from datetime import datetime
import json

app = Flask(__name__)
CORS(app)

# Database initialization
def init_db():
    conn = sqlite3.connect('review_rise.db')
    cursor = conn.cursor()
    
    # Create submissions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            upi_id TEXT NOT NULL,
            screenshot TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert default settings
    cursor.execute('''
        INSERT OR IGNORE INTO settings (key, value) VALUES 
        ('mapLink', 'https://maps.google.com/?q=Review+Rise+Office'),
        ('youtubeLink', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')
    ''')
    
    conn.commit()
    conn.close()

# API Routes
@app.route('/api/submit', methods=['POST'])
def submit_review():
    try:
        data = request.json
        full_name = data.get('fullName')
        upi_id = data.get('upiId')
        screenshot = data.get('screenshot')  # Base64 encoded image
        
        if not all([full_name, upi_id, screenshot]):
            return jsonify({'error': 'All fields are required'}), 400
        
        conn = sqlite3.connect('review_rise.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO submissions (full_name, upi_id, screenshot, status)
            VALUES (?, ?, ?, 'pending')
        ''', (full_name, upi_id, screenshot))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Submission successful', 'status': 'success'}), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/submissions', methods=['GET'])
def get_submissions():
    try:
        conn = sqlite3.connect('review_rise.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, full_name, upi_id, screenshot, status, created_at, updated_at
            FROM submissions ORDER BY created_at DESC
        ''')
        
        submissions = []
        for row in cursor.fetchall():
            submissions.append({
                'id': row[0],
                'fullName': row[1],
                'upiId': row[2],
                'screenshot': row[3],
                'status': row[4],
                'createdAt': row[5],
                'updatedAt': row[6]
            })
        
        conn.close()
        return jsonify(submissions), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/submissions/<int:submission_id>/<action>', methods=['POST'])
def update_submission(submission_id, action):
    try:
        valid_actions = ['approve', 'reject', 'paid', 'delete']
        if action not in valid_actions:
            return jsonify({'error': 'Invalid action'}), 400
        
        conn = sqlite3.connect('review_rise.db')
        cursor = conn.cursor()
        
        if action == 'delete':
            cursor.execute('DELETE FROM submissions WHERE id = ?', (submission_id,))
        else:
            status_map = {'approve': 'approved', 'reject': 'rejected', 'paid': 'paid'}
            new_status = status_map[action]
            
            cursor.execute('''
                UPDATE submissions 
                SET status = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (new_status, submission_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': f'Submission {action}d successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/<key>', methods=['GET', 'POST'])
def handle_settings(key):
    try:
        conn = sqlite3.connect('review_rise.db')
        cursor = conn.cursor()
        
        if request.method == 'GET':
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            result = cursor.fetchone()
            
            if result:
                return jsonify({'value': result[0]}), 200
            else:
                return jsonify({'error': 'Setting not found'}), 404
                
        elif request.method == 'POST':
            data = request.json
            value = data.get('value')
            
            if not value:
                return jsonify({'error': 'Value is required'}), 400
            
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, value))
            
            conn.commit()
            conn.close()
            
            return jsonify({'message': 'Setting updated successfully'}), 200
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        conn = sqlite3.connect('review_rise.db')
        cursor = conn.cursor()
        
        # Get counts for each status
        cursor.execute('SELECT COUNT(*) FROM submissions')
        total = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM submissions WHERE status = "approved"')
        approved = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM submissions WHERE status = "rejected"')
        rejected = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM submissions WHERE status = "paid"')
        paid = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM submissions WHERE status = "pending"')
        pending = cursor.fetchone()[0]
        
        conn.close()
        
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
    # Create static directory if it doesn't exist
    os.makedirs('static', exist_ok=True)
    
    # Initialize database
    init_db()
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5000)
