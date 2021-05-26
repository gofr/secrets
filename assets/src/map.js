import base32Encode from "base32-encode";
import * as Leaflet from "leaflet/dist/leaflet";
import "leaflet/dist/leaflet.css";  // for Webpack

var CryptoTileLayer = Leaflet.TileLayer.extend({
    options: {
        // @option decryptor: Decryptor = null
        // AES-GCM decryptor object
        decryptor: null,
        // @option key: CryptoKey = null
        // HMAC signing key
        key: null,
        // @option tiles: Array<string> = []
        // List of `${zoom}_${x}_${y}` strings for all available tiles
        tiles: []
    },
    createTile: function(coords, done) {
        let tile = Leaflet.TileLayer.prototype.createTile.call(this, coords, done);
        const point = `${this._getZoomForUrl()}_${coords.x}_${coords.y}`;
        if (this.options.tiles.includes(point)) {
            (async () => {
                try {
                    const hmac = await crypto.subtle.sign(
                        "HMAC", this.options.key, Int8Array.from(point, c => c.charCodeAt(0)));
                    const tileName = base32Encode(hmac, "RFC4648", {padding: false});
                    let url = await this.options.decryptor.fetchObject(`tiles/${tileName.toLowerCase()}`);
                    tile.src = url;
                    done(null, tile);
                } catch (error) {
                    done(error, tile);
                }
            })();
        }
        return tile;
    },
    getTileUrl: function(coords) {
        // Setting the real URL happens asynchronously in createTile():
        return this.options.errorTileUrl
    }
});
CryptoTileLayer.addInitHook(function() {
    this.on('tileload', function(element, point) {
        URL.revokeObjectURL(element.src);
    });
});
async function cryptoTileLayer(options) {
    const info = Uint8Array.from("names", c => c.charCodeAt(0));
    options.key = await crypto.subtle.deriveKey(
        {name: "HKDF", hash: "SHA-256", salt: new Uint8Array(), info: info},
        options.decryptor.base,
        {name: "HMAC", hash: "SHA-256"}, false, ["sign"]);
    return new CryptoTileLayer(null, options);
}

async function createMap(element, geojson, decryptor) {
    let feature = Leaflet.geoJSON(geojson);
    let bounds = feature.getBounds();
    let map = Leaflet.map(element, {
        zoomSnap: 5,
        zoomDelta: 5,
        maxBounds: bounds.pad(.05),
        maxBoundsViscosity: 1,
    }).setView(bounds.getCenter(), 10);
    Leaflet.control.scale().addTo(map);
    let layer = await cryptoTileLayer({
        attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 14,
        minZoom: 5,
        decryptor: decryptor,
        tiles: geojson.tiles,
    })
    layer.addTo(map);
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
                createMap(entry.target, geojson, decryptor);
                // Only load the first map that has become visible and has
                // not already been loaded.
                break;
            }
        }
    }
}

export { getCallback };
