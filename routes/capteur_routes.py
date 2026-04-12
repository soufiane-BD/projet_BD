import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user

from extensions import limiter
from services.capteur_service import add_capteur, delete_capteur, get_all_capteurs
from utils.security import api_login_required, normalize_order_field, require_admin_json
from utils.security import api_json_body_too_large

capteur_bp = Blueprint("capteur_bp", __name__)
_security = logging.getLogger("argan_security")


@capteur_bp.before_request
def _limit_json_payload():
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and api_json_body_too_large():
        return jsonify({"error": "Requête trop volumineuse"}), 413


@capteur_bp.route("/capteurs", methods=["GET"])
@api_login_required
def list_capteurs():
    """Return all active capteurs stored in the database."""
    order = request.args.get("order", "id")
    order = normalize_order_field(order)
    capteurs = get_all_capteurs(order=order)
    return jsonify(capteurs)


@capteur_bp.route("/capteurs", methods=["POST"])
@api_login_required
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

    try:
        capteur_id = add_capteur(nom, localisation, latitude=latitude, longitude=longitude, id_zone=id_zone)
    except ValueError:
        return jsonify({"error": "Données invalides."}), 400

    return jsonify({"id": capteur_id, "nom": nom, "localisation": localisation, "id_zone": id_zone}), 201


@capteur_bp.route("/capteurs/<int:capteur_id>", methods=["DELETE"])
@limiter.limit("30 per minute")
@require_admin_json
def remove_capteur(capteur_id):
    """Désactive un capteur (suppression logique) — réservé aux administrateurs."""
    deleted = delete_capteur(capteur_id)
    if not deleted:
        return jsonify({"error": "Capteur non trouvé."}), 404
    _security.warning(
        "SUPPRESSION_CAPTEUR capteur_id=%s admin_db_id=%s session_id=%s email=%s",
        capteur_id,
        getattr(current_user, "db_id", None),
        getattr(current_user, "id", None),
        getattr(current_user, "email", None),
    )
    return jsonify({"message": "Capteur désactivé."})
