## Project: https://hub.docker.com/r/venkatatejaveerabhadra718/nosql-labs-suite

# SENTINEL-X Kubernetes LabOps Website Integration

<!-- DOCKER-HUB-LINKS:START -->
## Docker Hub Links


<!-- DOCKER-HUB-LINKS:END -->


This is a targeted upgrade patch for the SENTINEL-X source bundle supplied in this conversation. It adds website control of the already-tested Kubernetes Lab16 -> Lab18 workflow.

## What it adds

- Admin-only **Start Lab16 -> Lab18** control on Lab 16 and Lab 18 detail pages.
- Kubernetes Python client in the API container; no `kubectl` binary is needed inside the container.
- Uses the reviewed `k8s/lab16-job.yaml` and `k8s/lab18-job.yaml` manifests.
- Creates a unique Kubernetes Job name for each workflow execution, so completed Jobs do not block future runs.
- Starts Lab18 only after Lab16 has succeeded. Lab16 failure prevents Lab18 from starting.
- Streams Kubernetes pod logs into the existing MongoDB `lab_jobs` history.
- Displays the latest workflow, both Kubernetes Job names/statuses, and execution output.
- Downloads the Lab18 Markdown report from the captured Job output.
- Resumes monitoring of existing Kubernetes Jobs after an API container restart; it does not rerun completed jobs.
- Removes the old local-subprocess Lab16/Lab18 entries from the normal experiment runner, preventing the old destructive Lab16 script from being launched from the website.

## Safety notes

- The new Lab16 script and manifests use the isolated datasets: `cti_hybrid.lab16_threats`, `cti.lab16_threat_by_id`, `cti.lab16_threats_by_platform`, and Neo4j `Lab16*` labels.
- No database volumes are removed or recreated.
- No `docker compose down -v`, prune, or database reset commands are used.
- The Kubernetes API credential is mounted read-only from the Windows user's `.kube` directory. Do not share the kubeconfig file.
- The API server hostname is set to `https://kubernetes.docker.internal:6443`, matching the Docker Desktop endpoint verified for this setup. If your `kubectl config view --minify` showed a different reachable endpoint, set `K8S_API_SERVER` in the project's `.env` to that exact endpoint.
- MongoDB in the Job manifests uses the observed primary at `host.docker.internal:27118`. If the replica-set primary changes, update both manifests before a new run.
- The Kubernetes client uses the kubeconfig's TLS credentials and keeps certificate verification enabled.

## Files in this patch

Copy these files into the existing project, preserving the folder structure:

- `backend/dashboard.py` (replace)
- `backend/lab_jobs.py` (replace)
- `backend/main.py` (replace)
- `backend/k8s_jobs.py` (new)
- `backend/requirements.txt` (replace; adds `kubernetes` and `PyYAML`)
- `Dockerfile` (replace; copies `k8s/` into the API image)
- `docker-compose.yml` (replace; mounts kubeconfig read-only and sets Kubernetes API environment)
- `frontend/js/app.js` (replace; adds the LabOps panel)
- `k8s/lab16-job.yaml` and `k8s/lab18-job.yaml` (new or replace with these reviewed manifests)

The files are full replacements based on the source bundle supplied for this integration. Back up your current versions before copying. Do not replace `.env`, database folders, Docker volumes, or any other project files.

## Installation on Windows PowerShell

1. Stop here if another lab workflow is currently running. Do not stop database containers.
2. Back up only the files being replaced:

   ```powershell
   $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
   New-Item -ItemType Directory -Force ".\backup-k8s-website-$stamp" | Out-Null
   Copy-Item .\backend\dashboard.py, .\backend\lab_jobs.py, .\backend\main.py, .\backend\requirements.txt, .\Dockerfile, .\docker-compose.yml, .\frontend\js\app.js ".\backup-k8s-website-$stamp\" -Force
   ```

3. Merge the patch folders into the project root. Allow replacement of the listed files. Create `backend\k8s_jobs.py` and the root `k8s` folder if needed.
4. Confirm the kubeconfig mount source exists:

   ```powershell
   Test-Path "$env:USERPROFILE\.kube\config"
   ```

5. Confirm the Docker Desktop Kubernetes endpoint is reachable from the host and that the API container can resolve it:

   ```powershell
   kubectl config view --minify -o jsonpath="{.clusters[0].cluster.server}"
   docker exec sentinelx-local-api python -c "import socket; print(socket.gethostbyname_ex('kubernetes.docker.internal'))"
   ```

6. If the endpoint returned by `kubectl config view` is not `https://kubernetes.docker.internal:6443`, add the actual endpoint to `.env` (do not overwrite other `.env` entries):

   ```dotenv
   K8S_API_SERVER=https://YOUR-VERIFIED-ENDPOINT:PORT
   ```

7. Rebuild and recreate **only the API service**, not its dependencies:

   ```powershell
   docker compose up -d --no-deps --build api
   ```

   This does not recreate MongoDB, Cassandra, or Neo4j. It does replace the API container.

8. Wait for the API health check:

   ```powershell
   docker compose ps api
   ```

9. Verify Kubernetes access from inside the rebuilt API container:

   ```powershell
   docker exec sentinelx-local-api python -c "from k8s_jobs import kubernetes_health; print(kubernetes_health())"
   ```

   Expected: `{'ok': True, ... 'message': 'Kubernetes API reachable and authenticated'}`.

10. Open the SENTINEL-X website, sign in as an administrator, and open **Lab 16 â€“ Polyglot persistence**. The new Kubernetes workflow panel appears above the existing Lab details.
11. Click **Start Lab16 -> Lab18**, confirm the prompt, and watch the live logs. Lab18 starts automatically only after Lab16 succeeds.
12. After the workflow status is `PASSED`, click **Benchmark report** to download the Markdown report.

## API routes

- `GET /api/dashboard/k8s/health`
- `POST /api/dashboard/k8s/workflow`
- `GET /api/dashboard/k8s/workflow/latest`
- `GET /api/dashboard/k8s/workflow/{workflow_id}`
- `GET /api/dashboard/k8s/workflow/{workflow_id}/report`

All routes require an authenticated administrator.

## Validation performed on this patch

- Python syntax compilation for the changed backend modules.
- JavaScript syntax check for `frontend/js/app.js`.
- YAML parsing for both Kubernetes Job manifests.

The patch has not been run against your live Windows Docker Desktop cluster from this build environment. The in-container health command in installation Step 9 is the required final connectivity test before starting a website-triggered workflow.




