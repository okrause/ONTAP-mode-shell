# gcnv-client

Auth and REST client for Google Cloud NetApp Volumes ONTAP-mode storage pools.

## Basic usage

```python
from gcnv_client import NetappVolumes, OntapModePool, configure_logging

configure_logging()
nv = NetappVolumes(project="my-project")
pool = OntapModePool(nv, "/locations/us-central1/storagePools/my-pool")
print(pool.ontap_cli("volume show"))
```

## Pool resource names

Parse a full Google Cloud storage pool URN into project, location, and pool name:

```python
from gcnv_client import parse_storage_pool_urn

parsed = parse_storage_pool_urn(
    "projects/my-project/locations/us-east1-b/storagePools/my-pool"
)
# parsed.project → "my-project"
# parsed.location → "us-east1-b"
# parsed.pool_name → "my-pool"
# parsed.api_path → "/locations/us-east1-b/storagePools/my-pool"
```

Accepted forms include leading `/`, short `locations/.../storagePools/...` (no project segment), and full HTTPS URLs.

The `ontap-mode-shell` and root `ontap_cli.py` entry points accept `--pool-urn` using this parser.

## Empty CLI results (HTTP 404)

When `ontap_cli()` receives HTTP 404 with `"entry doesn't exist"`, it returns an empty string instead of the error text. Callers should print only non-empty results — a `show` with no matching objects produces no output, matching native ONTAP behavior.
