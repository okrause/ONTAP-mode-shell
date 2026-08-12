import pytest

from gcnv_client.pool_urn import format_storage_pool_urn, parse_storage_pool_urn


class TestParseStoragePoolUrn:
    def test_full_resource_name(self):
        parsed = parse_storage_pool_urn(
            "projects/netapp-gcnv-vsa-pas-50/locations/us-east1-b/storagePools/ok-ontap-source-pool"
        )
        assert parsed.project == "netapp-gcnv-vsa-pas-50"
        assert parsed.location == "us-east1-b"
        assert parsed.pool_name == "ok-ontap-source-pool"
        assert (
            parsed.api_path
            == "/locations/us-east1-b/storagePools/ok-ontap-source-pool"
        )

    def test_leading_slash(self):
        parsed = parse_storage_pool_urn(
            "/projects/p1/locations/us-central1/storagePools/pool-a"
        )
        assert parsed.project == "p1"
        assert parsed.location == "us-central1"
        assert parsed.pool_name == "pool-a"

    def test_short_form_without_project(self):
        parsed = parse_storage_pool_urn(
            "locations/us-east1-b/storagePools/ok-unified-ontap"
        )
        assert parsed.project is None
        assert parsed.location == "us-east1-b"
        assert parsed.pool_name == "ok-unified-ontap"

    def test_https_url(self):
        parsed = parse_storage_pool_urn(
            "https://netapp.googleapis.com/v1beta1/projects/p1/locations/us-east1-b/storagePools/pool1"
        )
        assert parsed.project == "p1"
        assert parsed.location == "us-east1-b"
        assert parsed.pool_name == "pool1"

    def test_empty_urn(self):
        with pytest.raises(ValueError, match="must not be empty"):
            parse_storage_pool_urn("   ")

    def test_invalid_urn(self):
        with pytest.raises(ValueError, match="Invalid storage pool URN"):
            parse_storage_pool_urn("projects/p1/locations/us-east1-b")


class TestFormatStoragePoolUrn:
    def test_builds_full_name_from_api_path(self):
        assert (
            format_storage_pool_urn(
                "my-project", "/locations/us-east1-b/storagePools/my-pool"
            )
            == "projects/my-project/locations/us-east1-b/storagePools/my-pool"
        )

    def test_passes_through_existing_full_name(self):
        full = "projects/p1/locations/us-east1-b/storagePools/pool1"
        assert format_storage_pool_urn("other-project", full) == full

