// These imports, particularly the non-JS resources, are written for webpack,
// not JavaScript. They are parsed by webpack to manage dependencies and generate
// combined, minified files, with the JS "transpiled" down to ES5, using
// webpack.config.js as the configuration file.
import { Viewer } from "@photo-sphere-viewer/core";
import { VisibleRangePlugin } from "@photo-sphere-viewer/visible-range-plugin";

import "@photo-sphere-viewer/core/index.css";

/**
 * Zoom in to fill the vertical range of the panorama's viewer
 *
 * @param {Viewer} viewer
 */
function fillView(viewer) {
    // If the vertical range of the panorama does not fill the view,
    // zoom in to fill the height (to at most minFov).
    const visibleRangePlugin = viewer.getPlugin(VisibleRangePlugin);
    const vertical = visibleRangePlugin.config.verticalRange;
    if (vertical) {
        const view = Math.floor(180 * Math.abs(vertical[1] - vertical[0]) / Math.PI);
        if (view < viewer.state.vFov) {
            viewer.zoom(viewer.dataHelper.fovToZoomLevel(view));
        }
    }
}
/**
 * Create a Photo Sphere Viewer in the container element for the url image
 *
 * @param {Node} container
 * @param {DOMString} url
 */
 function createPanorama(container, url) {
    let viewer = new Viewer({
        "container": container,
        "panorama": url,
        "navbar": false,
        "mousewheel": false,
        "touchmoveTwoFingers": true,
        "plugins": [
            [VisibleRangePlugin, {usePanoData: true}]
        ],
    });
    viewer.addEventListener('ready', () => {
        URL.revokeObjectURL(url);
        viewer.getPlugin(VisibleRangePlugin);
        fillView(viewer);
    });
}
/**
 * Return IntersectionObserver callback to fetch, decrypt and load panoramas
 *
 * @param {Decryptor} decryptor
 * @return {IntersectionObserverCallback}
 */
function getCallback(decryptor) {
    return async entries => {
        for (let entry of entries) {
            if (entry.isIntersecting && 'panorama' in entry.target.dataset) {
                let blob = await decryptor.fetchObject(entry.target.dataset.panorama);
                delete entry.target.dataset.panorama;
                createPanorama(entry.target, blob);
                // Only load the first panorama that has become visible and has
                // not already been loaded.
                break;
            }
        }
    }
}

export { getCallback };
