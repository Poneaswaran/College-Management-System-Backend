"""HTTP client service for communicating with the external AI microservice."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from typing import Any, Mapping

import requests
from django.conf import settings


class AIClientError(Exception):
    """Base exception type for AI client errors."""


class AIClientTemporaryError(AIClientError):
    """Error type representing transient failures that can be retried."""


class AIClientPermanentError(AIClientError):
    """Error type representing non-retriable failures."""


@dataclass(frozen=True)
class AIIngestResponse:
    """Parsed ingestion response payload."""

    document_id: str
    payload: dict[str, Any]


class AIClientService:
    """Client wrapper around the FastAPI AI worker endpoints."""

    def __init__(self, session: requests.Session | None = None) -> None:
        """Initialize the AI client from Django settings.

        Args:
            session: Optional pre-configured requests session for testing.
        """
        self._session = session or requests.Session()
        self._base_url = str(getattr(settings, "AI_SERVICE_BASE_URL", "")).rstrip("/")
        self._api_secret = str(getattr(settings, "AI_SERVICE_API_SECRET", ""))
        self._ingest_path = str(getattr(settings, "AI_SERVICE_INGEST_PATH", "/ingest"))
        self._query_path = str(getattr(settings, "AI_SERVICE_QUERY_PATH", "/query"))
        self._delete_path = str(getattr(settings, "AI_SERVICE_DELETE_PATH", "/delete"))
        self._source_header_value = str(
            getattr(settings, "AI_SERVICE_SOURCE_HEADER", "django-cms-backend")
        )

        connect_timeout = float(getattr(settings, "AI_SERVICE_CONNECT_TIMEOUT_SECONDS", 5))
        read_timeout = float(getattr(settings, "AI_SERVICE_TIMEOUT_SECONDS", 20))
        self._timeout = (connect_timeout, read_timeout)

    def ingest_document(
        self,
        *,
        file_name: str,
        file_bytes: bytes,
        metadata: Mapping[str, Any],
    ) -> AIIngestResponse:
        """Send a file to the ingestion endpoint.

        Args:
            file_name: Name of the uploaded file.
            file_bytes: Binary file content.
            metadata: Metadata fields sent with the multipart form.

        Returns:
            Parsed ingestion response containing external document id.

        Raises:
            AIClientTemporaryError: For transient transport or server failures.
            AIClientPermanentError: For invalid payloads or permanent HTTP failures.
        """
        content_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        files = {
            "file": (file_name, file_bytes, content_type),
        }
        form_data = {key: str(value) for key, value in metadata.items()}

        payload = self._request(
            method="POST",
            path=self._ingest_path,
            files=files,
            data=form_data,
        )

        document_id = (
            payload.get("document_id")
            or payload.get("vector_document_id")
            or payload.get("id")
        )
        if not document_id:
            raise AIClientPermanentError("Ingestion response missing document identifier.")

        return AIIngestResponse(document_id=str(document_id), payload=payload)

    def query_document(self, *, message: str, material_id: int) -> dict[str, Any]:
        """Execute a scoped question query against the AI service.

        Args:
            message: User's chat question.
            material_id: Study material id used as strict retrieval filter.

        Returns:
            Dictionary containing answer and sources.

        Raises:
            AIClientTemporaryError: For transient transport or server failures.
            AIClientPermanentError: For invalid payloads or permanent HTTP failures.
        """
        payload = self._request(
            method="POST",
            path=self._query_path,
            json_body={
                "message": message,
                "filters": {"material_id": material_id},
            },
        )

        answer = payload.get("answer", "")
        sources = payload.get("sources", [])
        if not isinstance(sources, list):
            sources = []

        return {
            "answer": str(answer),
            "sources": sources,
        }

    def delete_document_vectors(self, *, vector_document_id: str) -> None:
        """Delete document vectors in the AI service.

        Args:
            vector_document_id: External vector identifier.

        Raises:
            AIClientTemporaryError: For transient transport or server failures.
            AIClientPermanentError: For invalid payloads or permanent HTTP failures.
        """
        self._request(
            method="POST",
            path=self._delete_path,
            json_body={"vector_document_id": vector_document_id},
        )

    def _request(
        self,
        *,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        data: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request and normalize errors.

        Args:
            method: HTTP method.
            path: API path.
            json_body: Optional JSON body.
            files: Optional multipart files payload.
            data: Optional multipart form fields.

        Returns:
            Parsed JSON response dictionary.

        Raises:
            AIClientTemporaryError: For transient transport or server failures.
            AIClientPermanentError: For invalid configuration/payload/permanent failures.
        """
        if not self._base_url:
            raise AIClientPermanentError("AI_SERVICE_BASE_URL is not configured.")

        url = f"{self._base_url}{path if path.startswith('/') else '/' + path}"
        headers = {
            "X-Internal-Source": self._source_header_value,
        }
        if self._api_secret:
            headers["X-Internal-Secret"] = self._api_secret

        try:
            response = self._session.request(
                method=method,
                url=url,
                headers=headers,
                timeout=self._timeout,
                json=json_body,
                files=files,
                data=data,
            )
        except (requests.ConnectTimeout, requests.ReadTimeout, requests.Timeout) as exc:
            raise AIClientTemporaryError(f"AI service timeout: {exc}") from exc
        except requests.ConnectionError as exc:
            raise AIClientTemporaryError(f"AI service connection error: {exc}") from exc
        except requests.RequestException as exc:
            raise AIClientPermanentError(f"AI service request failed: {exc}") from exc

        if response.status_code >= 500 or response.status_code in {408, 429}:
            raise AIClientTemporaryError(
                f"AI service temporary failure ({response.status_code}): {response.text[:300]}"
            )

        if response.status_code >= 400:
            raise AIClientPermanentError(
                f"AI service rejected request ({response.status_code}): {response.text[:300]}"
            )

        if response.status_code == 204 or not response.content:
            return {}

        try:
            payload = response.json()
        except ValueError as exc:
            raise AIClientPermanentError("AI service returned an invalid JSON response.") from exc

        if not isinstance(payload, dict):
            raise AIClientPermanentError("AI service response payload must be a JSON object.")

        return payload
