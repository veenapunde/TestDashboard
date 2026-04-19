import os
import sys
from datetime import datetime, timedelta, date
from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
import secrets

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Function to create .env file if it doesn't exist
def create_env_file_if_missing():
    if not os.path.exists('.env'):
        print("⚠️  .env file not found. Creating one with default settings...")
        
        # Try to get MySQL password from user
        print("\n🔧 Please enter your MySQL database password:")
        db_password = input("MySQL Password (press Enter for empty): ").strip()
        
        # Generate secure keys
        env_content = f"""# MySQL Database Configuration
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD={db_password}
DB_NAME=student_progress_db

# Security Keys
SECRET_KEY={secrets.token_hex(32)}
JWT_SECRET_KEY={secrets.token_hex(32)}

# Flask Settings
FLASK_DEBUG=True
"""
        with open('.env', 'w') as f:
            f.write(env_content)
        print("✅ .env file created successfully!")
        print("📁 You can edit this file anytime: .env")
    else:
        print("✅ .env file found")

# Create .env if missing
create_env_file_if_missing()

# Load environment variables from the script directory so cwd does not change DB config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'), override=True)

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ─── Configuration ────────────────────────────────────────────────────────────
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '3306')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASS = os.getenv('DB_PASSWORD', 'SSss@2233')
DB_PASS_ENCODED = quote_plus(DB_PASS)
DB_NAME = os.getenv('DB_NAME', 'student_progress_db')
DB_FALLBACK_TO_SQLITE = os.getenv('DB_FALLBACK_TO_SQLITE', 'true').lower() in ('1', 'true', 'yes')

mysql_uri = f"mysql+pymysql://{DB_USER}:{DB_PASS_ENCODED}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
sqlite_path = os.path.join(BASE_DIR, 'student_progress.db')
sqlite_uri = f"sqlite:///{sqlite_path}"

def resolve_database_uri():
    """
    Prefer MySQL when credentials work. If local auth fails, fall back to SQLite
    so the project can still boot on a new machine.
    """
    try:
        engine = create_engine(mysql_uri, future=True)
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        engine.dispose()
        print('Using MySQL database.')
        return mysql_uri, 'mysql'
    except Exception as exc:
        if not DB_FALLBACK_TO_SQLITE:
            raise
        print(f"MySQL unavailable, switching to SQLite. Reason: {exc}")
        return sqlite_uri, 'sqlite'


ACTIVE_DATABASE_URI, ACTIVE_DATABASE_BACKEND = resolve_database_uri()

app.config['SQLALCHEMY_DATABASE_URI'] = ACTIVE_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', secrets.token_hex(32))
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=8)

db = SQLAlchemy(app)
jwt = JWTManager(app)


# ─── Models ─────────────────────────────────────────────────────────────────
class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    college_id = db.Column(db.Integer, db.ForeignKey('colleges.id'), nullable=True)
    enrollment_date = db.Column(db.DateTime, default=datetime.utcnow)
    enrollments = db.relationship('Enrollment', backref='student', lazy=True, cascade='all, delete-orphan')
    progress_records = db.relationship('Progress', backref='student', lazy=True, cascade='all, delete-orphan')
    attendance_records = db.relationship('Attendance', backref='student', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'enrollment_date': self.enrollment_date.isoformat() if self.enrollment_date else None
        }


class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    course_name = db.Column(db.String(100), nullable=False)
    instructor_name = db.Column(db.String(100))
    duration = db.Column(db.String(50))
    enrollments = db.relationship('Enrollment', backref='course', lazy=True, cascade='all, delete-orphan')
    progress_records = db.relationship('Progress', backref='course', lazy=True, cascade='all, delete-orphan')
    attendance_records = db.relationship('Attendance', backref='course', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'course_name': self.course_name,
            'instructor_name': self.instructor_name,
            'duration': self.duration
        }


class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False)
    enrollment_date = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('student_id', 'course_id', name='unique_enrollment'),)

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'course_id': self.course_id,
            'student_name': self.student.name if self.student else None,
            'course_name': self.course.course_name if self.course else None,
            'enrollment_date': self.enrollment_date.isoformat() if self.enrollment_date else None
        }


class Progress(db.Model):
    __tablename__ = 'progress'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False)
    completion_percentage = db.Column(db.Integer, default=0)
    last_activity_date = db.Column(db.DateTime, default=datetime.utcnow)
    learning_hours = db.Column(db.Float, default=0.0)
    __table_args__ = (db.UniqueConstraint('student_id', 'course_id', name='unique_progress'),)

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'course_id': self.course_id,
            'student_name': self.student.name if self.student else None,
            'course_name': self.course.course_name if self.course else None,
            'completion_percentage': self.completion_percentage,
            'learning_hours': self.learning_hours,
            'last_activity_date': self.last_activity_date.isoformat() if self.last_activity_date else None
        }


class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False)  # 'Present' or 'Absent'

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'course_id': self.course_id,
            'student_name': self.student.name if self.student else None,
            'course_name': self.course.course_name if self.course else None,
            'date': self.date.isoformat() if self.date else None,
            'status': self.status
        }


# ─── Helpers ─────────────────────────────────────────────────────────────────
def success_response(data=None, message='Success', code=200):
    return jsonify({'success': True, 'message': message, 'data': data}), code

def error_response(message='Error', code=400):
    return jsonify({'success': False, 'message': message}), code


# ─── Static File Routes ───────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)


# ─── Auth Routes ─────────────────────────────────────────────────────────────
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    if not data:
        return error_response('No data provided')

    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return error_response('Username and password are required')

    admin = Admin.query.filter_by(username=username).first()
    if not admin or not admin.check_password(password):
        return error_response('Invalid username or password', 401)

    access_token = create_access_token(identity=str(admin.id))
    return jsonify({
        'success': True,
        'message': 'Login successful',
        'access_token': access_token,
        'admin': {'id': admin.id, 'username': admin.username}
    }), 200


# ─── Student Routes ───────────────────────────────────────────────────────────
@app.route('/api/students', methods=['GET'])
@jwt_required()
def get_students():
    students = Student.query.order_by(Student.id.desc()).all()
    return success_response([s.to_dict() for s in students])

@app.route('/api/students/<int:student_id>', methods=['GET'])
@jwt_required()
def get_student(student_id):
    student = Student.query.get_or_404(student_id)
    return success_response(student.to_dict())

@app.route('/api/students', methods=['POST'])
@jwt_required()
def create_student():
    data = request.get_json()
    if not data:
        return error_response('No data provided')

    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()

    if not name or not email:
        return error_response('Name and email are required')

    if Student.query.filter_by(email=email).first():
        return error_response('Email already exists', 409)

    student = Student(name=name, email=email, phone=phone)
    db.session.add(student)
    db.session.commit()
    return success_response(student.to_dict(), 'Student created successfully', 201)

@app.route('/api/students/<int:student_id>', methods=['PUT'])
@jwt_required()
def update_student(student_id):
    student = Student.query.get_or_404(student_id)
    data = request.get_json()
    if not data:
        return error_response('No data provided')

    if 'name' in data and data['name'].strip():
        student.name = data['name'].strip()
    if 'email' in data and data['email'].strip():
        existing = Student.query.filter_by(email=data['email'].strip()).first()
        if existing and existing.id != student_id:
            return error_response('Email already in use by another student', 409)
        student.email = data['email'].strip()
    if 'phone' in data:
        student.phone = data['phone'].strip()

    db.session.commit()
    return success_response(student.to_dict(), 'Student updated successfully')

@app.route('/api/students/<int:student_id>', methods=['DELETE'])
@jwt_required()
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    return success_response(None, 'Student deleted successfully')


# ─── Course Routes ────────────────────────────────────────────────────────────
@app.route('/api/courses', methods=['GET'])
@jwt_required()
def get_courses():
    courses = Course.query.order_by(Course.id.desc()).all()
    return success_response([c.to_dict() for c in courses])

@app.route('/api/courses/<int:course_id>', methods=['GET'])
@jwt_required()
def get_course(course_id):
    course = Course.query.get_or_404(course_id)
    return success_response(course.to_dict())

@app.route('/api/courses', methods=['POST'])
@jwt_required()
def create_course():
    data = request.get_json()
    if not data:
        return error_response('No data provided')

    course_name = data.get('course_name', '').strip()
    instructor_name = data.get('instructor_name', '').strip()
    duration = data.get('duration', '').strip()

    if not course_name:
        return error_response('Course name is required')

    course = Course(course_name=course_name, instructor_name=instructor_name, duration=duration)
    db.session.add(course)
    db.session.commit()
    return success_response(course.to_dict(), 'Course created successfully', 201)

@app.route('/api/courses/<int:course_id>', methods=['PUT'])
@jwt_required()
def update_course(course_id):
    course = Course.query.get_or_404(course_id)
    data = request.get_json()
    if not data:
        return error_response('No data provided')

    if 'course_name' in data and data['course_name'].strip():
        course.course_name = data['course_name'].strip()
    if 'instructor_name' in data:
        course.instructor_name = data['instructor_name'].strip()
    if 'duration' in data:
        course.duration = data['duration'].strip()

    db.session.commit()
    return success_response(course.to_dict(), 'Course updated successfully')

@app.route('/api/courses/<int:course_id>', methods=['DELETE'])
@jwt_required()
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()
    return success_response(None, 'Course deleted successfully')


# ─── Enrollment Routes ────────────────────────────────────────────────────────
@app.route('/api/enrollments', methods=['GET'])
@jwt_required()
def get_enrollments():
    enrollments = Enrollment.query.order_by(Enrollment.id.desc()).all()
    return success_response([e.to_dict() for e in enrollments])

@app.route('/api/enroll', methods=['POST'])
@jwt_required()
def enroll_student():
    data = request.get_json()
    if not data:
        return error_response('No data provided')

    student_id = data.get('student_id')
    course_id = data.get('course_id')

    if not student_id or not course_id:
        return error_response('Student ID and Course ID are required')

    student = Student.query.get(student_id)
    course = Course.query.get(course_id)

    if not student:
        return error_response('Student not found', 404)
    if not course:
        return error_response('Course not found', 404)

    existing = Enrollment.query.filter_by(student_id=student_id, course_id=course_id).first()
    if existing:
        return error_response('Student is already enrolled in this course', 409)

    enrollment = Enrollment(student_id=int(student_id), course_id=int(course_id))
    db.session.add(enrollment)

    # Also create initial progress record
    existing_progress = Progress.query.filter_by(student_id=student_id, course_id=course_id).first()
    if not existing_progress:
        progress = Progress(student_id=int(student_id), course_id=int(course_id),
                            completion_percentage=0, learning_hours=0.0)
        db.session.add(progress)

    db.session.commit()
    return success_response(enrollment.to_dict(), 'Student enrolled successfully', 201)

@app.route('/api/enrollments/<int:enrollment_id>', methods=['DELETE'])
@jwt_required()
def delete_enrollment(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    db.session.delete(enrollment)
    db.session.commit()
    return success_response(None, 'Enrollment removed successfully')


# ─── Progress Routes ──────────────────────────────────────────────────────────
@app.route('/api/progress', methods=['GET'])
@jwt_required()
def get_progress():
    records = Progress.query.order_by(Progress.id.desc()).all()
    return success_response([r.to_dict() for r in records])

@app.route('/api/progress/<int:progress_id>', methods=['GET'])
@jwt_required()
def get_progress_record(progress_id):
    record = Progress.query.get_or_404(progress_id)
    return success_response(record.to_dict())

@app.route('/api/progress', methods=['POST'])
@jwt_required()
def update_progress():
    data = request.get_json()
    if not data:
        return error_response('No data provided')

    student_id = data.get('student_id')
    course_id = data.get('course_id')
    completion = data.get('completion_percentage')
    hours = data.get('learning_hours')

    if not all([student_id, course_id, completion is not None, hours is not None]):
        return error_response('All fields are required')

    record = Progress.query.filter_by(student_id=int(student_id), course_id=int(course_id)).first()

    if record:
        record.completion_percentage = int(completion)
        record.learning_hours = float(hours)
        record.last_activity_date = datetime.utcnow()
        message = 'Progress updated successfully'
    else:
        record = Progress(
            student_id=int(student_id),
            course_id=int(course_id),
            completion_percentage=int(completion),
            learning_hours=float(hours),
            last_activity_date=datetime.utcnow()
        )
        db.session.add(record)
        message = 'Progress record created successfully'

    db.session.commit()
    return success_response(record.to_dict(), message)

@app.route('/api/progress/<int:progress_id>', methods=['PUT'])
@jwt_required()
def update_progress_by_id(progress_id):
    record = Progress.query.get_or_404(progress_id)
    data = request.get_json()
    if not data:
        return error_response('No data provided')

    if 'completion_percentage' in data:
        record.completion_percentage = int(data['completion_percentage'])
    if 'learning_hours' in data:
        record.learning_hours = float(data['learning_hours'])
    record.last_activity_date = datetime.utcnow()

    db.session.commit()
    return success_response(record.to_dict(), 'Progress updated successfully')


# ─── Attendance Routes ────────────────────────────────────────────────────────
@app.route('/api/attendance', methods=['GET'])
@jwt_required()
def get_attendance():
    records = Attendance.query.order_by(Attendance.date.desc(), Attendance.id.desc()).all()
    return success_response([r.to_dict() for r in records])

@app.route('/api/attendance', methods=['POST'])
@jwt_required()
def mark_attendance():
    data = request.get_json()
    if not data:
        return error_response('No data provided')

    student_id = data.get('student_id')
    course_id = data.get('course_id')
    att_date = data.get('date')
    status = data.get('status', 'Present')

    if not all([student_id, course_id, att_date]):
        return error_response('Student ID, Course ID, and Date are required')

    if status not in ('Present', 'Absent'):
        return error_response('Status must be Present or Absent')

    try:
        parsed_date = datetime.strptime(att_date, '%Y-%m-%d').date()
    except ValueError:
        return error_response('Invalid date format. Use YYYY-MM-DD')

    # Check if already marked for this student/course/date
    existing = Attendance.query.filter_by(
        student_id=int(student_id), course_id=int(course_id), date=parsed_date
    ).first()

    if existing:
        existing.status = status
        db.session.commit()
        return success_response(existing.to_dict(), 'Attendance updated successfully')

    record = Attendance(
        student_id=int(student_id),
        course_id=int(course_id),
        date=parsed_date,
        status=status
    )
    db.session.add(record)
    db.session.commit()
    return success_response(record.to_dict(), 'Attendance marked successfully', 201)

@app.route('/api/attendance/<int:attendance_id>', methods=['DELETE'])
@jwt_required()
def delete_attendance(attendance_id):
    record = Attendance.query.get_or_404(attendance_id)
    db.session.delete(record)
    db.session.commit()
    return success_response(None, 'Attendance record deleted successfully')


# ─── Analytics Routes ─────────────────────────────────────────────────────────
@app.route('/api/analytics/students/progress-summary', methods=['GET'])
@jwt_required()
def progress_summary():
    total_students = Student.query.count()
    total_courses = Course.query.count()
    total_enrollments = Enrollment.query.count()

    all_progress = Progress.query.all()
    avg_completion = 0.0
    total_hours = 0.0

    if all_progress:
        avg_completion = round(sum(p.completion_percentage for p in all_progress) / len(all_progress), 1)
        total_hours = round(sum(p.learning_hours for p in all_progress), 1)

    # Per-course average progress
    from sqlalchemy import func
    course_avg = db.session.query(
        Course.course_name,
        func.avg(Progress.completion_percentage).label('avg_progress')
    ).join(Progress, Progress.course_id == Course.id).group_by(Course.id, Course.course_name).all()

    course_performance = [
        {'course_name': row.course_name, 'avg_progress': round(float(row.avg_progress), 1)}
        for row in course_avg
    ]

    # Progress distribution
    high = sum(1 for p in all_progress if p.completion_percentage >= 70)
    medium = sum(1 for p in all_progress if 30 <= p.completion_percentage < 70)
    low = sum(1 for p in all_progress if p.completion_percentage < 30)

    return success_response({
        'total_students': total_students,
        'total_courses': total_courses,
        'total_enrollments': total_enrollments,
        'average_completion_percentage': avg_completion,
        'total_learning_hours': total_hours,
        'course_performance': course_performance,
        'progress_distribution': {'high': high, 'medium': medium, 'low': low}
    })

@app.route('/api/analytics/students/low-progress', methods=['GET'])
@jwt_required()
def low_progress_students():
    records = Progress.query.filter(Progress.completion_percentage < 30).all()
    return success_response([r.to_dict() for r in records])

@app.route('/api/analytics/students/inactive', methods=['GET'])
@jwt_required()
def inactive_students():
    threshold = datetime.utcnow() - timedelta(days=30)
    records = Progress.query.filter(Progress.last_activity_date < threshold).all()

    result = []
    now = datetime.utcnow()
    for r in records:
        days_inactive = (now - r.last_activity_date).days if r.last_activity_date else None
        d = r.to_dict()
        d['days_inactive'] = days_inactive
        result.append(d)

    return success_response(result)


# ─── Database Initialization ──────────────────────────────────────────────────
def init_db():
    with app.app_context():
        # Create tables
        db.create_all()
        print("✅ Database tables created or verified")
        
        # Create default admin if not exists
        if not Admin.query.filter_by(username='admin').first():
            admin = Admin(username='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print('✅ Default admin created: admin / admin123')
        else:
            print('ℹ️  Admin already exists.')


if __name__ == '__main__':
    print("🚀 Starting Student Progress Tracking System...")
    print("🔌 Attempting to connect to MySQL database...")
    
    try:
        init_db()
        print("✅ Database connection successful!")
        print("🌐 Open http://localhost:5000 in your browser")
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        print("❌ Database connection failed!")
        print(f"Error: {e}")
        print("\n🔧 Troubleshooting Tips:")
        print("1. Make sure MySQL is installed and running")
        print("2. Check your MySQL username and password in the .env file")
        print("3. Create the database manually: CREATE DATABASE student_progress_db;")
        print("4. Try running: pip install pymysql cryptography")



class College(db.Model):
    __tablename__ = 'colleges'
    id = db.Column(db.Integer, primary_key=True)
    college_name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200))
    established_year = db.Column(db.Integer)
    contact_email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    # ✅ college_id removed — it belongs on Student, not here

    def to_dict(self):
        return {
            'id': self.id,
            'college_name': self.college_name,
            'location': self.location,
            'established_year': self.established_year,
            'contact_email': self.contact_email,
            'phone': self.phone
            # ✅ college_id removed from dict too
        }


# ─── College Routes ───────────────────────────────────────────────────────────
@app.route('/api/colleges', methods=['GET'])
@jwt_required()
def get_colleges():
    colleges = College.query.order_by(College.id.desc()).all()
    return success_response([c.to_dict() for c in colleges])

@app.route('/api/colleges/<int:college_id>', methods=['GET'])
@jwt_required()
def get_college(college_id):
    college = College.query.get_or_404(college_id)
    return success_response(college.to_dict())

@app.route('/api/colleges', methods=['POST'])
@jwt_required()
def create_college():
    data = request.get_json()
    if not data:
        return error_response('No data provided')
    if not data.get('college_name', '').strip():
        return error_response('College name is required')
    college = College(
        college_name=data['college_name'].strip(),
        location=data.get('location', '').strip(),
        established_year=data.get('established_year') or None,
        contact_email=data.get('contact_email', '').strip(),
        phone=data.get('phone', '').strip()
    )
    db.session.add(college)
    db.session.commit()
    return success_response(college.to_dict(), 'College created successfully', 201)

@app.route('/api/colleges/<int:college_id>', methods=['PUT'])
@jwt_required()
def update_college(college_id):
    college = College.query.get_or_404(college_id)
    data = request.get_json()
    if not data:
        return error_response('No data provided')
    if 'college_name' in data and data['college_name'].strip():
        college.college_name = data['college_name'].strip()
    if 'location' in data:
        college.location = data['location'].strip()
    if 'established_year' in data:
        college.established_year = data['established_year'] or None
    if 'contact_email' in data:
        college.contact_email = data['contact_email'].strip()
    if 'phone' in data:
        college.phone = data['phone'].strip()
    db.session.commit()
    return success_response(college.to_dict(), 'College updated successfully')

@app.route('/api/colleges/<int:college_id>', methods=['DELETE'])
@jwt_required()
def delete_college(college_id):
    college = College.query.get_or_404(college_id)
    db.session.delete(college)
    db.session.commit()
    return success_response(None, 'College deleted successfully')

@app.route('/api/colleges/<int:college_id>/students', methods=['GET'])
@jwt_required()
def get_college_students(college_id):
    College.query.get_or_404(college_id)
    students = Student.query.filter_by(college_id=college_id).all()
    return success_response([s.to_dict() for s in students])
