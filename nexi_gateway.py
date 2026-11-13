"""Nexi HPP sandbox transport. Production endpoints are deliberately unsupported."""

import hashlib
import json
import re
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


SANDBOX_HOST = 'xpaysandbox.nexigroup.com'
SANDBOX_API = f'https://{SANDBOX_HOST}/api/phoenix-0.0/psp/api/v1'
ORDER_PATTERN = re.compile(r'^NX[a-f0-9]{16}$')


class NexiError(Exception):
    """A safe error: never exposes request headers, tokens or gateway payloads."""

    def __init__(self, status=None, uncertain=False):
        super().__init__('Nexi sandbox request failed')
        self.status = status
        self.uncertain = uncertain


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def token_digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def safe_checkout_url(value):
    if not isinstance(value, str) or len(value) > 4096:
        return False
    if any(char.isspace() or ord(char) < 32 for char in value):
        return False
    try:
        parsed = urlsplit(value)
        return bool(
            parsed.scheme == 'https'
            and parsed.hostname == SANDBOX_HOST
            and parsed.port in {None, 443}
            and not parsed.username and not parsed.password
            and not parsed.fragment
        )
    except ValueError:
        return False


def valid_public_origin(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return bool(
            parsed.scheme == 'https' and parsed.hostname
            and parsed.port in {None, 443}
            and not parsed.username and not parsed.password
            and parsed.path in {'', '/'}
            and not parsed.query and not parsed.fragment
        )
    except ValueError:
        return False


class NexiSandboxClient:
    def __init__(self, api_key, timeout=8):
        if not isinstance(api_key, str) or not api_key.strip():
            raise NexiError()
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, method, path, payload=None):
        body = json.dumps(payload).encode('utf-8') if payload is not None else None
        request = Request(
            SANDBOX_API + path,
            data=body,
            method=method,
            headers={
                'X-Api-Key': self.api_key,
                'Correlation-Id': str(uuid.uuid4()),
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        )
        try:
            with build_opener(NoRedirect()).open(request, timeout=self.timeout) as response:
                raw = response.read(262145)
                if len(raw) > 262144:
                    raise NexiError(uncertain=True)
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise NexiError(uncertain=True)
                return result
        except HTTPError as error:
            raise NexiError(error.code, uncertain=error.code >= 500) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise NexiError(uncertain=True) from None

    def create_checkout(self, order_id, amount_cents, origin, access_token):
        if not ORDER_PATTERN.fullmatch(order_id) or not valid_public_origin(origin):
            raise NexiError()
        if type(amount_cents) is not int or amount_cents <= 0:
            raise NexiError()
        result_url = f'{origin.rstrip("/")}/payments/nexi/sandbox/result/{access_token}'
        result = self._request('POST', '/orders/hpp', {
            'order': {'orderId': order_id, 'amount': str(amount_cents), 'currency': 'EUR'},
            'paymentSession': {
                'actionType': 'PAY',
                'captureType': 'IMPLICIT',
                'amount': str(amount_cents),
                'language': 'ITA',
                'recurrence': {'action': 'NO_RECURRING'},
                'resultUrl': f'{result_url}?orderId={order_id}',
                'cancelUrl': f'{result_url}?orderId={order_id}&cancel=1',
                'notificationUrl': f'{origin.rstrip("/")}/payments/nexi/sandbox/notification',
            },
        })
        security_token = result.get('securityToken')
        if (
            not safe_checkout_url(result.get('hostedPage'))
            or not isinstance(security_token, str)
            or not 16 <= len(security_token) <= 512
        ):
            raise NexiError(uncertain=True)
        return result['hostedPage'], token_digest(security_token)

    def get_order(self, order_id):
        if not ORDER_PATTERN.fullmatch(order_id):
            raise NexiError()
        return self._request('GET', '/orders/' + order_id)
