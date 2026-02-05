// Demalytics - Storage Market Analysis
// Main JavaScript Application

let map;
let draw;
let currentStudyId = null;
let mapboxToken = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', async () => {
    await loadConfig();
    await initMap();
    await loadCustomers();
    setupEventListeners();
});

// Load configuration (MapBox token)
async function loadConfig() {
    try {
        const response = await fetch('/api/config/');
        const data = await response.json();
        mapboxToken = data.mapbox_token;

        if (!mapboxToken) {
            showError('MapBox token not configured. Please set MB_PUBLIC_KEY in your environment.');
        }
    } catch (error) {
        showError('Failed to load configuration: ' + error.message);
    }
}

// Initialize MapBox map
async function initMap() {
    if (!mapboxToken) {
        showError('Cannot initialize map: MapBox token is missing.');
        return;
    }

    mapboxgl.accessToken = mapboxToken;

    // Default center: Surrey, BC, Canada
    map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/streets-v12',
        center: [-122.85, 49.19],
        zoom: 10
    });

    // Add navigation controls
    map.addControl(new mapboxgl.NavigationControl(), 'top-right');

    // Add drawing controls
    draw = new MapboxDraw({
        displayControlsDefault: false,
        controls: {
            polygon: true,
            trash: true
        },
        defaultMode: 'simple_select'
    });
    map.addControl(draw, 'top-left');

    // Handle draw events
    map.on('draw.create', updateGeometryStatus);
    map.on('draw.update', updateGeometryStatus);
    map.on('draw.delete', updateGeometryStatus);

    // Hide instructions when drawing starts
    map.on('draw.modechange', (e) => {
        const instructions = document.getElementById('map-instructions');
        if (e.mode === 'draw_polygon') {
            instructions.classList.add('hidden');
        }
    });

    map.on('load', () => {
        console.log('Map loaded successfully');
    });
}

// Load customers from API
async function loadCustomers() {
    try {
        const response = await fetch('/api/customers/');
        const data = await response.json();

        const select = document.getElementById('customer');
        data.customers.forEach(customer => {
            const option = document.createElement('option');
            option.value = customer.id;
            option.textContent = customer.name;
            select.appendChild(option);
        });
    } catch (error) {
        showError('Failed to load customers: ' + error.message);
    }
}

// Update geometry status when polygon is drawn
function updateGeometryStatus() {
    const data = draw.getAll();
    const statusBox = document.getElementById('geometry-status');
    const createBtn = document.getElementById('create-study-btn');

    if (data.features.length > 0) {
        const feature = data.features[0];
        const coords = feature.geometry.coordinates[0];
        const numPoints = coords.length - 1; // Last point is same as first

        statusBox.innerHTML = `
            <span class="status-indicator ready"></span>
            Area selected (${numPoints} points)
        `;
        createBtn.disabled = false;
    } else {
        statusBox.innerHTML = `
            <span class="status-indicator not-ready"></span>
            No area selected
        `;
        createBtn.disabled = true;
    }
}

// Setup event listeners
function setupEventListeners() {
    // Create study form
    document.getElementById('study-form').addEventListener('submit', handleCreateStudy);

    // Process study button
    document.getElementById('process-study-btn').addEventListener('click', handleProcessStudy);

    // Run analysis button
    document.getElementById('run-analysis-btn').addEventListener('click', handleRunAnalysis);
}

// Handle create study form submission
async function handleCreateStudy(e) {
    e.preventDefault();

    const data = draw.getAll();
    if (data.features.length === 0) {
        showError('Please draw a study area on the map first.');
        return;
    }

    const customerId = document.getElementById('customer').value;
    const studyName = document.getElementById('study-name').value;
    const description = document.getElementById('description').value;
    const country = document.querySelector('input[name="country"]:checked').value;

    if (!customerId) {
        showError('Please select a customer.');
        return;
    }

    const geometry = data.features[0];

    showProgress('Creating study...', 10);

    try {
        const response = await fetch('/api/studies/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                customer_id: parseInt(customerId),
                name: studyName,
                description: description,
                country: country,
                geometry: geometry
            })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || 'Failed to create study');
        }

        currentStudyId = result.study_id;

        // Update UI
        document.getElementById('current-study-name').textContent = result.name;
        document.getElementById('current-study-id').textContent = result.study_id;
        document.getElementById('analysis-section').classList.remove('hidden');

        showProgress('Study created successfully!', 100);
        setTimeout(() => hideProgress(), 2000);

        // Disable form to prevent duplicate submissions
        document.getElementById('create-study-btn').disabled = true;
        document.getElementById('study-form').querySelectorAll('input, select, textarea').forEach(el => {
            el.disabled = true;
        });

        // Disable drawing
        draw.changeMode('simple_select');

    } catch (error) {
        showError('Failed to create study: ' + error.message);
        hideProgress();
    }
}

// Handle process study
async function handleProcessStudy() {
    if (!currentStudyId) {
        showError('No study selected.');
        return;
    }

    const processBtn = document.getElementById('process-study-btn');
    processBtn.disabled = true;

    showProgress('Processing study... This may take several minutes.', 20);

    try {
        const response = await fetch(`/api/studies/${currentStudyId}/process/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || 'Failed to process study');
        }

        showProgress('Study processed! Demand and supply calculated.', 70);

        // Enable run analysis button
        document.getElementById('run-analysis-btn').disabled = false;

        setTimeout(() => {
            showProgress('Ready to generate map.', 70);
        }, 2000);

    } catch (error) {
        showError('Failed to process study: ' + error.message);
        processBtn.disabled = false;
        hideProgress();
    }
}

// Handle run analysis
async function handleRunAnalysis() {
    if (!currentStudyId) {
        showError('No study selected.');
        return;
    }

    const analysisBtn = document.getElementById('run-analysis-btn');
    analysisBtn.disabled = true;

    showProgress('Running final analysis...', 80);

    try {
        // Run the analysis calculation
        const response = await fetch(`/api/studies/${currentStudyId}/analysis/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || 'Failed to run analysis');
        }

        showProgress('Loading results on map...', 90);

        // Load GeoJSON results directly onto the map
        await loadResultsOnMap();

        showProgress('Analysis complete!', 100);

        // Show results
        const resultsSection = document.getElementById('results-section');
        resultsSection.classList.remove('hidden');
        document.getElementById('results-message').textContent = 'Analysis results are displayed on the map.';

    } catch (error) {
        showError('Failed to run analysis: ' + error.message);
        analysisBtn.disabled = false;
        hideProgress();
    }
}

// Load GeoJSON results directly onto the map
async function loadResultsOnMap() {
    try {
        // Fetch boundaries and stores GeoJSON
        const [boundariesResponse, storesResponse] = await Promise.all([
            fetch(`/api/studies/${currentStudyId}/boundaries.geojson`),
            fetch(`/api/studies/${currentStudyId}/stores.geojson`)
        ]);

        const boundariesData = await boundariesResponse.json();
        const storesData = await storesResponse.json();

        if (boundariesResponse.ok && boundariesData.features) {
            // Remove existing layers if they exist
            if (map.getLayer('boundary-analysis-fill')) {
                map.removeLayer('boundary-analysis-fill');
            }
            if (map.getLayer('boundary-analysis-line')) {
                map.removeLayer('boundary-analysis-line');
            }
            if (map.getSource('boundary-analysis')) {
                map.removeSource('boundary-analysis');
            }

            // Add boundaries source
            map.addSource('boundary-analysis', {
                type: 'geojson',
                data: boundariesData
            });

            // Get max residual for color scaling
            const maxResidual = boundariesData.metadata?.max_residual || 1000;

            // Add fill layer with red-white-green gradient
            map.addLayer({
                id: 'boundary-analysis-fill',
                type: 'fill',
                source: 'boundary-analysis',
                paint: {
                    'fill-color': [
                        'interpolate',
                        ['linear'],
                        ['get', 'residual'],
                        -maxResidual, '#d73027',  // Red for undersupply (negative residual = demand > supply)
                        0, '#ffffff',              // White for balanced
                        maxResidual, '#1a9850'    // Green for oversupply (positive residual = supply > demand)
                    ],
                    'fill-opacity': 0.7
                }
            });

            // Add outline layer
            map.addLayer({
                id: 'boundary-analysis-line',
                type: 'line',
                source: 'boundary-analysis',
                paint: {
                    'line-color': '#333333',
                    'line-width': 0.5
                }
            });

            // Add click handler for boundary info
            map.on('click', 'boundary-analysis-fill', (e) => {
                const props = e.features[0].properties;
                new mapboxgl.Popup()
                    .setLngLat(e.lngLat)
                    .setHTML(`
                        <strong>Boundary Analysis</strong><br>
                        Demand: ${props.demand?.toFixed(0) || 'N/A'}<br>
                        Supply: ${props.supply?.toFixed(0) || 'N/A'}<br>
                        Residual: ${props.residual?.toFixed(0) || 'N/A'}
                    `)
                    .addTo(map);
            });

            // Change cursor on hover
            map.on('mouseenter', 'boundary-analysis-fill', () => {
                map.getCanvas().style.cursor = 'pointer';
            });
            map.on('mouseleave', 'boundary-analysis-fill', () => {
                map.getCanvas().style.cursor = '';
            });
        }

        if (storesResponse.ok && storesData.features && storesData.features.length > 0) {
            // Remove existing layers if they exist
            if (map.getLayer('stores')) {
                map.removeLayer('stores');
            }
            if (map.getSource('stores')) {
                map.removeSource('stores');
            }

            // Add stores source
            map.addSource('stores', {
                type: 'geojson',
                data: storesData
            });

            // Get min/max sqft for circle sizing
            const minSqft = storesData.metadata?.min_sqft || 0;
            const maxSqft = storesData.metadata?.max_sqft || 100000;

            // Add stores layer
            map.addLayer({
                id: 'stores',
                type: 'circle',
                source: 'stores',
                paint: {
                    'circle-radius': [
                        'interpolate',
                        ['linear'],
                        ['sqrt', ['/', ['-', ['get', 'rentablesqft'], minSqft], ['-', maxSqft, minSqft]]],
                        0, 4,
                        1, 12
                    ],
                    'circle-color': '#000000',
                    'circle-stroke-width': 2,
                    'circle-stroke-color': '#ffffff'
                }
            });

            // Add click handler for store info
            map.on('click', 'stores', (e) => {
                const props = e.features[0].properties;
                new mapboxgl.Popup()
                    .setLngLat(e.lngLat)
                    .setHTML(`
                        <strong>${props.storename || 'Store'}</strong><br>
                        ${props.address || ''}<br>
                        ${props.city || ''}<br>
                        Rentable SqFt: ${props.rentablesqft?.toLocaleString() || 'N/A'}
                    `)
                    .addTo(map);
            });

            // Change cursor on hover
            map.on('mouseenter', 'stores', () => {
                map.getCanvas().style.cursor = 'pointer';
            });
            map.on('mouseleave', 'stores', () => {
                map.getCanvas().style.cursor = '';
            });
        }

        // Fit map to boundaries
        if (boundariesData.features && boundariesData.features.length > 0) {
            const bounds = new mapboxgl.LngLatBounds();
            boundariesData.features.forEach(feature => {
                if (feature.geometry.type === 'MultiPolygon') {
                    feature.geometry.coordinates.forEach(polygon => {
                        polygon[0].forEach(coord => bounds.extend(coord));
                    });
                } else if (feature.geometry.type === 'Polygon') {
                    feature.geometry.coordinates[0].forEach(coord => bounds.extend(coord));
                }
            });
            map.fitBounds(bounds, { padding: 50 });
        }

        // Hide drawing controls
        if (draw) {
            map.removeControl(draw);
            draw = null;
        }

        // Update instructions
        const instructions = document.getElementById('map-instructions');
        instructions.innerHTML = '<p>Click on boundaries or stores for details. Red = undersupply, Green = oversupply.</p>';
        instructions.classList.remove('hidden');

    } catch (error) {
        throw new Error('Failed to load map data: ' + error.message);
    }
}

// Show progress
function showProgress(message, percentage) {
    const progressSection = document.getElementById('progress-section');
    progressSection.classList.remove('hidden');

    document.getElementById('progress-text').textContent = message;
    document.getElementById('progress-fill').style.width = percentage + '%';
}

// Hide progress
function hideProgress() {
    document.getElementById('progress-section').classList.add('hidden');
}

// Show error
function showError(message) {
    const errorSection = document.getElementById('error-section');
    errorSection.classList.remove('hidden');
    document.getElementById('error-message').textContent = message;

    // Auto-hide after 10 seconds
    setTimeout(() => {
        errorSection.classList.add('hidden');
    }, 10000);
}

// Hide error
function hideError() {
    document.getElementById('error-section').classList.add('hidden');
}
