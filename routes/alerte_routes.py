from flask import Blueprint, jsonify, request
from flask_login import current_user

from extensions import limiter
from services.alerte_service import add_alerte, delete_alerte, get_all_alertes, get_alerte
from utils.database import get_db_connection
from utils.security import ALERTE_NIVEAU_API_TO_INTERNAL, api_json_body_too_large, api_login_required
from utils.security import log_security_event

alerte_bp = Blueprint("alerte_bp", __name__)

_ALLOWED_ALERTE_KEYS = frozenset({"mesure_id", "niveau", "zone", "message"})


@alerte_bp.before_request
def _limit_json_payload():
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and api_json_body_too_large():
        return jsonify({"error": "Requête trop volumineuse"}), 413


def _mesure_exists(mesure_id: int) -> bool:
    conn = get_db_connection()
    row = conn.execute("SELECT 1 FROM mesure WHERE id = ?", (mesure_id,)).fetchone()
    conn.close()
    return row is not None


@alerte_bp.route("/alertes", methods=["GET"])
@api_login_required
def list_alertes():
    """Return all alertes stored in the database."""
    alertes = get_all_alertes()
    return jsonify(alertes)


@alerte_bp.route("/alertes", methods=["POST"])
@limiter.limit("30 per minute")
@api_login_required
def create_alerte():
    """Create an alert manually from JSON (champs whitelistés, validation stricte)."""
    data = request.get_json(force=True, silent=True) or {}
    if any(k not in _ALLOWED_ALERTE_KEYS for k in data.keys()):
        log_security_event("POST alerte : champs non autorisés refusés")
        return jsonify({"error": "Données invalides."}), 400

    mesure_id = data.get("mesure_id")
    niveau = (data.get("niveau") or "").strip()
    zone = (data.get("zone") or "").strip()
    message = (data.get("message") or "").strip()

    if mesure_id is None:
        return jsonify({"error": "Données invalides."}), 400
    try:
        mid = int(mesure_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Données invalides."}), 400

    if niveau not in ALERTE_NIVEAU_API_TO_INTERNAL:
        return jsonify({"error": "Données invalides."}), 400
    if len(zone) > 100 or len(message) > 500:
        return jsonify({"error": "Données invalides."}), 400

    if not _mesure_exists(mid):
        return jsonify({"error": "Données invalides."}), 400

    internal = ALERTE_NIVEAU_API_TO_INTERNAL[niveau]
    full_message = f"[{zone}] {message}" if zone else message
    if not full_message.strip():
        full_message = "Alerte créée manuellement."

    alerte_id = add_alerte(mid, internal, full_message, created_by_user_ref=current_user.id)
    return jsonify({"id": alerte_id, "mesure_id": mid, "niveau": niveau}), 201


def _user_can_delete_alerte(alerte_row: dict) -> bool:
    if getattr(current_user, "role", None) == "admin":
        return True
    ref = alerte_row.get("created_by_user_ref")
    if ref is None:
        return False
    return ref == current_user.id


@alerte_bp.route("/alertes/<int:alerte_id>", methods=["DELETE"])
@api_login_required
def remove_alerte(alerte_id):
    """Delete an alert if owner or admin."""
    row = get_alerte(alerte_id)
    if not row:
        return jsonify({"error": "Ressource introuvable."}), 404
    if not _user_can_delete_alerte(row):
        log_security_event("Suppression alerte refusée id=%s user=%s", alerte_id, current_user.id)
        return jsonify({"error": "Accès refusé"}), 403

    deleted = delete_alerte(alerte_id)
    if not deleted:
        return jsonify({"error": "Ressource introuvable."}), 404
    return jsonify({"message": "Alerte supprimée."})
