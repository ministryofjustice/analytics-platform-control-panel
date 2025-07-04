def test_get_status_page_posts(PagerdutyClient):
    result = PagerdutyClient.get_status_page_posts("test-id")
    assert len(result) == 2
    maintenance = result[0]
    assert maintenance["post_type"] == "maintenance"
    incident = result[1]
    assert incident["post_type"] == "incident"
