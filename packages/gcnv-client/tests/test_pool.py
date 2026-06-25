from gcnv_client.pool import classify_lif_service


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
