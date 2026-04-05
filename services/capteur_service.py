from utils.database import get_db_connection


def get_all_capteurs():
    """Return all capteurs from the database."""
    connection = get_db_connection()
    rows = connection.execute("SELECT * FROM capteur").fetchall()
    connection.close()
    return [dict(row) for row in rows]


def add_capteur(nom, localisation, latitude=None, longitude=None, id_zone=None):
    """Add a new capteur record in the database."""
    connection = get_db_connection()
    cursor = connection.execute(
        "INSERT INTO capteur (nom, localisation, latitude, longitude, id_zone) VALUES (?, ?, ?, ?, ?)",
        (nom, localisation, latitude, longitude, id_zone),
    )
    connection.commit()
    capteur_id = cursor.lastrowid
    connection.close()
    return capteur_id


def get_capteur(capteur_id):
    """Return a capteur by id or None if it does not exist."""
    connection = get_db_connection()
    row = connection.execute("SELECT * FROM capteur WHERE id = ?", (capteur_id,)).fetchone()
    connection.close()
    return dict(row) if row else None


def delete_capteur(capteur_id):
    """Delete a capteur by its id."""
    connection = get_db_connection()
    cursor = connection.execute("DELETE FROM capteur WHERE id = ?", (capteur_id,))
    connection.commit()
    deleted = cursor.rowcount > 0
    connection.close()
    return deleted
