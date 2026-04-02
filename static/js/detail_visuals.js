const EXPLOR_TILE_URL =
  "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png";
const EXPLOR_TILE_SUBDOMAINS = "abcd";

function generateDivIcon(entityId, entityType) {
  const typeClass = (entityType || "route").replace(/\s+/g, "-").toLowerCase();
  return L.divIcon({
    html: '<span class="explor-map-marker-pin"></span>',
    className: `explor-map-marker explor-map-marker-${typeClass} marker-color-${entityId}`,
    iconAnchor: [9, 9],
    iconSize: [18, 18],
  });
}

function elevationChartDetailsPage(id, elevationArray) {
  const container = document.getElementById(id);
  if (!container || !Array.isArray(elevationArray) || elevationArray.length < 2) {
    return;
  }

  const width = Math.max(container.clientWidth || 760, 320);
  const height = 250;
  const padding = { top: 16, right: 14, bottom: 18, left: 14 };
  const usableWidth = width - padding.left - padding.right;
  const usableHeight = height - padding.top - padding.bottom;
  const maxValue = Math.max(...elevationArray);
  const minValue = Math.min(...elevationArray);
  const paddedMin = minValue - 0.05 * (maxValue - minValue || 1);

  const points = elevationArray.map((value, index) => {
    const x = padding.left + (index / Math.max(elevationArray.length - 1, 1)) * usableWidth;
    const y =
      padding.top +
      (1 - (value - paddedMin) / Math.max(maxValue - paddedMin, 1)) * usableHeight;
    return { value, x, y };
  });

  const linePath = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");
  const baselineY = height - padding.bottom;
  const areaPath = `${linePath} L ${points[points.length - 1].x.toFixed(2)} ${baselineY.toFixed(
    2,
  )} L ${points[0].x.toFixed(2)} ${baselineY.toFixed(2)} Z`;

  const sampleStep = Math.max(1, Math.floor(points.length / 10));
  const sampleButtons = points
    .filter((_, index) => index % sampleStep === 0 || index === points.length - 1)
    .map(
      (point, index) =>
        `<button class="visual-sample-chip" type="button" data-elevation-chip="${index}">${point.value}</button>`,
    )
    .join("");

  container.innerHTML = `
    <div class="elevation-chart-shell">
      <svg viewBox="0 0 ${width} ${height}" class="elevation-chart-svg" role="img" aria-label="Elevation profile">
        <defs>
          <linearGradient id="${id}-area" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="rgba(113, 184, 255, 0.62)"></stop>
            <stop offset="100%" stop-color="rgba(113, 184, 255, 0.08)"></stop>
          </linearGradient>
        </defs>
        <path class="elevation-chart-area" d="${areaPath}" fill="url(#${id}-area)"></path>
        <path class="elevation-chart-line" d="${linePath}"></path>
        ${points
          .map(
            (point, index) =>
              `<circle class="elevation-chart-hit" cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(
                2,
              )}" r="8" data-elevation-point="${index}"></circle>`,
          )
          .join("")}
        <circle class="elevation-chart-active" r="6" style="display:none"></circle>
      </svg>
      <div class="elevation-chart-readout">
        <span class="detail-story-label">Elevation</span>
        <span class="detail-story-value" data-elevation-value>${maxValue}</span>
      </div>
      <div class="visual-sample-rail">${sampleButtons}</div>
    </div>
  `;

  const activeMarker = container.querySelector(".elevation-chart-active");
  const readout = container.querySelector("[data-elevation-value]");
  const chips = Array.from(container.querySelectorAll("[data-elevation-chip]"));
  const hits = Array.from(container.querySelectorAll("[data-elevation-point]"));

  function setActive(index) {
    const point = points[index];
    if (!point || !activeMarker || !readout) {
      return;
    }
    activeMarker.setAttribute("cx", point.x.toFixed(2));
    activeMarker.setAttribute("cy", point.y.toFixed(2));
    activeMarker.style.display = "block";
    readout.textContent = `${point.value}`;
  }

  hits.forEach((hit, index) => {
    hit.addEventListener("mouseenter", () => setActive(index));
  });

  chips.forEach((chip, index) => {
    const pointIndex = Math.min(index * sampleStep, points.length - 1);
    chip.addEventListener("mouseenter", () => {
      chips.forEach((item) => item.classList.remove("visual-sample-chip-active"));
      chip.classList.add("visual-sample-chip-active");
      setActive(pointIndex);
    });
    chip.addEventListener("mouseleave", () => {
      chip.classList.remove("visual-sample-chip-active");
    });
  });

  setActive(points.length - 1);
}

function initLeafletVisual(container) {
  const configNode = document.querySelector(`[data-map-config][data-map-target="${container.id}"]`);
  if (!configNode) {
    return;
  }
  const config = JSON.parse(configNode.textContent);
  if (!config.layers || config.layers.length === 0) {
    return;
  }

  const map = L.map(container, {
    attributionControl: false,
    scrollWheelZoom: false,
  }).setView([0, 0], 9);

  L.tileLayer(EXPLOR_TILE_URL, { subdomains: EXPLOR_TILE_SUBDOMAINS }).addTo(map);

  let currentPolyline = null;
  let currentMarker = null;

  function polylineParts(latlngs) {
    if (!Array.isArray(latlngs) || latlngs.length === 0) {
      return [];
    }
    if (Array.isArray(latlngs[0]) && typeof latlngs[0][0] === "number") {
      return [latlngs];
    }
    return latlngs.filter(
      (part) =>
        Array.isArray(part) &&
        part.length > 0 &&
        Array.isArray(part[0]) &&
        typeof part[0][0] === "number",
    );
  }

  function layerHasVisibleDistance(layer) {
    const parts = polylineParts(layer?.latlngs);
    const flatPoints = parts.flat();
    if (flatPoints.length < 2) {
      return false;
    }
    const uniquePoints = new Set(
      flatPoints.map((point) =>
        Array.isArray(point) && point.length >= 2
          ? `${Number(point[0]).toFixed(5)},${Number(point[1]).toFixed(5)}`
          : "",
      ),
    );
    return uniquePoints.size > 1;
  }

  function defaultLayerIndex() {
    const firstVisibleIndex = config.layers.findIndex((layer) => layerHasVisibleDistance(layer));
    return firstVisibleIndex >= 0 ? firstVisibleIndex : 0;
  }

  let activeIndex = defaultLayerIndex();
  const buttons = Array.from(
    document.querySelectorAll(`[data-map-target="${container.id}"][data-map-layer-button]`),
  );

  function setActiveButton(index) {
    buttons.forEach((button, buttonIndex) => {
      button.classList.toggle("visual-toggle-active", buttonIndex === index);
    });
  }

  function showLayer(index) {
    if (currentPolyline && map.hasLayer(currentPolyline)) {
      map.removeLayer(currentPolyline);
    }
    if (currentMarker && map.hasLayer(currentMarker)) {
      map.removeLayer(currentMarker);
    }
    currentPolyline = null;
    currentMarker = null;

    const layer = config.layers[index];
    if (layerHasVisibleDistance(layer)) {
      currentPolyline = L.polyline(polylineParts(layer.latlngs), {
        color: index === 0 ? "#ff5a1f" : "#71b8ff",
        opacity: 0.96,
        weight: 6,
        lineCap: "round",
        lineJoin: "round",
      }).addTo(map);
      map.fitBounds(currentPolyline.getBounds(), { padding: [20, 20] });
    }

    if (config.marker && Array.isArray(config.marker.latlng)) {
      currentMarker = L.marker(config.marker.latlng, {
        icon: generateDivIcon(config.marker.entity_id, config.marker.entity_type),
      }).addTo(map);
      if (!currentPolyline) {
        map.setView(config.marker.latlng, 11);
      }
    }
    activeIndex = index;
    setActiveButton(index);
    window.requestAnimationFrame(() => {
      map.invalidateSize();
      if (currentPolyline) {
        map.fitBounds(currentPolyline.getBounds(), { padding: [20, 20] });
      }
    });
  }

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextIndex = Number(button.dataset.layerIndex || 0);
      showLayer(nextIndex);
    });
  });

  showLayer(activeIndex);
  window.setTimeout(() => showLayer(activeIndex), 60);
}

function initElevationVisual(container) {
  const configNode = container.parentElement?.querySelector("[data-elevation-config]");
  if (!configNode) {
    return;
  }
  const config = JSON.parse(configNode.textContent);
  if (!Array.isArray(config.elevations) || config.elevations.length < 2) {
    return;
  }
  elevationChartDetailsPage(container.id, config.elevations);
}

function bootDetailVisuals(attempt = 0) {
  const needsLeaflet = document.querySelector("[data-leaflet-visual]") !== null;
  const leafletReady = !needsLeaflet || typeof window.L !== "undefined";

  if (!leafletReady) {
    if (attempt < 40) {
      window.setTimeout(() => bootDetailVisuals(attempt + 1), 150);
    }
    return;
  }

  document.querySelectorAll("[data-leaflet-visual]").forEach((container) => {
    initLeafletVisual(container);
  });
  document.querySelectorAll("[data-elevation-visual]").forEach((container) => {
    initElevationVisual(container);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  bootDetailVisuals();
});
