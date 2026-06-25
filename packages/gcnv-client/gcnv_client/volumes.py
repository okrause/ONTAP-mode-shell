"""Google Cloud NetApp Volumes REST API client."""

from __future__ import annotations

import json
import logging
import os

import requests

from gcnv_client.auth import BearerAuth

logger = logging.getLogger(__name__)


class NetappVolumes:
    """Manage Google Cloud NetApp Volumes REST resources.

    See https://cloud.google.com/netapp/volumes/docs/reference/rest
    """

    project: str | None = None
    projectId: str | None = None
    service_account: str | None = None
    token: BearerAuth | None = None
    baseurl: str | None = None
    apiversion: str = "v1beta1"
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/hal+json",
        "User-Agent": "ok-ontap-ssh",
    }

    def __init__(
        self, service_account: str | None = None, project: str | None = None
    ) -> None:
        self.token = BearerAuth()

        if project is None:
            project = self.token.getProjectID()

        self.projectId = project

        autopush = os.getenv("NETAPP_AUTOPUSH")
        if autopush:
            print("Using AutoPush/Sandbox environment with base URL:", autopush)
            self.baseurl = f"{autopush}/{self.apiversion}"
        else:
            self.baseurl = f"https://netapp.googleapis.com/{self.apiversion}"
        self.projecturl = self.baseurl + f"/projects/{self.projectId}"

    def __str__(self) -> str:
        return f"NetAppVolumes: Project: {self.projectId}\n"

    def getProjectID(self) -> str:
        return self.projectId

    def _log_response(self, resp: requests.Response, *args, **kwargs) -> None:
        if resp.status_code not in (200, 202):
            logging.warning("%s returned: %s", resp.url, resp.text)

    def rest_get(self, resource_path: str) -> requests.Response:
        logging.debug("GET %s", self.projecturl + resource_path)
        response = requests.get(
            self.projecturl + resource_path,
            headers=self.headers,
            auth=self.token,
            hooks={"response": self._log_response},
        )
        response.raise_for_status()
        return response

    def rest_post(self, resource_path: str, payload: dict) -> requests.Response:
        logging.debug(
            "POST %s with payload: %s",
            self.projecturl + resource_path,
            json.dumps(payload),
        )
        response = requests.post(
            self.projecturl + resource_path,
            headers=self.headers,
            auth=self.token,
            json=payload,
        )
        response.raise_for_status()
        return response
