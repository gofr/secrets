import * as Leaflet from "leaflet/dist/leaflet";
import "leaflet/dist/leaflet.css";  // for Webpack

function createMap(element, geojson) {
    let feature = Leaflet.geoJSON(geojson);
    let bounds = feature.getBounds();
    let map = Leaflet.map(element, {
        zoomSnap: 5,
        zoomDelta: 5,
        maxBounds: bounds,
        maxBoundsViscosity: 1,
    }).setView(bounds.getCenter(), 10);
    Leaflet.control.scale().addTo(map);
    Leaflet.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 14,
        minZoom: 5,
    }).addTo(map);
    feature.addTo(map);
}

/**
 * Return IntersectionObserver callback to fetch, decrypt and load maps
 *
 * @param {Decryptor} decryptor
 * @return {IntersectionObserverCallback}
 */
 function getCallback(decryptor) {
    return async entries => {
        for (let entry of entries) {
            if (entry.isIntersecting && 'geojson' in entry.target.dataset) {
                let geojson = JSON.parse(await decryptor.fetchText(entry.target.dataset.geojson));
                delete entry.target.dataset.geojson;
                createMap(entry.target, geojson);
                // Only load the first map that has become visible and has
                // not already been loaded.
                break;
            }
        }
    }
}

export { getCallback };
