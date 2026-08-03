"""
The OpenAPI spec and the docs page it is rendered on.

flask-smorest builds the spec from the same marshmallow schemas that parse
incoming requests, so the documentation cannot describe a body the code
does not accept - there is one declaration, used twice, rather than a
description sitting next to an implementation and slowly disagreeing with
it. Routes and their path parameters come from the blueprints themselves,
so a new endpoint is documented the moment it is registered.

Responses are deliberately not schema'd. Every route already returns its
own shape with a `_links` map, and describing all of them would be a
second, hand-maintained account of what the code returns - exactly the
drift this setup exists to avoid. The spec says what a request must look
like, which is the half a caller has to get right.
"""
from flask import Flask
from flask_smorest import Api, Blueprint as SmorestBlueprint
from webargs.flaskparser import FlaskParser

IDEMPOTENCY_KEY = {
    'name': 'Idempotency-Key',
    'in': 'header',
    'required': False,
    'schema': {'type': 'string'},
    'description': (
        'Optional. Makes the request safe to retry: the work is done for '
        'whichever request claims the key first, and any repeat gets that '
        'same response back instead of acting twice.'
    ),
}

_SPEC_ROUTE = '/apispec_1.json'
_DOCS_ROUTE = '/apidocs/'

_PINNED_SCALAR_SRC = 'https://cdn.jsdelivr.net/npm/@scalar/api-reference@1.64.0'

_SCALAR_PAGE = f"""<!doctype html>
<html>
  <head>
    <title>Portfolio Manager API</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
  </head>
  <body>
    <div id="app"></div>
    <script src="{_PINNED_SCALAR_SRC}"></script>
    <script>
      Scalar.createApiReference('#app', {{ url: '{_SPEC_ROUTE}' }})
    </script>
  </body>
</html>
"""


class _Parser(FlaskParser):
    """
    webargs answers a failed validation with 422. Everything else in this
    API answers bad input with 400, and the client tells the two apart by
    status, so a second code for the same kind of failure would be a new
    case for no reason.
    """

    DEFAULT_VALIDATION_STATUS = 400


class Blueprint(SmorestBlueprint):
    """A smorest Blueprint that rejects bad input with 400."""

    ARGUMENTS_PARSER = _Parser()


def init_app(app: Flask) -> Api:
    """
    Configure the spec and serve the docs page.

    Returns the Api the blueprints must be registered on - registering
    through Flask directly would leave them out of the spec.
    """
    app.config.update(
        API_TITLE='Portfolio Manager API',
        API_VERSION='1.0.0',
        OPENAPI_VERSION='3.0.3',
        OPENAPI_URL_PREFIX='/',
        OPENAPI_JSON_PATH=_SPEC_ROUTE.lstrip('/'),
    )

    api = Api(app)

    @app.route(_DOCS_ROUTE)
    def apidocs() -> str:
        return _SCALAR_PAGE

    return api
