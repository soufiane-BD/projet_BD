"""Extensions Flask initialisées dans app (évite imports circulaires)."""
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter

csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[], storage_uri="memory://")
