/**
 * Simulation démo — probabilité de propagation à partir du vent et de l'humidité.
 * Remplacez par un appel API vers votre procédure stockée en production.
 */
(function () {
  const windKmh = document.getElementById("sim-wind-kmh");
  const windDeg = document.getElementById("sim-wind-deg");
  const humidity = document.getElementById("sim-humidity");
  const tempC = document.getElementById("sim-temp");
  const outKmh = document.getElementById("out-wind-kmh");
  const outDeg = document.getElementById("out-wind-deg");
  const outHum = document.getElementById("out-humidity");
  const outTemp = document.getElementById("out-temp");
  const windRose = document.getElementById("wind-rose");
  const fill = document.getElementById("sim-gauge-fill");
  const probVal = document.getElementById("sim-prob-value");
  const spreadDeg = document.getElementById("sim-spread-deg");
  const impactTemp = document.getElementById("impact-temp");
  const impactWind = document.getElementById("impact-wind");
  const impactHum = document.getElementById("impact-hum");
  const indexEl = document.getElementById("sim-index");
  const btn = document.getElementById("sim-recalc");

  if (!windKmh || !humidity || !tempC || !fill || !probVal) return;

  function roseLabel(deg) {
    const d = ((deg % 360) + 360) % 360;
    const dirs = [
      "N",
      "NNE",
      "NE",
      "ENE",
      "E",
      "ESE",
      "SE",
      "SSE",
      "S",
      "SSW",
      "SW",
      "WSW",
      "W",
      "WNW",
      "NW",
      "NNW",
    ];
    const idx = Math.round(d / 22.5) % 16;
    return dirs[idx] + " (" + Math.round(d) + "°)";
  }

  function computeProbability(wKmh, wDeg, hum, tC) {
    const dryness = (100 - hum) / 100;
    const windFactor = Math.min(1, wKmh / 70);
    const tempFactor = Math.min(1, tC / 55);
    
    const raw = (tempFactor * 0.45) + (windFactor * 0.35) + (dryness * 0.20);
    const p = Math.min(0.98, Math.max(0.02, raw));
    const spread = (wDeg + dryness * 12) % 360;
    const combined = (dryness * windFactor).toFixed(2);
    return { p, spread, combined, dryness, windFactor, tempFactor };
  }

  function updateImpact(el, value, thresholds) {
    let label = thresholds[0].text;
    let color = "rgba(255,255,255,0.2)";
    
    for (const t of thresholds) {
      if (value >= t.min) {
        label = t.text;
        color = t.color;
      }
    }
    el.textContent = label;
    el.style.borderColor = color;
    el.style.color = color;
  }

  function render() {
    const wKmh = Number(windKmh.value);
    const wDeg = Number(windDeg.value);
    const hum = Number(humidity.value);
    const tC = Number(tempC.value);

    outKmh.textContent = String(wKmh);
    outDeg.textContent = wDeg + "°";
    outHum.textContent = String(hum);
    outTemp.textContent = String(tC);
    if (windRose) windRose.textContent = roseLabel(wDeg);

    const { p, spread, combined, dryness, windFactor, tempFactor } = computeProbability(wKmh, wDeg, hum, tC);
    
    updateImpact(impactTemp, tC, [
      { min: 0, text: "Stable", color: "#70a1ff" },
      { min: 30, text: "Chaleur intense", color: "#ffa502" },
      { min: 45, text: "Critique", color: "#ff4757" }
    ]);
    
    updateImpact(impactWind, wKmh, [
      { min: 0, text: "Faible", color: "#70a1ff" },
      { min: 25, text: "Poussée active", color: "#ffa502" },
      { min: 50, text: "Chergui violent", color: "#ff4757" }
    ]);

    updateImpact(impactHum, 100 - hum, [
      { min: 0, text: "Normal", color: "#70a1ff" },
      { min: 60, text: "Sec", color: "#ffa502" },
      { min: 85, text: "Aridité extrême", color: "#ff4757" }
    ]);

    const pct = Math.round(p * 100);
    fill.style.width = pct + "%";
    probVal.textContent = pct + " %";
    spreadDeg.textContent = roseLabel(spread);
    indexEl.textContent = combined + " (normalisé)";
  }

  [windKmh, windDeg, humidity, tempC].forEach(function (el) {
    el.addEventListener("input", render);
  });
  if (btn) btn.addEventListener("click", render);

  render();
})();
