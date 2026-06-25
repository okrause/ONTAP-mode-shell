# gcnv-client

Auth and REST client for Google Cloud NetApp Volumes ONTAP-mode storage pools.

```python
from gcnv_client import NetappVolumes, OntapModePool, configure_logging

configure_logging()
nv = NetappVolumes(project="my-project")
pool = OntapModePool(nv, "/locations/us-central1/storagePools/my-pool")
print(pool.ontap_cli("volume show"))
```
