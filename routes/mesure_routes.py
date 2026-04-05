from flask import Blueprint, jsonify, request
from services.mesure_service import add_mesure, delete_mesure, get_all_mesures

mesure_bp = Blueprint("mesure_bp", __name__)


@mesure_bp.route("/mesures", methods=["GET"])
def list_mesures():
    """Return the list of mesures stored in the database."""
    mesures = get_all_mesures()
    return jsonify(mesures)


@mesure_bp.route("/mesures", methods=["POST"])
def create_mesure():
    """Create a new mesure and possibly generate an alert."""
    data = request.get_json(force=True, silent=True) or {}
    capteur_id = data.get("capteur_id")
    temperature = data.get("temperature")
    humidite = data.get("humidite")
    vitesse_vent = data.get("vitesse_vent")
    direction_vent = data.get("direction_vent")

    if capteur_id is None or temperature is None or humidite is None:
        return jsonify({"error": "capteur_id, temperature et humidite sont requis."}), 400

    try:
        result = add_mesure(
            capteur_id=capteur_id,
            temperature=temperature,
            humidite=humidite,
            vitesse_vent=vitesse_vent,
            direction_vent=direction_vent,
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    response = {"id": result["id"], "alerte": result.get("alerte")}
    return jsonify(response), 201


@mesure_bp.route("/mesures/<int:mesure_id>", methods=["DELETE"])
def remove_mesure(mesure_id):
    """Delete a mesure by its identifier."""
    deleted = delete_mesure(mesure_id)
    if not deleted:
        return jsonify({"error": "Mesure non trouvée."}), 404
    return jsonify({"message": "Mesure supprimée."})
