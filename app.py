import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import date
from models import db, User, Trek, Booking

app = Flask(__name__)
app.config['SECRET_KEY'] = 'trekking123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trek.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
ALLOWED = ['png', 'jpg', 'jpeg', 'gif']
db.init_app(app)


def save_photo(f, user):
    if not f or f.filename == '':
        return None
    name = secure_filename(f.filename)
    if '.' not in name:
        return None
    ext = name.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED:
        return None
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    filename = 'user_' + str(user.id) + '.' + ext
    f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return filename


def current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


@app.route('/')
def home():
    user = current_user()
    q = request.args.get('q', '')
    difficulty = request.args.get('difficulty', '')
    treks = Trek.query.filter(Trek.status.in_(['Approved', 'Open']))
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
            flash('Wrong username or password', 'danger')
            return redirect(url_for('login'))
        if user.blocked:
            flash('Your account has been blocked by admin', 'danger')
            return redirect(url_for('login'))
        if user.role == 'staff' and not user.approved:
            flash('Your account is waiting for admin approval', 'warning')
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
            flash('Username already taken', 'danger')
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
        flash('Registration done, please login', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/staff/register', methods=['GET', 'POST'])
def staff_register():
    if request.method == 'POST':
        username = request.form['username']
        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'danger')
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
        flash('Registration sent to admin for approval', 'success')
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
    q = request.args.get('q', '')
    treks = Trek.query
    if q:
        if q.isdigit():
            treks = treks.filter_by(id=int(q))
        else:
            treks = treks.filter(Trek.name.like('%' + q + '%'))
    treks = treks.all()
    pending = User.query.filter_by(role='staff', approved=False).all()
    total_users = User.query.filter_by(role='user').count()
    total_staff = User.query.filter_by(role='staff').count()
    total_treks = Trek.query.count()
    total_bookings = Booking.query.filter_by(status='Booked').count()
    show = request.args.get('show', '')
    bookings = []
    if show == 'bookings':
        bookings = Booking.query.all()
    staff_list = []
    if show == 'add':
        staff_list = User.query.filter_by(role='staff', approved=True, blocked=False).all()
    users = []
    if show == 'users':
        users = User.query.filter_by(role='user')
        if q:
            if q.isdigit():
                users = users.filter_by(id=int(q))
            else:
                users = users.filter(User.name.like('%' + q + '%'))
        users = users.all()
    stats = []
    if show == 'staff':
        for s in User.query.filter_by(role='staff', approved=True).order_by(User.name).all():
            assigned = Trek.query.filter_by(staff_id=s.id).order_by(Trek.id).all()
            capacity = 0
            filled = 0
            for t in assigned:
                capacity = capacity + t.total_slots
                filled = filled + (t.total_slots - t.available_slots)
            stats.append({'staff': s, 'treks': assigned, 'capacity': capacity, 'filled': filled})
    return render_template('admin_dashboard.html', treks=treks, pending=pending,
                           total_users=total_users, total_staff=total_staff,
                           total_treks=total_treks, total_bookings=total_bookings,
                           show=show, bookings=bookings, staff_list=staff_list, stats=stats,
                           users=users, q=q, user=current_user())


@app.route('/admin/bookings')
def all_bookings():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    return redirect(url_for('admin_dashboard', show='bookings'))


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
                 end_date=request.form['end_date'],
                 total_slots=slots,
                 available_slots=slots,
                 description=request.form['description'],
                 status='Pending')
        db.session.add(t)
        db.session.commit()
        flash('Trek added', 'success')
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
            flash('Total slots cannot be less than already booked slots', 'danger')
            return redirect(url_for('edit_trek', tid=tid))
        trek.name = request.form['name']
        trek.location = request.form['location']
        trek.difficulty = request.form['difficulty']
        trek.duration = int(request.form['duration'])
        trek.price = int(request.form['price'])
        trek.start_date = request.form['start_date']
        trek.end_date = request.form['end_date']
        trek.total_slots = new_total
        trek.available_slots = new_total - booked
        trek.description = request.form['description']
        trek.status = request.form['status']
        db.session.commit()
        flash('Trek updated', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('trek_form.html', trek=trek, user=current_user())


@app.route('/admin/trek/delete/<int:tid>', methods=['GET', 'POST'])
def delete_trek(tid):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    trek = Trek.query.get_or_404(tid)
    if request.method == 'POST':
        Booking.query.filter_by(trek_id=trek.id).delete()
        db.session.delete(trek)
        db.session.commit()
        flash('Trek deleted', 'success')
        return redirect(url_for('admin_dashboard'))
    active = Booking.query.filter_by(trek_id=trek.id, status='Booked').count()
    total = Booking.query.filter_by(trek_id=trek.id).count()
    return render_template('confirm_delete.html', trek=trek, active=active,
                           total=total, user=current_user())


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
                flash('This staff cannot be assigned', 'danger')
                return redirect(url_for('assign_staff', tid=tid))
            trek.staff_id = staff.id
        db.session.commit()
        flash('Staff assigned', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('assign.html', trek=trek, staff_list=staff_list, user=current_user())


@app.route('/admin/staff')
def manage_staff():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    return redirect(url_for('admin_dashboard', show='staff'))


@app.route('/admin/staff/approve/<int:uid>')
def approve_staff(uid):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    staff = User.query.get_or_404(uid)
    staff.approved = True
    db.session.commit()
    flash('Staff approved', 'success')
    return redirect(url_for('admin_dashboard', show='staff'))


@app.route('/admin/staff/reject/<int:uid>')
def reject_staff(uid):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    staff = User.query.get_or_404(uid)
    db.session.delete(staff)
    db.session.commit()
    flash('Staff request rejected', 'success')
    return redirect(url_for('admin_dashboard', show='staff'))


@app.route('/admin/users')
def manage_users():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    return redirect(url_for('admin_dashboard', show='users'))


@app.route('/admin/block/<int:uid>')
def block_user(uid):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    person = User.query.get_or_404(uid)
    if person.role == 'admin':
        flash('Admin cannot be blocked', 'danger')
        return redirect(url_for('admin_dashboard'))
    person.blocked = not person.blocked
    db.session.commit()
    if person.role == 'staff':
        return redirect(url_for('admin_dashboard', show='staff'))
    return redirect(url_for('admin_dashboard', show='users'))


@app.route('/staff')
def staff_dashboard():
    if session.get('role') != 'staff':
        return redirect(url_for('login'))
    user = current_user()
    treks = Trek.query.filter_by(staff_id=user.id).all()
    counts = {}
    for t in treks:
        counts[t.id] = Booking.query.filter_by(trek_id=t.id, status='Booked').count()
    return render_template('staff_dashboard.html', treks=treks, counts=counts, user=user)


@app.route('/staff/trek/<int:tid>', methods=['GET', 'POST'])
def staff_trek(tid):
    if session.get('role') != 'staff':
        return redirect(url_for('login'))
    user = current_user()
    trek = Trek.query.get_or_404(tid)
    if trek.staff_id != user.id:
        flash('This trek is not assigned to you', 'danger')
        return redirect(url_for('staff_dashboard'))
    if request.method == 'POST':
        booked = trek.total_slots - trek.available_slots
        new_total = int(request.form['total_slots'])
        if new_total < booked:
            flash('Total slots cannot be less than already booked slots', 'danger')
            return redirect(url_for('staff_trek', tid=tid))
        trek.total_slots = new_total
        trek.available_slots = new_total - booked
        trek.status = request.form['status']
        if trek.status == 'Completed':
            for b in trek.bookings:
                if b.status == 'Booked':
                    b.status = 'Completed'
        db.session.commit()
        flash('Trek updated', 'success')
        return redirect(url_for('staff_dashboard'))
    bookings = Booking.query.filter_by(trek_id=trek.id).all()
    return render_template('staff_trek.html', trek=trek, bookings=bookings, user=user)


@app.route('/staff/booking/<int:bid>/cancel')
def staff_cancel_booking(bid):
    if session.get('role') != 'staff':
        return redirect(url_for('login'))
    user = current_user()
    b = Booking.query.get_or_404(bid)
    if b.trek.staff_id != user.id:
        flash('This booking is not on your trek', 'danger')
        return redirect(url_for('staff_dashboard'))
    if b.status != 'Booked':
        flash('This booking cannot be cancelled', 'danger')
        return redirect(url_for('staff_trek', tid=b.trek_id))
    b.status = 'Cancelled'
    b.trek.available_slots = b.trek.available_slots + b.members
    db.session.commit()
    flash('Booking cancelled and slots returned', 'success')
    return redirect(url_for('staff_trek', tid=b.trek_id))


@app.route('/dashboard')
def user_dashboard():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    user = current_user()
    bookings = Booking.query.filter_by(user_id=user.id).all()
    available = Trek.query.filter_by(status='Open').all()
    return render_template('user_dashboard.html', bookings=bookings, available=available, user=user)


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    if request.method == 'POST':
        user.name = request.form['name']
        user.email = request.form['email']
        user.phone = request.form['phone']
        if request.form['password']:
            user.password = generate_password_hash(request.form['password'])
        photo = save_photo(request.files.get('photo'), user)
        if photo:
            user.photo = photo
        elif request.files.get('photo') and request.files['photo'].filename != '':
            flash('Only png, jpg, jpeg or gif images are allowed', 'danger')
            return redirect(url_for('profile'))
        db.session.commit()
        flash('Profile updated', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=user)


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
        flash('You are blocked and cannot book treks', 'danger')
        return redirect(url_for('home'))
    trek = Trek.query.get_or_404(tid)
    members = int(request.form['members'])
    if trek.status != 'Open':
        flash('Booking is closed for this trek', 'danger')
        return redirect(url_for('trek_details', tid=tid))
    old = Booking.query.filter_by(user_id=user.id, trek_id=trek.id, status='Booked').first()
    if old:
        flash('You have already booked this trek', 'danger')
        return redirect(url_for('trek_details', tid=tid))
    if members < 1 or members > trek.available_slots:
        flash('Not enough slots available', 'danger')
        return redirect(url_for('trek_details', tid=tid))
    b = Booking(user_id=user.id, trek_id=trek.id, members=members,
                status='Booked', booked_on=str(date.today()))
    trek.available_slots = trek.available_slots - members
    db.session.add(b)
    db.session.commit()
    flash('Trek booked', 'success')
    return redirect(url_for('user_dashboard'))


@app.route('/cancel/<int:bid>')
def cancel_booking(bid):
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    user = current_user()
    b = Booking.query.get_or_404(bid)
    if b.user_id != user.id:
        flash('Not allowed', 'danger')
        return redirect(url_for('user_dashboard'))
    if b.status != 'Booked':
        flash('This booking cannot be cancelled', 'danger')
        return redirect(url_for('user_dashboard'))
    b.status = 'Cancelled'
    b.trek.available_slots = b.trek.available_slots + b.members
    db.session.commit()
    flash('Booking cancelled', 'success')
    return redirect(url_for('user_dashboard'))


@app.errorhandler(413)
def too_large(e):
    flash('The image is too big, please use one under 2 MB', 'danger')
    return redirect(url_for('profile'))


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
