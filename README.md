# Secrets

A not really host-proof, encrypted blog.

Don't use this for anything serious.

## Run

On Linux, you could do this in your Git checkout:

```bash
# Create a virtual environment and activate it:
python3 -m venv venv
source venv/bin/activate
# Install requirements in the virtual environment:
pip install -r requirements.txt
# Run the help command:
./encrypt.py --help
```

## Contribute

* Make sure you've installed the development requirements, in a virtual environment as above:

    ```bash
    pip install -r requirements-dev.txt
    ```

* Run `isort` and `flake8`.
* Run the tests:

    ```bash
    python3 -m unittest discover -s tests
    ```

## Licenses

This software is released under the MIT license. See `LICENSE.txt`.

Support for viewing panorama photos uses [Photo Sphere Viewer](https://github.com/mistic100/Photo-Sphere-Viewer). A single minified JS file that contains it and its requirements ([uEvent](https://github.com/mistic100/uEvent) and [three.js](https://github.com/mrdoob/three.js)) is included. All three of those also use the MIT license. Their licenses are included in `licenses/`.
