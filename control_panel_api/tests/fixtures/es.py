BUCKET_HITS_AGGREGATION = {
    "took": 560,
    "timed_out": False,
    "_shards": {
        "total": 861,
        "successful": 861,
        "skipped": 806,
        "failed": 0
    },
    "hits": {
        "total": 14,
        "max_score": 11.39674,
        "hits": [
            {
                "_index": "s3logs-2018.04.25",
                "_type": "s3-access-log",
                "_id": "AWL8niuzVNAApOu8LF1D",
                "_score": 11.39674,
                "_source": {
                    "request_header_user_agent": "libcurl/7.57.0 r-curl/3.0 httr/1.3.1",
                    "request_method": "GET",
                    "error": None,
                    "turnaround_time": "112",
                    "remote_ip": "34.251.212.33",
                    "time_received": "2018-04-25T10:39:17+00:00",
                    "request_first_line": "GET /alpha-app-sentencing-policy-model/base_data.csv HTTP/1.1",
                    "total_bytes": "20065578",
                    "total_time": "367",
                    "request_header_referer": None,
                    "s3_request_id": "C9383271F55F4EFC",
                    "key": "base_data.csv",
                    "geoip": {
                        "continent_name": "North America",
                        "city_name": "Houston",
                        "country_iso_code": "US",
                        "region_name": "Texas",
                        "location": {
                            "lon": -95.5858,
                            "lat": 29.6997
                        }
                    },
                    "version_id": None,
                    "request_url": "/alpha-app-sentencing-policy-model/base_data.csv",
                    "bucket": "alpha-app-sentencing-policy-model",
                    "bytes": "20065578",
                    "bucket_owner": "7040326b5ad7aa545c783bfa4b4b015c3588d829d66caea8df056f6175115082",
                    "operation": "REST.GET.OBJECT",
                    "requester_id": "arn:aws:sts::593291632749:assumed-role/alpha_app_sentencing-policy-model/5487346a-alpha_app_sentencing-policy-model",
                    "request_http_ver": "1.1",
                    "status": "200"
                }
            }
            ,
            {
                "_index": "s3logs-2018.04.25",
                "_type": "s3-access-log",
                "_id": "AWL8nix6VNAApOu8LF2q",
                "_score": 11.321399,
                "_source": {
                    "request_header_user_agent": "libcurl/7.57.0 r-curl/3.0 httr/1.3.1",
                    "request_method": "GET",
                    "error": None,
                    "turnaround_time": "72",
                    "remote_ip": "34.251.212.33",
                    "time_received": "2018-04-25T10:39:19+00:00",
                    "request_first_line": "GET /alpha-app-sentencing-policy-model/base_data.csv HTTP/1.1",
                    "total_bytes": "20065578",
                    "total_time": "308",
                    "request_header_referer": None,
                    "s3_request_id": "40C441D4C103012B",
                    "key": "base_data.csv",
                    "geoip": {
                        "continent_name": "North America",
                        "city_name": "Houston",
                        "country_iso_code": "US",
                        "region_name": "Texas",
                        "location": {
                            "lon": -95.5858,
                            "lat": 29.6997
                        }
                    },
                    "version_id": None,
                    "request_url": "/alpha-app-sentencing-policy-model/base_data.csv",
                    "bucket": "alpha-app-sentencing-policy-model",
                    "bytes": "20065578",
                    "bucket_owner": "7040326b5ad7aa545c783bfa4b4b015c3588d829d66caea8df056f6175115082",
                    "operation": "REST.GET.OBJECT",
                    "requester_id": "arn:aws:sts::593291632749:assumed-role/alpha_app_sentencing-policy-model/5487346a-alpha_app_sentencing-policy-model",
                    "request_http_ver": "1.1",
                    "status": "200"
                }
            }
            ,
            {
                "_index": "s3logs-2018.04.19",
                "_type": "s3-access-log",
                "_id": "AWLdbwC3VNAApOu8ocEJ",
                "_score": 11.253059,
                "_source": {
                    "request_header_user_agent": "libcurl/7.57.0 r-curl/3.0 httr/1.3.1",
                    "request_method": "GET",
                    "error": None,
                    "turnaround_time": "25",
                    "remote_ip": "34.250.17.221",
                    "time_received": "2018-04-19T09:14:44+00:00",
                    "request_first_line": "GET /alpha-app-sentencing-policy-model/prison_pop.csv HTTP/1.1",
                    "total_bytes": "718",
                    "total_time": "26",
                    "request_header_referer": None,
                    "s3_request_id": "6FD2B9DAA2DA138A",
                    "key": "prison_pop.csv",
                    "geoip": {
                        "continent_name": "North America",
                        "city_name": "Houston",
                        "country_iso_code": "US",
                        "region_name": "Texas",
                        "location": {
                            "lon": -95.5858,
                            "lat": 29.6997
                        }
                    },
                    "version_id": None,
                    "request_url": "/alpha-app-sentencing-policy-model/prison_pop.csv",
                    "bucket": "alpha-app-sentencing-policy-model",
                    "bytes": "718",
                    "bucket_owner": "7040326b5ad7aa545c783bfa4b4b015c3588d829d66caea8df056f6175115082",
                    "operation": "REST.GET.OBJECT",
                    "requester_id": "arn:aws:sts::593291632749:assumed-role/alpha_app_sentencing-policy-model/e33d655d-alpha_app_sentencing-policy-model",
                    "request_http_ver": "1.1",
                    "status": "200"
                }
            }
            ,
            {
                "_index": "s3logs-2018.04.19",
                "_type": "s3-access-log",
                "_id": "AWLeVO4MVNAApOu884IR",
                "_score": 11.253059,
                "_source": {
                    "request_header_user_agent": "libcurl/7.57.0 r-curl/3.0 httr/1.3.1",
                    "request_method": "GET",
                    "error": None,
                    "turnaround_time": "32",
                    "remote_ip": "34.250.17.221",
                    "time_received": "2018-04-19T13:35:59+00:00",
                    "request_first_line": "GET /alpha-app-sentencing-policy-model/projection.csv HTTP/1.1",
                    "total_bytes": "1411",
                    "total_time": "33",
                    "request_header_referer": None,
                    "s3_request_id": "872A497DE205D529",
                    "key": "projection.csv",
                    "geoip": {
                        "continent_name": "North America",
                        "city_name": "Houston",
                        "country_iso_code": "US",
                        "region_name": "Texas",
                        "location": {
                            "lon": -95.5858,
                            "lat": 29.6997
                        }
                    },
                    "version_id": None,
                    "request_url": "/alpha-app-sentencing-policy-model/projection.csv",
                    "bucket": "alpha-app-sentencing-policy-model",
                    "bytes": "1411",
                    "bucket_owner": "7040326b5ad7aa545c783bfa4b4b015c3588d829d66caea8df056f6175115082",
                    "operation": "REST.GET.OBJECT",
                    "requester_id": "arn:aws:sts::593291632749:assumed-role/alpha_app_sentencing-policy-model/e33d655d-alpha_app_sentencing-policy-model",
                    "request_http_ver": "1.1",
                    "status": "200"
                }
            }
            ,
            {
                "_index": "s3logs-2018.04.19",
                "_type": "s3-access-log",
                "_id": "AWLdan_CFi8cP14IdNGu",
                "_score": 10.490343,
                "_source": {
                    "request_header_user_agent": "libcurl/7.57.0 r-curl/3.0 httr/1.3.1",
                    "request_method": "GET",
                    "error": None,
                    "turnaround_time": "104",
                    "remote_ip": "34.250.17.221",
                    "time_received": "2018-04-19T09:15:33+00:00",
                    "request_first_line": "GET /alpha-app-sentencing-policy-model/base_data.csv HTTP/1.1",
                    "total_bytes": "20065578",
                    "total_time": "354",
                    "request_header_referer": None,
                    "s3_request_id": "7387188E48C3BE7F",
                    "key": "base_data.csv",
                    "geoip": {
                        "continent_name": "North America",
                        "city_name": "Houston",
                        "country_iso_code": "US",
                        "region_name": "Texas",
                        "location": {
                            "lon": -95.5858,
                            "lat": 29.6997
                        }
                    },
                    "version_id": None,
                    "request_url": "/alpha-app-sentencing-policy-model/base_data.csv",
                    "bucket": "alpha-app-sentencing-policy-model",
                    "bytes": "20065578",
                    "bucket_owner": "7040326b5ad7aa545c783bfa4b4b015c3588d829d66caea8df056f6175115082",
                    "operation": "REST.GET.OBJECT",
                    "requester_id": "arn:aws:sts::593291632749:assumed-role/alpha_app_sentencing-policy-model/1d233a54-alpha_app_sentencing-policy-model",
                    "request_http_ver": "1.1",
                    "status": "200"
                }
            }
            ,
            {
                "_index": "s3logs-2018.04.19",
                "_type": "s3-access-log",
                "_id": "AWLdbv_KVNAApOu8ocD_",
                "_score": 10.490343,
                "_source": {
                    "request_header_user_agent": "libcurl/7.57.0 r-curl/3.0 httr/1.3.1",
                    "request_method": "GET",
                    "error": None,
                    "turnaround_time": "103",
                    "remote_ip": "34.250.17.221",
                    "time_received": "2018-04-19T09:14:43+00:00",
                    "request_first_line": "GET /alpha-app-sentencing-policy-model/base_data.csv HTTP/1.1",
                    "total_bytes": "20065578",
                    "total_time": "201",
                    "request_header_referer": None,
                    "s3_request_id": "641D5FCFFB1D82DC",
                    "key": "base_data.csv",
                    "geoip": {
                        "continent_name": "North America",
                        "city_name": "Houston",
                        "country_iso_code": "US",
                        "region_name": "Texas",
                        "location": {
                            "lon": -95.5858,
                            "lat": 29.6997
                        }
                    },
                    "version_id": None,
                    "request_url": "/alpha-app-sentencing-policy-model/base_data.csv",
                    "bucket": "alpha-app-sentencing-policy-model",
                    "bytes": "20065578",
                    "bucket_owner": "7040326b5ad7aa545c783bfa4b4b015c3588d829d66caea8df056f6175115082",
                    "operation": "REST.GET.OBJECT",
                    "requester_id": "arn:aws:sts::593291632749:assumed-role/alpha_app_sentencing-policy-model/e33d655d-alpha_app_sentencing-policy-model",
                    "request_http_ver": "1.1",
                    "status": "200"
                }
            }
            ,
            {
                "_index": "s3logs-2018.04.19",
                "_type": "s3-access-log",
                "_id": "AWLeVPChVNAApOu884J0",
                "_score": 10.490343,
                "_source": {
                    "request_header_user_agent": "libcurl/7.57.0 r-curl/3.0 httr/1.3.1",
                    "request_method": "GET",
                    "error": None,
                    "turnaround_time": "235",
                    "remote_ip": "34.250.17.221",
                    "time_received": "2018-04-19T13:35:59+00:00",
                    "request_first_line": "GET /alpha-app-sentencing-policy-model/base_data.csv HTTP/1.1",
                    "total_bytes": "20065578",
                    "total_time": "355",
                    "request_header_referer": None,
                    "s3_request_id": "DBC34C794BD79846",
                    "key": "base_data.csv",
                    "geoip": {
                        "continent_name": "North America",
                        "city_name": "Houston",
                        "country_iso_code": "US",
                        "region_name": "Texas",
                        "location": {
                            "lon": -95.5858,
                            "lat": 29.6997
                        }
                    },
                    "version_id": None,
                    "request_url": "/alpha-app-sentencing-policy-model/base_data.csv",
                    "bucket": "alpha-app-sentencing-policy-model",
                    "bytes": "20065578",
                    "bucket_owner": "7040326b5ad7aa545c783bfa4b4b015c3588d829d66caea8df056f6175115082",
                    "operation": "REST.GET.OBJECT",
                    "requester_id": "arn:aws:sts::593291632749:assumed-role/alpha_app_sentencing-policy-model/e33d655d-alpha_app_sentencing-policy-model",
                    "request_http_ver": "1.1",
                    "status": "200"
                }
            }
            ,
            {
                "_index": "s3logs-2018.04.19",
                "_type": "s3-access-log",
                "_id": "AWLdanyhFi8cP14IdNFp",
                "_score": 10.086214,
                "_source": {
                    "request_header_user_agent": "libcurl/7.57.0 r-curl/3.0 httr/1.3.1",
                    "request_method": "GET",
                    "error": None,
                    "turnaround_time": "38",
                    "remote_ip": "34.250.17.221",
                    "time_received": "2018-04-19T09:15:33+00:00",
                    "request_first_line": "GET /alpha-app-sentencing-policy-model/projection.csv HTTP/1.1",
                    "total_bytes": "1411",
                    "total_time": "40",
                    "request_header_referer": None,
                    "s3_request_id": "601A0A793210E130",
                    "key": "projection.csv",
                    "geoip": {
                        "continent_name": "North America",
                        "city_name": "Houston",
                        "country_iso_code": "US",
                        "region_name": "Texas",
                        "location": {
                            "lon": -95.5858,
                            "lat": 29.6997
                        }
                    },
                    "version_id": None,
                    "request_url": "/alpha-app-sentencing-policy-model/projection.csv",
                    "bucket": "alpha-app-sentencing-policy-model",
                    "bytes": "1411",
                    "bucket_owner": "7040326b5ad7aa545c783bfa4b4b015c3588d829d66caea8df056f6175115082",
                    "operation": "REST.GET.OBJECT",
                    "requester_id": "arn:aws:sts::593291632749:assumed-role/alpha_app_sentencing-policy-model/1d233a54-alpha_app_sentencing-policy-model",
                    "request_http_ver": "1.1",
                    "status": "200"
                }
            }
            ,
            {
                "_index": "s3logs-2018.04.19",
                "_type": "s3-access-log",
                "_id": "AWLdaoCyFi8cP14IdNI0",
                "_score": 10.086214,
                "_source": {
                    "request_header_user_agent": "libcurl/7.57.0 r-curl/3.0 httr/1.3.1",
                    "request_method": "GET",
                    "error": None,
                    "turnaround_time": "20",
                    "remote_ip": "34.250.17.221",
                    "time_received": "2018-04-19T09:15:33+00:00",
                    "request_first_line": "GET /alpha-app-sentencing-policy-model/prison_pop.csv HTTP/1.1",
                    "total_bytes": "718",
                    "total_time": "24",
                    "request_header_referer": None,
                    "s3_request_id": "B6B7E0BD55734884",
                    "key": "prison_pop.csv",
                    "geoip": {
                        "continent_name": "North America",
                        "city_name": "Houston",
                        "country_iso_code": "US",
                        "region_name": "Texas",
                        "location": {
                            "lon": -95.5858,
                            "lat": 29.6997
                        }
                    },
                    "version_id": None,
                    "request_url": "/alpha-app-sentencing-policy-model/prison_pop.csv",
                    "bucket": "alpha-app-sentencing-policy-model",
                    "bytes": "718",
                    "bucket_owner": "7040326b5ad7aa545c783bfa4b4b015c3588d829d66caea8df056f6175115082",
                    "operation": "REST.GET.OBJECT",
                    "requester_id": "arn:aws:sts::593291632749:assumed-role/alpha_app_sentencing-policy-model/1d233a54-alpha_app_sentencing-policy-model",
                    "request_http_ver": "1.1",
                    "status": "200"
                }
            }
            ,
            {
                "_index": "s3logs-2018.04.19",
                "_type": "s3-access-log",
                "_id": "AWLdbwGUFi8cP14IdbFv",
                "_score": 10.086214,
                "_source": {
                    "request_header_user_agent": "libcurl/7.57.0 r-curl/3.0 httr/1.3.1",
                    "request_method": "GET",
                    "error": None,
                    "turnaround_time": "36",
                    "remote_ip": "34.250.17.221",
                    "time_received": "2018-04-19T09:14:44+00:00",
                    "request_first_line": "GET /alpha-app-sentencing-policy-model/projection.csv HTTP/1.1",
                    "total_bytes": "1411",
                    "total_time": "37",
                    "request_header_referer": None,
                    "s3_request_id": "A28C0393EE9536A1",
                    "key": "projection.csv",
                    "geoip": {
                        "continent_name": "North America",
                        "city_name": "Houston",
                        "country_iso_code": "US",
                        "region_name": "Texas",
                        "location": {
                            "lon": -95.5858,
                            "lat": 29.6997
                        }
                    },
                    "version_id": None,
                    "request_url": "/alpha-app-sentencing-policy-model/projection.csv",
                    "bucket": "alpha-app-sentencing-policy-model",
                    "bytes": "1411",
                    "bucket_owner": "7040326b5ad7aa545c783bfa4b4b015c3588d829d66caea8df056f6175115082",
                    "operation": "REST.GET.OBJECT",
                    "requester_id": "arn:aws:sts::593291632749:assumed-role/alpha_app_sentencing-policy-model/e33d655d-alpha_app_sentencing-policy-model",
                    "request_http_ver": "1.1",
                    "status": "200"
                }
            }
            ,
            {
                "_index": "s3logs-2018.04.19",
                "_type": "s3-access-log",
                "_id": "AWLeVO-HVNAApOu884Jm",
                "_score": 10.086214,
                "_source": {
                    "request_header_user_agent": "libcurl/7.57.0 r-curl/3.0 httr/1.3.1",
                    "request_method": "GET",
                    "error": None,
                    "turnaround_time": "230",
                    "remote_ip": "34.250.17.221",
                    "time_received": "2018-04-19T13:35:59+00:00",
                    "request_first_line": "GET /alpha-app-sentencing-policy-model/prison_pop.csv HTTP/1.1",
                    "total_bytes": "718",
                    "total_time": "231",
                    "request_header_referer": None,
                    "s3_request_id": "9C95B118FF0F8F37",
                    "key": "prison_pop.csv",
                    "geoip": {
                        "continent_name": "North America",
                        "city_name": "Houston",
                        "country_iso_code": "US",
                        "region_name": "Texas",
                        "location": {
                            "lon": -95.5858,
                            "lat": 29.6997
                        }
                    },
                    "version_id": None,
                    "request_url": "/alpha-app-sentencing-policy-model/prison_pop.csv",
                    "bucket": "alpha-app-sentencing-policy-model",
                    "bytes": "718",
                    "bucket_owner": "7040326b5ad7aa545c783bfa4b4b015c3588d829d66caea8df056f6175115082",
                    "operation": "REST.GET.OBJECT",
                    "requester_id": "arn:aws:sts::593291632749:assumed-role/alpha_app_sentencing-policy-model/e33d655d-alpha_app_sentencing-policy-model",
                    "request_http_ver": "1.1",
                    "status": "200"
                }
            }
            ,
            {
                "_index": "s3logs-2018.04.18",
                "_type": "s3-access-log",
                "_id": "AWLYg33vFi8cP14InCdc",
                "_score": 8.207737,
                "_source": {
                    "request_header_user_agent": "libcurl/7.52.1 r-curl/3.0 httr/1.3.1",
                    "request_method": "GET",
                    "error": None,
                    "turnaround_time": "21",
                    "remote_ip": "34.250.17.221",
                    "time_received": "2018-04-18T10:35:44+00:00",
                    "request_first_line": "GET /alpha-app-sentencing-policy-model/ HTTP/1.1",
                    "total_bytes": None,
                    "total_time": "22",
                    "request_header_referer": None,
                    "s3_request_id": "5EC34B5F2DF1EDB1",
                    "key": None,
                    "geoip": {
                        "continent_name": "North America",
                        "city_name": "Houston",
                        "country_iso_code": "US",
                        "region_name": "Texas",
                        "location": {
                            "lon": -95.5858,
                            "lat": 29.6997
                        }
                    },
                    "version_id": None,
                    "request_url": "/alpha-app-sentencing-policy-model/",
                    "bucket": "alpha-app-sentencing-policy-model",
                    "bytes": "3393",
                    "bucket_owner": "7040326b5ad7aa545c783bfa4b4b015c3588d829d66caea8df056f6175115082",
                    "operation": "REST.GET.BUCKET",
                    "requester_id": "arn:aws:sts::593291632749:assumed-role/alpha_user_foobar/5acc32a6-alpha_user_foobar",
                    "request_http_ver": "1.1",
                    "status": "200"
                }
            }
            ,
            {
                "_index": "s3logs-2018.04.18",
                "_type": "s3-access-log",
                "_id": "AWLYkE1hFi8cP14IoTaY",
                "_score": 8.016539,
                "_source": {
                    "request_header_user_agent": "libcurl/7.52.1 r-curl/3.0 httr/1.3.1",
                    "request_method": "GET",
                    "error": None,
                    "turnaround_time": "13",
                    "remote_ip": "34.250.17.221",
                    "time_received": "2018-04-18T10:50:01+00:00",
                    "request_first_line": "GET /alpha-app-sentencing-policy-model/ HTTP/1.1",
                    "total_bytes": None,
                    "total_time": "14",
                    "request_header_referer": None,
                    "s3_request_id": "18842F34558F72D7",
                    "key": None,
                    "geoip": {
                        "continent_name": "North America",
                        "city_name": "Houston",
                        "country_iso_code": "US",
                        "region_name": "Texas",
                        "location": {
                            "lon": -95.5858,
                            "lat": 29.6997
                        }
                    },
                    "version_id": None,
                    "request_url": "/alpha-app-sentencing-policy-model/",
                    "bucket": "alpha-app-sentencing-policy-model",
                    "bytes": "3393",
                    "bucket_owner": "7040326b5ad7aa545c783bfa4b4b015c3588d829d66caea8df056f6175115082",
                    "operation": "REST.GET.BUCKET",
                    "requester_id": "arn:aws:sts::593291632749:assumed-role/alpha_user_foobar/5acc32a6-alpha_user_foobar",
                    "request_http_ver": "1.1",
                    "status": "200"
                }
            }
            ,
            {
                "_index": "s3logs-2018.04.18",
                "_type": "s3-access-log",
                "_id": "AWLYoOIhFi8cP14Ip4eP",
                "_score": 8.016539,
                "_source": {
                    "request_header_user_agent": "libcurl/7.52.1 r-curl/3.0 httr/1.3.1",
                    "request_method": "GET",
                    "error": None,
                    "turnaround_time": "14",
                    "remote_ip": "34.250.17.221",
                    "time_received": "2018-04-18T10:49:08+00:00",
                    "request_first_line": "GET /alpha-app-sentencing-policy-model/ HTTP/1.1",
                    "total_bytes": None,
                    "total_time": "14",
                    "request_header_referer": None,
                    "s3_request_id": "C893B33FBC55B26D",
                    "key": None,
                    "geoip": {
                        "continent_name": "North America",
                        "city_name": "Houston",
                        "country_iso_code": "US",
                        "region_name": "Texas",
                        "location": {
                            "lon": -95.5858,
                            "lat": 29.6997
                        }
                    },
                    "version_id": None,
                    "request_url": "/alpha-app-sentencing-policy-model/",
                    "bucket": "alpha-app-sentencing-policy-model",
                    "bytes": "3393",
                    "bucket_owner": "7040326b5ad7aa545c783bfa4b4b015c3588d829d66caea8df056f6175115082",
                    "operation": "REST.GET.BUCKET",
                    "requester_id": "arn:aws:sts::593291632749:assumed-role/alpha_user_foobar/5acc32a6-alpha_user_foobar",
                    "request_http_ver": "1.1",
                    "status": "200"
                }
            }
        ]
    },
    "aggregations": {
        "bucket_hits": {
            "doc_count_error_upper_bound": 0,
            "sum_other_doc_count": 0,
            "buckets": [
                {
                    "key": "arn:aws:sts::593291632749:assumed-role/alpha_app_sentencing-policy-model/e33d655d-alpha_app_sentencing-policy-model",
                    "doc_count": 6
                }
                ,
                {
                    "key": "arn:aws:sts::593291632749:assumed-role/alpha_app_sentencing-policy-model/1d233a54-alpha_app_sentencing-policy-model",
                    "doc_count": 3
                }
                ,
                {
                    "key": "arn:aws:sts::593291632749:assumed-role/alpha_user_foobar/5acc32a6-alpha_user_foobar",
                    "doc_count": 3
                }
                ,
                {
                    "key": "arn:aws:sts::593291632749:assumed-role/alpha_app_sentencing-policy-model/5487346a-alpha_app_sentencing-policy-model",
                    "doc_count": 2
                }
            ]
        }
    }
}
