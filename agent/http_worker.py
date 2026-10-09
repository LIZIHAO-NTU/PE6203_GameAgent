"""Trusted HTTP transport process. Nothing from the model is executed here."""
import base64
import json
import sys
import urllib.error
import urllib.request

from .provider import NoRedirect


def main():
    try:
        payload = json.loads(sys.stdin.buffer.read())
        request = urllib.request.Request(payload["url"], data=base64.b64decode(payload["body"]),
                                         headers=payload["headers"], method="POST")
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=payload["timeout"]) as response:
            body = response.read(3_000_001)
        if len(body) > 3_000_000:
            result = {"kind": "oversized_response"}
        else:
            result = {"kind": "ok", "body": base64.b64encode(body).decode("ascii")}
    except urllib.error.HTTPError as error:
        result = {"kind": "http_error", "status": error.code}
    except Exception as error:
        # Do not echo URLs, request bodies, headers, or exception text that may contain keys.
        result = {"kind": "transport_error", "error_type": type(error).__name__}
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
