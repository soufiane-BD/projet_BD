import datetime
from services.alerte_service import add_alerte

def simulate_propagation(temperature, humidity, wind_speed, wind_deg=None, mesure_id=None):
    """
    Calcule le risque de propagation d'un incendie.
    Logique : Température haute + Vent fort + Humidité basse = Danger.
    """
    # Formule : score = (température * 0.5) + (vent * 0.3) - (humidité * 0.2)
    score = (temperature * 0.5) + (wind_speed * 0.3) - (humidity * 0.2)
    
    if score >= 25:
        risk_level = "High propagation"
    elif score >= 15:
        risk_level = "Medium propagation"
    else:
        risk_level = "Low propagation"
    result = {
        "score": round(score, 2),
        "risk_level": risk_level,
        "details": {
            "temp_impact": temperature * 0.5,
            "wind_impact": wind_speed * 0.3,
            "humidity_penalty": humidity * 0.2
        }
    }
    return result