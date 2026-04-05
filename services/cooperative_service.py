from utils.database import get_db_connection

def get_all_cooperatives():
    """Return all cooperatives from the database."""
    connection = get_db_connection()
    rows = connection.execute("SELECT * FROM cooperative").fetchall()
    connection.close()
    return [dict(row) for row in rows]

def add_cooperative(nom, region=None, ville=None, latitude=None, longitude=None, adresse=None, date_de_creation=None):
    """Add a new cooperative record."""
    connection = get_db_connection()
    cursor = connection.execute(
        "INSERT INTO cooperative (nom, region, ville, latitude, longitude, adresse, date_de_creation) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (nom, region, ville, latitude, longitude, adresse, date_de_creation),
    )
    connection.commit()
    coop_id = cursor.lastrowid
    connection.close()
    return coop_id

def delete_cooperative(coop_id):
    """Delete a cooperative by its identifier."""
    connection = get_db_connection()
    cursor = connection.execute("DELETE FROM cooperative WHERE id = ?", (coop_id,))
    connection.commit()
    deleted = cursor.rowcount > 0
    connection.close()
    return deleted