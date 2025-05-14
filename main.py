from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

app.jinja_env.filters['todatetime'] = lambda date_str, fmt: datetime.strptime(date_str, fmt)

def init_db():
    if not os.path.exists("users.db"):
        conn = sqlite3.connect("users.db")
        c = conn.cursor()

        # إنشاء جدول المستخدمين
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                name TEXT,
                national_id TEXT,
                phone TEXT,
                email TEXT,
                role TEXT,
                specialty TEXT,
                intern_specialty TEXT,
                university TEXT,
                permission TEXT,
                start_date TEXT,
                end_date TEXT,
                notes TEXT
            )
        """)

        # إدخال المستخدم الافتراضي إذا ما فيه أحد
        c.execute("SELECT COUNT(*) FROM users")
        if c.fetchone()[0] == 0:
            c.execute("""
                INSERT INTO users (username, password, name, role, permission)
                VALUES (?, ?, ?, ?, ?)
            """, ('amjad', 'Admin2025', 'أمجد الأدمن', 'موظف', 'أدمن'))

        # إنشاء جدول settings إن ما كان موجود
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_receiver TEXT
            )
        """)

        # إدخال بريد افتراضي إذا ما فيه بيانات
        c.execute("SELECT COUNT(*) FROM settings")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO settings (email_receiver) VALUES (?)", ("amjaad.alsubaie@gmail.com",))

        conn.commit()
        conn.close()
   
init_db()

def get_user_by_credentials(username, password):
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    conn.close()
    return user

def get_receiver_email():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT email_receiver FROM settings LIMIT 1")
    result = c.fetchone()
    conn.close()
    return result[0] if result else "amjaad.alsubaie@gmail.com"

def send_email(name, email, message, file=None, filename=None):
    sender_email = "amjaad.alsubaie@gmail.com"
    app_password = "dyfgblfooqwhwlmf"
    receiver_email = get_receiver_email()

    subject = f"طلب تقديم جديد من {name}"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'plain'))

    if file and filename:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(file.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        msg.attach(part)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print("خطأ أثناء إرسال الإيميل:", e)

@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = get_user_by_credentials(username, password)

        if user:
            session['user'] = user['id']
            session['username'] = user['username']
            session['permission'] = user['permission']

            if user['permission'] == 'أدمن':
                return redirect(url_for('admin_dashboard'))
            elif user['permission'] in ['تعديل', 'حذف']:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_profile'))
        else:
            error = 'اسم المستخدم أو كلمة المرور غير صحيحة!'

    return render_template('login.html', error=error)

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')

@app.route('/members/view')
def view_members():
    if 'username' not in session:
        return redirect(url_for('login'))

    if session.get('permission') in ['أدمن', 'تعديل', 'حذف']:
        conn = sqlite3.connect('users.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM users")
        rows = c.fetchall()
        members = []

        for row in rows:
            row = dict(row)
            try:
                if row['role'] == 'متدرب' and row['start_date'] and row['end_date']:
                    start = datetime.strptime(row['start_date'], '%Y-%m-%d')
                    end = datetime.strptime(row['end_date'], '%Y-%m-%d')
                    row['training_days'] = (end - start).days + 1
                else:
                    row['training_days'] = None
            except:
                row['training_days'] = None
            members.append(row)

        conn.close()
        return render_template('view_members.html', members=members)
    else:
        return "ليس لديك صلاحية لعرض الأعضاء"

@app.route('/members/add', methods=['GET', 'POST'])
def add_member():
    if 'username' not in session:
        return redirect(url_for('login'))

    if session.get('permission') != 'أدمن':
        return render_template('admin_dashboard.html', error='ليس لديك صلاحية إضافة أعضاء')

    message = None
    message_type = None

    if request.method == 'POST':
        member_type = request.form.get('member-type')
        username = request.form.get('username')
        password = request.form.get('password')
        fullname = request.form.get('fullname')
        id_number = request.form.get('id_number')
        phone = request.form.get('phone')
        email = request.form.get('email')
        permission = request.form.get('permission') if member_type == 'موظف' else ''
        notes = request.form.get('notes')

        role = member_type
        specialty = ''
        intern_specialty = ''
        university = ''
        start_date = ''
        end_date = ''

        if member_type == 'موظف':
            specialty = request.form.get('specialization')
            start_date = request.form.get('employee_start_date')
        elif member_type == 'متدرب':
            university = request.form.get('university')
            intern_specialty = request.form.get('intern_specialization')
            start_date = request.form.get('intern_start_date')
            end_date = request.form.get('end_date')

        try:
            with sqlite3.connect('users.db') as conn:
                c = conn.cursor()
                c.execute('''
                    INSERT INTO users (
                        username, password, name, national_id, phone, email, role,
                        specialty, intern_specialty, university, permission,
                        start_date, end_date, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    username, password, fullname, id_number, phone, email, role,
                    specialty, intern_specialty, university, permission,
                    start_date, end_date, notes
                ))
                conn.commit()
            message = 'تمت إضافة العضو بنجاح!'
            message_type = 'success'
        except sqlite3.IntegrityError:
            message = 'اسم المستخدم موجود بالفعل! يرجى اختيار اسم آخر.'
            message_type = 'error'
        except sqlite3.OperationalError:
            message = 'تعذر الوصول لقاعدة البيانات. يرجى المحاولة مرة أخرى.'
            message_type = 'error'

    return render_template('add_member.html', message=message, message_type=message_type)

@app.route('/user/profile')
def user_profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (session['user'],))
    user = c.fetchone()
    conn.close()
    return render_template('member_info.html', user=user)

@app.route('/update_member', methods=['POST'])
def update_member():
    if 'username' not in session or session.get('permission') not in ['تعديل', 'أدمن']:
        return jsonify({'status': 'error', 'message': 'ليس لديك صلاحية التعديل'}), 403

    data = request.get_json()
    try:
        with sqlite3.connect('users.db') as conn:
            c = conn.cursor()
            c.execute('''
                UPDATE users SET
                    name = ?, username = ?, national_id = ?, phone = ?, email = ?,
                    role = ?, specialty = ?, intern_specialty = ?, university = ?,
                    start_date = ?, end_date = ?, notes = ?
                WHERE id = ?
            ''', (
                data['name'], data['username'], data['national_id'], data['phone'], data['email'],
                data['role'], data['specialty'], data.get('intern_specialty'), data['university'],
                data['start_date'], data['end_date'], data['notes'], data['id']
            ))
            conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/delete_member', methods=['POST'])
def delete_member():
    if 'username' not in session or session.get('permission') not in ['حذف', 'أدمن']:
        return jsonify({'status': 'error', 'message': 'ليس لديك صلاحية الحذف'}), 403

    data = request.get_json()
    try:
        with sqlite3.connect('users.db') as conn:
            c = conn.cursor()
            c.execute("DELETE FROM users WHERE id = ?", (data['id'],))
            conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/apply', methods=['GET', 'POST'])
def apply_form():
    if request.method == 'POST':
        req_type = request.form.get('type')
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        city = request.form.get('city')
        university = request.form.get('university')
        message = request.form.get('message')
        cv_file = request.files.get('cv_file')

        full_message = f"""
نوع الطلب: {req_type}
الاسم الكامل: {name}
البريد الإلكتروني: {email}
رقم الجوال: {phone}
المدينة: {city}
الجامعة / المعهد: {university}

سبب التقديم:
{message}
        """

        if cv_file and cv_file.filename.endswith('.pdf'):
            send_email(name, email, full_message, file=cv_file, filename=cv_file.filename)
        else:
            send_email(name, email, full_message)

        return render_template('apply_form.html', success=True)

    return render_template('apply_form.html')


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    message = None
    error = None
    success = False

    if request.method == 'POST':
        identifier = request.form.get('identifier')  # اسم المستخدم أو الإيميل
        new_password = request.form.get('new_password')

        if not identifier or not new_password:
            error = "يرجى تعبئة جميع الحقول."
        else:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username = ? OR email = ?", (identifier, identifier))
            user = c.fetchone()

            if user:
                c.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user[0]))
                conn.commit()
                conn.close()
                message = "تم تحديث كلمة المرور بنجاح."
                success = True
                return render_template('forgot_password.html', message=message, success=success)
            else:
                conn.close()
                error = "المستخدم غير موجود. تأكد من كتابة الاسم أو الإيميل بشكل صحيح."

    return render_template('forgot_password.html', message=message, error=error, success=success)

@app.route('/update_email', methods=['GET', 'POST'])
def update_email():
    if 'username' not in session:
        return redirect(url_for('login'))

    if session.get('permission') != 'أدمن':
        error = "ليس لديك صلاحية الدخول إلى الإعدادات"
        return render_template('admin_dashboard.html', error=error)

    message = None
    if request.method == 'POST':
        new_email = request.form.get('new_email')
        if new_email:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("UPDATE settings SET email_receiver = ? WHERE id = 1", (new_email,))
            conn.commit()
            conn.close()
            message = "تم تحديث البريد بنجاح!"

    return render_template('update_email.html', message=message)

if __name__ == '__main__':
    app.run(debug=True)