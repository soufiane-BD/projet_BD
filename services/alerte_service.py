import datetime
from utils.database import get_db_connection
from services.notification_service import send_email_notification, log_notification_to_db


def get_all_alertes():
    """Return all alertes from the database."""
    connection = get_db_connection()
    rows = connection.execute("SELECT * FROM alerte ORDER BY created_at DESC").fetchall()
    connection.close()
    return [dict(row) for row in rows]


def get_alertes_for_view():
    """Return alertes formatted for the alertes template."""
    connection = get_db_connection()
    query = """
        SELECT
            a.id,
            a.niveau_risque,
            a.message,
            a.est_traite,
            a.created_at AS iso,
            m.temperature AS temp_c,
            m.id AS mesure_id,
            c.nom AS capteur_nom,
            c.localisation AS capteur_localisation
        FROM alerte a
        LEFT JOIN mesure m ON a.mesure_id = m.id
        LEFT JOIN capteur c ON m.capteur_id = c.id
        ORDER BY a.created_at DESC
    """
    rows = connection.execute(query).fetchall()
    connection.close()

    alertes = []
    for row in rows:
        niveau = row["niveau_risque"]
        verbose_action = (
            "SMS pompiers + log trigger" if niveau == "élevé" else "Enregistrement automatique"
        )
        alertes.append(
            {
                "id": row["id"],
                "horodatage": row["iso"],
                "iso": row["iso"],
                "lieu": f"{row['capteur_nom'] or 'Capteur inconnu'}",
                "temp_c": row["temp_c"] if row["temp_c"] is not None else 0,
                "action": verbose_action,
                "log_statut": "immutable",
                "critique": niveau == "élevé",
                "est_traite": bool(row["est_traite"]),
            }
        )
    return alertes


def toggle_alerte_status(alerte_id):
    """Inverse l'état traité/non-traité d'une alerte."""
    connection = get_db_connection()
    row = connection.execute("SELECT est_traite FROM alerte WHERE id = ?", (alerte_id,)).fetchone()
    if row:
        new_status = 0 if row["est_traite"] else 1
        connection.execute("UPDATE alerte SET est_traite = ? WHERE id = ?", (new_status, alerte_id))
        connection.commit()
    connection.close()
    return True


def add_alerte(mesure_id, niveau_risque, message):
    """Create a new alerte linked to a mesure."""
    connection = get_db_connection()
    
    # Récupérer les détails du capteur pour enrichir l'email
    sensor_query = """
        SELECT c.nom, c.localisation 
        FROM mesure m 
        JOIN capteur c ON m.capteur_id = c.id 
        WHERE m.id = ?
    """
    sensor = connection.execute(sensor_query, (mesure_id,)).fetchone()

    cursor = connection.execute(
        "INSERT INTO alerte (mesure_id, niveau_risque, message) VALUES (?, ?, ?)",
        (mesure_id, niveau_risque, message),
    )
    connection.commit()
    alerte_id = cursor.lastrowid
    connection.close()

    nom_capteur = sensor["nom"] if sensor else "Inconnu"
    loc_capteur = sensor["localisation"] if sensor else "Non précisée"

    # Déclenchement de la notification par email
    sujet = f"🔥 ARGAN-FIRE WATCH : Alerte {niveau_risque.upper()}"
    corps = (
        f"Une alerte de risque {niveau_risque} a été détectée sur le réseau de surveillance.\n\n"
        f"Détails de l'incident :\n"
        f"- Capteur : {nom_capteur}\n"
        f"- Localisation : {loc_capteur}\n"
        f"- Message : {message}\n"
        f"- Date/Heure : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
    )
    
    statut, notified_pompier_ids = send_email_notification(sujet, corps)
    log_notification_to_db(alerte_id, message, statut, notified_pompier_ids)

    return alerte_id


def delete_alerte(alerte_id):
    """Delete an alerte by its id."""
    connection = get_db_connection()
    cursor = connection.execute("DELETE FROM alerte WHERE id = ?", (alerte_id,))
    connection.commit()
    deleted = cursor.rowcount > 0
    connection.close()
    return deleted
