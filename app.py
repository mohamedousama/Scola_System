from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scola_academy.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'scola_academy_secret_key_2025'
db = SQLAlchemy(app)

# Define models directly in app.py to avoid circular imports
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='student') # 'admin' or 'student'

    student = db.relationship('Student', backref='user', uselist=False)
    wallet = db.relationship('Wallet', backref='user', uselist=False)

    def __repr__(self):
        return f'<User {self.username}>'

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)

    enrollments = db.relationship('Enrollment', backref='course', lazy=True)

    def __repr__(self):
        return f'<Course {self.name}>'

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)

    enrollments = db.relationship('Enrollment', backref='student', lazy=True)

    def __repr__(self):
        return f'<Student {self.full_name}>'

class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    remaining_amount = db.Column(db.Float, nullable=False)
    commission_percentage = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<Enrollment {self.student_id} - {self.course_id}>'

class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return f'<Wallet {self.user_id} - {self.balance}>'

@app.route('/')
def index():
    courses = Course.query.all()
    return render_template('index.html', courses=courses)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash('تم تسجيل الدخول بنجاح!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        full_name = request.form['full_name']
        
        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم موجود بالفعل', 'error')
            return render_template('register.html')
        
        # Create new user
        password_hash = generate_password_hash(password)
        new_user = User(username=username, password_hash=password_hash, role='student')
        db.session.add(new_user)
        db.session.commit()
        
        # Create student profile
        new_student = Student(user_id=new_user.id, full_name=full_name)
        db.session.add(new_student)
        
        # Create wallet
        new_wallet = Wallet(user_id=new_user.id, balance=0.0)
        db.session.add(new_wallet)
        
        db.session.commit()
        
        flash('تم إنشاء الحساب بنجاح!', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    courses = Course.query.all()
    wallet = Wallet.query.filter_by(user_id=user.id).first()
    
    if user.role == 'admin':
        return render_template('admin_dashboard.html', user=user, courses=courses, wallet=wallet)
    else:
        student = Student.query.filter_by(user_id=user.id).first()
        enrollments = Enrollment.query.filter_by(student_id=student.id).all() if student else []
        return render_template('student_dashboard.html', user=user, student=student, courses=courses, enrollments=enrollments, wallet=wallet)

@app.route('/enroll_student', methods=['POST'])
def enroll_student():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('غير مصرح لك بالوصول لهذه الصفحة', 'error')
        return redirect(url_for('login'))
    
    student_name = request.form['student_name']
    course_id = request.form['course_id']
    amount_paid = float(request.form['amount_paid'])
    
    # Get course details
    course = Course.query.get(course_id)
    if not course:
        flash('الكورس غير موجود', 'error')
        return redirect(url_for('dashboard'))
    
    # Calculate remaining amount
    remaining_amount = course.price - amount_paid
    if remaining_amount < 0:
        remaining_amount = 0
    
    # Calculate 10% commission
    commission_percentage = course.price * 0.10
    
    # Check if student already exists or create new one
    existing_user = User.query.filter_by(username=student_name.lower().replace(' ', '_')).first()
    
    if existing_user and existing_user.student:
        # Student already exists
        student = existing_user.student
        
        # Check if already enrolled in this course
        existing_enrollment = Enrollment.query.filter_by(student_id=student.id, course_id=course_id).first()
        if existing_enrollment:
            flash('الطالب مسجل بالفعل في هذا الكورس', 'error')
            return redirect(url_for('dashboard'))
    else:
        # Create new student user
        username = student_name.lower().replace(' ', '_')
        password_hash = generate_password_hash('123456')  # Default password
        new_user = User(username=username, password_hash=password_hash, role='student')
        db.session.add(new_user)
        db.session.commit()
        
        # Create student profile
        student = Student(user_id=new_user.id, full_name=student_name)
        db.session.add(student)
        
        # Create wallet for student
        student_wallet = Wallet(user_id=new_user.id, balance=0.0)
        db.session.add(student_wallet)
        db.session.commit()
    
    # Create enrollment
    enrollment = Enrollment(
        student_id=student.id,
        course_id=course_id,
        amount_paid=amount_paid,
        remaining_amount=remaining_amount,
        commission_percentage=commission_percentage
    )
    db.session.add(enrollment)
    
    # Update student wallet with commission
    student_wallet = Wallet.query.filter_by(user_id=student.user_id).first()
    if student_wallet:
        student_wallet.balance += commission_percentage
    
    # Update admin wallet with commission
    admin_user = User.query.filter_by(role='admin').first()
    if admin_user:
        admin_wallet = Wallet.query.filter_by(user_id=admin_user.id).first()
        if admin_wallet:
            admin_wallet.balance += commission_percentage
    
    db.session.commit()
    
    flash(f'تم تسجيل الطالب {student_name} بنجاح في كورس {course.name}', 'success')
    flash(f'تم إضافة {commission_percentage} جنيه لمحفظة الطالب والإدارة', 'success')
    
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create admin user if not exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin_password = generate_password_hash('admin123')
            admin_user = User(username='admin', password_hash=admin_password, role='admin')
            db.session.add(admin_user)
            db.session.commit()
            
            # Create admin wallet
            admin_wallet = Wallet(user_id=admin_user.id, balance=0.0)
            db.session.add(admin_wallet)
            db.session.commit()
        
        # Create sample courses if not exist
        if Course.query.count() == 0:
            courses = [
                Course(name='Python Programming', price=500.0, description='تعلم البرمجة بلغة Python من الصفر'),
                Course(name='Web Development', price=750.0, description='تطوير المواقع الإلكترونية باستخدام HTML, CSS, JavaScript'),
                Course(name='Data Science', price=1000.0, description='علم البيانات والتحليل الإحصائي'),
                Course(name='Mobile App Development', price=800.0, description='تطوير تطبيقات الهاتف المحمول')
            ]
            for course in courses:
                db.session.add(course)
            db.session.commit()
    
    app.run(host='0.0.0.0', port=5001, debug=True)
