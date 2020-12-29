# Secrets

A not really host-proof, encrypted blog.

Don't use this for anything serious.

## Run

On Linux, you could do this in your Git checkout:

```bash
# Create an virtual environment and activate it:
python3 -m venv venv
source venv/bin/activate
# Install requirements in the virtual environment:
pip install -r requirements.txt
# Run the help command:
./encrypt.py --help
```

### Test

Run tests, in the virtual environment if you created one, with:

    python3 -m unittest discover -s tests

## Licenses

This software is released under the MIT license. See `LICENSE.txt`.

Support for viewing panorama photos uses [Photo Sphere Viewer](https://github.com/mistic100/Photo-Sphere-Viewer). A single minified JS file that contains it and its requirements ([uEvent](https://github.com/mistic100/uEvent) and [three.js](https://github.com/mrdoob/three.js)) is included. All three of those also use the MIT license. Their licenses are included in `licenses/`.
