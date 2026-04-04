from django.test import SimpleTestCase


class V33StructuralContractsTests(SimpleTestCase):
    def test_application_package_exports_v33_structural_entrypoints(self):
        from wms import application

        self.assertTrue(hasattr(application, "scan"))
        self.assertTrue(hasattr(application, "pilotage"))
        self.assertTrue(hasattr(application, "portal"))
        self.assertTrue(hasattr(application, "planning"))
        self.assertTrue(hasattr(application, "parties"))
        self.assertTrue(hasattr(application, "planning_artifacts"))

    def test_v33_packages_export_public_runtime_facades(self):
        from wms import artifacts, events, jobs, parties

        self.assertTrue(hasattr(events, "RuntimeEvent"))
        self.assertTrue(hasattr(events, "build_shipment_status_changed_event"))
        self.assertTrue(hasattr(events, "enqueue_integration_event"))

        self.assertTrue(hasattr(jobs, "record_job_run"))
        self.assertTrue(hasattr(jobs, "run_refresh_ops_pilotage_job"))
        self.assertTrue(hasattr(jobs, "run_print_artifact_queue_job"))

        self.assertTrue(hasattr(parties, "validated_recipient_organizations_for_destination"))
        self.assertTrue(hasattr(parties, "merge_recipient_organizations"))
        self.assertTrue(hasattr(parties, "sync_portal_recipient_graph"))

        self.assertTrue(hasattr(artifacts, "build_planning_artifacts"))
        self.assertTrue(hasattr(artifacts, "planning_pdf_delivery_state"))
        self.assertTrue(hasattr(artifacts, "build_print_artifact_sync_summary"))
