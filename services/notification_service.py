from utils.database import get_db_connection
import smtplib
import os
from email.mime.text import MIMEText
import datetime

def send_email_notification(subject, body):
    """Envoie un email via un serveur SMTP (Configuration exemple Gmail)."""
    # --- CONFIGURATION À PERSONNALISER ---
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 465
    SENDER_EMAIL = os.getenv("EMAIL_USER")
    SENDER_PASSWORD = os.getenv("EMAIL_PASS")
    # -------------------------------------

    # Récupération de tous les pompiers depuis la base de données
    connection = get_db_connection()
    rows = connection.execute("SELECT id, email FROM pompiers").fetchall()
    connection.close()

    # Liste des emails et des IDs pour la traçabilité
    recipients = [r['email'] for row in rows if (r := dict(row))['email']]
    pompier_ids = [row['id'] for row in rows if row['email']]

    # Si aucun pompier n'est en base, on utilise le destinataire par défaut du .env
    if not recipients:
        recipients = [os.getenv("EMAIL_RECEIVER")]
        pompier_ids = []

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(recipients)

    try:
        if not SENDER_EMAIL or not SENDER_PASSWORD:
            raise ValueError("Les identifiants email ne sont pas configurés dans le fichier .env")
            
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipients, msg.as_string())
        print(f" NOTIFICATION : Email envoyé à {len(recipients)} destinataire(s).")
        return "Envoyé avec succès", pompier_ids
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email : {e}")
        return f"Échec : {str(e)}", []

def log_notification_to_db(alerte_id, message, statut, pompier_ids=[]):
    """Enregistre la trace de l'envoi et lie les pompiers concernés."""
    connection = get_db_connection()
    cursor = connection.execute(
        "INSERT INTO notification (alerte_id, message, statut_envoi, date_envoi) VALUES (?, ?, ?, ?)",
        (alerte_id, message, statut, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    )
    notification_id = cursor.lastrowid

    # Remplissage de la table de liaison 'recoit'
    for p_id in pompier_ids:
        connection.execute(
            "INSERT INTO recoit (notification_id, pompiers_id) VALUES (?, ?)",
            (notification_id, p_id)
        )

    # Remplissage de la table de liaison 'recoit1' (Lien avec les utilisateurs du système)
    user_rows = connection.execute("SELECT id FROM user").fetchall()
    for u_row in user_rows:
        connection.execute(
            "INSERT INTO recoit1 (user_id, notification_id) VALUES (?, ?)",
            (u_row['id'], notification_id)
        )

    connection.commit()
    connection.close()


def get_recent_notifications():
    """Retourne l'historique réel des envois d'emails depuis la table notification."""
    connection = get_db_connection()
    query = """
        SELECT
            n.id,
            n.message,
            n.date_envoi AS iso,
            n.statut_envoi,
            a.niveau_risque,
            c.nom AS capteur_nom
        FROM notification n
        JOIN alerte a ON n.alerte_id = a.id
        LEFT JOIN mesure m ON a.mesure_id = m.id
        LEFT JOIN capteur c ON m.capteur_id = c.id
        ORDER BY n.date_envoi DESC
        LIMIT 15
    """
    rows = connection.execute(query).fetchall()
    connection.close()

    notifications = []
    for row in rows:
        is_success = "succès" in row["statut_envoi"].lower()
        notifications.append(
            {
                "title": f"Email : Alerte {row['niveau_risque']}",
                "text": row["message"],
                "time": row["iso"],
                "iso": row["iso"],
                "kind": "sms" if is_success else "alert",
                "unread": not is_success,
                "meta": f"Statut : {row['statut_envoi']} | Capteur : {row['capteur_nom'] or 'N/A'}",
            }
        )
    return notifications
