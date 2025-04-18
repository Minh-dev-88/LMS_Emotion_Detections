import mysql.connector
from config import Config

def get_db():
    return mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )

def create_class(name):
    db = get_db()
    cursor = db.cursor()
    try:
        query = "INSERT INTO classes (name) VALUES (%s)"
        cursor.execute(query, (name,))
        db.commit()
        return cursor.lastrowid
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None
    finally:
        cursor.close()
        db.close()

def get_classes():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        query = "SELECT * FROM classes"
        cursor.execute(query)
        return cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return []
    finally:
        cursor.close()
        db.close()

def get_class_by_name(name):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        query = "SELECT * FROM classes WHERE name = %s"
        cursor.execute(query, (name,))
        return cursor.fetchone()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None
    finally:
        cursor.close()
        db.close()