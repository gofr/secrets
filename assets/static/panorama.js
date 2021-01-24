"use strict";
(function() {
    var viewer;

    function fillView(viewer) {
        // If the vertical range of the panorama does not fill the view,
        // zoom in to fill the height (to at most minFov).
        const visibleRangePlugin = viewer.getPlugin(PhotoSphereViewer.VisibleRangePlugin);
        const latitude = visibleRangePlugin.config.latitudeRange;
        if (latitude !== null) {
            const view = 180 * Math.abs(latitude[1] - latitude[0]) / Math.PI;
            if (view < viewer.prop.vFov) {
                viewer.zoom(viewer.dataHelper.fovToZoomLevel(view));
            }
        }

    }
    async function panoramaCallback(entries, observer) {
        for (let entry of entries) {
            if (entry.isIntersecting && 'panorama' in entry.target.dataset) {
                let blob = await fetchDecryptedObject(
                    entry.target.dataset.panorama, sessionStorage.getItem('key'))
                delete entry.target.dataset.panorama

                viewer = new PhotoSphereViewer.Viewer({
                    "container": entry.target,
                    "panorama": blob,
                    "navbar": false,
                    "mousewheel": false,
                    "touchmoveTwoFingers": true,
                    "plugins": [
                        [PhotoSphereViewer.VisibleRangePlugin, {usePanoData: true}]
                    ],
                });
                viewer.on('ready', function() {
                    URL.revokeObjectURL(blob);
                    const visibleRangePlugin = viewer.getPlugin(PhotoSphereViewer.VisibleRangePlugin);
                    fillView(viewer);
                });
                break;
            }
        }
    }

    window.panoramaObserver = new IntersectionObserver(panoramaCallback);
})();
