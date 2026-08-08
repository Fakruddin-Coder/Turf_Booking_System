"""Run AFTER schema.sql to set the real admin password hash."""
import os
import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# Load environment variables from .env
load_dotenv()

# Connect using values from .env
conn = mysql.connector.connect(
    host=os.environ["DB_HOST"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    database=os.environ["DB_NAME"],
    port=int(os.environ["DB_PORT"])
)

cur = conn.cursor()

# Update or insert the admin record
cur.execute(
    "UPDATE admins SET password_hash=%s WHERE email=%s",
    (generate_password_hash("admin123"), "admin@greenfield.com")
)

if cur.rowcount == 0:
    cur.execute(
        "INSERT INTO admins (name, email, password_hash) VALUES (%s, %s, %s)",
        ("Arena Admin", "admin@greenfield.com", generate_password_hash("admin123"))
    )

conn.commit()
cur.close()
conn.close()

print("✅ Admin ready: admin@greenfield.com / admin123")
