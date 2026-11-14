# Department Inventory Manager

Streamlit app for tracking consumable / IT inventory, with SQLite persistence and Podman packaging.

## Features
- Add items (name, code, quantity); codes are unique and stored uppercase
- Update quantity (set exact value, or add/remove stock; never below zero)
- Search by name or code
- Archive / restore items (soft delete, so history is kept)
- Current stock table with **low-stock warning** (banner + highlighted rows)
  - Threshold is assigned via `LOW_STOCK_THRESHOLD` (default 10) and can be adjusted in the sidebar

## Run locally (no container)
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Run with Podman

### 1. Build the image
```bash
podman build -t inventory-app -f Containerfile .
```

### 2. Create a named volume (this holds the database)
```bash
podman volume create inventory-data
```

### 3. Run the container
```bash
podman run -d --name inventory \
  -p 8501:8501 \
  -v inventory-data:/data \
  -e LOW_STOCK_THRESHOLD=10 \
  inventory-app
```
Open http://localhost:8501

## Demonstrate persistence after container recreation

1. In the app, add a few items (e.g. `Toner Cartridge`, `TONER-01`, qty `4`; `USB Cable`, `USB-01`, qty `25`).
   The toner row should trigger the low-stock warning.
2. Destroy the container completely:
   ```bash
   podman stop inventory
   podman rm inventory
   podman ps -a          # confirm it is gone
   podman volume ls      # inventory-data still exists
   ```
3. Recreate it with the same command from step 3 above.
4. Refresh http://localhost:8501 — all items, quantities and archived state are still there.

Optional check from the host:
```bash
podman volume inspect inventory-data
podman exec inventory ls -l /data
```

## Cleanup
```bash
podman rm -f inventory
podman volume rm inventory-data   # deletes the data permanently
```

## Notes
- If `podman build` cannot pull the base image, make sure `docker.io` is in your registries, or use the fully-qualified name already in the Containerfile.
- For a bind mount instead of a named volume on SELinux systems (Fedora/RHEL), use `-v ./data:/data:Z`.
