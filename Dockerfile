FROM alpine:3.6

MAINTAINER Andy Driver <andy.driver@digital.justice.gov.uk>

RUN apk update && \
    apk add \
        --virtual build-deps \
        gcc \
        musl-dev \
        postgresql-dev \
        python3-dev

WORKDIR /home/control-panel

# install python dependencies
ADD requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

ADD manage.py manage.py
ADD run_api run_api
ADD run_tests run_tests
ADD wait_for_db wait_for_db
ADD control_panel_api control_panel_api

# collect static files for deployment
RUN python3 manage.py collectstatic

EXPOSE 8000

CMD ["./run_api"]
