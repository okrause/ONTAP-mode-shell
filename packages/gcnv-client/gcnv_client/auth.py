"""Google Application Default Credentials bearer auth for NetApp Volumes API."""

from __future__ import annotations

import threading
import warnings

import google.auth
import google.auth.transport.requests
import requests


class BearerAuth(requests.auth.AuthBase):
    """Store, pass, and refresh JWT tokens for Google REST calls."""

    credentials = None
    projectID = None

    def __init__(self) -> None:
        self._lock = threading.Lock()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            credentials, project = google.auth.default()
            request = google.auth.transport.requests.Request()
            credentials.refresh(request)

        self.projectID = project
        self.credentials = credentials

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        request.headers["authorization"] = "Bearer " + self.get_token()
        return request

    def __str__(self) -> str:
        return self.get_token()

    def getProjectID(self) -> str:
        """Return project ID from Application Default Credentials."""
        return self.projectID

    def get_token(self) -> str:
        with self._lock:
            if self.credentials.expired:
                request = google.auth.transport.requests.Request()
                self.credentials.refresh(request)
        return self.credentials.token
