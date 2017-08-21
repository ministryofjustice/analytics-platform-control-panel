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

ADD requirements.txt requirements.txt

RUN pip3 install -r requirements.txt

ADD run_tests run_tests
ADD wait_for_db wait_for_db
ADD manage.py manage.py
ADD control_panel_api control_panel_api

EXPOSE 8000

CMD ["python3", "manage.py", "runserver"]
