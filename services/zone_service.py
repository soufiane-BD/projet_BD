from utils.database import get_db_connection


def get_zones_summary():
    """Return a simple summary of zones with active sensor count and risk."""
    connection = get_db_connection()
    query = """
        SELECT
            z.id,
            z.nom,
            z.niveau_risque,
            c.region,
            c.ville,
            COALESCE(COUNT(cap.id), 0) AS capteurs,
            MAX(m.created_at) AS derniere_synchro,
            c.nom AS coop_nom
        FROM zone z
        LEFT JOIN cooperative c ON z.id_cooperative = c.id
        LEFT JOIN capteur cap ON cap.id_zone = z.id
        LEFT JOIN mesure m ON m.capteur_id = cap.id
        GROUP BY z.id
        ORDER BY derniere_synchro DESC
    """
    rows = connection.execute(query).fetchall()
    connection.close()

    zones = []
    for row in rows:
        niveau = (row["niveau_risque"] or "low").lower()
        if "high" in niveau or "élevé" in niveau:
            risk = "high"
            label = "Risque élevé"
        elif "medium" in niveau or "modéré" in niveau:
            risk = "medium"
            label = "Risque modéré"
        else:
            risk = "low"
            label = "Risque faible"

        if row["derniere_synchro"]:
            iso = row["derniere_synchro"]
            derniere_synchro = row["derniere_synchro"]
        else:
            iso = ""
            derniere_synchro = "Aucune donnée"

        zones.append(
            {
                "nom": row["nom"] or f"Zone {row['id']}",
                "commune": row["ville"] or row["region"] or "Inconnue",
                "surface_ha": 0,
                "capteurs": row["capteurs"],
                "risk": risk,
                "risk_label": label,
                "derniere_synchro": derniere_synchro,
                "iso": iso,
                "note": f"Coopérative : {row['coop_nom'] or 'N/A'}",
            }
        )
    return zones

def get_all_zones_with_coop():
    """Return all zones with their associated cooperative name."""
    connection = get_db_connection()
    query = "SELECT z.*, c.nom as coop_nom FROM zone z LEFT JOIN cooperative c ON z.id_cooperative = c.id"
    rows = connection.execute(query).fetchall()
    connection.close()
    return [dict(row) for row in rows]

def add_zone(nom, id_cooperative):
    """Add a new zone record."""
    connection = get_db_connection()
    cursor = connection.execute(
        "INSERT INTO zone (nom, id_cooperative) VALUES (?, ?)",
        (nom, id_cooperative),
    )
    connection.commit()
    zone_id = cursor.lastrowid
    connection.close()
    return zone_id

def delete_zone(zone_id):
    """Delete a zone by its identifier."""
    connection = get_db_connection()
    cursor = connection.execute("DELETE FROM zone WHERE id = ?", (zone_id,))
    connection.commit()
    deleted = cursor.rowcount > 0
    connection.close()
    return deleted
