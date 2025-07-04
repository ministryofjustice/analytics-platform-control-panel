# Standard library
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Third-party
from django.conf import settings
from pagerduty import RestApiV2Client


class PagerdutyClient:

    maintenance_colour = "blue"
    incident_colour = "orange"

    def __init__(
        self,
    ):
        self.client = RestApiV2Client(settings.PAGERDUTY_TOKEN)
        self.statuses = None

    def get_status_page_posts(self, status_page_id):

        if self.statuses is None:
            self.statuses = self.get_status_page_statuses(status_page_id)

        response = self.client.get(
            f"status_pages/{status_page_id}/posts", params={"status": self.statuses}
        )
        response.raise_for_status()
        posts = response.json().get("posts", None)

        if len(posts) == 0:
            return None

        for post in posts:
            if post.get("post_type") == "maintenance":
                post["label_colour"] = self.maintenance_colour
                starts_at = (
                    datetime.strptime(post.get("starts_at"), "%Y-%m-%dT%H:%M:%SZ")
                    .replace(tzinfo=timezone.utc)
                    .astimezone(ZoneInfo("Europe/London"))
                )
                ends_at = (
                    datetime.strptime(post.get("ends_at"), "%Y-%m-%dT%H:%M:%SZ")
                    .replace(tzinfo=timezone.utc)
                    .astimezone(ZoneInfo("Europe/London"))
                )
                post["starts_at"] = starts_at.strftime("%-d %b %Y, %H:%M")
                post["ends_at"] = ends_at.strftime("%-d %b %Y, %H:%M")
            else:
                post["label_colour"] = self.incident_colour

        return posts

    def get_status_page_statuses(self, status_page_id):
        # Will get all status ids that don't represent a completed post
        response = self.client.get(f"status_pages/{status_page_id}/statuses", params={})
        response.raise_for_status()
        statuses = response.json()["statuses"]

        result = []
        ignore_list = ["completed", "resolved"]
        for status in statuses:
            if status["description"] not in ignore_list:
                result.append(status["id"])

        return result
