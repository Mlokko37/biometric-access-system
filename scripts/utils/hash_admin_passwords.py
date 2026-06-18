from werkzeug.security import generate_password_hash
from src.database.connection import DatabaseConnection

db = DatabaseConnection()
db.connect()

new_password = "admin123"  # 👈 TEMP password
hashed = generate_password_hash(new_password)

db.execute_query(
    "UPDATE administrators SET password_hash=%s WHERE username=%s",
    (hashed, "MLOKKO")
)

db.close()
print("[OK] Password updated & hashed")
