# Secrets

A not really host-proof, encrypted blog.

Don't use this for anything serious.

## Installation

On Linux, you could do this in your Git checkout:

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ./encrypt.py --help

## Licenses

This software is released under the MIT license. See `LICENSE.txt`.

Support for viewing panorama photos uses [Photo Sphere Viewer](https://github.com/mistic100/Photo-Sphere-Viewer). A single minified JS file that contains it and its requirements ([uEvent](https://github.com/mistic100/uEvent) and [three.js](https://github.com/mrdoob/three.js)) is included. All three of those also use the MIT license. Their licenses are included in `3rdparty/`.
