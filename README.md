# Secrets

A not really host-proof, encrypted blog.

Don't use this for anything serious.

## Install

The JavaScript front-end code uses Node.js (14.16.0) and webpack. On Ubuntu 20.04 you can install Node with:

```bash
sudo snap install node --classic
```

Also see [the Snapcraft website](https://snapcraft.io/node) or [the Node.js documentation](https://nodejs.org/en/download/).

Once you've installed that, run the following in `assets/` in your Git checkout to install all the Node package dependencies:

```bash
npm install
```

The Python backend code uses Python 3.8+. You should ideally create a virtual environment and install the necessary Python packages in that. On Linux, you could do this in your Git checkout:

```bash
# Create a virtual environment and activate it:
python3 -m venv venv
source venv/bin/activate
# Install requirements in the virtual environment:
pip install -r requirements.txt
```

## Run

Run the help command:

```bash
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
