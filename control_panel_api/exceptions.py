from rest_framework.exceptions import APIException


class AWSException(APIException):
    status_code = 500
    default_detail = 'There was an error with AWS'
    default_code = 'aws_error'


class HelmException(APIException):
    status_code = 500
    default_detail = 'There was an error with Helm'
    default_code = 'helm_error'


class ESException(APIException):
    status_code = 500
    default_detail = 'There was an error with ElasticSearch'
    default_code = 'es_error'
