"""ONTAP-mode storage pool client."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from time import sleep
from typing import Any

import requests

from gcnv_client.volumes import NetappVolumes

logger = logging.getLogger(__name__)

_LIF_SERVICE_NAS = frozenset({"data_nfs", "data_cifs", "data_s3_server"})
_LIF_SERVICE_SAN = frozenset({"data_iscsi", "data_nvme_tcp"})


@dataclass(frozen=True)
class OntapLif:
    name: str
    address: str
    service: str
    ipspace: str


def classify_lif_service(services: list[str]) -> str:
    """Map ONTAP LIF services to a display service type."""
    service_set = set(services)
    if "intercluster_core" in service_set:
        return "intercluster"
    if "cluster_mgmt" in service_set:
        return "cluster_mgmt"
    if service_set & _LIF_SERVICE_NAS:
        return "NAS"
    if service_set & _LIF_SERVICE_SAN:
        return "SAN"
    return ",".join(sorted(services))


class OntapModePool:
    """Google Cloud NetApp Volumes Flex Unified ONTAP-mode storage pool.

    See https://cloud.google.com/netapp/volumes/docs/ontap-mode/reference/rest
    """

    netappvolumes: NetappVolumes
    google_pool_urn: str
    ontap_cluster_name: str
    ontap_svms: dict[str, str]
    ontap_aggregates: dict[str, list[str]]
    ontap_lifs: list[OntapLif]

    def __init__(self, netappvolumes: NetappVolumes, google_pool_urn: str) -> None:
        self.netappvolumes = netappvolumes
        self.google_pool_urn = google_pool_urn
        cluster = self.ontap_get("/cluster")
        self.ontap_cluster_name = cluster["name"]
        svms = self.ontap_get("/svm/svms?ontap_fields=uuid,name,aggregates")
        self.ontap_svms = {svm["name"]: svm["uuid"] for svm in svms}
        self.ontap_aggregates = {
            svm["name"]: [agg["name"] for agg in svm["aggregates"]] for svm in svms
        }
        lifs = self.ontap_get(
            "/network/ip/interfaces?ontap_fields=name,ip.address,services,ipspace.name"
        )
        self.ontap_lifs = [
            OntapLif(
                name=lif["name"],
                address=lif["ip"]["address"],
                ipspace=lif["ipspace"]["name"],
                service=classify_lif_service(lif["services"]),
            )
            for lif in lifs
        ]

    def __str__(self) -> str:
        return (
            f"OntapModePool: Pool: {self.google_pool_urn}\n"
            f" SVMs: {list(self.ontap_svms.keys())}, "
            f"Aggregates: {self.ontap_aggregates}\n"
        )

    def wait_for_ontap_job(self, resp: requests.Response) -> Any:
        resp.raise_for_status()
        msg = resp.json()
        if "body" in msg:
            if "job" in msg["body"]:
                job_href = msg["body"]["job"]["_links"]["self"]["href"]
                job_state = "running"
                while job_state not in ("success", "failed"):
                    sleep(3)
                    job = self.netappvolumes.rest_get(
                        self.google_pool_urn + "/ontap" + job_href
                    )
                    job_state = job.json()["body"]["state"]
                if job_state != "success":
                    raise ValueError(
                        f"ONTAP Job {job_href} failed with status: {job_state}"
                    )
                description = job.json()["body"]["description"]
                for prefix in ("POST ", "PATCH ", "GET ", "DELETE "):
                    if description.startswith(prefix):
                        description = description[len(prefix) :]
                        break
                return self.ontap_get(description.removeprefix("/api"))
            return resp.json()["body"]
        return None

    def ontap_get(self, ontap_urn: str) -> dict | list[dict]:
        response = self.netappvolumes.rest_get(
            self.google_pool_urn + "/ontap/api" + ontap_urn
        )
        payload = response.json()
        logging.debug(payload)
        if "body" in payload:
            if "records" in payload["body"]:
                return payload["body"]["records"]
            return payload["body"]
        return payload

    def ontap_post(self, ontap_urn: str, payload: dict) -> dict:
        wrapped = {"body": payload}
        try:
            response = self.netappvolumes.rest_post(
                self.google_pool_urn + "/ontap/api" + ontap_urn, wrapped
            )
        except requests.exceptions.HTTPError as exc:
            return {"error": exc.response.json()["error"]["message"]}
        logging.debug(response.json())
        return self.wait_for_ontap_job(response)

    def ontap_cli(self, cli_command: str) -> Any:
        payload = {"input": cli_command}
        resp = self.ontap_post("/private/cli", payload)
        if "output" in resp:
            return resp["output"].removeprefix(
                "\n\nThis is your first recorded login.\n\n"
            )
        if "error" in resp:
            return resp["error"]
        return resp
