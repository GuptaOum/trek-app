from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    phone = db.Column(db.String(15))
    role = db.Column(db.String(10), nullable=False)
    experience = db.Column(db.String(200))
    approved = db.Column(db.Boolean, default=True)
    blocked = db.Column(db.Boolean, default=False)
    treks = db.relationship('Trek', backref='staff')
    bookings = db.relationship('Booking', backref='user')


class Trek(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.String(20))
    end_date = db.Column(db.String(20))
    total_slots = db.Column(db.Integer, nullable=False)
    available_slots = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(500))
    status = db.Column(db.String(20), default='Pending')
    staff_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    bookings = db.relationship('Booking', backref='trek')


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    trek_id = db.Column(db.Integer, db.ForeignKey('trek.id'), nullable=False)
    members = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), default='Booked')
    booked_on = db.Column(db.String(20))
