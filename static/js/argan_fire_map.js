/**
 * Argan-Fire Watch — carte + vent (Chergui) + propagation.
 * Données : script #page-data JSON (center, zoom, windDeg, spreadDeg, sensors, fireOrigin)
 */
(function () {
  const mapEl = document.getElementById("forest-map");
  if (!mapEl || typeof L === "undefined") return;

  const dataEl = document.getElementById("page-data");
  let cfg = {
    center: [30.4278, -9.5981],
    zoom: 11,
    windDeg: 75,
    spreadDeg: null,
    fireOrigin: [30.42, -9.61],
    sensors: [
      { id: "C1", lat: 30.435, lng: -9.59, tempC: 38 },
      { id: "C2", lat: 30.418, lng: -9.605, tempC: 42 },
      { id: "C3", lat: 30.428, lng: -9.62, tempC: 35 },
    ],
  };

  if (dataEl && dataEl.textContent.trim()) {
    try {
      cfg = { ...cfg, ...JSON.parse(dataEl.textContent) };
    } catch (e) {
      console.warn("page-data JSON invalide, valeurs par défaut utilisées", e);
    }
  }

  if (cfg.spreadDeg == null) cfg.spreadDeg = cfg.windDeg;

  const map = L.map("forest-map", { scrollWheelZoom: true }).setView(cfg.center, cfg.zoom);

  L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {
    maxZoom: 17,
    attribution:
      '© <a href="https://www.openstreetmap.org/copyright">OSM</a>, © <a href="https://opentopomap.org">OpenTopoMap</a>',
  }).addTo(map);

  function degToRad(d) {
    return (d * Math.PI) / 180;
  }

  function destination(lat, lng, bearingDeg, distanceKm) {
    const R = 6371;
    const br = degToRad(bearingDeg);
    const φ1 = degToRad(lat);
    const λ1 = degToRad(lng);
    const δ = distanceKm / R;
    const φ2 = Math.asin(
      Math.sin(φ1) * Math.cos(δ) + Math.cos(φ1) * Math.sin(δ) * Math.cos(br)
    );
    const λ2 =
      λ1 +
      Math.atan2(
        Math.sin(br) * Math.sin(δ) * Math.cos(φ1),
        Math.cos(δ) - Math.sin(φ1) * Math.sin(φ2)
      );
    return [(φ2 * 180) / Math.PI, (λ2 * 180) / Math.PI];
  }

  const origin = cfg.fireOrigin || cfg.center;
  const lenKm = 2.2;

  const windEnd = destination(origin[0], origin[1], cfg.windDeg, lenKm);
  const fireEnd = destination(origin[0], origin[1], cfg.spreadDeg, lenKm * 1.1);

  L.polyline([origin, windEnd], {
    color: "#5eb3e8",
    weight: 4,
    opacity: 0.95,
  })
    .bindTooltip("Vent (Chergui) — " + cfg.windDeg + "°", { sticky: true, className: "afw-tip" })
    .addTo(map);

  L.polyline([origin, fireEnd], {
    color: "#e85d3b",
    weight: 5,
    opacity: 0.95,
    dashArray: "10, 8",
  })
    .bindTooltip("Propagation estimée — " + Math.round(cfg.spreadDeg) + "°", {
      sticky: true,
      className: "afw-tip",
    })
    .addTo(map);

  L.circleMarker(origin, {
    radius: 10,
    color: "#e85d3b",
    fillColor: "#ff7a5c",
    fillOpacity: 0.88,
    weight: 2,
  })
    .bindPopup("<strong>Foyer / coopérative</strong><br>Point de référence pour la propagation.")
    .addTo(map);

  (cfg.sensors || []).forEach(function (s) {
    const hot = s.tempC > 50;
    L.circleMarker([s.lat, s.lng], {
      radius: hot ? 12 : 7,
      color: hot ? "#e01b24" : "#f4a261",
      fillColor: hot ? "#ff5c64" : "#f4a261",
      fillOpacity: 0.92,
      weight: 2,
    })
      .bindPopup(
        "<strong>" +
          (s.id || "Capteur") +
          "</strong><br>" +
          s.tempC +
          " °C" +
          (hot ? "<br><span style='color:#ffb4b8;font-weight:600'>Seuil pompiers dépassé</span>" : "")
      )
      .addTo(map);
  });

  const bounds = L.latLngBounds([origin, windEnd, fireEnd]);
  (cfg.sensors || []).forEach(function (s) {
    bounds.extend([s.lat, s.lng]);
  });
  map.fitBounds(bounds.pad(0.15));
})();
