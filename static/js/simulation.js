/**
 * Simulation démo — probabilité de propagation à partir du vent et de l'humidité.
 * Remplacez par un appel API vers votre procédure stockée en production.
 */
(function () {
  const windKmh = document.getElementById("sim-wind-kmh");
  const windDeg = document.getElementById("sim-wind-deg");
  const humidity = document.getElementById("sim-humidity");
  const outKmh = document.getElementById("out-wind-kmh");
  const outDeg = document.getElementById("out-wind-deg");
  const outHum = document.getElementById("out-humidity");
  const windRose = document.getElementById("wind-rose");
  const fill = document.getElementById("sim-gauge-fill");
  const probVal = document.getElementById("sim-prob-value");
  const spreadDeg = document.getElementById("sim-spread-deg");
  const indexEl = document.getElementById("sim-index");
  const btn = document.getElementById("sim-recalc");

  if (!windKmh || !humidity || !fill || !probVal) return;

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

  /** Formule démo déterministe (0–1), à aligner avec votre procédure SQL. */
  function computeProbability(wKmh, wDeg, hum) {
    const dryness = (100 - hum) / 100;
    const windFactor = Math.min(1, wKmh / 70);
    const raw = 0.08 + dryness * 0.52 + windFactor * 0.38;
    const p = Math.min(0.97, Math.max(0.03, raw));
    const spread = (wDeg + dryness * 12) % 360;
    const combined = (dryness * windFactor).toFixed(2);
    return { p, spread, combined };
  }

  function render() {
    const wKmh = Number(windKmh.value);
    const wDeg = Number(windDeg.value);
    const hum = Number(humidity.value);

    outKmh.textContent = String(wKmh);
    outDeg.textContent = wDeg + "°";
    outHum.textContent = String(hum);
    if (windRose) windRose.textContent = roseLabel(wDeg);

    const { p, spread, combined } = computeProbability(wKmh, wDeg, hum);
    const pct = Math.round(p * 100);
    fill.style.width = pct + "%";
    probVal.textContent = pct + " %";
    spreadDeg.textContent = roseLabel(spread);
    indexEl.textContent = combined + " (normalisé)";
  }

  [windKmh, windDeg, humidity].forEach(function (el) {
    el.addEventListener("input", render);
  });
  if (btn) btn.addEventListener("click", render);

  render();
})();
