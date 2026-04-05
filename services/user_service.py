from utils.database import get_db_connection
from werkzeug.security import generate_password_hash

def get_all_users():
    """Return all users from the database."""
    connection = get_db_connection()
    query = """
        SELECT u.id, u.email, u.nom, u.id_cooperative, c.nom as coop_nom 
        FROM user u 
        LEFT JOIN cooperative c ON u.id_cooperative = c.id
    """
    rows = connection.execute(query).fetchall()
    connection.close()
    return [dict(row) for row in rows]

def add_user(email, password, nom, id_cooperative=None):
    """Add a new user with a hashed password."""
    password_hash = generate_password_hash(password)
    connection = get_db_connection()
    cursor = connection.execute(
        "INSERT INTO user (email, password_hash, nom, id_cooperative) VALUES (?, ?, ?, ?)",
        (email, password_hash, nom, id_cooperative),
    )
    connection.commit()
    user_id = cursor.lastrowid
    connection.close()
    print(f"DEBUG: Utilisateur {email} inséré avec succès (ID: {user_id})")
    return user_id

def delete_user(user_id):
    """Delete a user by its ID."""
    connection = get_db_connection()
    cursor = connection.execute("DELETE FROM user WHERE id = ?", (user_id,))
    connection.commit()
    deleted = cursor.rowcount > 0
    connection.close()
    return deleted