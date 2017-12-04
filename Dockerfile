FROM alpine:3.6

MAINTAINER Andy Driver <andy.driver@digital.justice.gov.uk>

# install build dependencies (they'll be uninstalled after pip install)
RUN apk add --no-cache \
        --virtual build-deps \
        gcc \
        musl-dev

# install python3 and 'ca-certificates' so that HTTPS works consistently
RUN apk add --no-cache \
        openssl \
        ca-certificates \
        libffi-dev \
        libressl-dev \
        postgresql-dev \
        python3-dev

# Install helm
ENV HELM_VERSION 2.7.0
RUN wget https://storage.googleapis.com/kubernetes-helm/helm-v$HELM_VERSION-linux-amd64.tar.gz \
    && tar xzf helm-v$HELM_VERSION-linux-amd64.tar.gz \
    && mv linux-amd64/helm /usr/local/bin \
    && rm -rf helm-v$HELM_VERSION-linux-amd64.tar.gz linux-amd64

# Configure helm
ENV HELM_HOME /tmp/helm
RUN helm init --client-only
COPY helm-repositories.yaml /tmp/helm/repository/repositories.yaml
RUN helm repo update

WORKDIR /home/control-panel

# install python dependencies
ADD requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

# uninstall build dependencies
RUN apk del build-deps

ENV DJANGO_SETTINGS_MODULE "control_panel_api.settings"

ADD manage.py manage.py
ADD run_api run_api
ADD run_tests run_tests
ADD wait_for_db wait_for_db
ADD control_panel_api control_panel_api
ADD moj_analytics moj_analytics

# collect static files for deployment
RUN python3 manage.py collectstatic

EXPOSE 8000

CMD ["./run_api"]
