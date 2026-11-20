"""ReFound Version 12: campus lost-and-found; automated verification and security defaults."""
import os
import re
import sqlite3
import uuid
import io
from datetime import date
from PIL import Image, UnidentifiedImageError
from datetime import timedelta
from pathlib import Path
from flask import Flask, jsonify, request, session, send_from_directory, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=None)
app.config.update(
    SECRET_KEY=os.getenv('REFOUND_SECRET_KEY') or os.urandom(32),
    DATABASE=os.getenv('REFOUND_DATABASE', str(BASE / 'instance' / 'refound.db')),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.getenv('REFOUND_HTTPS', '0') == '1',
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    MAX_CONTENT_LENGTH=6 * 1024 * 1024,
)
EMAIL_PATTERN = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


def get_db():
    if 'db' not in g:
        dbpath = Path(app.config['DATABASE'])
        dbpath.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(dbpath)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        get_db().execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        get_db().execute("""CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            kind TEXT NOT NULL CHECK(kind IN ('lost','found')),
            title TEXT NOT NULL, category TEXT NOT NULL,
            color TEXT NOT NULL, location TEXT NOT NULL,
            event_date TEXT NOT NULL, description TEXT NOT NULL,
            image_name TEXT, status TEXT NOT NULL DEFAULT 'open'
              CHECK(status IN ('open','resolved')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        get_db().execute("""CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL REFERENCES reports(id),
            requester_id INTEGER NOT NULL REFERENCES users(id),
            proof TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','rejected','closed')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(report_id, requester_id)
        )""")
        get_db().execute("""CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id INTEGER NOT NULL REFERENCES claims(id),
            sender_id INTEGER NOT NULL REFERENCES users(id),
            body TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        db = get_db()
        cols = {r['name'] for r in db.execute('PRAGMA table_info(users)').fetchall()}
        if 'is_admin' not in cols:
            db.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0')
        db.execute('''CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            link TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS moderation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            report_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        db.commit()


def error(message, status=400):
    return jsonify(ok=False, message=message), status


def allowed_domain(email):
    raw = os.getenv('REFOUND_ALLOWED_DOMAINS', '').strip()
    if not raw:
        return True  # DEVELOPMENT ONLY: specify domains for real university restriction.
    domains = {d.strip().lower().lstrip('@') for d in raw.split(',') if d.strip()}
    return email.rsplit('@', 1)[-1] in domains


@app.after_request
def security_response_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.before_request
def protect_json_writes():
    if request.path.startswith('/api/') and request.method in ('POST', 'PATCH', 'DELETE'):
        # Same-origin requests only; browsers send Origin for fetch POST requests.
        origin = request.headers.get('Origin')
        if origin and origin.rstrip('/') != request.host_url.rstrip('/'):
            return error('Invalid request origin', 403)
        if request.path != '/api/reports' and not request.is_json:
            return error('JSON request required', 415)


@app.post('/api/register')
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get('fullName', '')).strip()
    email = str(data.get('email', '')).strip().lower()
    password = data.get('password', '')
    if not 3 <= len(name) <= 80:
        return error('Full name must be 3–80 characters.')
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        return error('Invalid email address.')
    if not allowed_domain(email):
        return error('Please use your approved university email.')
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        return error('Password must be 8–128 characters.')
    if data.get('confirmPassword') != password:
        return error('Passwords do not match.')
    if data.get('agreement') is not True:
        return error('You must accept the usage agreement.')
    try:
        cur = get_db().execute('INSERT INTO users (full_name,email,password_hash) VALUES (?,?,?)',
                               (name, email, generate_password_hash(password)))
        get_db().commit()
    except sqlite3.IntegrityError:
        return error('An account already exists with this email.', 409)
    session.clear()
    session['user_id'] = cur.lastrowid
    return jsonify(ok=True, fullName=name), 201


@app.post('/api/login')
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get('email', '')).strip().lower()
    password = data.get('password', '')
    if not isinstance(password, str) or not email:
        return error('Email and password required.')
    user = get_db().execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
    if user is None or not check_password_hash(user['password_hash'], password):
        return error('Email or password is incorrect.', 401)
    session.clear()
    session['user_id'] = user['id']
    session.permanent = bool(data.get('remember'))
    return jsonify(ok=True, fullName=user['full_name'])


@app.get('/api/me')
def me():
    uid = session.get('user_id')
    user = get_db().execute('SELECT id, full_name, email, is_admin FROM users WHERE id=?', (uid,)).fetchone() if uid else None
    if user is None:
        return error('Not signed in.', 401)
    return jsonify(ok=True, user=dict(user))


@app.post('/api/logout')
def logout():
    session.clear()
    return jsonify(ok=True)


def signed_in_user():
    uid = session.get('user_id')
    if not uid:
        return None
    return get_db().execute('SELECT id FROM users WHERE id=?', (uid,)).fetchone()


def public_report(row):
    r = dict(row)
    r['image_url'] = '/uploads/' + r['image_name'] if r['image_name'] else None
    r.pop('image_name', None)
    return r


def notify(user_id, kind, title, body, link):
    get_db().execute('INSERT INTO notifications (user_id,kind,title,body,link) VALUES (?,?,?,?,?)',
                     (user_id,kind,title[:150],body[:400],link[:240]))


def admin_user():
    user = signed_in_user()
    if not user:
        return None
    return get_db().execute('SELECT id, is_admin FROM users WHERE id=?', (user['id'],)).fetchone()


@app.get('/api/notifications')
def notifications():
    user = signed_in_user()
    if not user: return error('Sign in required',401)
    db = get_db()
    rows = db.execute('SELECT id,kind,title,body,link,is_read,created_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 80',(user['id'],)).fetchall()
    unread = db.execute('SELECT COUNT(*) n FROM notifications WHERE user_id=? AND is_read=0',(user['id'],)).fetchone()['n']
    return jsonify(ok=True, notifications=[dict(r) for r in rows], unread=unread)


@app.patch('/api/notifications/<int:notification_id>')
def read_notification(notification_id):
    user = signed_in_user()
    if not user: return error('Sign in required',401)
    cur=get_db().execute('UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?',(notification_id,user['id']))
    get_db().commit()
    if not cur.rowcount: return error('Notification not found',404)
    return jsonify(ok=True)


@app.post('/api/notifications/read-all')
def read_all_notifications():
    user = signed_in_user()
    if not user: return error('Sign in required',401)
    get_db().execute('UPDATE notifications SET is_read=1 WHERE user_id=?',(user['id'],))
    get_db().commit()
    return jsonify(ok=True)


@app.get('/api/admin/overview')
def admin_overview():
    user = admin_user()
    if not user or not user['is_admin']: return error('Admin access required',403)
    db=get_db()
    totals={key: db.execute('SELECT COUNT(*) n FROM '+table).fetchone()['n'] for key,table in [('users','users'),('reports','reports'),('claims','claims'),('messages','messages')]}
    totals['open_reports']=db.execute("SELECT COUNT(*) n FROM reports WHERE status='open'").fetchone()['n']
    totals['pending_claims']=db.execute("SELECT COUNT(*) n FROM claims WHERE status='pending'").fetchone()['n']
    reports=db.execute("SELECT r.id,r.title,r.kind,r.status,r.category,r.created_at,u.full_name AS author,u.email AS author_email FROM reports r JOIN users u ON u.id=r.user_id ORDER BY r.id DESC LIMIT 100").fetchall()
    return jsonify(ok=True,stats=totals,reports=[dict(r) for r in reports])


@app.post('/api/admin/reports/<int:report_id>/resolve')
def admin_resolve(report_id):
    user=admin_user()
    if not user or not user['is_admin']: return error('Admin access required',403)
    data=request.get_json(silent=True) or {}
    reason=str(data.get('reason','')).strip()
    if not 5<=len(reason)<=250: return error('Reason must be 5–250 characters',400)
    db=get_db(); row=db.execute('SELECT user_id,title,status FROM reports WHERE id=?',(report_id,)).fetchone()
    if not row: return error('Report not found',404)
    if row['status'] != 'open': return error('Report already resolved',409)
    db.execute("UPDATE reports SET status='resolved' WHERE id=?",(report_id,))
    db.execute('INSERT INTO moderation_log (admin_id,report_id,action,reason) VALUES (?,?,?,?)',
               (user['id'],report_id,'resolve',reason))
    notify(row['user_id'],'moderation','Report reviewed',f'Your report “{row["title"]}” was closed by moderation: {reason}',f'report.html?id={report_id}')
    db.commit()
    return jsonify(ok=True)


@app.get('/api/reports')
def list_reports():
    kind = request.args.get('kind', 'all')
    search = request.args.get('q', '').strip()[:100]
    category = request.args.get('category', '').strip()[:50]
    mine = request.args.get('mine') == '1'
    if kind not in ('all', 'lost', 'found'):
        return error('Invalid type')
    if mine and not signed_in_user():
        return error('Sign in required', 401)
    sql = 'SELECT * FROM reports WHERE 1=1'
    args = []
    if not mine:
        sql += " AND status='open'"
    if mine:
        sql += ' AND user_id=?'; args.append(session['user_id'])
    if kind != 'all':
        sql += ' AND kind=?'; args.append(kind)
    if category:
        sql += ' AND category=?'; args.append(category)
    if search:
        sql += ' AND (title LIKE ? OR description LIKE ? OR location LIKE ? OR color LIKE ?)'
        args.extend(['%' + search + '%'] * 4)
    sql += ' ORDER BY created_at DESC, id DESC LIMIT 100'
    return jsonify(ok=True, reports=[public_report(r) for r in get_db().execute(sql, args).fetchall()])


@app.get('/api/reports/<int:report_id>')
def report_details(report_id):
    row = get_db().execute('SELECT * FROM reports WHERE id=?', (report_id,)).fetchone()
    if not row or (row['status'] != 'open' and session.get('user_id') != row['user_id']):
        return error('Report not found', 404)
    return jsonify(ok=True, report=public_report(row))


@app.post('/api/reports')
def create_report():
    user = signed_in_user()
    if not user:
        return error('Sign in required', 401)
    if not request.mimetype == 'multipart/form-data':
        return error('Multipart form required', 415)
    v = {k: request.form.get(k, '').strip() for k in
         ['kind','title','category','color','location','event_date','description']}
    if v['kind'] not in ('lost', 'found'):
        return error('Choose lost or found')
    for k, limit in [('title',100), ('category',50), ('color',50), ('location',120), ('description',2000)]:
        if not v[k] or len(v[k]) > limit:
            return error('Invalid field: ' + k)
    try:
        day = date.fromisoformat(v['event_date'])
        if day > date.today() or day.year < 2000:
            return error('Invalid date')
    except ValueError:
        return error('Invalid date')
    photo = request.files.get('image')
    filename = None
    if photo and photo.filename:
        raw = photo.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            return error('Image must be under 5 MB')
        try:
            image = Image.open(io.BytesIO(raw))
            image.verify()
            image = Image.open(io.BytesIO(raw))
            if image.format not in ('JPEG', 'PNG', 'WEBP') or image.width * image.height > 16000000:
                return error('Unsupported image')
            image = image.convert('RGB')
            image.thumbnail((1200,1200))
            filename = uuid.uuid4().hex + '.jpg'
            folder = Path(app.config['DATABASE']).parent / 'uploads'
            folder.mkdir(parents=True,exist_ok=True)
            image.save(folder / filename, 'JPEG', quality=85)
        except (UnidentifiedImageError, OSError, ValueError):
            return error('Invalid image')
    cur = get_db().execute("""INSERT INTO reports
        (user_id,kind,title,category,color,location,event_date,description,image_name)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (user['id'],*[v[x] for x in ['kind','title','category','color','location','event_date','description']],filename))
    get_db().commit()
    return jsonify(ok=True, id=cur.lastrowid), 201


@app.patch('/api/reports/<int:report_id>')
def update_report(report_id):
    if not signed_in_user():
        return error('Sign in required', 401)
    data = request.get_json(silent=True) or {}
    if data.get('status') not in ('open','resolved'):
        return error('Invalid status')
    cur = get_db().execute('UPDATE reports SET status=? WHERE id=? AND user_id=?',
                           (data['status'],report_id,session['user_id']))
    get_db().commit()
    if not cur.rowcount:
        return error('Report not found', 404)
    return jsonify(ok=True)


def claim_access(claim_id):
    user = signed_in_user()
    if user is None:
        return None, error('Sign in required', 401)
    row = get_db().execute("""SELECT c.*, r.user_id AS owner_id, r.title AS report_title,
                        r.kind AS report_kind, r.status AS report_status,
                        u.full_name AS requester_name, owner.full_name AS owner_name
                        FROM claims c JOIN reports r ON r.id=c.report_id
                        JOIN users u ON u.id=c.requester_id
                        JOIN users owner ON owner.id=r.user_id WHERE c.id=?""", (claim_id,)).fetchone()
    if row is None or user['id'] not in (row['owner_id'], row['requester_id']):
        return None, error('Request not found', 404)
    return row, None


@app.post('/api/reports/<int:report_id>/claims')
def submit_claim(report_id):
    user = signed_in_user()
    if user is None:
        return error('Sign in required', 401)
    data = request.get_json(silent=True) or {}
    proof = str(data.get('proof', '')).strip()
    if not 15 <= len(proof) <= 1200:
        return error('Ownership details must be 15–1200 characters')
    report = get_db().execute('SELECT * FROM reports WHERE id=?', (report_id,)).fetchone()
    if report is None or report['status'] != 'open':
        return error('This report is unavailable', 404)
    if report['user_id'] == user['id']:
        return error('You cannot contact your own report', 400)
    try:
        cur = get_db().execute('INSERT INTO claims (report_id,requester_id,proof) VALUES (?,?,?)',
                               (report_id, user['id'], proof))
        get_db().commit()
    except sqlite3.IntegrityError:
        return error('You have already sent a request for this report', 409)
    notify(report['user_id'],'claim','New recovery request',f'A student requested your item: {report["title"]}',f'claims.html?claim={cur.lastrowid}')
    get_db().commit()
    return jsonify(ok=True, id=cur.lastrowid), 201


@app.get('/api/claims')
def list_claims():
    user = signed_in_user()
    if user is None:
        return error('Sign in required', 401)
    rows = get_db().execute("""SELECT c.id, c.report_id, c.requester_id, c.proof, c.status,
      c.created_at, r.title AS report_title, r.kind AS report_kind, r.status AS report_status,
      r.user_id AS owner_id, u.full_name AS requester_name, owner.full_name AS owner_name,
      (SELECT COUNT(*) FROM messages m WHERE m.claim_id=c.id) AS message_count
      FROM claims c JOIN reports r ON c.report_id=r.id
      JOIN users u ON u.id=c.requester_id JOIN users owner ON owner.id=r.user_id
      WHERE c.requester_id=? OR r.user_id=? ORDER BY c.created_at DESC, c.id DESC LIMIT 150""",
      (user['id'], user['id'])).fetchall()
    return jsonify(ok=True, claims=[dict(r) for r in rows], user_id=user['id'])


@app.get('/api/claims/<int:claim_id>')
def claim_details(claim_id):
    row, err = claim_access(claim_id)
    if err: return err
    messages = get_db().execute('SELECT id, sender_id, body, created_at FROM messages WHERE claim_id=? ORDER BY id ASC LIMIT 300',
                                (claim_id,)).fetchall()
    return jsonify(ok=True, claim=dict(row), messages=[dict(m) for m in messages], user_id=session['user_id'])


@app.patch('/api/claims/<int:claim_id>')
def change_claim(claim_id):
    row, err = claim_access(claim_id)
    if err: return err
    if session['user_id'] != row['owner_id']:
        return error('Only the report owner can review requests', 403)
    status = (request.get_json(silent=True) or {}).get('status')
    if row['status'] != 'pending' or status not in ('accepted', 'rejected'):
        return error('This request cannot be updated', 409)
    if row['report_status'] != 'open':
        return error('This report is no longer open', 409)
    get_db().execute('UPDATE claims SET status=? WHERE id=?', (status,claim_id))
    notify(row['requester_id'],'claim', 'Recovery request updated', f'Your request for {row["report_title"]} was {status}.', f'claims.html?claim={claim_id}')
    get_db().commit()
    return jsonify(ok=True)


@app.post('/api/claims/<int:claim_id>/messages')
def post_message(claim_id):
    row, err = claim_access(claim_id)
    if err: return err
    if row['status'] != 'accepted' or row['report_status'] != 'open':
        return error('Chat is available only for accepted open requests', 403)
    body = str((request.get_json(silent=True) or {}).get('body', '')).strip()
    if not 1 <= len(body) <= 1500:
        return error('Message must be 1–1500 characters')
    cur = get_db().execute('INSERT INTO messages (claim_id,sender_id,body) VALUES (?,?,?)',
                            (claim_id,session['user_id'],body))
    target = row['requester_id'] if session['user_id'] == row['owner_id'] else row['owner_id']
    notify(target,'message','New private message',f'New message about {row["report_title"]}',f'claims.html?claim={claim_id}')
    get_db().commit()
    return jsonify(ok=True, id=cur.lastrowid), 201



@app.get('/api/matches')
def smart_matches():
    user = signed_in_user()
    if user is None:
        return error('Sign in required', 401)
    try:
        report_id = int(request.args.get('report_id', '0'))
    except (TypeError, ValueError):
        return error('Invalid report identifier', 400)
    source = get_db().execute('SELECT * FROM reports WHERE id=? AND user_id=? AND status=\'open\'',
                              (report_id, user['id'])).fetchone()
    if source is None:
        return error('Your open report was not found', 404)
    others = get_db().execute("""SELECT * FROM reports WHERE kind != ? AND status='open'
         AND id != ? AND user_id != ? ORDER BY created_at DESC, id DESC LIMIT 500""",
         (source['kind'],report_id,user['id'])).fetchall()
    from matching import score_matches
    # De-duplicate accidental repeated postings by the SAME student.
    # Do not collapse similar-looking reports from different students.
    unique_reports = []
    seen = set()
    for row in others:
        data = dict(row)
        fingerprint = (data['user_id'], data['kind'],
                       *(str(data[field] or '').strip().casefold() for field in
                         ('title', 'category', 'color', 'location', 'event_date', 'description')))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique_reports.append(data)
    candidates, mode = score_matches(dict(source), unique_reports)
    for item in candidates:
        item['report'] = public_report(item['report'])
    # Return only top 15; callers can always browse all reports separately.
    return jsonify(ok=True, mode=mode, source=public_report(source),
                   matches=candidates[:15], total_candidates=len(candidates))



@app.get('/api/dashboard/stats')
def dashboard_stats():
    """Real counts derived from SQLite; personal figures scoped to the logged-in student."""
    user = signed_in_user()
    if user is None:
        return error('Sign in required', 401)
    db = get_db()
    uid = user['id']
    personal = db.execute("""SELECT COUNT(*) AS total,
        SUM(CASE WHEN kind='lost' THEN 1 ELSE 0 END) AS lost,
        SUM(CASE WHEN kind='found' THEN 1 ELSE 0 END) AS found,
        SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) AS open,
        SUM(CASE WHEN status='resolved' THEN 1 ELSE 0 END) AS resolved
        FROM reports WHERE user_id=?""", (uid,)).fetchone()
    requests = db.execute("""SELECT
        COUNT(*) AS total,
        SUM(CASE WHEN c.status='pending' THEN 1 ELSE 0 END) AS pending,
        SUM(CASE WHEN c.status='accepted' THEN 1 ELSE 0 END) AS accepted
        FROM claims c JOIN reports r ON r.id=c.report_id
        WHERE c.requester_id=? OR r.user_id=?""", (uid,uid)).fetchone()
    community = db.execute("""SELECT COUNT(*) AS total,
        SUM(CASE WHEN kind='lost' THEN 1 ELSE 0 END) AS lost,
        SUM(CASE WHEN kind='found' THEN 1 ELSE 0 END) AS found,
        SUM(CASE WHEN status='resolved' THEN 1 ELSE 0 END) AS resolved
        FROM reports""").fetchone()
    # last 7 calendar dates inclusive; database DATE() is UTC. Dates are labeled explicitly.
    trend = db.execute("""WITH RECURSIVE days(d) AS (
        SELECT DATE('now','-6 days') UNION ALL
        SELECT DATE(d,'+1 day') FROM days WHERE d < DATE('now')
    ) SELECT days.d AS day,
        (SELECT COUNT(*) FROM reports r WHERE r.user_id=? AND DATE(r.created_at)=days.d) AS count
        FROM days ORDER BY days.d""", (uid,)).fetchall()
    categories = db.execute("""SELECT category, COUNT(*) AS count
        FROM reports WHERE user_id=? GROUP BY category
        ORDER BY count DESC, category COLLATE NOCASE LIMIT 5""", (uid,)).fetchall()
    safe_counts = lambda row: {key:int(row[key] or 0) for key in row.keys()}
    return jsonify(ok=True, personal=safe_counts(personal),
                   requests=safe_counts(requests), community=safe_counts(community),
                   trend=[dict(r) for r in trend], categories=[dict(r) for r in categories])

@app.get('/uploads/<path:filename>')
def uploaded_image(filename):
    if not re.fullmatch(r'[0-9a-f]{32}\.jpg', filename):
        return error('Not found', 404)
    return send_from_directory(Path(app.config['DATABASE']).parent / 'uploads',filename)


@app.get('/')
def home():
    return send_from_directory(BASE, 'index.html')


@app.get('/<path:filename>')
def public_files(filename):
    allowed = {'index.html', 'login.html', 'register.html', 'dashboard.html',
               'style.css', 'script.js', 'auth.js', 'session.js', 'dashboard.js',
               'reports.html', 'reports.js', 'report.html', 'report.js',
               'claims.html', 'claims.js', 'matches.html', 'matches.js', 'dashboard-v7.css', 'admin.html', 'admin.js', 'notifications.html', 'notifications.js', 'v8.css', 'v9.css', 'v10.css', 'v11.css', 'shared-nav.js'}
    if filename not in allowed and filename != 'assets/refound-logo.png':
        return error('Not found.', 404)
    return send_from_directory(BASE, filename)


init_db()
if __name__ == '__main__':
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == 'make-admin':
        email = sys.argv[2].strip().lower()
        with app.app_context():
            db=get_db()
            user=db.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
            if not user:
                print('Account not found. Register normally first.')
                sys.exit(1)
            db.execute('UPDATE users SET is_admin=1 WHERE id=?',(user['id'],))
            db.commit()
            print('Admin permission granted to existing account:',email)
    else:
        app.run(debug=False)

