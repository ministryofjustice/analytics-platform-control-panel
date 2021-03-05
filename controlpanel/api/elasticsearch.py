import logging

from dateutil.parser import parse
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Q, Search
from elasticsearch_dsl.query import Range

from django.conf import settings

log = logging.getLogger(__name__)


def bucket_hits_aggregation(bucket_name, num_days=None):
    conn = Elasticsearch(hosts=settings.ELASTICSEARCH['hosts'])

    s = Search(using=conn, index=settings.ELASTICSEARCH['indices']['s3-logs'])

    q1 = Q('term', **{'bucket.keyword': bucket_name})
    q2 = Q('terms',
           **{'operation.keyword': ["REST.GET.BUCKET", "REST.GET.OBJECT"]})
    q3 = Q('match', request_header_user_agent='AWS-Support-TrustedAdvisor')

    s = s.query(q1 & q2 & ~q3)

    if num_days:
        s = s.filter(Range(time_received={"gte": f"now-{num_days}d/d"}))

    s.aggs.bucket('bucket_hits', 'terms', field='requester_id.keyword',
                  size=100)

    return s.execute().aggregations.bucket_hits


def app_logs(app, num_hours=None):
    # Disable logs for noisy app ("covid19-early-release")
    # to prevent its App details page to timeout
    log.info("Get app logs for: " + str(app.id))
    if app.id == 171:
        return []

    if not num_hours:
        num_hours = 1

    conn = Elasticsearch(hosts=settings.ELASTICSEARCH['hosts'])
    # Create Search object. Timeout after 10 seconds, can be retried.
    search_obj = Search(
        using=conn,
        index=settings.ELASTICSEARCH['indices']['app-logs']
    ).sort('time_nano').source(['@timestamp', 'message'])

    exist_filter = Q('exists', field='message')
    app_filter = Q('term', **{"kubernetes.labels.app.keyword": f"{app.release_name}-webapp"})
    time_filter = Range(**{'@timestamp': {
        'lte': 'now',
        'gte': f'now-{num_hours}h',
        },
    })

    query_obj = search_obj.filter(exist_filter & app_filter & time_filter)

    try:
        logs = []
        log.info(f"Got {query_obj.count()} log entries.")
        for entry in query_obj.scan():
            entry['timestamp'] = parse(entry['@timestamp'])
            logs.append(entry)
    except Exception as ex:
        log.error(ex)
        logs = []
    return logs 
