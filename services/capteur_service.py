from utils.database import get_db_connection
from utils.security import normalize_order_field, validate_capteur_nom


def get_all_capteurs(order: str | None = None):
    """Retourne les capteurs actifs, triés selon un champ whitelisté."""
    order_col = normalize_order_field(order)
    connection = get_db_connection()
    rows = connection.execute(
        f"""
        SELECT * FROM capteur
        WHERE COALESCE(actif, 1) = 1
        ORDER BY {order_col} ASC
        """
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def add_capteur(nom, localisation, latitude=None, longitude=None, id_zone=None):
    """Ajoute un capteur (nom validé par regex ; affichage sécurisé par autoescape Jinja)."""
    ok, nom_clean = validate_capteur_nom(nom)
    if not ok:
        raise ValueError("Nom de capteur invalide (caractères ou longueur non autorisés).")
    nom_store = nom_clean
    loc = (localisation or "").strip()
    connection = get_db_connection()
    cursor = connection.execute(
        "INSERT INTO capteur (nom, localisation, latitude, longitude, id_zone, actif) VALUES (?, ?, ?, ?, ?, 1)",
        (nom_store, loc, latitude, longitude, id_zone),
    )
    connection.commit()
    capteur_id = cursor.lastrowid
    connection.close()
    return capteur_id


def get_capteur(capteur_id):
    """Retourne un capteur actif par id ou None."""
    connection = get_db_connection()
    row = connection.execute(
        "SELECT * FROM capteur WHERE id = ? AND COALESCE(actif, 1) = 1",
        (capteur_id,),
    ).fetchone()
    connection.close()
    return dict(row) if row else None


def soft_delete_capteur(capteur_id):
    """Désactive un capteur (suppression logique)."""
    connection = get_db_connection()
    cursor = connection.execute(
        "UPDATE capteur SET actif = 0 WHERE id = ? AND COALESCE(actif, 1) = 1",
        (capteur_id,),
    )
    connection.commit()
    updated = cursor.rowcount > 0
    connection.close()
    return updated


def delete_capteur(capteur_id):
    """Compatibilité : suppression logique."""
    return soft_delete_capteur(capteur_id)
