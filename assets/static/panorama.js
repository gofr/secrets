"use strict";
(function() {
    var viewer;

    function getLatitudeRange(panoData) {
        const p = panoData;
        if (p.croppedHeight == p.fullHeight && p.croppedY == 0) {
            return null;
        } else {
            const latitude = y => Math.PI * (1 - y / p.fullHeight) - (Math.PI / 2);
            return [latitude(p.croppedY), latitude(p.croppedY + p.croppedHeight)];
        }
    }
    function getLongitudeRange(panoData) {
        const p = panoData;
        if (p.croppedWidth == p.fullWidth && p.croppedX == 0) {
            return null;
        } else {
            const longitude = x => 2 * Math.PI * (x / p.fullWidth) - Math.PI;
            return [longitude(p.croppedX), longitude(p.croppedX + p.croppedWidth)];
        }
    }
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
                        PhotoSphereViewer.VisibleRangePlugin,
                    ],
                });
                viewer.on('ready', function() {
                    URL.revokeObjectURL(blob);
                    const visibleRangePlugin = viewer.getPlugin(PhotoSphereViewer.VisibleRangePlugin);
                    // TODO: Drop this and use upstreamed fix (e5da3944).
                    visibleRangePlugin.setLongitudeRange(getLongitudeRange(viewer.prop.panoData));
                    visibleRangePlugin.setLatitudeRange(getLatitudeRange(viewer.prop.panoData));
                    fillView(viewer);
                });
                break;
            }
        }
    }

    window.panoramaObserver = new IntersectionObserver(panoramaCallback);
})();
