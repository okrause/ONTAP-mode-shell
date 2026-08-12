from gcnv_client.pool import OntapModePool, classify_lif_service


class TestClassifyLifService:
    def test_intercluster(self):
        assert classify_lif_service(["intercluster_core"]) == "intercluster"

    def test_cluster_mgmt(self):
        assert classify_lif_service(["cluster_mgmt"]) == "cluster_mgmt"

    def test_data_nas(self):
        assert classify_lif_service(["data_nfs", "data_cifs"]) == "NAS"

    def test_data_san(self):
        assert classify_lif_service(["data_iscsi"]) == "SAN"

    def test_unknown_services_joined(self):
        assert classify_lif_service(["foo", "bar"]) == "bar,foo"


class TestSnapshotNames:
    def test_lists_snapshots_for_matching_volumes(self):
        pool = OntapModePool.__new__(OntapModePool)
        responses = {
            "/storage/volumes?ontap_fields=name,uuid,svm.name": [
                {"name": "vol1", "uuid": "uuid-1", "svm": {"name": "svm1"}},
                {"name": "vol2", "uuid": "uuid-2", "svm": {"name": "svm1"}},
            ],
            "/storage/volumes/uuid-1/snapshots?ontap_fields=name": [{"name": "snap-a"}],
            "/storage/volumes/uuid-2/snapshots?ontap_fields=name": [{"name": "snap-b"}],
        }
        pool.ontap_get = lambda urn: responses[urn]
        assert set(pool.snapshot_names()) == {"snap-a", "snap-b"}
        assert pool.snapshot_names(volume="vol1") == ["snap-a"]


class TestOntapCli:
    _EMPTY_404 = (
        'code: 404, message: {\n  "code":  404,\n  '
        '"message":  "entry doesn\'t exist"\n}'
    )

    def test_empty_result_returns_empty_string(self):
        pool = OntapModePool.__new__(OntapModePool)
        pool.ontap_post = lambda _urn, _payload: {"error": self._EMPTY_404}
        assert pool.ontap_cli("volume show -volume missing") == ""

    def test_other_errors_are_returned(self):
        pool = OntapModePool.__new__(OntapModePool)
        pool.ontap_post = lambda _urn, _payload: {"error": "code: 400, message: bad"}
        assert pool.ontap_cli("bad command") == "code: 400, message: bad"

    def test_successful_output_is_unchanged(self):
        pool = OntapModePool.__new__(OntapModePool)
        pool.ontap_post = lambda _urn, _payload: {"output": "volume show\n"}
        assert pool.ontap_cli("volume show") == "volume show\n"


class TestFullGooglePoolUrn:
    def test_full_urn_includes_project(self):
        pool = OntapModePool.__new__(OntapModePool)
        pool.netappvolumes = type("NV", (), {"projectId": "my-project"})()
        pool.google_pool_urn = "/locations/us-east1-b/storagePools/my-pool"
        assert (
            pool.full_google_pool_urn
            == "projects/my-project/locations/us-east1-b/storagePools/my-pool"
        )

