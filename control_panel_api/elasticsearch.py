from django.conf import settings
from elasticsearch import Elasticsearch as _Elasticsearch
from elasticsearch_dsl import Q, Search
from elasticsearch_dsl.query import Range


def bucket_hits_aggregation(index, bucket_name, num_days=None):
    client = _Elasticsearch(settings.ELASTICSEARCH_CONN)
    s = Search(using=client, index=index)

    q1 = Q('term', **{'bucket.keyword': bucket_name})
    q2 = Q('terms',
           **{'operation.keyword': ["REST.GET.BUCKET", "REST.GET.OBJECT"]})
    q3 = Q('match', request_header_user_agent='AWS-Support-TrustedAdvisor')

    s = s.query(q1 & q2 & ~q3)

    if num_days:
        s = s.filter(Range(time_received={"gte": f"now-{num_days}d/d"}))

    s.aggs.bucket('bucket_hits', 'terms', field='requester_id.keyword',
                  size=100)

    return s.execute()
