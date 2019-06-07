import requests


ORG_REPOS_API_URL = "https://api.github.com/orgs/{org}/repos"


class OrgRepositories:

    def __init__(self, org):
        self.org = org
        self.url = ORG_REPOS_API_URL.format(org=org)

    def __iter__(self):
        while self._fetch_page():
            for repo in self._page:
                yield repo

    def _fetch_page(self):
        if not self.url:
            return False

        response = requests.get(self.url)
        response.raise_for_status()
        self._page = response.json()
        self.url = self._next_url(response.headers)
        return True

    def _next_url(self, headers):
        links = headers.get("Link", "").split(",")
        for link in links:
            parts = link.strip().split("; ")
            if len(parts) == 2:
                if parts[1] == 'rel="next"':
                    return parts[0].strip("<>")
