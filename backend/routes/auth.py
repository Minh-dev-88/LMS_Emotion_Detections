# backend/routes/auth.py
from flask import Blueprint, request, render_template, jsonify, session, redirect, url_for
from models.user import create_user, get_user, get_students, update_password
from models.class_session import create_class, get_classes, update_class, delete_class, get_class_by_id
from models.class_model import get_classes as get_class_list
import re
import pandas as pd
import mysql.connector
from config import Config

def create_auth_bp():
    auth_bp = Blueprint('auth', __name__)

    @auth_bp.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            data = request.get_json()
            email = data.get('email')
            password = data.get('password')
            user = get_user(email, password)
            if user:
                session['user_id'] = user['id']
                session['role'] = user['role']
                session['email'] = user['email']
                session['name'] = user['name']
                session['class_id'] = user['class_id']
                return jsonify({'message': 'Đăng nhập thành công', 'role': user['role']}), 200
            return jsonify({'message': 'Email hoặc mật khẩu sai'}), 401
        return render_template('login.html')

    @auth_bp.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('auth.login'))

    @auth_bp.route('/teacher_home', methods=['GET'])
    def teacher_home():
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            return jsonify({'message': 'Không có quyền truy cập'}), 403
        section = request.args.get('section', 'home')
        classes = get_classes(session['user_id'])
        class_list = get_class_list()
        return render_template('teacher_home.html', section=section, classes=classes, class_list=class_list)

    @auth_bp.route('/student_home')
    def student_home():
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('role') != 'student':
            return jsonify({'message': 'Không có quyền truy cập'}), 403
        section = request.args.get('section', 'home')  # Lấy section từ query string
        class_id = session.get('class_id')
        db = get_db()
        cursor = db.cursor(dictionary=True)
        try:
            query = """
                SELECT cs.*, c.name as class_name 
                FROM class_sessions cs 
                JOIN classes c ON cs.class_id = c.id 
                WHERE cs.class_id = %s
            """
            cursor.execute(query, (class_id,))
            classes = cursor.fetchall()
        except mysql.connector.Error as err:
            print(f"Error: {err}")
            classes = []
        finally:
            cursor.close()
            db.close()
        return render_template('student_home.html', section=section, classes=classes)

    @auth_bp.route('/change_password', methods=['POST'])
    def change_password():
        if session.get('role') != 'student':
            return jsonify({'message': 'Không có quyền truy cập'}), 403
        data = request.get_json()
        old_password = data.get('oldPassword')
        new_password = data.get('newPassword')
        user = get_user(session['email'], old_password)
        if not user:
            return jsonify({'message': 'Mật khẩu cũ không đúng'}), 400
        if update_password(session['email'], new_password):
            return jsonify({'message': 'Đổi mật khẩu thành công'}), 200
        return jsonify({'message': 'Lỗi khi đổi mật khẩu'}), 400

    @auth_bp.route('/create_student', methods=['POST'])
    def create_student():
        if session.get('role') != 'admin':
            return jsonify({'message': 'Không có quyền truy cập'}), 403
        data = request.get_json()
        email = data.get('email')
        name = data.get('name')
        class_name = data.get('class_name')
        password = data.get('password')
        if not re.match(r'.+@st\.neu\.edu\.vn$', email):
            return jsonify({'message': 'Email phải thuộc @st.neu.edu.vn'}), 400
        if create_user(email, name, class_name, password, 'student'):
            return jsonify({'message': 'Tạo tài khoản học sinh thành công'}), 201
        return jsonify({'message': 'Email đã tồn tại'}), 400

    @auth_bp.route('/bulk_create_students', methods=['POST'])
    def bulk_create_students():
        if session.get('role') != 'admin':
            return jsonify({'message': 'Không có quyền truy cập'}), 403
        if 'file' not in request.files:
            return jsonify({'message': 'Không có file được tải lên'}), 400
        file = request.files['file']
        if not file.filename.endswith('.xlsx'):
            return jsonify({'message': 'File phải là định dạng Excel (.xlsx)'}), 400

        try:
            df = pd.read_excel(file)
            for _, row in df.iterrows():
                email = row[0]
                name = row[1]
                class_name = row[2]
                password = '123@'
                if not re.match(r'.+@st\.neu\.edu\.vn$', str(email)):
                    continue
                create_user(str(email), str(name), str(class_name), password, 'student')
            return jsonify({'message': 'Tạo tài khoản hàng loạt thành công'}), 201
        except Exception as e:
            return jsonify({'message': f'Lỗi khi xử lý file: {str(e)}'}), 400

    @auth_bp.route('/create_class', methods=['POST'])
    def create_class_route():
        if session.get('role') != 'admin':
            return jsonify({'message': 'Không có quyền truy cập'}), 403
        data = request.get_json()
        name = data.get('name')
        class_id = data.get('class_id')
        date = data.get('date')
        time = data.get('time')
        admin_id = session['user_id']
        class_id = create_class(name, admin_id, class_id, date, time)
        if class_id:
            return jsonify({'message': 'Tạo buổi học thành công'}), 201
        return jsonify({'message': 'Lỗi khi tạo buổi học'}), 400

    @auth_bp.route('/update_class/<int:class_id>', methods=['POST'])
    def update_class_route(class_id):
        if session.get('role') != 'admin':
            return jsonify({'message': 'Không có quyền truy cập'}), 403
        data = request.get_json()
        date = data.get('date')
        time = data.get('time')
        if update_class(class_id, date, time):
            return jsonify({'message': 'Cập nhật buổi học thành công'}), 200
        return jsonify({'message': 'Lỗi khi cập nhật buổi học'}), 400

    @auth_bp.route('/delete_class/<int:class_id>', methods=['POST'])
    def delete_class_route(class_id):
        if session.get('role') != 'admin':
            return jsonify({'message': 'Không có quyền truy cập'}), 403
        if delete_class(class_id):
            return jsonify({'message': 'Xóa buổi học thành công'}), 200
        return jsonify({'message': 'Lỗi khi xóa buổi học'}), 400

    @auth_bp.route('/join_room', methods=['POST'])
    def join_room():
        return jsonify({'status': 'OK'})

    def get_db():
        return mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )

    return auth_bp