FROM alpine:3.8 AS base

LABEL maintainer="andy.driver@digital.justice.gov.uk"

ARG HELM_VERSION=2.13.0
ARG HELM_TARBALL=helm-v${HELM_VERSION}-linux-amd64.tar.gz
ARG HELM_BASEURL=https://storage.googleapis.com/kubernetes-helm

ENV DJANGO_SETTINGS_MODULE "controlpanel.settings"
ENV HELM_HOME /tmp/helm

WORKDIR /home/controlpanel

# install build dependencies (they'll be uninstalled after pip install)
RUN apk add --no-cache \
        build-base=0.5-r1 \
        ca-certificates=20171114-r3 \
        libffi-dev=3.2.1-r4 \
        python3-dev=3.6.6-r0 \
        libressl-dev=2.7.5-r0 \
        postgresql-dev=10.5-r0 \
        postgresql-client=10.5-r0

# download and install helm
COPY docker/helm-repositories.yaml /tmp/helm/repository/repositories.yaml
RUN wget ${HELM_BASEURL}/${HELM_TARBALL} -nv -O - | \
    tar xz -C /usr/local/bin --strip 1 linux-amd64/helm && \
    helm init --client-only && \
    helm repo update

# install python dependencies (and then remove build dependencies)
COPY requirements.lock manage.py ./
RUN pip3 install -U pip && \
    pip3 install -r requirements.lock && \
    apk del build-base

COPY controlpanel controlpanel


# fetch javascript dependencies in separate stage
FROM node:8-alpine AS jsdep
COPY package.json package-lock.json ./
COPY controlpanel/frontend/static/javascripts src
RUN npm install && \
    mkdir -p dist && \
    ./node_modules/.bin/babel src -o dist/app.js -s


FROM base

# install javascript dependencies
COPY --from=jsdep dist/app.js static/app.js
COPY --from=jsdep node_modules/govuk-frontend static/govuk-frontend
COPY --from=jsdep node_modules/html5shiv/dist static/html5-shiv
COPY --from=jsdep node_modules/jquery/dist static/jquery
COPY --from=jsdep node_modules/jquery-modal static/jquery-modal
COPY --from=jsdep node_modules/jquery-typeahead/dist static/jquery-typeahead

# collect static files for deployment
RUN python3 manage.py collectstatic

EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "controlpanel.asgi:application"]
