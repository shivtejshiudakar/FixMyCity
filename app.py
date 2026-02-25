import os
from flask import Flask, render_template, request, redirect, session, send_from_directory, flash
from werkzeug.utils import secure_filename
import psycopg2
import psycopg2.extras

# =========================
# APP CONFIG
# =========================
app = Flask(__name__)
app.secret_key = "fixmycity_secret_key"

UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# =========================
# DATABASE CONNECTION
# =========================
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL)

# =========================
# HELPERS
# =========================
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# =========================
# PUBLIC DASHBOARD (HOME)
# =========================
@app.route('/')
def public_dashboard():

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT COUNT(*) as total FROM civic_reports")
    total = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as count FROM civic_reports WHERE status='Reported'")
    open_count = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM civic_reports WHERE status='In Progress'")
    progress = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM civic_reports WHERE status='Resolved'")
    resolved = cursor.fetchone()['count']

    cursor.execute("""
        SELECT issue_type, COUNT(*) as count
        FROM civic_reports
        GROUP BY issue_type
        ORDER BY count DESC
    """)
    categories = cursor.fetchall()

    cursor.execute("""
        SELECT issue_type, description, status, report_date, location
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


# =========================
# REGISTER
# =========================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO users (name, email, password)
            VALUES (%s, %s, %s)
        """, (
            request.form['name'],
            request.form['email'],
            request.form['password']
        ))

        conn.commit()
        conn.close()

        flash("Registration successful. Please login.", "success")
        return redirect('/login')

    return render_template('register.html')


# =========================
# LOGIN
# =========================
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        conn = get_db()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            SELECT * FROM users
            WHERE email=%s AND password=%s
        """, (
            request.form.get("email"),
            request.form.get("password")
        ))

        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_id'] = user['user_id']
            session['user_name'] = user['name']
            flash("Login successful!", "success")
            return redirect('/dashboard')
        else:
            flash("Invalid Email or Password", "danger")

    return render_template('login.html')


# =========================
# USER DASHBOARD
# =========================
@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM civic_reports
        WHERE user_id = %s
        ORDER BY report_id DESC
    """, (session['user_id'],))

    reports = cursor.fetchall()
    conn.close()

    return render_template('citizen_dashboard.html', reports=reports)


# =========================
# REPORT PAGE
# =========================
@app.route('/report')
def report():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('report_issue.html')


# =========================
# SUBMIT ISSUE
# =========================
@app.route('/submit', methods=['POST'])
def submit():

    if 'user_id' not in session:
        return redirect('/login')

    image = request.files.get('image')
    image_filename = None

    if image and image.filename != "":
        image_filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO civic_reports
        (user_id, user_name, issue_type, description, location, status, report_date, image_path)
        VALUES (%s,%s,%s,%s,%s,%s,CURRENT_DATE,%s)
    """, (
        session['user_id'],
        session['user_name'],
        request.form['issue_type'],
        request.form['description'],
        request.form['location'],
        "Reported",
        image_filename
    ))

    conn.commit()
    conn.close()

    flash("Issue submitted successfully!", "success")
    return redirect('/dashboard')


# =========================
# UPLOADS
# =========================
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# =========================
# LOGOUT
# =========================
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect('/')


# =========================
# ADMIN LOGIN
# =========================
@app.route('/admin', methods=['GET','POST'])
def admin_login():

    if request.method == 'POST':

        if request.form['username'] == "admin" and request.form['password'] == "admin123":
            session['admin'] = True
            return redirect('/admin/dashboard')

        flash("Invalid credentials", "danger")

    return render_template('admin_login.html')


# =========================
# ADMIN DASHBOARD
# =========================
@app.route('/admin/dashboard')
def admin_dashboard():

    if 'admin' not in session:
        return redirect('/admin')

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT * FROM civic_reports ORDER BY report_id DESC")
    reports = cursor.fetchall()

    conn.close()

    return render_template('admin_dashboard.html', reports=reports)


# =========================
# UPDATE STATUS
# =========================
@app.route('/admin/update/<int:id>', methods=['POST'])
def update_status(id):

    if 'admin' not in session:
        return redirect('/admin')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE civic_reports SET status=%s WHERE report_id=%s",
        (request.form['status'], id)
    )

    conn.commit()
    conn.close()

    flash("Status updated successfully!", "success")
    return redirect('/admin/dashboard')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/')


# =========================
# TEST ROUTE
# =========================
@app.route('/test')
def test():
    return "Test Working"

# =========================
@app.route('/status')
def status():

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM civic_reports
        ORDER BY report_id DESC
    """)

    reports = cursor.fetchall()
    conn.close()

    return render_template('status.html', reports=reports)


if __name__ == "__main__":
    app.run(debug=True)