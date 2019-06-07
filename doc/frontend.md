# Frontend app

The Control Panel Frontend is a OIDC login protected web application which
allows users of the Analytical Platform to manage their hosted tools (including
RStudio and Jupyter Lab), web apps and data sources. It also provides an admin
interface for superusers to manage other users.

## Contributing

### GOV.UK Frontend

The Frontend app makes use of the
[GOV.UK Frontend](https://design-system.service.gov.uk/get-started/production/)
design system to markup and style the web interface.

We install GOV.UK Frontend using npm, to easily track updated releases. The npm
package is automatically installed as part of the Docker image build.

We use the SASS styles and Javascript sources directly, but because the Nunjucks
templates are not entirely compatible with Jinja2, we cannot use them (although
we can derive Jinja2 templates from them fairly trivially).
