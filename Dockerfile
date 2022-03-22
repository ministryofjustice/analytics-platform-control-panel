FROM quay.io/mojanalytics/node:8-alpine AS jsdep
COPY package.json package-lock.json ./
COPY jest.config.js controlpanel/frontend/static /src/

RUN npm install
RUN mkdir -p dist &&\
  ./node_modules/.bin/babel src/module-loader.js src/components src/javascripts -o dist/app.js -s
RUN ./node_modules/.bin/node-sass --include-path ./node_modules/ -o dist/ --output-style compact src/app.scss
WORKDIR /src
RUN /node_modules/.bin/jest

FROM 593291632749.dkr.ecr.eu-west-1.amazonaws.com/python:3.9-slim-buster AS base

ARG HELM_VERSION=2.13.1
ARG HELM_TARBALL=helm-v${HELM_VERSION}-linux-amd64.tar.gz
ARG HELM_BASEURL=https://get.helm.sh

ENV DJANGO_SETTINGS_MODULE="controlpanel.settings" \
  HELM_HOME=/tmp/helm

# create a user to run as
RUN addgroup -gid 1000 controlpanel && \
  adduser -uid 1000 --gid 1000 controlpanel

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /home/controlpanel

# download and install helm
COPY docker/helm-repositories.yaml /tmp/helm/repository/repositories.yaml
RUN wget ${HELM_BASEURL}/${HELM_TARBALL} -nv -O - | \
  tar xz -C /usr/local/bin --strip 1 linux-amd64/helm && \
  helm init --client-only && \
  helm repo update && \
  chown -R root:controlpanel ${HELM_HOME} && \
  chmod -R g+rwX ${HELM_HOME}



RUN pip install -U pip

COPY requirements.txt requirements.dev.txt manage.py ./
RUN pip install -U --no-cache-dir pip
RUN pip install -r requirements.txt
RUN pip uninstall python-dotenv -y

# Re-enable dev packages
RUN python3 -m venv --system-site-packages dev-packages \
    && dev-packages/bin/pip3 install -U --no-cache-dir pip \
    && dev-packages/bin/pip3 install -r requirements.dev.txt

RUN apt-get update
RUN apt-get install -y curl ca-certificates apt-transport-https gnupg
RUN curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -
RUN touch /etc/apt/sources.list.d/kubernetes.list
RUN echo "deb http://apt.kubernetes.io/ kubernetes-xenial main" | tee -a /etc/apt/sources.list.d/kubernetes.list
RUN apt-get update
RUN apt-get install -y kubectl
RUN apt-get install -y awscli
RUN apt-get install -y iputils-ping
RUN apt install iproute2 -y

# RUN echo "kind-control-plane host.docker.internal" > /etc/host.aliases
# RUN echo "export HOSTALIASES=/etc/host.aliases" >> /etc/profile

USER controlpanel
COPY controlpanel controlpanel
COPY docker docker
COPY tests tests
COPY setup.cfg setup.cfg
COPY pytest.ini pytest.ini



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

