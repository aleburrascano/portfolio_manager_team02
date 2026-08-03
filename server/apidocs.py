"""
Interactive API documentation, served at /apidocs.

The route list is generated from Flask's own URL map rather than written out
by hand, so an endpoint added later is documented the moment it is
registered. That is the whole point of doing it this way: a checked-in
openapi.yaml drifts the first time somebody forgets to update it, and the
failure is silent - the endpoint simply isn't there.

What is deliberately not described is the shape of request and response
bodies. Those are read at runtime out of request.get_json(), so there is
nothing to introspect; claiming a shape here would be writing it by hand
under a different name, with the same drift. Each operation carries the
route, its method, its typed path parameters and its docstring.

The spec is rendered by Scalar rather than Swagger UI. Both read the same
document, so this is a change of reader, not of what is being said.
"""
import inspect
import re
from typing import Any, Dict, List

from flasgger import Swagger

# Matches a Werkzeug rule variable: <converter(args):name>, where both the
# converter and its arguments are optional.
_RULE_VARIABLE = re.compile(
    r'<(?:(?P<converter>[a-zA-Z_][a-zA-Z0-9_]*)(?:\([^)]*\))?:)?(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)>'
)

# Werkzeug's converters in the vocabulary OpenAPI uses for the same idea.
# Anything absent - string, path, uuid, or a custom converter - is a string.
_PARAM_TYPES = {'int': 'integer', 'float': 'number'}

# Flask's own static file handler is not part of the API.
_SKIP_ENDPOINTS = {'static'}

# HTTP methods Werkzeug adds on its own behalf rather than the route's.
_IMPLICIT_METHODS = {'HEAD', 'OPTIONS'}


def _openapi_path(rule: str) -> str:
    """`/users/<int:user_id>/balance` -> `/users/{user_id}/balance`."""
    return _RULE_VARIABLE.sub(lambda match: '{%s}' % match.group('name'), rule)


def _path_parameters(rule: str) -> List[Dict[str, Any]]:
    return [
        {
            'name': match.group('name'),
            'in': 'path',
            'required': True,
            'type': _PARAM_TYPES.get(match.group('converter') or '', 'string'),
        }
        for match in _RULE_VARIABLE.finditer(rule)
    ]


def _operation(view: Any, tag: str, parameters: List[Dict[str, Any]]) -> Dict[str, Any]:
    # getdoc normalises the indentation and drops the leading blank line, so
    # the first line is the summary and the rest - the Query/Body/Returns
    # prose the routes already carry - becomes the description.
    doc = inspect.getdoc(view) or ''
    lines = doc.splitlines()
    description = '\n'.join(lines[1:]).strip()

    operation: Dict[str, Any] = {
        'tags': [tag],
        'summary': lines[0].strip() if lines else '',
        # Swagger 2.0 requires a responses object for an operation to
        # validate at all. This says an endpoint answers, and nothing about
        # what it answers with.
        'responses': {'200': {'description': 'Successful response'}},
    }
    if description:
        operation['description'] = description
    if parameters:
        operation['parameters'] = parameters
    return operation


def _generate_paths(app: Any) -> Dict[str, Dict[str, Any]]:
    paths: Dict[str, Dict[str, Any]] = {}

    for rule in app.url_map.iter_rules():
        if rule.endpoint in _SKIP_ENDPOINTS:
            continue

        view = app.view_functions[rule.endpoint]
        # Blueprint-qualified endpoints group the UI by blueprint; the
        # health check at / is the only route without one.
        tag = rule.endpoint.split('.')[0] if '.' in rule.endpoint else 'health'
        parameters = _path_parameters(rule.rule)
        operations = paths.setdefault(_openapi_path(rule.rule), {})

        for method in sorted((rule.methods or set()) - _IMPLICIT_METHODS):
            operations[method.lower()] = _operation(view, tag, parameters)

    return paths


_SPEC_ROUTE = '/apispec_1.json'
_DOCS_ROUTE = '/apidocs/'

# Pinned rather than floating: an unpinned CDN URL means the docs page can
# change without anything in this repository changing. This is the only
# third-party request the project makes, and it is on an internal docs
# page - not in the client bundle, which deliberately has none.
_SCALAR_SRC = 'https://cdn.jsdelivr.net/npm/@scalar/api-reference@1.64.0'

_SCALAR_PAGE = f"""<!doctype html>
<html>
  <head>
    <title>Portfolio Manager API</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
  </head>
  <body>
    <div id="app"></div>
    <script src="{_SCALAR_SRC}"></script>
    <script>
      Scalar.createApiReference('#app', {{ url: '{_SPEC_ROUTE}' }})
    </script>
  </body>
</html>
"""


def init_app(app: Any) -> None:
    """
    Wire up the docs. Must be called after every blueprint is registered -
    the URL map is the source, so anything registered later is missed.

    Flasgger generates and serves the spec; its own Swagger UI is turned off
    and Scalar renders the same document instead. Two UIs over one spec
    would only be two things to keep in step.
    """
    Swagger(
        app,
        config={
            'headers': [],
            'specs': [
                {
                    'endpoint': 'apispec_1',
                    'route': _SPEC_ROUTE,
                    'rule_filter': lambda rule: True,
                    'model_filter': lambda tag: True,
                }
            ],
            'static_url_path': '/flasgger_static',
            'swagger_ui': False,
            'specs_route': _DOCS_ROUTE,
        },
        template={
            'swagger': '2.0',
            'info': {
                'title': 'Portfolio Manager API',
                'description': (
                    'Routes are generated from the application URL map. '
                    'Request and response bodies are described in each '
                    "endpoint's own description rather than as schemas."
                ),
                'version': '1.0.0',
            },
            'paths': _generate_paths(app),
        },
    )

    @app.route(_DOCS_ROUTE)
    def apidocs() -> str:
        return _SCALAR_PAGE
