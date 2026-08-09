from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
from models import db, User, Trek, Booking

app = Flask(__name__)
app.config['SECRET_KEY'] = 'trekking123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trek.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


def current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


@app.route('/')
def home():
    user = current_user()
    q = request.args.get('q', '')
    difficulty = request.args.get('difficulty', '')
    treks = Trek.query.filter(Trek.status != 'Cancelled')
    if q:
        treks = treks.filter(db.or_(Trek.name.like('%' + q + '%'), Trek.location.like('%' + q + '%')))
    if difficulty:
        treks = treks.filter_by(difficulty=difficulty)
    treks = treks.all()
    return render_template('index.html', treks=treks, user=user, q=q, difficulty=difficulty)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password, password):
            flash('Wrong username or password')
            return redirect(url_for('login'))
        if user.blocked:
            flash('Your account has been blocked by admin')
            return redirect(url_for('login'))
        if user.role == 'staff' and not user.approved:
            flash('Your account is waiting for admin approval')
            return redirect(url_for('login'))
        session['user_id'] = user.id
        session['role'] = user.role
        if user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        if user.role == 'staff':
            return redirect(url_for('staff_dashboard'))
        return redirect(url_for('user_dashboard'))
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        if User.query.filter_by(username=username).first():
            flash('Username already taken')
            return redirect(url_for('register'))
        u = User(username=username,
                 password=generate_password_hash(request.form['password']),
                 name=request.form['name'],
                 email=request.form['email'],
                 phone=request.form['phone'],
                 role='user',
                 approved=True)
        db.session.add(u)
        db.session.commit()
        flash('Registration done, please login')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/staff/register', methods=['GET', 'POST'])
def staff_register():
    if request.method == 'POST':
        username = request.form['username']
        if User.query.filter_by(username=username).first():
            flash('Username already taken')
            return redirect(url_for('staff_register'))
        u = User(username=username,
                 password=generate_password_hash(request.form['password']),
                 name=request.form['name'],
                 email=request.form['email'],
                 phone=request.form['phone'],
                 experience=request.form['experience'],
                 role='staff',
                 approved=False)
        db.session.add(u)
        db.session.commit()
        flash('Registration sent to admin for approval')
        return redirect(url_for('login'))
    return render_template('staff_register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    treks = Trek.query.all()
    pending = User.query.filter_by(role='staff', approved=False).all()
    total_users = User.query.filter_by(role='user').count()
    total_bookings = Booking.query.filter_by(status='Booked').count()
    return render_template('admin_dashboard.html', treks=treks, pending=pending,
                           total_users=total_users, total_bookings=total_bookings,
                           user=current_user())


@app.route('/admin/trek/add', methods=['GET', 'POST'])
def add_trek():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        slots = int(request.form['total_slots'])
        t = Trek(name=request.form['name'],
                 location=request.form['location'],
                 difficulty=request.form['difficulty'],
                 duration=int(request.form['duration']),
                 price=int(request.form['price']),
                 start_date=request.form['start_date'],
                 total_slots=slots,
                 available_slots=slots,
                 description=request.form['description'],
                 status='Upcoming')
        db.session.add(t)
        db.session.commit()
        flash('Trek added')
        return redirect(url_for('admin_dashboard'))
    return render_template('trek_form.html', trek=None, user=current_user())


@app.route('/admin/trek/edit/<int:tid>', methods=['GET', 'POST'])
def edit_trek(tid):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    trek = Trek.query.get_or_404(tid)
    if request.method == 'POST':
        booked = trek.total_slots - trek.available_slots
        new_total = int(request.form['total_slots'])
        if new_total < booked:
            flash('Total slots cannot be less than already booked slots')
            return redirect(url_for('edit_trek', tid=tid))
        trek.name = request.form['name']
        trek.location = request.form['location']
        trek.difficulty = request.form['difficulty']
        trek.duration = int(request.form['duration'])
        trek.price = int(request.form['price'])
        trek.start_date = request.form['start_date']
        trek.total_slots = new_total
        trek.available_slots = new_total - booked
        trek.description = request.form['description']
        db.session.commit()
        flash('Trek updated')
        return redirect(url_for('admin_dashboard'))
    return render_template('trek_form.html', trek=trek, user=current_user())


@app.route('/admin/trek/delete/<int:tid>')
def delete_trek(tid):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    trek = Trek.query.get_or_404(tid)
    Booking.query.filter_by(trek_id=trek.id).delete()
    db.session.delete(trek)
    db.session.commit()
    flash('Trek deleted')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/trek/assign/<int:tid>', methods=['GET', 'POST'])
def assign_staff(tid):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    trek = Trek.query.get_or_404(tid)
    staff_list = User.query.filter_by(role='staff', approved=True, blocked=False).all()
    if request.method == 'POST':
        sid = request.form['staff_id']
        if sid == '':
            trek.staff_id = None
        else:
            staff = User.query.get(int(sid))
            if staff is None or staff.role != 'staff' or not staff.approved or staff.blocked:
                flash('This staff cannot be assigned')
                return redirect(url_for('assign_staff', tid=tid))
            trek.staff_id = staff.id
        db.session.commit()
        flash('Staff assigned')
        return redirect(url_for('admin_dashboard'))
    return render_template('assign.html', trek=trek, staff_list=staff_list, user=current_user())


@app.route('/admin/staff')
def manage_staff():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    pending = User.query.filter_by(role='staff', approved=False).all()
    approved = User.query.filter_by(role='staff', approved=True).all()
    return render_template('admin_staff.html', pending=pending, approved=approved, user=current_user())


@app.route('/admin/staff/approve/<int:uid>')
def approve_staff(uid):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    staff = User.query.get_or_404(uid)
    staff.approved = True
    db.session.commit()
    flash('Staff approved')
    return redirect(url_for('manage_staff'))


@app.route('/admin/staff/reject/<int:uid>')
def reject_staff(uid):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    staff = User.query.get_or_404(uid)
    db.session.delete(staff)
    db.session.commit()
    flash('Staff request rejected')
    return redirect(url_for('manage_staff'))


@app.route('/admin/users')
def manage_users():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    users = User.query.filter_by(role='user').all()
    return render_template('admin_users.html', users=users, user=current_user())


@app.route('/admin/block/<int:uid>')
def block_user(uid):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    person = User.query.get_or_404(uid)
    if person.role == 'admin':
        flash('Admin cannot be blocked')
        return redirect(url_for('admin_dashboard'))
    person.blocked = not person.blocked
    db.session.commit()
    if person.role == 'staff':
        return redirect(url_for('manage_staff'))
    return redirect(url_for('manage_users'))


@app.route('/staff')
def staff_dashboard():
    if session.get('role') != 'staff':
        return redirect(url_for('login'))
    user = current_user()
    treks = Trek.query.filter_by(staff_id=user.id).all()
    return render_template('staff_dashboard.html', treks=treks, user=user)


@app.route('/staff/trek/<int:tid>', methods=['GET', 'POST'])
def staff_trek(tid):
    if session.get('role') != 'staff':
        return redirect(url_for('login'))
    user = current_user()
    trek = Trek.query.get_or_404(tid)
    if trek.staff_id != user.id:
        flash('This trek is not assigned to you')
        return redirect(url_for('staff_dashboard'))
    if request.method == 'POST':
        booked = trek.total_slots - trek.available_slots
        new_total = int(request.form['total_slots'])
        if new_total < booked:
            flash('Total slots cannot be less than already booked slots')
            return redirect(url_for('staff_trek', tid=tid))
        trek.total_slots = new_total
        trek.available_slots = new_total - booked
        trek.status = request.form['status']
        if trek.status == 'Completed':
            for b in trek.bookings:
                if b.status == 'Booked':
                    b.status = 'Completed'
        db.session.commit()
        flash('Trek updated')
        return redirect(url_for('staff_dashboard'))
    bookings = Booking.query.filter_by(trek_id=trek.id).all()
    return render_template('staff_trek.html', trek=trek, bookings=bookings, user=user)


@app.route('/dashboard')
def user_dashboard():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    user = current_user()
    bookings = Booking.query.filter_by(user_id=user.id).all()
    return render_template('user_dashboard.html', bookings=bookings, user=user)


@app.route('/trek/<int:tid>')
def trek_details(tid):
    trek = Trek.query.get_or_404(tid)
    return render_template('trek_details.html', trek=trek, user=current_user())


@app.route('/book/<int:tid>', methods=['POST'])
def book_trek(tid):
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    user = current_user()
    if user.blocked:
        flash('You are blocked and cannot book treks')
        return redirect(url_for('home'))
    trek = Trek.query.get_or_404(tid)
    members = int(request.form['members'])
    if trek.status != 'Upcoming':
        flash('Booking is closed for this trek')
        return redirect(url_for('trek_details', tid=tid))
    old = Booking.query.filter_by(user_id=user.id, trek_id=trek.id, status='Booked').first()
    if old:
        flash('You have already booked this trek')
        return redirect(url_for('trek_details', tid=tid))
    if members < 1 or members > trek.available_slots:
        flash('Not enough slots available')
        return redirect(url_for('trek_details', tid=tid))
    b = Booking(user_id=user.id, trek_id=trek.id, members=members,
                status='Booked', booked_on=str(date.today()))
    trek.available_slots = trek.available_slots - members
    db.session.add(b)
    db.session.commit()
    flash('Trek booked')
    return redirect(url_for('user_dashboard'))


@app.route('/cancel/<int:bid>')
def cancel_booking(bid):
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    user = current_user()
    b = Booking.query.get_or_404(bid)
    if b.user_id != user.id:
        flash('Not allowed')
        return redirect(url_for('user_dashboard'))
    if b.status != 'Booked':
        flash('This booking cannot be cancelled')
        return redirect(url_for('user_dashboard'))
    b.status = 'Cancelled'
    b.trek.available_slots = b.trek.available_slots + b.members
    db.session.commit()
    flash('Booking cancelled')
    return redirect(url_for('user_dashboard'))


def setup():
    db.create_all()
    if not User.query.filter_by(role='admin').first():
        admin = User(username='admin',
                     password=generate_password_hash('admin123'),
                     name='Administrator',
                     email='admin@trek.com',
                     role='admin',
                     approved=True)
        db.session.add(admin)
        db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        setup()
    app.run(debug=True)
