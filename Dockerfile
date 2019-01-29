FROM alpine:3.7

MAINTAINER Andy Driver <andy.driver@digital.justice.gov.uk>

ENV HELM_VERSION 2.9.1
ENV HELM_HOME /tmp/helm
ENV DJANGO_SETTINGS_MODULE "control_panel_api.settings"
ENV USE_VENV=false

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
COPY Makefile ./
RUN make install-helm \
 && helm init --client-only \
 && helm repo update

# install python dependencies (and then remove build dependencies)
COPY requirements.txt ./
RUN make dependencies \
 && apk del build-base \
 && apk add --no-cache make

COPY control_panel_api control_panel_api
COPY moj_analytics moj_analytics
COPY manage.py wait_for_db ./

# collect static files for deployment
RUN make collectstatic

EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "control_panel_api.wsgi:application"]
