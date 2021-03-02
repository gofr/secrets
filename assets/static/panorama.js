import { Viewer, VisibleRangePlugin } from "./photo-sphere-viewer.js";
import { fetchDecryptedObject } from "./decrypt.js";

var viewer;

function fillView(viewer) {
    // If the vertical range of the panorama does not fill the view,
    // zoom in to fill the height (to at most minFov).
    const visibleRangePlugin = viewer.getPlugin(VisibleRangePlugin);
    const latitude = visibleRangePlugin.config.latitudeRange;
    if (latitude !== null) {
        const view = Math.floor(180 * Math.abs(latitude[1] - latitude[0]) / Math.PI);
        if (view < viewer.prop.vFov) {
            viewer.zoom(viewer.dataHelper.fovToZoomLevel(view));
        }
    }
}

function getPanoramaCallback(decryptor) {
    return async entries => {
        for (let entry of entries) {
            if (entry.isIntersecting && 'panorama' in entry.target.dataset) {
                let blob = await fetchDecryptedObject(
                    entry.target.dataset.panorama, decryptor);
                delete entry.target.dataset.panorama;

                viewer = new Viewer({
                    "container": entry.target,
                    "panorama": blob,
                    "navbar": false,
                    "mousewheel": false,
                    "touchmoveTwoFingers": true,
                    "plugins": [
                        [VisibleRangePlugin, {usePanoData: true}]
                    ],
                });
                viewer.on('ready', function() {
                    URL.revokeObjectURL(blob);
                    viewer.getPlugin(VisibleRangePlugin);
                    fillView(viewer);
                });
                break;
            }
        }
    }
}

export { getPanoramaCallback };
