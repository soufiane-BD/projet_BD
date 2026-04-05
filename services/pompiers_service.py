from utils.database import get_db_connection
from werkzeug.security import generate_password_hash

def get_all_pompiers():
    """Return all pompiers from the database."""
    connection = get_db_connection()
    rows = connection.execute("SELECT * FROM pompiers").fetchall()
    connection.close()
    return [dict(row) for row in rows]

def add_pompier(nom, prenom, email, telephone, password, admin_id):
    """Add a new pompier record."""
    pw_hash = generate_password_hash(password)
    connection = get_db_connection()
    cursor = connection.execute(
        "INSERT INTO pompiers (nom, prenom, email, telephone, password_hash, created_by_admin_id) VALUES (?, ?, ?, ?, ?, ?)",
        (nom, prenom, email, telephone, pw_hash, admin_id),
    )
    connection.commit()
    pompier_id = cursor.lastrowid
    connection.close()
    return pompier_id

def delete_pompier(pompier_id):
    """Delete a pompier by its ID."""
    connection = get_db_connection()
    cursor = connection.execute("DELETE FROM pompiers WHERE id = ?", (pompier_id,))
    connection.commit()
    deleted = cursor.rowcount > 0
    connection.close()
    return deleted