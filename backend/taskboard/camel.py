import re
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer

_camel_re = re.compile(r'_([a-z])')
_snake_re = re.compile(r'([A-Z])')


def to_camel(key):
    if not isinstance(key, str):
        return key
    return _camel_re.sub(lambda m: m.group(1).upper(), key)


def to_snake(key):
    if not isinstance(key, str):
        return key
    return _snake_re.sub(lambda m: '_' + m.group(1).lower(), key)


def camelize(data):
    if isinstance(data, list):
        return [camelize(item) for item in data]
    if isinstance(data, dict):
        return {to_camel(k): camelize(v) for k, v in data.items()}
    return data


def underscoreize(data):
    if isinstance(data, list):
        return [underscoreize(item) for item in data]
    if isinstance(data, dict):
        return {to_snake(k): underscoreize(v) for k, v in data.items()}
    return data


class CamelCaseJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        return super().render(camelize(data), accepted_media_type, renderer_context)


class CamelCaseJSONParser(JSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        return underscoreize(super().parse(stream, media_type, parser_context))
