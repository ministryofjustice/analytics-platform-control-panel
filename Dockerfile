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

ADD ./ .

RUN pip3 install -r requirements.txt

EXPOSE 8000

CMD ["python3", "manage.py", "runserver"]
