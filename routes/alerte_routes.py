from flask import Blueprint, jsonify, request
from services.alerte_service import add_alerte, delete_alerte, get_all_alertes

alerte_bp = Blueprint("alerte_bp", __name__)


@alerte_bp.route("/alertes", methods=["GET"])
def list_alertes():
    """Return all alertes stored in the database."""
    alertes = get_all_alertes()
    return jsonify(alertes)


@alerte_bp.route("/alertes", methods=["POST"])
def create_alerte():
    """Create a simple alert manually from JSON request data."""
    data = request.get_json(force=True, silent=True) or {}
    mesure_id = data.get("mesure_id")
    niveau_risque = (data.get("niveau_risque") or "inconnu").strip()
    message = (data.get("message") or "Alerte créée manuellement.").strip()

    if mesure_id is None:
        return jsonify({"error": "mesure_id est requis."}), 400

    alerte_id = add_alerte(mesure_id, niveau_risque, message)
    return jsonify({"id": alerte_id, "mesure_id": mesure_id, "niveau_risque": niveau_risque}), 201


@alerte_bp.route("/alertes/<int:alerte_id>", methods=["DELETE"])
def remove_alerte(alerte_id):
    """Delete an alert by its identifier."""
    deleted = delete_alerte(alerte_id)
    if not deleted:
        return jsonify({"error": "Alerte non trouvée."}), 404
    return jsonify({"message": "Alerte supprimée."})
