# Python dictionary version (excerpt) of what you'd find in the helm
# repository index YAML file at
# $(helm home)/repository/cache/mojanalytics-index.yaml
#
# used for testing the `helm` module
#
# (see `helm home --help`)
HELM_MOJANALYTICS_INDEX = {
    "apiVersion": "v1",
    "entries": {
        "rstudio": [
            {
                "apiVersion": "v1",
                "appVersion": "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10",
                "created": "2020-05-18T10:28:14.187538013Z",
                "description": "RStudio with Auth0 authentication proxy",
                "digest": "283e735476479425a76634840d73024f83e9d0bed7f009cb18b87916a3b84741",
                "name": "rstudio",
                "urls": [
                    "http://moj-analytics-helm-repo.s3-website-eu-west-1.amazonaws.com/rstudio-2.2.5.tgz",
                ],
                "version": "2.2.5",
            },
            {
                "apiVersion": "v1",
                "created": "2018-05-18T16:05:37.748243984Z",
                "description": "A Helm chart for RStudio",
                "digest": "a2df2dfe7aa0d04a6d7de175b134cc2e1e3e1b930f8b2acfdbda52fb396a4329",
                "name": "rstudio",
                "urls": [
                    "https://ministryofjustice.github.io/analytics-platform-helm-charts/charts/rstudio-1.0.0.tgz",
                ],
                "version": "1.0.0",
            },
        ],
    },
}
