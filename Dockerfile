# checkov:skip=CKV_DOCKER_2:Healthcheck instructions have not been added to container images
FROM public.ecr.aws/docker/library/node:20.11.1 AS build-node
COPY package.json package-lock.json ./
COPY jest.config.js controlpanel/frontend/static /src/

RUN npm install
RUN mkdir -p dist &&\
  ./node_modules/.bin/babel src/module-loader.js src/components src/javascripts -o dist/app.js -s
RUN ./node_modules/.bin/sass --load-path=./ --style=compressed src/app.scss:dist/app.css
WORKDIR /src
RUN /node_modules/.bin/jest

FROM public.ecr.aws/docker/library/python:3.12-alpine3.21 AS base

ARG HELM_VERSION=3.17.2
ARG HELM_TARBALL=helm-v${HELM_VERSION}-linux-amd64.tar.gz
ARG HELM_BASEURL=https://get.helm.sh

ENV DJANGO_SETTINGS_MODULE="controlpanel.settings" \
  HELM_HOME=/tmp/helm \
  HELM_CONFIG_HOME=/tmp/helm/repository \
  HELM_CACHE_HOME=/tmp/helm/cache \
  HELM_DATA_HOME=/tmp/helm/data

# create a user to run as
RUN addgroup -g 1000 controlpanel \
    && adduser -G controlpanel -u 1000 controlpanel -D

RUN apk update && apk upgrade \
    && apk add --no-cache \
        postgresql-client \
        wget \
        gcc \
        curl-dev \
        python3-dev \
        gnutls-dev \
        openssl-dev \
        libffi-dev \
        musl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /home/controlpanel

# download and install helm
COPY docker/helm-repositories.yaml /tmp/helm/repository/repositories.yaml
RUN wget ${HELM_BASEURL}/${HELM_TARBALL} -nv -O - | \
  tar xz -C /usr/local/bin --strip 1 linux-amd64/helm && \
  helm repo update && \
  chown -R root:controlpanel ${HELM_HOME} && \
  chmod -R g+rwX ${HELM_HOME}



RUN pip install -U pip

COPY requirements.txt requirements.dev.txt manage.py settings.yaml ./
RUN pip install -U --no-cache-dir pip
RUN pip install -r requirements.txt

# Re-enable dev packages
RUN python3 -m venv --system-site-packages dev-packages \
    && dev-packages/bin/pip3 install -U --no-cache-dir pip \
    && dev-packages/bin/pip3 install -r requirements.dev.txt

USER controlpanel
COPY controlpanel controlpanel
COPY docker docker
COPY tests tests

# install javascript dependencies
COPY --from=build-node dist/app.css dist/app.js static/
COPY --from=build-node node_modules/govuk-frontend/dist/govuk/assets/fonts/. static/assets/fonts
COPY --from=build-node node_modules/govuk-frontend/dist/govuk/assets/images/. static/assets/images
COPY --from=build-node node_modules/govuk-frontend/dist/govuk/govuk-frontend.min.js static/assets/js/govuk-frontend.min.js
COPY --from=build-node node_modules/govuk-frontend/dist/govuk/govuk-frontend.min.js.map static/assets/js/govuk-frontend.min.js.map
COPY --from=build-node node_modules/accessible-autocomplete/dist/ static/accessible-autocomplete
COPY --from=build-node node_modules/govuk-frontend static/govuk-frontend
COPY --from=build-node node_modules/@ministryofjustice/frontend/moj static/ministryofjustice-frontend
COPY --from=build-node node_modules/html5shiv/dist static/html5-shiv
COPY --from=build-node node_modules/jquery/dist static/jquery
COPY --from=build-node node_modules/jquery-ui/dist/ static/jquery-ui

# empty .env file to prevent warning messages
RUN touch .env

# collect static files for deployment
RUN SLACK_API_TOKEN=dummy python3 manage.py collectstatic --noinput --ignore=*.scss
EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "controlpanel.asgi:application"]
