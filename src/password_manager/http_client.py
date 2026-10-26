"""Bounded HTTPS; HTTP failures never include request bodies or bearer tokens."""
import json
import urllib.error
import urllib.request

from .errors import VaultError


class HttpError(VaultError):
    def __init__(self, status=0):
        self.status = status
        super().__init__(f"Ошибка сети или Google API (код {status}). Локальные данные сохранены; повторите синхронизацию позже.")


def request(method, url, *, headers=None, body=None, limit=5 * 1024 * 1024, cancel=None):
    if not url.startswith("https://"):
        raise HttpError()
    if cancel is not None and cancel.is_set():
        raise HttpError()
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    # Do not forward Authorization to redirects, even on another HTTPS host.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs): return None
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=20) as response:
            data = response.read(limit + 1)
            if len(data) > limit:
                raise HttpError()
            return data
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
        raise HttpError(status) from None
    except (OSError, ValueError, urllib.error.URLError):
        raise HttpError() from None


def json_request(method, url, **kwargs):
    from .crypto import parse
    data = request(method, url, **kwargs)
    result = parse(data)
    if not isinstance(result, dict):
        raise HttpError()
    return result
