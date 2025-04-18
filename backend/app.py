from flask import Flask, render_template, session, redirect, url_for, request, jsonify, Response
from routes.auth import create_auth_bp
from config import Config
import requests
import cv2
import numpy as np
from ultralytics import YOLO
from deepface import DeepFace
import base64
import logging
import mysql.connector
from mysql.connector import Error
import pandas as pd
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# Thiết lập logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# Đăng ký blueprint
app.register_blueprint(create_auth_bp())

# Hàm kết nối với MySQL
def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        if connection.is_connected():
            logger.info("Successfully connected to MySQL database")
            return connection
    except Error as e:
        logger.error(f"Error connecting to MySQL database: {str(e)}")
        return None

# Khởi tạo YOLO Face model
try:
    yolo_model = YOLO('yolov8n-face.pt')  # Tải mô hình YOLO Face
    logger.info("YOLO Face model loaded successfully")
except Exception as e:
    logger.error(f"Error loading YOLO Face model: {str(e)}")
    raise e

# Hàm tạo báo cáo cảm xúc dưới dạng file Excel
def generate_emotion_report(class_id):
    connection = get_db_connection()
    if connection is None:
        logger.error("Failed to connect to database for emotion report")
        return None

    try:
        cursor = connection.cursor(dictionary=True)

        # Lấy danh sách học sinh tham gia buổi học
        cursor.execute("""
            SELECT DISTINCT e.user_id, u.name
            FROM emotions e
            JOIN users u ON e.user_id = u.id
            WHERE e.class_id = %s
        """, (class_id,))
        students = cursor.fetchall()

        if not students:
            logger.info(f"No students found for class_id {class_id}")
            return None

        # Tổng hợp dữ liệu cảm xúc
        emotion_summary = []
        for student in students:
            user_id = student['user_id']
            cursor.execute("""
                SELECT emotion, COUNT(*) as count
                FROM emotions
                WHERE class_id = %s AND user_id = %s
                GROUP BY emotion
            """, (class_id, user_id))
            emotions = cursor.fetchall()

            # Tạo dictionary cho học sinh này
            student_data = {'Student Name': student['name']}
            emotion_counts = {
                'happy': 0,
                'sad': 0,
                'angry': 0,
                'fearful': 0,
                'disgust': 0,
                'surprise': 0,
                'neutral': 0
            }
            for emotion in emotions:
                if emotion['emotion'] in emotion_counts:
                    emotion_counts[emotion['emotion']] = emotion['count']

            # Thêm số lần xuất hiện của từng cảm xúc vào student_data
            student_data.update({
                'Happy': emotion_counts['happy'],
                'Sad': emotion_counts['sad'],
                'Angry': emotion_counts['angry'],
                'Fearful': emotion_counts['fearful'],
                'Disgust': emotion_counts['disgust'],
                'Surprise': emotion_counts['surprise'],
                'Neutral': emotion_counts['neutral']
            })
            emotion_summary.append(student_data)

        # Tạo DataFrame từ dữ liệu tổng hợp
        df = pd.DataFrame(emotion_summary)

        # Tạo thư mục để lưu file nếu chưa tồn tại
        report_dir = "emotion_reports"
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)

        # Tạo tên file với timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_dir}/emotion_report_class_{class_id}_{timestamp}.xlsx"

        # Xuất DataFrame ra file Excel
        df.to_excel(filename, index=False)
        logger.info(f"Emotion report generated: {filename}")
        return filename
    except Exception as e:
        logger.error(f"Error generating emotion report: {str(e)}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            logger.info("MySQL connection closed")

# Thêm endpoint để gọi Gemini API
@app.route('/api/ask-ai', methods=['POST'])
def ask_ai():
    data = request.get_json()
    user_message = data.get('message')

    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    try:
        api_key = 'AIzaSyAHapMRnS0Av3lkDQkrc6XDRnFa89frkXQ'
        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}'
        headers = {
            'Content-Type': 'application/json'
        }
        formatted_prompt = f"{user_message}\nHãy trả lời với các ý phân cấp, sử dụng ký hiệu * cho ý chính, - cho ý con, và + cho ý con của ý con."
        payload = {
            'contents': [
                {
                    'parts': [
                        {'text': formatted_prompt}
                    ]
                }
            ]
        }
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        ai_response = response.json()['candidates'][0]['content']['parts'][0]['text']
        
        return jsonify({'response': ai_response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Endpoint để lưu cảm xúc vào database MySQL
@app.route('/api/save-emotion', methods=['POST'])
def save_emotion_to_db():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'User not logged in'}), 401

        data = request.get_json()
        emotion = data.get('emotion')
        if not emotion:
            return jsonify({'error': 'No emotion provided'}), 400

        user_id = session['user_id']
        class_id = session.get('class_id')  # Lấy class_id từ session

        if not class_id:
            return jsonify({'error': 'Class ID not found'}), 400

        # Kết nối với MySQL
        connection = get_db_connection()
        if connection is None:
            return jsonify({'error': 'Failed to connect to database'}), 500

        try:
            cursor = connection.cursor()
            # Chèn dữ liệu vào bảng emotions
            query = """
                INSERT INTO emotions (user_id, class_id, emotion)
                VALUES (%s, %s, %s)
            """
            values = (user_id, class_id, emotion)
            cursor.execute(query, values)
            connection.commit()
            logger.info(f"Emotion saved to database: {emotion} for user {user_id} in class {class_id}")
            return jsonify({'success': True})
        except Error as e:
            logger.error(f"Error saving emotion to database: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
                logger.info("MySQL connection closed")
    except Exception as e:
        logger.error(f"Error in save_emotion_to_db: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Endpoint để nhận diện khuôn mặt và cảm xúc
@app.route('/api/detect-emotion', methods=['POST'])
def detect_emotion():
    try:
        # Nhận dữ liệu hình ảnh từ request (dạng binary)
        if 'image' not in request.files:
            logger.error("No image file provided in request")
            return jsonify({'error': 'No image file provided'}), 400

        image_file = request.files['image']
        if image_file.filename == '':
            logger.error("No selected file")
            return jsonify({'error': 'No selected file'}), 400

        # Đọc dữ liệu hình ảnh từ file
        image_bytes = image_file.read()
        if not image_bytes:
            logger.error("Image file is empty")
            return jsonify({'error': 'Image file is empty'}), 400

        # Chuyển dữ liệu thành numpy array và giải mã bằng OpenCV
        np_arr = np.frombuffer(image_bytes, np.uint8)
        if np_arr.size == 0:
            logger.error("Buffer is empty after converting from binary")
            return jsonify({'error': 'Buffer is empty'}), 400

        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            logger.error("Failed to decode image from buffer")
            return jsonify({'error': 'Failed to decode image from buffer'}), 400

        logger.debug(f"Frame shape: {frame.shape}")

        # Nhận diện khuôn mặt bằng YOLO Face
        results = yolo_model(frame, conf=0.3)  # Giảm ngưỡng confidence để tăng khả năng phát hiện
        faces = []
        if results:
            logger.debug(f"Number of detections: {len(results)}")
            for result in results:
                boxes = result.boxes.xyxy.cpu().numpy()  # Lấy tọa độ khung bao (x1, y1, x2, y2)
                logger.debug(f"Boxes detected: {boxes}")
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box)
                    face_roi = frame[y1:y2, x1:x2]  # Cắt vùng khuôn mặt

                    # Nhận diện cảm xúc bằng DeepFace
                    try:
                        emotion_analysis = DeepFace.analyze(face_roi, actions=['emotion'], enforce_detection=False)
                        emotion = emotion_analysis[0]['dominant_emotion']
                        logger.debug(f"Emotion detected: {emotion}")
                    except Exception as e:
                        logger.warning(f"DeepFace failed to analyze emotion: {str(e)}")
                        emotion = "Unknown"

                    # Lưu thông tin khuôn mặt và cảm xúc
                    faces.append({
                        'box': [x1, y1, x2, y2],
                        'emotion': emotion
                    })
        else:
            logger.warning("No faces detected by YOLO Face")

        # Vẽ khung bao và nhãn cảm xúc lên hình ảnh
        for face in faces:
            x1, y1, x2, y2 = face['box']
            emotion = face['emotion']
            # Vẽ khung bao quanh khuôn mặt
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            # Hiển thị nhãn cảm xúc
            cv2.putText(frame, emotion, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        # Mã hóa hình ảnh đã xử lý thành base64 để trả về
        _, buffer = cv2.imencode('.jpg', frame)
        processed_image = base64.b64encode(buffer).decode('utf-8')
        return jsonify({'image': f"data:image/jpeg;base64,{processed_image}", 'faces': faces})

    except Exception as e:
        logger.error(f"Error in detect_emotion: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    if session['role'] == 'admin':
        return redirect(url_for('teacher_home'))
    return redirect(url_for('student_home'))

@app.route('/teacher_home')
def teacher_home():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('auth.login'))
    section = request.args.get('section', 'home')

    # Lấy danh sách lớp học
    connection = get_db_connection()
    if connection is None:
        logger.error("Failed to connect to database in teacher_home")
        return "Failed to connect to database", 500

    try:
        cursor = connection.cursor(dictionary=True)

        # Lấy tất cả lớp học (cho form tạo lớp học và tạo tài khoản học sinh)
        cursor.execute("SELECT id, name FROM classes")
        all_classes = cursor.fetchall()
        logger.info(f"All classes for teacher: {all_classes}")
        # Lấy danh sách buổi học chưa kết thúc
        cursor.execute("""
            SELECT cs.id, cs.name, c.name as class_name, cs.date, cs.time, cs.is_ended
            FROM class_sessions cs
            JOIN classes c ON cs.class_id = c.id
            WHERE cs.is_ended = 0
        """)
        classes = cursor.fetchall()
        logger.info(f"Classes (is_ended = 0) for teacher: {classes}")

        # Lấy danh sách buổi học đã tham gia (is_ended = 1)
        cursor.execute("""
            SELECT cs.id, cs.name, c.name as class_name, cs.date, cs.time, cs.is_ended
            FROM class_sessions cs
            JOIN classes c ON cs.class_id = c.id
            WHERE cs.is_ended = 1
        """)
        joined_classes = cursor.fetchall()

        logger.info(f"Joined classes (is_ended = 1) for teacher: {joined_classes}")
        if not joined_classes:
            logger.warning("No joined classes found for teacher (is_ended = 1)")
        else:
            logger.info(f"Joined classes (is_ended = 1) for teacher: {joined_classes}")

    except Error as e:
        logger.error(f"Error fetching classes: {str(e)}")
        classes = []
        joined_classes = []
        all_classes = []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            logger.info("MySQL connection closed in teacher_home")

    return render_template('teacher_home.html', section=section, classes=classes, joined_classes=joined_classes, class_list=all_classes)

@app.route('/student_home')
def student_home():
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('auth.login'))

    section = request.args.get('section', 'home')

    # Lấy danh sách buổi học của học sinh
    connection = get_db_connection()
    if connection is None:
        return "Failed to connect to database", 500

    try:
        cursor = connection.cursor(dictionary=True)

        # Lấy class_id của học sinh từ bảng users
        cursor.execute("SELECT class_id FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        if not user or user['class_id'] is None:
            logger.error(f"Student {session['user_id']} has no class_id assigned")
            return render_template('student_home.html', section=section, classes=[], joined_classes=[])

        student_class_id = user['class_id']
        logger.info(f"Student {session['user_id']} belongs to class_id: {student_class_id}")

        # Lấy danh sách buổi học chưa kết thúc (is_ended = 0)
        cursor.execute("""
            SELECT cs.id, cs.name, c.name as class_name, cs.date, cs.time, cs.is_ended
            FROM class_sessions cs
            JOIN classes c ON cs.class_id = c.id
            WHERE cs.class_id = %s AND cs.is_ended = 0
        """, (student_class_id,))
        classes = cursor.fetchall()
        logger.info(f"Classes (is_ended = 0) for student {session['user_id']}: {classes}")

        # Lấy danh sách buổi học đã tham gia (is_ended = 1)
        cursor.execute("""
            SELECT cs.id, cs.name, c.name as class_name, cs.date, cs.time, cs.is_ended
            FROM class_sessions cs
            JOIN classes c ON cs.class_id = c.id
            WHERE cs.class_id = %s AND cs.is_ended = 1
        """, (student_class_id,))
        joined_classes = cursor.fetchall()
        logger.info(f"Joined classes (is_ended = 1) for student {session['user_id']}: {joined_classes}")

    except Error as e:
        logger.error(f"Error fetching classes for student: {str(e)}")
        classes = []
        joined_classes = []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

    return render_template('student_home.html', section=section, classes=classes, joined_classes=joined_classes)

@app.route('/meeting/<int:class_id>')
def meeting(class_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    # Kiểm tra xem class_id có tồn tại không
    connection = get_db_connection()
    if connection is None:
        return "Failed to connect to database", 500

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM class_sessions WHERE id = %s", (class_id,))
        class_session = cursor.fetchone()
        if not class_session:
            return "Buổi học không tồn tại", 404

        # Kiểm tra quyền truy cập
        cursor.execute("SELECT class_id FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        if not user:
            return "Người dùng không tồn tại", 404

        cursor.execute("SELECT class_id FROM class_sessions WHERE id = %s", (class_id,))
        session_class = cursor.fetchone()
        if session['role'] != 'admin' and user['class_id'] != session_class['class_id']:
            return "Bạn không có quyền truy cập buổi học này", 403

        # Lưu class_id vào session để sử dụng trong save-emotion
        session['class_id'] = class_id

    except Error as e:
        logger.error(f"Error accessing meeting: {str(e)}")
        return "Đã có lỗi xảy ra", 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

    return render_template('meeting.html', class_id=class_id)

@app.route('/delete_class/<int:class_id>', methods=['POST'])
def delete_class(class_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    connection = get_db_connection()
    if connection is None:
        return jsonify({'error': 'Failed to connect to database'}), 500

    try:
        cursor = connection.cursor()

        # Xóa bản ghi trong bảng class_sessions
        # Các bản ghi trong emotions sẽ tự động bị xóa nhờ ON DELETE CASCADE
        cursor.execute("DELETE FROM class_sessions WHERE id = %s", (class_id,))
        connection.commit()

        logger.info(f"Class {class_id} deleted successfully")
        return jsonify({'message': 'Xóa buổi học thành công'})
    except Error as e:
        logger.error(f"Error deleting class: {str(e)}")
        connection.rollback()  # Rollback nếu có lỗi
        return jsonify({'error': str(e)}), 400
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            logger.info("MySQL connection closed")

@app.route('/api/emotion_data/<int:class_id>', methods=['GET'])
def get_emotion_data(class_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    connection = get_db_connection()
    if connection is None:
        return jsonify({'error': 'Failed to connect to database'}), 500

    try:
        cursor = connection.cursor(dictionary=True)

        # Lấy danh sách học sinh tham gia buổi học
        cursor.execute("""
            SELECT DISTINCT e.user_id, u.name
            FROM emotions e
            JOIN users u ON e.user_id = u.id
            WHERE e.class_id = %s
        """, (class_id,))
        students = cursor.fetchall()

        # Nếu không có học sinh, trả về thông báo
        if not students:
            return jsonify({'emotion_data': {}}), 200

        # Lấy dữ liệu cảm xúc cho từng học sinh
        emotion_data = {}
        for student in students:
            user_id = student['user_id']
            cursor.execute("""
                SELECT emotion, detected_at
                FROM emotions
                WHERE class_id = %s AND user_id = %s
                ORDER BY detected_at
            """, (class_id, user_id))
            emotions = cursor.fetchall()

            # Tạo dữ liệu cho biểu đồ
            emotion_counts = {
                'happy': 0,
                'sad': 0,
                'angry': 0,
                'fearful': 0,
                'disgust': 0,
                'surprise': 0,
                'neutral': 0
            }
            for emotion in emotions:
                if emotion['emotion'] in emotion_counts:
                    emotion_counts[emotion['emotion']] += 1

            emotion_data[student['name']] = emotion_counts

        return jsonify({'emotion_data': emotion_data})
    except Error as e:
        logger.error(f"Error fetching emotion data: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            logger.info("MySQL connection closed")

@app.route('/emotion_chart/<int:class_id>')
def emotion_chart(class_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('teacher_home', section='home'))

    # Kiểm tra xem class_id có tồn tại không
    connection = get_db_connection()
    if connection is None:
        return "Failed to connect to database", 500

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id FROM class_sessions WHERE id = %s", (class_id,))
        class_session = cursor.fetchone()
        if not class_session:
            return "Buổi học không tồn tại", 404
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

    # Lấy thông báo từ session (nếu có) và xóa sau khi hiển thị
    message = session.pop('emotion_report_message', None)

    return render_template('emotion_chart.html', class_id=class_id, message=message)

@app.route('/leave_meeting/<int:class_id>', methods=['POST'])
def leave_meeting(class_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403

    # Kiểm tra xem class_id có tồn tại không
    connection = get_db_connection()
    if connection is None:
        return jsonify({'error': 'Failed to connect to database'}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, is_ended FROM class_sessions WHERE id = %s", (class_id,))
        class_session = cursor.fetchone()
        if not class_session:
            return jsonify({'error': 'Buổi học không tồn tại'}), 404

        # Đánh dấu buổi học là kết thúc
        cursor.execute("UPDATE class_sessions SET is_ended = 1 WHERE id = %s", (class_id,))
        connection.commit()
        logger.info(f"Updated class_session {class_id} to is_ended = 1")

        # Kiểm tra lại trạng thái is_ended sau khi cập nhật
        cursor.execute("SELECT is_ended FROM class_sessions WHERE id = %s", (class_id,))
        updated_session = cursor.fetchone()
        logger.info(f"Class session {class_id} after update: is_ended = {updated_session['is_ended']}")

        # Tạo báo cáo cảm xúc và redirect theo vai trò
        if session['role'] == 'admin':
            # Giáo viên: Tạo báo cáo và redirect về emotion_chart
            filename = generate_emotion_report(class_id)
            if filename:
                session['emotion_report_message'] = f'Rời buổi họp thành công, báo cáo cảm xúc đã được tạo. File: {filename}'
            else:
                session['emotion_report_message'] = 'Rời buổi họp thành công, nhưng không thể tạo báo cáo cảm xúc'
            return redirect(url_for('emotion_chart', class_id=class_id))
        else:
            # Học sinh: Redirect về trang chủ học sinh
            session['message'] = 'Rời buổi họp thành công'
            return redirect(url_for('student_home', section='home'))
    except Error as e:
        logger.error(f"Error leaving meeting: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == '__main__':
    app.run(debug=True)