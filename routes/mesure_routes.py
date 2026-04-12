from flask import Blueprint, jsonify, request

from extensions import limiter
from services.mesure_service import add_mesure, delete_mesure, get_all_mesures
from utils.security import api_json_body_too_large, api_login_required

mesure_bp = Blueprint("mesure_bp", __name__)


@mesure_bp.before_request
def _limit_json_payload():
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and api_json_body_too_large():
        return jsonify({"error": "Requête trop volumineuse"}), 413


@mesure_bp.route("/mesures", methods=["GET"])
@api_login_required
def list_mesures():
    """Return the list of mesures stored in the database."""
    mesures = get_all_mesures()
    return jsonify(mesures)


@mesure_bp.route("/mesures", methods=["POST"])
@limiter.limit("60 per minute")
@api_login_required
def create_mesure():
    """Create a new mesure and possibly generate an alert."""
    data = request.get_json(force=True, silent=True) or {}
    capteur_id = data.get("capteur_id")
    temperature = data.get("temperature")
    humidite = data.get("humidite")
    vitesse_vent = data.get("vitesse_vent")
    direction_vent = data.get("direction_vent")

    if capteur_id is None or temperature is None or humidite is None:
        return jsonify({"error": "Données invalides."}), 400

    try:
        result = add_mesure(
            capteur_id=capteur_id,
            temperature=temperature,
            humidite=humidite,
            vitesse_vent=vitesse_vent,
            direction_vent=direction_vent,
        )
    except ValueError:
        return jsonify({"error": "Données invalides."}), 400

    response = {"id": result["id"], "alerte": result.get("alerte")}
    return jsonify(response), 201


@mesure_bp.route("/mesures/<int:mesure_id>", methods=["DELETE"])
@api_login_required
def remove_mesure(mesure_id):
    """Delete a mesure by its identifier."""
    deleted = delete_mesure(mesure_id)
    if not deleted:
        return jsonify({"error": "Ressource introuvable."}), 404
    return jsonify({"message": "Mesure supprimée."})
