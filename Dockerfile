FROM alpine:3.8 AS base

LABEL maintainer="andy.driver@digital.justice.gov.uk"

ARG HELM_VERSION=2.13.1
ARG HELM_TARBALL=helm-v${HELM_VERSION}-linux-amd64.tar.gz
ARG HELM_BASEURL=https://storage.googleapis.com/kubernetes-helm

ENV DJANGO_SETTINGS_MODULE "controlpanel.settings"
ENV HELM_HOME /tmp/helm

# create a user to run as
RUN addgroup -g 1000 -S controlpanel && \
    adduser -u 1000 -S controlpanel -G controlpanel

WORKDIR /home/controlpanel

# install build dependencies
RUN apk add --no-cache \
        build-base=0.5-r1 \
        ca-certificates=20190108-r0 \
        libffi-dev=3.2.1-r4 \
        python3-dev=3.6.8-r0 \
        libressl-dev=2.7.5-r0 \
        libstdc++=6.4.0-r9 \
        postgresql-dev=10.8-r0 \
        postgresql-client=10.8-r0

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

RUN pip3 install django-debug-toolbar

USER controlpanel
COPY controlpanel controlpanel
COPY tests tests


# fetch javascript dependencies in separate stage
FROM node:8-alpine AS jsdep
COPY package.json package-lock.json ./
COPY controlpanel/frontend/static src
RUN npm install && \
    mkdir -p dist && \
    ./node_modules/.bin/babel \
        src/module-loader.js \
        src/components \
        src/javascripts \
        -o dist/app.js -s && \
    ./node_modules/.bin/node-sass \
      --include-path ./node_modules/ \
      -o dist/ \
      --output-style compact \
      src/app.scss


FROM base

USER controlpanel

# install javascript dependencies
COPY --from=jsdep dist/app.css dist/app.js static/
COPY --from=jsdep node_modules/accessible-autocomplete/dist/ static/accessible-autocomplete
COPY --from=jsdep node_modules/govuk-frontend static/govuk-frontend
COPY --from=jsdep node_modules/@hmcts/frontend static/hmcts-frontend
COPY --from=jsdep node_modules/html5shiv/dist static/html5-shiv
COPY --from=jsdep node_modules/jquery/dist static/jquery

# collect static files for deployment
RUN python3 manage.py collectstatic --noinput --ignore=*.scss

EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "controlpanel.asgi:application"]
