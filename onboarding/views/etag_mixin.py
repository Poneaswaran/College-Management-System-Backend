import hashlib
import json

from rest_framework import status


class ETagMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)

        if request.method != "GET":
            return response

        if response.status_code >= 400:
            return response

        try:
            data = getattr(response, "data", None)
            last_updated = None
            if isinstance(data, dict):
                for key in ["updated_at", "completed_at", "generated_at", "issued_at", "revoked_at"]:
                    if key in data and data[key]:
                        last_updated = str(data[key])
                        break

            payload = {
                "data": data,
                "last_updated": last_updated,
            }
            digest = hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
            etag = f'"{digest}"'

            if_none_match = request.headers.get("If-None-Match")
            if if_none_match == etag:
                response.status_code = status.HTTP_304_NOT_MODIFIED
                response.data = None
                response.content = b""

            response["ETag"] = etag
        except Exception:
            # ETag must never break endpoint behavior.
            return response

        return response
