# backend/models/user.py
import mysql.connector
from config import Config  # Sửa thành relative import

def get_db():
    return mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )

def create_user(email, name, class_name, password, role):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return False
        
        cursor.execute("SELECT id FROM classes WHERE name = %s", (class_name,))
        class_row = cursor.fetchone()
        if class_row:
            class_id = class_row[0]
        else:
            cursor.execute("INSERT INTO classes (name) VALUES (%s)", (class_name,))
            class_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO users (email, name, password, role, class_id) VALUES (%s, %s, %s, %s, %s)",
            (email, name, password, role, class_id if role == 'student' else None)
        )
        db.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return False
    finally:
        cursor.close()
        db.close()

def get_user(email, password):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        return cursor.fetchone()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None
    finally:
        cursor.close()
        db.close()

def get_students():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT u.*, c.name as class_name FROM users u LEFT JOIN classes c ON u.class_id = c.id WHERE u.role = 'student'")
        return cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return []
    finally:
        cursor.close()
        db.close()

def update_password(email, new_password):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE users SET password = %s WHERE email = %s", (new_password, email))
        db.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return False
    finally:
        cursor.close()
        db.close()