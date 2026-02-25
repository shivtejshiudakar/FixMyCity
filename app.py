import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
import mysql.connector
from config import DB_CONFIG

app = Flask(__name__)
app.secret_key = "fixmycity_secret_key"

db = mysql.connector.connect(**DB_CONFIG)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root123",          # put your MySQL password if any
        database="fixmycity_db"
    )


@app.route('/')
def home():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    # Total issues
    cursor.execute("SELECT COUNT(*) as total FROM civic_reports")
    total = cursor.fetchone()['total']

    # Status counts
    cursor.execute("SELECT COUNT(*) as count FROM civic_reports WHERE status='Reported'")
    open_count = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM civic_reports WHERE status='In Progress'")
    progress = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM civic_reports WHERE status='Resolved'")
    resolved = cursor.fetchone()['count']

    # Category distribution
    cursor.execute("""
        SELECT issue_type, COUNT(*) as count
        FROM civic_reports
        GROUP BY issue_type
        ORDER BY count DESC
    """)
    categories = cursor.fetchall()

    # Recent reports
    cursor.execute("""
        SELECT issue_type, description, status, report_date , location
        FROM civic_reports
        ORDER BY report_id DESC
        LIMIT 5
    """)
    recent = cursor.fetchall()

    conn.close()

    return render_template(
        "public_dashboard.html",
        total=total,
        open_count=open_count,
        progress=progress,
        resolved=resolved,
        categories=categories,
        recent=recent
    )



@app.route('/')
def public_dashboard():

    cursor = db.cursor(dictionary=True)

    # Total Issues
    cursor.execute("SELECT COUNT(*) as total FROM civic_reports")
    total = cursor.fetchone()['total']

    # Open
    cursor.execute("SELECT COUNT(*) as open_count FROM civic_reports WHERE status='Reported'")
    open_count = cursor.fetchone()['open_count']

    # In Progress
    cursor.execute("SELECT COUNT(*) as progress FROM civic_reports WHERE status='In Progress'")
    progress = cursor.fetchone()['progress']

    # Resolved
    cursor.execute("SELECT COUNT(*) as resolved FROM civic_reports WHERE status='Resolved'")
    resolved = cursor.fetchone()['resolved']

    # Categories
    cursor.execute("""
        SELECT issue_type, COUNT(*) as count
        FROM civic_reports
        GROUP BY issue_type
        ORDER BY count DESC
    """)
    categories = cursor.fetchall()

    return render_template(
        'public_dashboard.html',
        total=total,
        open_count=open_count,
        progress=progress,
        resolved=resolved,
        categories=categories
    )



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO users (name, email, password)
            VALUES (%s, %s, %s)
        """, (
            request.form['name'],
            request.form['email'],
            request.form['password']
        ))
        db.commit()

        flash("Registration successful. Please login.", "success")
        return redirect('/login')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM users
            WHERE email=%s AND password=%s
        """, (email, password))

        user = cursor.fetchone()

        if user:
            session['user_id'] = user['user_id']
            session['user_name'] = user['name']
            flash("Login successful!", "success")
            return redirect('/dashboard')
        else:
            flash("Invalid Email or Password", "danger")

    return render_template('login.html')



@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT *
        FROM civic_reports
        WHERE user_id = %s
        ORDER BY report_id DESC
    """, (session['user_id'],))

    reports = cursor.fetchall()

    return render_template('citizen_dashboard.html', reports=reports)


@app.route('/report')
def report():
    if 'user_id' not in session:
        return redirect('/login')

    return render_template('report_issue.html')

@app.route('/delete/<int:report_id>', methods=['POST'])
def delete_report(report_id):

    if 'user_id' not in session:
        return redirect('/login')

    cursor = db.cursor()

    # Ensure user can delete only their own report
    cursor.execute("""
        DELETE FROM civic_reports
        WHERE report_id = %s AND user_id = %s
    """, (report_id, session['user_id']))

    db.commit()

    flash("Report deleted successfully!", "info")
    return redirect('/dashboard')


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


from werkzeug.utils import secure_filename
UPLOAD_FOLDER = "static/uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
@app.route('/submit', methods=['POST'])
def submit():

    if 'user_id' not in session:
        return redirect('/login')

    # Handle image upload
    image = request.files.get('image')
    image_filename = None

    if image and image.filename != "":
        image_filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO civic_reports
        (user_id, user_name, issue_type, description, location, status, report_date, image_path)
        VALUES (%s, %s, %s, %s, %s, %s, CURDATE(), %s)
    """, (
        session['user_id'],
        session['user_name'],
        request.form['issue_type'],
        request.form['description'],
        request.form['location'],
        "Reported",
        image_filename
    ))

    db.commit()

    flash("Issue submitted successfully!", "success")
    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    flash("Logged out successfully!", "info")
    return redirect('/')

@app.route('/status')
def status():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM civic_reports ORDER BY report_id DESC")
    reports = cursor.fetchall()
    return render_template('status.html', reports=reports)


@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == "admin" and password == "admin123":
            session['admin'] = True
            flash("Login successful!", "success")
            return redirect('/admin/dashboard')
        else:
            flash("Invalid credentials", "danger")
    return render_template('admin_login.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect('/admin')

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM civic_reports ORDER BY report_id DESC")
    reports = cursor.fetchall()

    return render_template('admin_dashboard.html', reports=reports)


@app.route('/admin/update/<int:id>', methods=['POST'])
def update_status(id):
    if 'admin' not in session:
        return redirect('/admin')

    new_status = request.form['status']

    cursor = db.cursor()
    cursor.execute(
        "UPDATE civic_reports SET status=%s WHERE report_id=%s",
        (new_status, id)
    )
    db.commit()
    flash("Status updated successfully!", "success")
    return redirect('/admin/dashboard')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash("Logged out successfully!", "info")
    return redirect('/')

@app.route('/test')
def test():
    return "Test Working"


if __name__ == "__main__":
    app.run(debug=True)
