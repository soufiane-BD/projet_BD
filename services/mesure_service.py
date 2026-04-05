import datetime
from utils.database import get_db_connection
from services.alerte_service import add_alerte
from services.capteur_service import get_capteur
from services.simulation_service import simulate_propagation


def get_all_mesures():
    """Return all mesures from the database."""
    connection = get_db_connection()
    rows = connection.execute("SELECT * FROM mesure ORDER BY created_at DESC").fetchall()
    connection.close()
    return [dict(row) for row in rows]


def add_mesure(capteur_id, temperature, humidite, vitesse_vent=None, direction_vent=None):
    """Add a mesure and create an alert if the fire risk is high."""
    if get_capteur(capteur_id) is None:
        raise ValueError("Capteur introuvable. Créez d’abord un capteur avec l’ID fourni.")

    connection = get_db_connection()
    cursor = connection.execute(
        "INSERT INTO mesure (capteur_id, temperature, humidite, vitesse_vent, direction_vent) VALUES (?, ?, ?, ?, ?)",
        (capteur_id, temperature, humidite, vitesse_vent, direction_vent),
    )
    connection.commit()
    mesure_id = cursor.lastrowid
    connection.close()

    alert_data = None

    # Analyse de la mesure pour détecter les risques d'incendie
    if temperature is not None and humidite is not None:
        # Appel au service de simulation pour calculer le score de propagation
        sim = simulate_propagation(temperature, humidite, vitesse_vent or 0, wind_deg=direction_vent)
        
        if sim['risk_level'] == "High propagation":
            # 1. Enregistrement du résultat dans simulation_de_propagation
            conn = get_db_connection()
            cursor = conn.execute(
                """INSERT INTO simulation_de_propagation 
                   (probabilite, vitesse_de_propagation, date_simulation, direction_du_feu, methode_calcule) 
                   VALUES (?, ?, ?, ?, ?)""",
                (sim['score'], vitesse_vent or 0, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), direction_vent, "Automatique v1")
            )
            sim_id = cursor.lastrowid
            conn.commit()

            # 2. Création de l'alerte
            msg = f"ALERTE CRITIQUE : Score propagation {sim['score']}. Temp {temperature}°C."
            alerte_id = add_alerte(mesure_id, "élevé", msg)

            # 3. Liaison entre l'alerte et la simulation (table donne_lieu)
            conn.execute("INSERT INTO donne_lieu (alerte_id, simulation_id) VALUES (?, ?)", (alerte_id, sim_id))
            conn.commit()
            conn.close()
            
            alert_data = {"id": alerte_id, "niveau": "élevé"}

        elif temperature > 38:
            # Risque modéré simple (seuil de température)
            alerte_id = add_alerte(mesure_id, "modéré", f"Température élevée détectée : {temperature}°C")
            alert_data = {"id": alerte_id, "niveau": "modéré"}

    return {"id": mesure_id, "alerte": alert_data}

def delete_mesure(mesure_id):
    """Delete a mesure by its id."""
    connection = get_db_connection()
    cursor = connection.execute("DELETE FROM mesure WHERE id = ?", (mesure_id,))
    connection.commit()
    deleted = cursor.rowcount > 0
    connection.close()
    return deleted
