from wms.jobs.runtime_tracking import record_job_run
from wms.workflow_projection import rebuild_shipment_workflow_projections


def run_rebuild_workflow_projection_job():
    return record_job_run(
        job_key="workflow_projection_rebuild",
        runner=rebuild_shipment_workflow_projections,
    )
