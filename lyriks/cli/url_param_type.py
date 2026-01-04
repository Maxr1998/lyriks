from urllib.parse import urlparse

from click.types import StringParamType


class UrlParamType(StringParamType):
    name = "url"

    def convert(self, value, param, ctx):
        value = super().convert(value, param, ctx)

        (scheme, netloc, path, params, query, fragment) = urlparse(value)
        if scheme not in ('http', 'https') or not netloc:
            self.fail(f'{value!r} is not a valid URL')

        return value.removesuffix("/")


URL = UrlParamType()
