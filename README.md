# Trekking Management Application

Web application to manage treks, trek staff and trekker bookings.

## Technologies
- Flask
- Jinja2, HTML, CSS, Bootstrap
- SQLite with Flask-SQLAlchemy

## How to run

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 in the browser. The database file `trek.db` is created automatically on the first run.

## Admin login
Username: admin
Password: admin123

## Roles

**Admin** creates treks, approves or rejects staff requests, assigns staff to treks, and blocks users or staff.

**Trek Staff** registers from the site and can log in only after admin approval. Staff can see the treks assigned to them, change the number of slots and update the trek status.

**Users** register, search and filter treks by name, location and difficulty, book available treks, cancel a booking and see their booking history.

## Files
- `app.py` - routes and application logic
- `models.py` - database tables
- `templates/` - Jinja2 pages
- `static/style.css` - extra styling
