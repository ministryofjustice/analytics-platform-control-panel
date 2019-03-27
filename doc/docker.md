# Running with Docker

To build the docker image, use the following command:
```sh
docker build -t controlpanel .
```

Running the app requires a PostgreSQL database, and this is provided with
docker-compose:
```sh
docker-compose up
```

You can then view the Control Panel in your browser at http://localhost:8000/

To create a superuser able to administer the Control Panel, you need to run the
following command in a separate terminal window:
```sh
docker-compose exec app python3 manage.py createsuperuser
```


## Running tests

To run the test suite inside a docker container, use the following command:
```sh
make docker-test
```


# Dockerfile structure

The `Dockerfile` defines a multi-stage build with the following structure:

  1. Create a `base` image, building on Alpine and installing needed OS packages
  2. Download and install Helm
  3. Install Python dependencies
  4. Create a `jsdep` image, based on Node to download Javascript dependencies using `npm`
  5. Copy Javascript dependencies to the `base` image
  6. Collect static files ready to serve

Using a separate `jsdep` image means the final image doesn't need Node.JS
installed.

This structure hopefully makes the best use of the Docker cache, in that more
frequent updates to Javascript and Python dependencies happen later in the
build, and less frequent, more cachable updates to OS packages and Helm are
earlier.
