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

