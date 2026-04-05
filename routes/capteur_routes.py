from flask import Blueprint, jsonify, request
from services.capteur_service import add_capteur, delete_capteur, get_all_capteurs

capteur_bp = Blueprint("capteur_bp", __name__)


@capteur_bp.route("/capteurs", methods=["GET"])
def list_capteurs():
    """Return all capteurs stored in the database."""
    capteurs = get_all_capteurs()
    return jsonify(capteurs)


@capteur_bp.route("/capteurs", methods=["POST"])
def create_capteur():
    """Create a new capteur from JSON request data."""
    data = request.get_json(force=True, silent=True) or {}
    nom = (data.get("nom") or "").strip()
    localisation = (data.get("localisation") or "").strip()
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    id_zone = data.get("id_zone")
    
    if not nom:
        return jsonify({"error": "Le nom du capteur est requis."}), 400

    capteur_id = add_capteur(nom, localisation, latitude=latitude, longitude=longitude, id_zone=id_zone)
    return jsonify({"id": capteur_id, "nom": nom, "localisation": localisation, "id_zone": id_zone}), 201


@capteur_bp.route("/capteurs/<int:capteur_id>", methods=["DELETE"])
def remove_capteur(capteur_id):
    """Delete a capteur by its identifier."""
    deleted = delete_capteur(capteur_id)
    if not deleted:
        return jsonify({"error": "Capteur non trouvé."}), 404
    return jsonify({"message": "Capteur supprimé."})
