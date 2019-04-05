FROM alpine:3.7

MAINTAINER Andy Driver <andy.driver@digital.justice.gov.uk>

ENV HELM_VERSION 2.13.0
ENV HELM_HOME /tmp/helm
ENV DJANGO_SETTINGS_MODULE "control_panel_api.settings"

WORKDIR /home/control-panel

# install build dependencies (they'll be uninstalled after pip install)
RUN apk add --no-cache \
        build-base \
        openssl \
        ca-certificates \
        libffi-dev \
        python3-dev \
        libressl-dev \
        postgresql-dev

# Install and configure helm
COPY helm-repositories.yaml /tmp/helm/repository/repositories.yaml
RUN wget https://storage.googleapis.com/kubernetes-helm/helm-v${HELM_VERSION}-linux-amd64.tar.gz -O helm.tgz \
 && tar fxz helm.tgz \
 && mv linux-amd64/helm /usr/local/bin \
 && rm -rf helm.tgz linux-amd64 \
 && helm init --client-only \
 && helm repo update

# install python dependencies (and then remove build dependencies)
COPY requirements.txt ./
RUN pip3 install -r requirements.txt \
 && apk del build-base

COPY control_panel_api control_panel_api
COPY moj_analytics moj_analytics
COPY manage.py wait_for_db ./

# collect static files for deployment
RUN python3 manage.py collectstatic

EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "control_panel_api.wsgi:application"]
