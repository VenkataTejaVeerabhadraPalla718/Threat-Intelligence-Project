# Labs 5–6 website integration

Labs 5 and 6 are registered in the existing SENTINEL-X LabOps allow-listed background runner. The website lists Labs 1–18, exposes a Run action for each activity, streams stdout/stderr to the live console, persists outputs in `lab_jobs` and `experiment_runs`, and supports viewing/downloading previous output and exporting execution history.

The new scripts use isolated databases `lab5_sales_analytics` and `lab6_indexing`, with the runner passing the existing `MONGO_URI` as `MONGODB_URI`. The shared `cti` threat collections are not used by these exercises.

Deploy by copying the updated project files into the existing project folder while preserving `.env` and Docker volumes, then rebuilding only the API: `docker compose up -d --build api`. Never use `docker compose down -v`.
