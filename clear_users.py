import sqlite3

# Update this to match your DB name
conn = sqlite3.connect("placement_system.db")  # or database.db
cursor = conn.cursor()

# Get existing tables in the database
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
existing_tables = set(row[0] for row in cursor.fetchall())

# Safe list of tables to wipe
tables_to_clear = [
    "users",
    "student_profiles",
    "recruiter_profiles",
    "applications",
    "jobs",
    "companies",
]

for table in tables_to_clear:
    if table in existing_tables:
        cursor.execute(f"DELETE FROM {table};")
        print(f"✅ Cleared {table}")
    else:
        print(f"⚠️ Table '{table}' does not exist — skipped")

conn.commit()
conn.close()
print("🧼 Cleanup complete.")
