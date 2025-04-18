import mysql.connector
from config import Config
import jwt
import time  # Giữ nguyên module time

def get_db():
    return mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )

def generate_signature(meeting_number):
    iat = int(time.time())
    exp = iat + 60 * 60 * 2  # Hết hạn sau 2 giờ
    payload = {
        "sdkKey": Config.ZOOM_SDK_KEY,
        "mn": meeting_number,
        "role": 1,  # 1: host, 0: participant
        "iat": iat,
        "exp": exp,
        "tokenExp": exp
    }
    signature = jwt.encode(payload, Config.ZOOM_SDK_SECRET, algorithm="HS256")
    return signature

def create_class(name, admin_id, class_id, date, class_time):  # Đổi 'time' thành 'class_time'
    db = get_db()
    cursor = db.cursor()
    try:
        session_id = f"{admin_id}_{int(time.time())}"  # Sử dụng module time đúng cách
        query = "INSERT INTO class_sessions (name, admin_id, class_id, session_id, date, time) VALUES (%s, %s, %s, %s, %s, %s)"
        cursor.execute(query, (name, admin_id, class_id, session_id, date, class_time))  # Sử dụng 'class_time' thay vì 'time'
        db.commit()
        return cursor.lastrowid
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None
    finally:
        cursor.close()
        db.close()

def get_classes(admin_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        query = """
            SELECT cs.*, c.name as class_name 
            FROM class_sessions cs 
            JOIN classes c ON cs.class_id = c.id 
            WHERE cs.admin_id = %s
        """
        cursor.execute(query, (admin_id,))
        return cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return []
    finally:
        cursor.close()
        db.close()

def get_class_by_id(class_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        query = """
            SELECT cs.*, c.name as class_name 
            FROM class_sessions cs 
            JOIN classes c ON cs.class_id = c.id 
            WHERE cs.id = %s
        """
        cursor.execute(query, (class_id,))
        return cursor.fetchone()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None
    finally:
        cursor.close()
        db.close()

def update_class(class_id, date, class_time):  # Đổi 'time' thành 'class_time'
    db = get_db()
    cursor = db.cursor()
    try:
        query = "UPDATE class_sessions SET date = %s, time = %s WHERE id = %s"
        cursor.execute(query, (date, class_time, class_id))  # Sử dụng 'class_time' thay vì 'time'
        db.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return False
    finally:
        cursor.close()
        db.close()

def delete_class(class_id):
    db = get_db()
    cursor = db.cursor()
    try:
        query = "DELETE FROM class_sessions WHERE id = %s"
        cursor.execute(query, (class_id,))
        db.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return False
    finally:
        cursor.close()
        db.close()
