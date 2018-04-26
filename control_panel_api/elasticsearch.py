from elasticsearch import Elasticsearch
from elasticsearch_dsl import Q, Search
from elasticsearch_dsl.query import Range


class ElasticSearch(object):
    def __init__(self, connection):
        self.client = Elasticsearch(connection)

    def bucket_hits_aggregation(self, index, bucket_name, day_range=None):
        s = Search(using=self.client, index=index)

        q1 = Q('term', **{'bucket.keyword': bucket_name})
        q2 = Q('terms',
               **{'operation.keyword': ["REST.GET.BUCKET", "REST.GET.OBJECT"]})

        s = s.query(q1 & q2)

        if day_range:
            s = s.filter(Range(time_received={"gte": f"now-{day_range}d/d"}))

        s.aggs.bucket('bucket_hits', 'terms', field='requester_id.keyword',
                      size=100)

        return s.execute()
