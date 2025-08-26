import os, sqlite3, time
from contextlib import contextmanager
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "placement_system.db")

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        # Users
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL CHECK(role IN ('STUDENT','RECRUITER','ADMIN')),
                email TEXT NOT NULL UNIQUE,
                name TEXT,
                usn TEXT,
                password_hash BLOB NOT NULL,
                email_verified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);")

        # OTP
        c.execute("""
            CREATE TABLE IF NOT EXISTS otp_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                purpose TEXT NOT NULL, -- SIGNUP, LOGIN, RESET
                expires_at INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)

        # Students
        c.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                name   TEXT, usn TEXT UNIQUE, branch TEXT, email TEXT, phone TEXT, resume BLOB,
                status TEXT DEFAULT 'Not Applied',
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
            );
        """)

        # Recruiters (also holds job postings)
        c.execute("""
            CREATE TABLE IF NOT EXISTS recruiters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                company_name TEXT NOT NULL,
                job_desc     TEXT NOT NULL,
                salary       TEXT,
                location     TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
            );
        """)

        # Applications
        c.execute("""
            CREATE TABLE IF NOT EXISTS job_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id  INTEGER NOT NULL,
                recruiter_id INTEGER NOT NULL,
                status TEXT DEFAULT 'Applied',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY(recruiter_id) REFERENCES recruiters(id) ON DELETE CASCADE
            );
        """)

        c.execute("CREATE INDEX IF NOT EXISTS idx_students_usn ON students(usn);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_app_student ON job_applications(student_id);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_app_recruiter ON job_applications(recruiter_id);")
        conn.commit()

# Passwords
def hash_password(plain: str) -> bytes:
    try:
        import bcrypt
    except ImportError:
        raise RuntimeError("Install bcrypt: pip install bcrypt")
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt())

def check_password(plain: str, hashed: bytes) -> bool:
    import bcrypt
    try:
        return bcrypt.checkpw(plain.encode(), hashed)
    except Exception:
        return False

# Users
def create_user(role: str, email: str, name: str, password: str, usn: Optional[str] = None) -> int:
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("Email is required")
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE email=?", (email,))
        if c.fetchone():
            raise ValueError("Email already registered")
        ph = hash_password(password)
        c.execute("INSERT INTO users(role,email,name,usn,password_hash) VALUES(?,?,?,?,?)",
                  (role.upper(), email, name, usn, ph))
        conn.commit()
        return c.lastrowid

def get_user_by_email(email: str):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT id, role, email, name, usn, password_hash, email_verified FROM users WHERE email=?",
                  ((email or "").lower(),))
        return c.fetchone()

def set_password(user_id: int, new_password: str):
    with get_conn() as conn:
        c = conn.cursor()
        ph = hash_password(new_password)
        c.execute("UPDATE users SET password_hash=? WHERE id=?", (ph, user_id))
        conn.commit()

def mark_email_verified(user_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET email_verified=1 WHERE id=?", (user_id,))
        conn.commit()

# OTP
import secrets as _sec
def _choice(s): return _sec.choice(s)

def create_otp(user_id: int, purpose: str, ttl_seconds: int = 600) -> str:
    code = "".join(_choice("0123456789") for _ in range(6))
    expires = int(time.time()) + ttl_seconds
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO otp_codes(user_id, code, purpose, expires_at) VALUES(?,?,?,?)",
                  (user_id, code, purpose, expires))
        conn.commit()
    print(f"[OTP] {purpose} for user {user_id}: {code}")
    return code

def verify_otp(user_id: int, code: str, purpose: str) -> bool:
    now = int(time.time())
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, expires_at FROM otp_codes
            WHERE user_id=? AND code=? AND purpose=?
            ORDER BY id DESC LIMIT 1
        """, (user_id, code, purpose))
        row = c.fetchone()
        if not row: return False
        if row[1] < now: return False
        c.execute("DELETE FROM otp_codes WHERE id=?", (row[0],))
        conn.commit()
        return True

# Placement operations
def upsert_student_profile(user_id: int, name, usn, branch, email, phone, resume_bytes):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM students WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if row:
            c.execute("""
                UPDATE students SET name=?, usn=?, branch=?, email=?, phone=?, resume=?
                WHERE user_id=?
            """, (name, usn, branch, email, phone, resume_bytes, user_id))
        else:
            c.execute("""
                INSERT INTO students(user_id, name, usn, branch, email, phone, resume)
                VALUES(?,?,?,?,?,?,?)
            """, (user_id, name, usn, branch, email, phone, resume_bytes))
        conn.commit()

def list_jobs(q=None):
    with get_conn() as conn:
        c = conn.cursor()
        if q:
            q_like = f"%{q.lower()}%"
            c.execute("""
                SELECT id, company_name, job_desc, salary, location, user_id
                FROM recruiters
                WHERE lower(company_name) LIKE ? OR lower(job_desc) LIKE ? OR lower(location) LIKE ?
                ORDER BY id DESC
            """, (q_like, q_like, q_like))
        else:
            c.execute("SELECT id, company_name, job_desc, salary, location, user_id FROM recruiters ORDER BY id DESC")
        return c.fetchall()

def create_job(user_id: int, company_name, job_desc, salary, location):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO recruiters(user_id, company_name, job_desc, salary, location)
            VALUES(?,?,?,?,?)
        """, (user_id, company_name, job_desc, salary, location))
        conn.commit()
        return c.lastrowid

def get_student_id_email_by_user(user_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT id, COALESCE(email,'') FROM students WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if not row: return (None, "")
        return row[0], row[1]

def get_recruiter_email_by_recruiter_id(recruiter_id: int) -> str:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT u.email FROM recruiters r
            JOIN users u ON u.id = r.user_id
            WHERE r.id=?
        """, (recruiter_id,))
        row = c.fetchone()
        return row[0] if row else ""

def apply_job(student_user_id: int, recruiter_id: int):
    sid, student_email = get_student_id_email_by_user(student_user_id)
    if not sid:
        raise ValueError("Complete your student profile first")
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM job_applications WHERE student_id=? AND recruiter_id=?", (sid, recruiter_id))
        if c.fetchone():
            return False, student_email
        c.execute("INSERT INTO job_applications(student_id, recruiter_id) VALUES(?,?)", (sid, recruiter_id))
        conn.commit()
        return True, student_email

def list_applications_for_student(student_user_id: int):
    sid, _ = get_student_id_email_by_user(student_user_id)
    if not sid: return []
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT a.id, r.company_name, r.job_desc, a.status, a.created_at, a.recruiter_id
            FROM job_applications a
            JOIN recruiters r ON r.id = a.recruiter_id
            WHERE a.student_id = ?
            ORDER BY a.id DESC
        """, (sid,))
        return c.fetchall()

def list_all_applications():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT a.id, s.name, u.usn, r.company_name, r.job_desc, a.status, a.created_at, a.student_id, a.recruiter_id
            FROM job_applications a
            JOIN students s ON s.id = a.student_id
            JOIN users u ON u.id = s.user_id
            JOIN recruiters r ON r.id = a.recruiter_id
            ORDER BY a.id DESC
        """)
        return c.fetchall()

def set_application_status(app_id: int, status: str):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT s.email, r.company_name
            FROM job_applications a
            JOIN students s ON s.id = a.student_id
            JOIN recruiters r ON r.id = a.recruiter_id
            WHERE a.id=?
        """, (app_id,))
        row = c.fetchone()
        if not row:
            return None, None
        student_email, company = row
        c.execute("UPDATE job_applications SET status=? WHERE id=?", (status, app_id))
        conn.commit()
        return student_email, company

# helper used by main_app for notifications
def get_recruiter_email_by_recruiter_id(recruiter_id: int) -> str:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT u.email FROM recruiters r
            JOIN users u ON u.id = r.user_id
            WHERE r.id=?
        """, (recruiter_id,))
        row = c.fetchone()
        return row[0] if row else ""
