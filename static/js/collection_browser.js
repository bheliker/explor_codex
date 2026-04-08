const EXPLOR_BROWSER_TILE_URL =
  "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png";
const EXPLOR_BROWSER_TILE_SUBDOMAINS = "abcd";

function collectionBrowser(config) {
  return {
    areaQuery: "",
    areaResults: [],
    abortController: null,
    areaAbortController: null,
    clubId: "",
    collectionLabel: config.collectionLabel,
    eventfulOnly: "false",
    favoritesOnly: false,
    filterOptions: config.filterOptions || {},
    focus: config.focus,
    items: [...(config.items || [])],
    limit: config.limit || 30,
    loading: false,
    map: null,
    mapOnly: true,
    markerIndex: new Map(),
    moveTimer: null,
    offset: config.offset || 0,
    query: "",
    ready: false,
    selectedItemId: null,
    sortKey: "closest",
    suppressMapMoveFetch: false,
    terrain: "",
    totalMatching: config.totalMatching || (config.items || []).length,
    view: "grid",
    world: config.bounds,

    init() {
      if (this.ready) {
        return;
      }
      this.initMap();
      this.renderMapItems();
      this.ready = true;
      this.fetchItems();
    },

    initMap() {
      if (!this.$refs.map || typeof L === "undefined") {
        return;
      }

      if (this.map) {
        return;
      }

      const existingMap = this.$refs.map.__explorLeafletMap;
      if (existingMap && typeof existingMap.remove === "function") {
        existingMap.remove();
      }

      if (this.$refs.map._leaflet_id) {
        this.$refs.map._leaflet_id = null;
      }

      this.map = L.map(this.$refs.map, {
        attributionControl: false,
        scrollWheelZoom: true,
      });
      this.$refs.map.__explorLeafletMap = this.map;

      L.tileLayer(EXPLOR_BROWSER_TILE_URL, {
        subdomains: EXPLOR_BROWSER_TILE_SUBDOMAINS,
        maxZoom: 18,
      }).addTo(this.map);

      this.lineLayer = L.featureGroup().addTo(this.map);
      this.markerLayer = L.featureGroup().addTo(this.map);

      const southWest = [this.world.minLat, this.world.minLng];
      const northEast = [this.world.maxLat, this.world.maxLng];
      this.map.fitBounds([southWest, northEast], { padding: [24, 24] });

      if (this.focus) {
        this.map.setView([this.focus.lat, this.focus.lng], 10);
      }

      this.map.on("moveend zoomend", () => {
        if (this.suppressMapMoveFetch) {
          this.suppressMapMoveFetch = false;
          return;
        }
        window.clearTimeout(this.moveTimer);
        this.moveTimer = window.setTimeout(() => this.fetchItems(), 180);
      });
    },

    visibleItems() {
      return this.items;
    },

    resultsLabel() {
      const start = this.totalMatching === 0 ? 0 : this.offset + 1;
      const end = this.offset + this.items.length;
      return `${start}-${end} loaded`;
    },

    focusLabel() {
      return this.mapOnly
        ? "Map area is backed by a server query."
        : `Showing the best ${this.limit} matches across the full dataset.`;
    },

    totalLabel() {
      return `${this.items.length} of ${this.totalMatching} matching ${this.collectionLabel.toLowerCase()} loaded`;
    },

    canPageBack() {
      return this.offset > 0;
    },

    canPageForward() {
      return this.offset + this.items.length < this.totalMatching;
    },

    previousPage() {
      if (!this.canPageBack()) {
        return;
      }
      this.offset = Math.max(0, this.offset - this.limit);
      this.fetchItems();
    },

    nextPage() {
      if (!this.canPageForward()) {
        return;
      }
      this.offset += this.limit;
      this.fetchItems();
    },

    collectionSingular() {
      return this.collectionLabel.endsWith("s")
        ? this.collectionLabel.slice(0, -1)
        : this.collectionLabel;
    },

    hasFocusPoint() {
      return Boolean(this.focus || this.map);
    },

    viewportLabel() {
      if (!this.map) {
        return "Map loading";
      }
      const bounds = this.map.getBounds();
      const latSpan = (bounds.getNorth() - bounds.getSouth()).toFixed(2);
      const lngSpan = (bounds.getEast() - bounds.getWest()).toFixed(2);
      return `Viewport ${latSpan}° x ${lngSpan}°`;
    },

    resetViewport() {
      if (!this.map) {
        return;
      }
      this.offset = 0;
      this.suppressMapMoveFetch = true;
      const southWest = [this.world.minLat, this.world.minLng];
      const northEast = [this.world.maxLat, this.world.maxLng];
      this.map.fitBounds([southWest, northEast], { padding: [24, 24] });
      this.fetchItems();
    },

    searchFullDatabase() {
      this.mapOnly = false;
      this.offset = 0;
      this.fetchItems();
    },

    searchMapArea() {
      this.mapOnly = true;
      this.offset = 0;
      this.fetchItems();
    },

    panToItem(item) {
      if (!this.map || !item.center) {
        return;
      }
      this.selectedItemId = item.id;
      this.suppressMapMoveFetch = true;
      this.map.setView([item.center.lat, item.center.lng], Math.max(this.map.getZoom(), 12));
      const marker = this.markerIndex.get(item.id);
      if (marker) {
        marker.openPopup();
      }
    },

    fitLoadedResults() {
      if (!this.map || !this.items.length) {
        return;
      }
      const bounds = [];
      this.items.forEach((item) => {
        if (item.center) {
          bounds.push([item.center.lat, item.center.lng]);
        }
      });
      if (bounds.length) {
        this.suppressMapMoveFetch = true;
        this.map.fitBounds(bounds, { padding: [30, 30] });
        this.fetchItems();
      }
    },

    scheduleFetch() {
      window.clearTimeout(this.fetchTimer);
      this.fetchTimer = window.setTimeout(() => {
        if (this.query.trim()) {
          this.mapOnly = false;
        }
        this.offset = 0;
        this.fetchItems();
      }, 180);
    },

    scheduleAreaSearch() {
      window.clearTimeout(this.areaTimer);
      this.areaTimer = window.setTimeout(() => this.searchAreas(), 180);
    },

    async searchAreas() {
      const query = this.areaQuery.trim();
      if (query.length < 2) {
        this.areaResults = [];
        return;
      }

      if (this.areaAbortController) {
        this.areaAbortController.abort();
      }

      this.areaAbortController = new AbortController();

      try {
        const response = await fetch(
          `/api/browser/areas?q=${encodeURIComponent(query)}`,
          {
            headers: { Accept: "application/json" },
            signal: this.areaAbortController.signal,
          },
        );
        if (!response.ok) {
          throw new Error(`Area search failed with ${response.status}`);
        }
        const payload = await response.json();
        this.areaResults = Array.isArray(payload.items) ? payload.items : [];
      } catch (error) {
        if (error.name !== "AbortError") {
          console.error("area search failed", error);
        }
        this.areaResults = [];
      }
    },

    jumpToFirstAreaResult() {
      if (this.areaResults.length) {
        this.jumpToArea(this.areaResults[0]);
      }
    },

    jumpToArea(area) {
      if (!this.map) {
        return;
      }
      this.mapOnly = true;
      this.offset = 0;
      this.suppressMapMoveFetch = true;
      this.map.setView([area.lat, area.lng], 9);
      this.fetchItems();
    },

    async fetchItems() {
      const apiUrl = config.apiUrl;
      if (!apiUrl) {
        return;
      }

      if (this.abortController) {
        this.abortController.abort();
      }

      this.abortController = new AbortController();
      this.loading = true;

      try {
        const params = new URLSearchParams();
        params.set("limit", String(this.limit));
        params.set("offset", String(this.offset));
        params.set("sort", this.sortKey);
        if (this.query) {
          params.set("q", this.query);
        }
        if (this.clubId) {
          params.set("club_id", this.clubId);
        }
        if (this.terrain) {
          params.set("terrain", this.terrain);
        }
        if (this.favoritesOnly) {
          params.set("favorites_only", "true");
        }
        if (this.eventfulOnly === "true") {
          params.set("eventful_only", "true");
        }
        if (this.map) {
          const center = this.map.getCenter();
          params.set("focus_lat", String(center.lat));
          params.set("focus_lng", String(center.lng));
          if (this.mapOnly) {
            const bounds = this.map.getBounds();
            params.set("min_lat", String(bounds.getSouth()));
            params.set("max_lat", String(bounds.getNorth()));
            params.set("min_lng", String(bounds.getWest()));
            params.set("max_lng", String(bounds.getEast()));
          }
        }

        const response = await fetch(`${apiUrl}?${params.toString()}`, {
          headers: { Accept: "application/json" },
          signal: this.abortController.signal,
        });
        if (!response.ok) {
          throw new Error(`Request failed with ${response.status}`);
        }
        const payload = await response.json();
        this.items = Array.isArray(payload.items) ? payload.items : [];
        this.offset =
          typeof payload.offset === "number" ? payload.offset : this.offset;
        this.totalMatching =
          typeof payload.total_matching === "number"
            ? payload.total_matching
            : this.items.length;
        if (!this.items.some((item) => item.id === this.selectedItemId)) {
          this.selectedItemId = null;
        }
        this.renderMapItems();
      } catch (error) {
        if (error.name !== "AbortError") {
          console.error("collection browser fetch failed", error);
        }
      } finally {
        this.loading = false;
      }
    },

    renderMapItems() {
      if (!this.map || !this.lineLayer || !this.markerLayer) {
        return;
      }

      this.lineLayer.clearLayers();
      this.markerLayer.clearLayers();
      this.markerIndex.clear();

      this.items.forEach((item) => {
        if (item.geometry?.coordinates?.length) {
          const latlngs = item.geometry.coordinates.map((coordinate) => [
            coordinate[1],
            coordinate[0],
          ]);
          if (latlngs.length > 1) {
            L.polyline(latlngs, {
              color: item.favorite ? "#ff9f43" : "#71b8ff",
              opacity: 0.9,
              weight: item.favorite ? 5 : 4,
            }).addTo(this.lineLayer);
          }
        }

        if (item.center) {
          const marker = L.marker([item.center.lat, item.center.lng], {
            icon: this.markerIcon(item),
            title: item.title || "",
          }).addTo(this.markerLayer);
          marker.bindPopup(this.popupHtml(item), {
            autoPan: false,
            className: "browser-map-popup-shell",
          });
          marker.on("click", () => {
            this.selectedItemId = item.id;
          });
          this.markerIndex.set(item.id, marker);
        }
      });
    },

    markerIcon(item) {
      const markerClass = item.favorite
        ? "browser-map-marker browser-map-marker-favorite"
        : "browser-map-marker";
      return L.divIcon({
        className: markerClass,
        html: '<span class="browser-map-marker-pin"></span>',
        iconAnchor: [10, 10],
        iconSize: [20, 20],
      });
    },

    popupHtml(item) {
      const tags = Array.isArray(item.tags)
        ? item.tags
            .slice(0, 3)
            .map((tag) => `<span class="tag">${this.escapeHtml(tag)}</span>`)
            .join("")
        : "";
      const related = item.relatedPreview?.clubs?.length
        ? `Clubs: ${item.relatedPreview.clubs.join(", ")}`
        : item.relatedPreview?.routes?.length
          ? `Routes: ${item.relatedPreview.routes.join(", ")}`
          : "";
      const openLink = item.detailUrl
        ? `<a class="nav-link" href="${item.detailUrl}">Open record</a>`
        : "";
      return `
        <div class="browser-map-popup">
          <h3>${this.escapeHtml(item.title || "")}</h3>
          <div class="browser-map-popup-meta">${this.escapeHtml(item.metaLine || item.subtitle || "")}</div>
          <p>${this.escapeHtml(item.description || "")}</p>
          ${tags ? `<div class="browser-map-popup-tags">${tags}</div>` : ""}
          ${related ? `<p>${this.escapeHtml(related)}</p>` : ""}
          ${openLink}
        </div>
      `;
    },

    escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    },
  };
}

window.collectionBrowser = collectionBrowser;
