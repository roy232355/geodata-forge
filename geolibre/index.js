/**
 * GeoData Forge: Synthetic Spatial Feature Generator Plugin for GeoLibre.
 * Outputs realistic, domain-correlated geometries and schema tables.
 */

// ============================================================================
// Mathematical Geometry Generators (Javascript equivalents)
// ============================================================================

class GeometryGenerator {
  static generateUniformPoints(bounds, count, random) {
    const [xmin, ymin, xmax, ymax] = bounds;
    const points = [];
    for (let i = 0; i < count; i++) {
      const x = xmin + random() * (xmax - xmin);
      const y = ymin + random() * (ymax - ymin);
      points.push([x, y]);
    }
    return points;
  }

  static generateClusteredPoints(bounds, count, random, numClusters = 4) {
    const [xmin, ymin, xmax, ymax] = bounds;
    const width = xmax - xmin;
    const height = ymax - ymin;
    const centers = [];
    for (let i = 0; i < numClusters; i++) {
      centers.push([
        xmin + width * 0.1 + random() * width * 0.8,
        ymin + height * 0.1 + random() * height * 0.8
      ]);
    }
    const points = [];
    const stdX = width * 0.05;
    const stdY = height * 0.05;
    
    // Gauss approximation
    const gauss = () => {
      let u = 0, v = 0;
      while(u === 0) u = random();
      while(v === 0) v = random();
      return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
    };

    for (let i = 0; i < count; i++) {
      const center = centers[Math.floor(random() * centers.length)];
      const x = center[0] + gauss() * stdX;
      const y = center[1] + gauss() * stdY;
      points.push([x, y]);
    }
    return points;
  }

  static generatePoissonDiscPoints(bounds, count, random, minSpacing) {
    const [xmin, ymin, xmax, ymax] = bounds;
    const width = xmax - xmin;
    const height = ymax - ymin;
    
    if (minSpacing <= 0 || minSpacing > Math.max(width, height)) {
      return this.generateUniformPoints(bounds, count, random);
    }

    const cellSize = minSpacing / Math.sqrt(2);
    const gridWidth = Math.ceil(width / cellSize);
    const gridHeight = Math.ceil(height / cellSize);
    const grid = {};
    const points = [];
    const activeList = [];

    const getGridCoords = (pt) => [
      Math.floor((pt[0] - xmin) / cellSize),
      Math.floor((pt[1] - ymin) / cellSize)
    ];

    const isValidCandidate = (pt) => {
      if (pt[0] < xmin || pt[0] > xmax || pt[1] < ymin || pt[1] > ymax) return false;
      const [gx, gy] = getGridCoords(pt);
      
      for (let nx = Math.max(0, gx - 2); nx <= Math.min(gridWidth - 1, gx + 2); nx++) {
        for (let ny = Math.max(0, gy - 2); ny <= Math.min(gridHeight - 1, gy + 2); ny++) {
          const idx = grid[`${nx},${ny}`];
          if (idx !== undefined) {
            const other = points[idx];
            const dist = Math.sqrt((pt[0] - other[0]) ** 2 + (pt[1] - other[1]) ** 2);
            if (dist < minSpacing) return false;
          }
        }
      }
      return true;
    };

    // First point
    let startPt = [xmin + random() * width, ymin + random() * height];
    points.push(startPt);
    activeList.push(0);
    const [sgx, sgy] = getGridCoords(startPt);
    grid[`${sgx},${sgy}`] = 0;

    let attempts = 0;
    const maxAttempts = count * 25;
    while (activeList.length > 0 && points.length < count && attempts < maxAttempts) {
      attempts++;
      const activeIdx = Math.floor(random() * activeList.length);
      const refPt = points[activeList[activeIdx]];
      let found = false;

      for (let i = 0; i < 30; i++) {
        const angle = random() * 2 * Math.PI;
        const radius = minSpacing + random() * minSpacing;
        const candidate = [
          refPt[0] + radius * Math.cos(angle),
          refPt[1] + radius * Math.sin(angle)
        ];

        if (isValidCandidate(candidate)) {
          const newIdx = points.length;
          points.push(candidate);
          activeList.push(newIdx);
          const [cgx, cgy] = getGridCoords(candidate);
          grid[`${cgx},${cgy}`] = newIdx;
          found = true;
          break;
        }
      }

      if (!found) {
        activeList.splice(activeIdx, 1);
      }
    }

    if (points.length < count) {
      const extra = this.generateUniformPoints(bounds, count - points.length, random);
      points.push(...extra);
    }
    return points.slice(0, count);
  }

  static generateRandomPaths(bounds, count, random, segments = 4) {
    const [xmin, ymin, xmax, ymax] = bounds;
    const width = xmax - xmin;
    const height = ymax - ymin;
    const stepLimit = Math.min(width, height) * 0.12;
    const lines = [];

    for (let i = 0; i < count; i++) {
      let cx = xmin + random() * width;
      let cy = ymin + random() * height;
      const coords = [[cx, cy]];

      for (let j = 0; j < segments; j++) {
        const angle = random() * 2 * Math.PI;
        const length = stepLimit * 0.4 + random() * stepLimit * 0.6;
        cx += length * Math.cos(angle);
        cy += length * Math.sin(angle);
        
        // Clamp to boundary
        cx = Math.max(xmin, Math.min(xmax, cx));
        cy = Math.max(ymin, Math.min(ymax, cy));
        coords.push([cx, cy]);
      }
      lines.push(coords);
    }
    return lines;
  }

  static generateStarPolygons(bounds, count, random, numVertices = 6) {
    const [xmin, ymin, xmax, ymax] = bounds;
    const width = xmax - xmin;
    const height = ymax - ymin;
    const maxRadius = Math.min(width, height) * 0.04;
    const minRadius = maxRadius * 0.3;
    const polygons = [];

    for (let i = 0; i < count; i++) {
      const cx = xmin + random() * width;
      const cy = ymin + random() * height;
      const angles = [];
      for (let v = 0; v < numVertices; v++) {
        angles.push((2 * Math.PI * v) / numVertices + (random() - 0.5) * 0.15);
      }
      angles.sort((a, b) => a - b);

      const ring = [];
      for (const angle of angles) {
        const r = minRadius + random() * (maxRadius - minRadius);
        ring.push([cx + r * Math.cos(angle), cy + r * Math.sin(angle)]);
      }
      ring.push(ring[0]); // Close ring
      polygons.push([ring]);
    }
    return polygons;
  }
}

// ============================================================================
// Simple Seeded Random for Reproducibility
// ============================================================================
function getSeededRandom(seed) {
  let h = seed ^ 0xDEADBEEF;
  return function() {
    h = Math.imul(h ^ (h >>> 16), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return ((h ^= h >>> 16) >>> 0) / 4294967296;
  };
}

// ============================================================================
// Domain presetting database schema mappings
// ============================================================================
const TEMPLATE_SCHEMAS = {
  parcel: [
    { name: "parcel_id", type: "SequentialID" },
    { name: "zoning_class", type: "Category", choices: ["Residential", "Commercial", "Industrial", "Agricultural", "Mixed-Use", "Conservation"] },
    { name: "land_value_usd", type: "Numeric", min: 10000, max: 2000000 }
  ],
  telecom: [
    { name: "tower_id", type: "SequentialID" },
    { name: "provider", type: "Category", choices: ["Verizon", "T-Mobile", "AT&T", "Dish Wireless"] },
    { name: "tower_height_m", type: "Numeric", min: 15, max: 120 }
  ],
  forestry: [
    { name: "tree_id", type: "SequentialID" },
    { name: "species", type: "Category", choices: ["Pinus sylvestris", "Quercus robur", "Betula pendula", "Picea abies"] },
    { name: "dbh_cm", type: "Numeric", min: 10, max: 150 }
  ],
  utility: [
    { name: "pipe_id", type: "SequentialID" },
    { name: "material", type: "Category", choices: ["PVC", "Iron", "Steel", "Copper"] },
    { name: "flow_status", type: "Category", choices: ["Flowing", "Restricted", "Maintenance"] }
  ]
};

// ============================================================================
// Main ES Module GeoLibre Plugin Registration
// ============================================================================

export default {
  id: "geodata-forge",
  name: "GeoData Forge",
  version: "1.0.0",

  activate(app) {
    this.app = app;
    this.previewLayerId = null;

    // Register our interactive generator panel inside the Right Panel space
    this._unregisterRight = app.registerRightPanel({
      id: "geodata-forge",
      title: "GeoData Forge",
      dock: "right-of-style",
      defaultWidth: 340,
      render: (container) => {
        container.innerHTML = `
          <div class="geodata-forge-panel">
            <div class="geodata-forge-header">
              <span>🛠️ GeoData Forge</span>
            </div>

            <!-- Spatial Boundary Section -->
            <div class="geodata-forge-section">
              <div class="geodata-forge-section-title">Spatial Settings</div>
              <div class="geodata-forge-form-group">
                <label class="geodata-forge-label">Feature Count</label>
                <input type="number" id="forge-count" class="geodata-forge-input" value="100" min="1" max="1000" />
              </div>
              <div class="geodata-forge-form-group">
                <label class="geodata-forge-label">Distribution Layout</label>
                <select id="forge-dist" class="geodata-forge-select">
                  <option value="Uniform">Uniform Random</option>
                  <option value="Clustered">Gaussian Cluster</option>
                  <option value="Poisson">Poisson Disc (Spacing)</option>
                </select>
              </div>
              <div class="geodata-forge-form-group" id="forge-spacing-group" style="display:none;">
                <label class="geodata-forge-label">Min Spacing (Degrees)</label>
                <input type="number" id="forge-spacing" class="geodata-forge-input" value="0.01" step="0.001" />
              </div>
              <div class="geodata-forge-form-group">
                <label class="geodata-forge-label">Random Seed</label>
                <input type="number" id="forge-seed" class="geodata-forge-input" value="42" />
              </div>
            </div>

            <!-- Geometry & Presets Section -->
            <div class="geodata-forge-section">
              <div class="geodata-forge-section-title">Geometry & Presets</div>
              <div class="geodata-forge-form-group">
                <label class="geodata-forge-label">Geometry Type</label>
                <select id="forge-geom" class="geodata-forge-select">
                  <option value="Point">Point Features</option>
                  <option value="Line">Random Paths</option>
                  <option value="Polygon">Star-convex Polygons</option>
                </select>
              </div>
              <div class="geodata-forge-form-group">
                <label class="geodata-forge-label">Domain Presets</label>
                <select id="forge-preset" class="geodata-forge-select">
                  <option value="parcel">🏡 Cadastral / Zoning Parcel</option>
                  <option value="telecom">📡 Telecom Towers</option>
                  <option value="forestry">🌳 Forestry Canopy Survey</option>
                  <option value="utility">🚰 Utility Water Pipes</option>
                </select>
              </div>
            </div>

            <!-- Action Controls -->
            <button class="geodata-forge-btn geodata-forge-btn-preview" id="forge-preview-btn">
              👁️ Preview Temporary Draft
            </button>
            <button class="geodata-forge-btn" id="forge-commit-btn">
              ➕ Add to Map Collection
            </button>
            <button class="geodata-forge-btn geodata-forge-btn-clear" id="forge-clear-btn">
              🧹 Clear Preview
            </button>

            <!-- Diagnostics log area -->
            <div class="geodata-forge-log" id="forge-log">Ready to generate.</div>
          </div>
        `;

        // Event hooks
        const distSelect = container.querySelector("#forge-dist");
        const spacingGroup = container.querySelector("#forge-spacing-group");
        distSelect.addEventListener("change", () => {
          spacingGroup.style.display = distSelect.value === "Poisson" ? "block" : "none";
        });

        const logArea = container.querySelector("#forge-log");
        const writeLog = (msg) => {
          logArea.innerText = `[${new Date().toLocaleTimeString()}] ${msg}`;
        };

        const generateGeoJSON = () => {
          const map = app.getMap ? app.getMap() : null;
          if (!map) {
            writeLog("Error: No active map canvas context found.");
            return null;
          }

          const mapBounds = map.getBounds();
          const bounds = [
            mapBounds.getWest(),
            mapBounds.getSouth(),
            mapBounds.getEast(),
            mapBounds.getNorth()
          ];

          const count = parseInt(container.querySelector("#forge-count").value, 10);
          const distribution = container.querySelector("#forge-dist").value;
          const geomType = container.querySelector("#forge-geom").value;
          const presetName = container.querySelector("#forge-preset").value;
          const seed = parseInt(container.querySelector("#forge-seed").value, 10);
          const spacing = parseFloat(container.querySelector("#forge-spacing").value);

          const random = getSeededRandom(seed);
          let coordinatesList = [];

          if (geomType === "Point") {
            if (distribution === "Poisson") {
              coordinatesList = GeometryGenerator.generatePoissonDiscPoints(bounds, count, random, spacing);
            } else if (distribution === "Clustered") {
              coordinatesList = GeometryGenerator.generateClusteredPoints(bounds, count, random);
            } else {
              coordinatesList = GeometryGenerator.generateUniformPoints(bounds, count, random);
            }
          } else if (geomType === "Line") {
            coordinatesList = GeometryGenerator.generateRandomPaths(bounds, count, random);
          } else {
            coordinatesList = GeometryGenerator.generateStarPolygons(bounds, count, random);
          }

          // Build attributes based on preset fields mapping
          const schema = TEMPLATE_SCHEMAS[presetName];
          const features = coordinatesList.map((coords, idx) => {
            const properties = {};
            schema.forEach((field) => {
              if (field.type === "SequentialID") {
                properties[field.name] = idx + 1;
              } else if (field.type === "Category") {
                properties[field.name] = field.choices[Math.floor(random() * field.choices.length)];
              } else if (field.type === "Numeric") {
                properties[field.name] = Math.round(field.min + random() * (field.max - field.min));
              }
            });

            let geometryObj;
            if (geomType === "Point") {
              geometryObj = { type: "Point", coordinates: coords };
            } else if (geomType === "Line") {
              geometryObj = { type: "LineString", coordinates: coords };
            } else {
              geometryObj = { type: "Polygon", coordinates: coords };
            }

            return {
              type: "Feature",
              geometry: geometryObj,
              properties: properties
            };
          });

          return {
            type: "FeatureCollection",
            features: features
          };
        };

        // Click actions
        container.querySelector("#forge-preview-btn").addEventListener("click", () => {
          const geojson = generateGeoJSON();
          if (!geojson) return;

          const map = app.getMap ? app.getMap() : null;
          if (map) {
            if (this.previewLayerId && map.getLayer(this.previewLayerId)) {
              map.removeLayer(this.previewLayerId);
              map.removeSource(this.previewLayerId);
            }

            this.previewLayerId = `forge-preview-${Date.now()}`;
            map.addSource(this.previewLayerId, {
              type: "geojson",
              data: geojson
            });

            // Handle points or lines/polygons layers styling
            const geomType = container.querySelector("#forge-geom").value;
            if (geomType === "Point") {
              map.addLayer({
                id: this.previewLayerId,
                source: this.previewLayerId,
                type: "circle",
                paint: {
                  "circle-radius": 6,
                  "circle-color": "#10b981",
                  "circle-stroke-width": 1.5,
                  "circle-stroke-color": "#ffffff"
                }
              });
            } else if (geomType === "Line") {
              map.addLayer({
                id: this.previewLayerId,
                source: this.previewLayerId,
                type: "line",
                paint: {
                  "line-width": 3,
                  "line-color": "#10b981"
                }
              });
            } else {
              map.addLayer({
                id: this.previewLayerId,
                source: this.previewLayerId,
                type: "fill",
                paint: {
                  "fill-color": "#10b981",
                  "fill-opacity": 0.4,
                  "fill-outline-color": "#ffffff"
                }
              });
            }
            writeLog(`Rendered temporary preview with ${geojson.features.length} shapes.`);
          }
        });

        container.querySelector("#forge-commit-btn").addEventListener("click", () => {
          const geojson = generateGeoJSON();
          if (!geojson) return;

          const presetName = container.querySelector("#forge-preset").value;
          const layerName = `Forge_${presetName}_${Date.now() % 1000}`;
          
          app.addGeoJsonLayer(layerName, geojson);
          writeLog(`SUCCESS: Added permanently to Layers Panel: '${layerName}'.`);
          
          // Clean up temp preview
          const map = app.getMap ? app.getMap() : null;
          if (map && this.previewLayerId && map.getLayer(this.previewLayerId)) {
            map.removeLayer(this.previewLayerId);
            map.removeSource(this.previewLayerId);
            this.previewLayerId = null;
          }
        });

        container.querySelector("#forge-clear-btn").addEventListener("click", () => {
          const map = app.getMap ? app.getMap() : null;
          if (map && this.previewLayerId && map.getLayer(this.previewLayerId)) {
            map.removeLayer(this.previewLayerId);
            map.removeSource(this.previewLayerId);
            this.previewLayerId = null;
          }
          writeLog("Cleared active preview draft layers.");
        });
      }
    });

    app.openRightPanel("geodata-forge");
  },

  deactivate(app) {
    if (this._unregisterRight) {
      this._unregisterRight();
    }
    
    // Clear leftover preview layers if any
    const map = app.getMap ? app.getMap() : null;
    if (map && this.previewLayerId && map.getLayer(this.previewLayerId)) {
      map.removeLayer(this.previewLayerId);
      map.removeSource(this.previewLayerId);
    }
  }
};
