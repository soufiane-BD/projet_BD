from flask import Blueprint, jsonify

from services.mesure_service import get_all_mesures
from services.simulation_service import simulate_propagation
from utils.security import api_login_required

simulation_bp = Blueprint("simulation_bp", __name__)


@simulation_bp.route("/simulate", methods=["GET"])
@api_login_required
def simulate():
    """
    Récupère la dernière mesure et calcule le risque de propagation.
    """
    mesures = get_all_mesures()

    if not mesures:
        return jsonify({"error": "Aucune donnée disponible"}), 404

    latest = mesures[0]

    temp = latest.get("temperature")
    hum = latest.get("humidite")
    wind = latest.get("vitesse_vent") or 0
    m_id = latest.get("id")

    result = simulate_propagation(temp, hum, wind, mesure_id=m_id)

    visual = "🟢 Calme"
    if result["risk_level"] == "High propagation":
        visual = "🔥 DANGER : Propagation rapide vers l'OUEST (Chergui)"
    elif result["risk_level"] == "Medium propagation":
        visual = "🟠 ATTENTION : Propagation modérée"

    return jsonify(
        {
            "mesure_utilisee": {"id": m_id, "temp": temp, "hum": hum, "vent": wind},
            "simulation": result,
            "visual_indicator": visual,
            "timestamp": latest.get("created_at"),
        }
    )
