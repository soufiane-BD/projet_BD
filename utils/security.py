"""Utilitaires de sécurité : journalisation, validation, garde-corps JSON."""
import logging
import re
import time
from functools import wraps

from flask import jsonify, request
from flask_login import current_user

logger = logging.getLogger("argan_security")

_CAPTEUR_NOM_RE = re.compile(r"^[a-zA-Z0-9\s\-_\.]{1,100}$")
_PASSWORD_STRONG_RE = re.compile(
    r"^(?=.{8,})(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).*$"
)

ALLOWED_ORDER_FIELDS = frozenset({"nom", "id", "created_at", "localisation"})
MAX_JSON_BODY = 10_000

ALERTE_NIVEAU_API_TO_INTERNAL = {
    "faible": "modéré",
    "moyen": "modéré",
    "critique": "élevé",
}


def log_security_event(message: str, *args) -> None:
    logger.warning(message, *args)


def validate_capteur_nom(nom: str) -> tuple[bool, str]:
    s = (nom or "").strip()
    if not s:
        return False, ""
    if not _CAPTEUR_NOM_RE.match(s):
        log_security_event("Validation capteur nom échouée")
        return False, ""
    return True, s


def validate_password_strength(password: str) -> bool:
    if not password or not _PASSWORD_STRONG_RE.match(password):
        log_security_event("Mot de passe trop faible rejeté")
        return False
    return True


def normalize_order_field(order: str | None) -> str:
    o = (order or "id").strip()
    if o not in ALLOWED_ORDER_FIELDS:
        return "id"
    return o


def api_json_body_too_large() -> bool:
    cl = request.content_length
    if cl is not None and cl > MAX_JSON_BODY:
        return True
    return False


def api_login_required(fn):
    """Exige une session valide ; réponse JSON 401 pour les routes API."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            log_security_event("Accès API refusé : non authentifié %s", request.path)
            return jsonify({"error": "Authentification requise"}), 401
        return fn(*args, **kwargs)

    return wrapper


def require_admin_json(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentification requise"}), 401
        if getattr(current_user, "role", None) != "admin":
            log_security_event("Action admin refusée pour %s", getattr(current_user, "id", "?"))
            return jsonify({"error": "Accès refusé"}), 403
        return fn(*args, **kwargs)

    return wrapper


class LoginFailureTracker:
    """Suivi des échecs de connexion par adresse IP (mémoire)."""

    def __init__(self) -> None:
        self._failures: dict[str, dict] = {}

    def is_locked(self, ip: str) -> bool:
        rec = self._failures.get(ip)
        if not rec:
            return False
        until = rec.get("locked_until")
        if until and time.time() < until:
            return True
        if until and time.time() >= until:
            self._failures.pop(ip, None)
        return False

    def register_failure(self, ip: str) -> None:
        rec = self._failures.setdefault(ip, {"consecutive": 0, "locked_until": None})
        rec["consecutive"] = rec.get("consecutive", 0) + 1
        if rec["consecutive"] >= 5:
            rec["locked_until"] = time.time() + 15 * 60
            rec["consecutive"] = 0
            log_security_event("Verrouillage 15 min après échecs pour IP %s", ip)

    def reset(self, ip: str) -> None:
        self._failures.pop(ip, None)

    def get_consecutive(self, ip: str) -> int:
        return self._failures.get(ip, {}).get("consecutive", 0)


login_failure_tracker = LoginFailureTracker()


def progressive_delay_on_failure(consecutive: int) -> None:
    """Délai croissant après échec (proportionnel au nombre d'échecs consécutifs)."""
    delay = min(0.3 * max(consecutive, 0), 3.0)
    if delay > 0:
        time.sleep(delay)
