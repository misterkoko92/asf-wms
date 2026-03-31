from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("wms", "0101_workflowblockageclaim"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShipmentWorkflowProjection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(blank=True, default="", max_length=80)),
                ("tracking_token", models.UUIDField(blank=True, null=True)),
                ("destination_label", models.CharField(blank=True, default="", max_length=200)),
                ("shipment_status", models.CharField(blank=True, default="", max_length=40)),
                ("shipment_created_at", models.DateTimeField(blank=True, null=True)),
                ("planned_at", models.DateTimeField(blank=True, null=True)),
                ("boarding_ok_at", models.DateTimeField(blank=True, null=True)),
                ("received_correspondent_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("current_segment", models.CharField(blank=True, default="", max_length=40)),
                ("segment_started_at", models.DateTimeField(blank=True, null=True)),
                ("segment_age_hours", models.FloatField(default=0.0)),
                ("is_closed", models.BooleanField(default=False)),
                ("lead_hours_planned_to_boarding", models.FloatField(blank=True, null=True)),
                ("lead_hours_boarding_to_correspondent", models.FloatField(blank=True, null=True)),
                ("lead_hours_correspondent_to_delivery", models.FloatField(blank=True, null=True)),
                ("lead_hours_delivery_to_close", models.FloatField(blank=True, null=True)),
                ("lead_hours_total_to_delivery", models.FloatField(blank=True, null=True)),
                ("has_open_dispute", models.BooleanField(default=False)),
                ("dispute_reason", models.CharField(blank=True, default="", max_length=40)),
                ("dispute_owner", models.CharField(blank=True, default="", max_length=20)),
                ("dispute_opened_at", models.DateTimeField(blank=True, null=True)),
                ("dispute_resolved_at", models.DateTimeField(blank=True, null=True)),
                ("dispute_resolution_hours", models.FloatField(blank=True, null=True)),
                ("delay_state", models.CharField(blank=True, default="on_time", max_length=20)),
                ("current_delay_hours", models.FloatField(default=0.0)),
                ("active_blockage_category", models.CharField(blank=True, default="", max_length=32)),
                ("projected_at", models.DateTimeField(auto_now=True)),
                (
                    "destination",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="shipment_workflow_projections",
                        to="wms.destination",
                    ),
                ),
                (
                    "shipment",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workflow_projection",
                        to="wms.shipment",
                    ),
                ),
            ],
            options={
                "ordering": ["reference", "shipment_id"],
            },
        ),
        migrations.AddIndex(
            model_name="shipmentworkflowprojection",
            index=models.Index(
                fields=["shipment_status", "current_segment"],
                name="wms_shipwf_status_seg_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="shipmentworkflowprojection",
            index=models.Index(
                fields=["delay_state", "is_closed"],
                name="wms_shipwf_delay_closed_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="shipmentworkflowprojection",
            index=models.Index(
                fields=["has_open_dispute", "projected_at"],
                name="wms_shipwf_dispute_proj_idx",
            ),
        ),
    ]
