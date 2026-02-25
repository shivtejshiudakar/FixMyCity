import os
import psycopg2

DATABASE_URL = os.environ.get("postgresql://fixmycity_user:99F5qKTAHUO4ha1YSrj9U9EceJec9yJ8@dpg-d6fc63hr0fns73f80hu0-a.oregon-postgres.render.com/fixmycity_05oq")

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    password VARCHAR(100)
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS civic_reports (
    report_id SERIAL PRIMARY KEY,
    user_id INT,
    user_name VARCHAR(100),
    issue_type VARCHAR(100),
    description TEXT,
    location VARCHAR(200),
    status VARCHAR(50),
    report_date DATE,
    image_path VARCHAR(255)
);
""")

conn.commit()
conn.close()

print("Tables created successfully!")