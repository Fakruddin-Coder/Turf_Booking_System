"""Run AFTER schema.sql to set the real admin password hash."""
import os, mysql.connector
from werkzeug.security import generate_password_hash
conn = mysql.connector.connect(
    host=os.environ.get("DB_HOST","localhost"),
    user=os.environ.get("DB_USER","root"),
    password=os.environ.get("DB_PASSWORD","Khan@123"),
    database=os.environ.get("DB_NAME","turf_booking"))
cur = conn.cursor()
cur.execute("UPDATE admins SET password_hash=%s WHERE email=%s",
            (generate_password_hash("admin123"), "admin@greenfield.com"))
conn.commit()
print("Admin ready: admin@greenfield.com / admin123")
