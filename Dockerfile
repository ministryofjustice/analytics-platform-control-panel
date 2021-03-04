FROM quay.io/mojanalytics/node:8-alpine AS jsdep
COPY package.json package-lock.json ./
COPY jest.config.js controlpanel/frontend/static /src/

RUN npm install
RUN mkdir -p dist &&\
  ./node_modules/.bin/babel src/module-loader.js src/components src/javascripts -o dist/app.js -s
RUN ./node_modules/.bin/node-sass --include-path ./node_modules/ -o dist/ --output-style compact src/app.scss
WORKDIR /src
RUN /node_modules/.bin/jest

FROM quay.io/mojanalytics/alpine:3.13 AS base

ARG HELM_VERSION=2.13.1
ARG HELM_TARBALL=helm-v${HELM_VERSION}-linux-amd64.tar.gz
ARG HELM_BASEURL=https://storage.googleapis.com/kubernetes-helm

ENV DJANGO_SETTINGS_MODULE="controlpanel.settings" \
  HELM_HOME=/tmp/helm

# create a user to run as
RUN addgroup -g 1000 -S controlpanel && \
  adduser -u 1000 -S controlpanel -G controlpanel

WORKDIR /home/controlpanel

# download and install helm
COPY docker/helm-repositories.yaml /tmp/helm/repository/repositories.yaml
RUN wget ${HELM_BASEURL}/${HELM_TARBALL} -nv -O - | \
  tar xz -C /usr/local/bin --strip 1 linux-amd64/helm && \
  helm init --client-only && \
  helm repo update && \
  chown -R root:controlpanel ${HELM_HOME} && \
  chmod -R g+rwX ${HELM_HOME}

RUN apk add --no-cache \
            python3 \
            alpine-sdk \
            gcc \
            cargo \
            musl-dev \
            ca-certificates \
            libffi-dev \
            python3-dev \
            py3-pip \
            libressl-dev \
            postgresql-dev \
            libstdc++ \
            postgresql-client \
            graphviz \
            graphviz-dev \
            ttf-freefont \
  && pip3 install -U pip

COPY requirements.txt requirements.dev.txt manage.py ./
RUN pip3 install -U --no-cache-dir pip
RUN pip3 install -r requirements.txt
RUN python3 -m venv --system-site-packages dev-packages \
    && dev-packages/bin/pip3 install -U --no-cache-dir pip \
    && dev-packages/bin/pip3 install -r requirements.dev.txt

USER controlpanel
COPY controlpanel controlpanel
COPY docker docker
COPY tests tests

# install javascript dependencies
COPY --from=jsdep dist/app.css dist/app.js static/
COPY --from=jsdep node_modules/accessible-autocomplete/dist/ static/accessible-autocomplete
COPY --from=jsdep node_modules/govuk-frontend static/govuk-frontend
COPY --from=jsdep node_modules/@ministryofjustice/frontend/moj static/ministryofjustice-frontend
COPY --from=jsdep node_modules/html5shiv/dist static/html5-shiv
COPY --from=jsdep node_modules/jquery/dist static/jquery

# empty .env file to prevent warning messages
RUN touch .env

# collect static files for deployment
RUN SLACK_API_TOKEN=dummy python3 manage.py collectstatic --noinput --ignore=*.scss
EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "controlpanel.asgi:application"]
