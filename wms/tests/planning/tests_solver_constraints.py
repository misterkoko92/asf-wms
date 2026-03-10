from django.test import TestCase

from wms.planning.rules import compute_compatibility


class SolverConstraintTests(TestCase):
    def test_blank_slot_on_matching_date_is_incompatible(self):
        payload = {
            "shipments": [
                {
                    "snapshot_id": 101,
                    "destination_iata": "ABJ",
                    "carton_count": 2,
                    "equivalent_units": 2,
                }
            ],
            "volunteers": [
                {
                    "snapshot_id": 201,
                    "max_colis_vol": 4,
                    "availability_summary": {
                        "slots": [
                            {
                                "date": "2026-03-10",
                                "start_time": "",
                                "end_time": "",
                            }
                        ]
                    },
                }
            ],
            "flights": [
                {
                    "snapshot_id": 301,
                    "departure_date": "2026-03-10",
                    "departure_time": "10:00",
                    "destination_iata": "ABJ",
                    "capacity_units": 12,
                }
            ],
        }

        compatibility = compute_compatibility(payload)

        self.assertEqual(compatibility[101], [])

    def test_departure_time_requires_three_hour_mission_window(self):
        payload = {
            "shipments": [
                {
                    "snapshot_id": 101,
                    "destination_iata": "ABJ",
                    "carton_count": 2,
                    "equivalent_units": 2,
                }
            ],
            "volunteers": [
                {
                    "snapshot_id": 201,
                    "max_colis_vol": 4,
                    "availability_summary": {
                        "slots": [
                            {
                                "date": "2026-03-10",
                                "start_time": "08:00",
                                "end_time": "12:00",
                            }
                        ]
                    },
                }
            ],
            "flights": [
                {
                    "snapshot_id": 301,
                    "departure_date": "2026-03-10",
                    "departure_time": "10:00",
                    "destination_iata": "ABJ",
                    "capacity_units": 12,
                }
            ],
        }

        compatibility = compute_compatibility(payload)

        self.assertEqual(compatibility[101], [])

    def test_departure_time_outside_volunteer_slot_is_incompatible(self):
        payload = {
            "shipments": [
                {
                    "snapshot_id": 101,
                    "destination_iata": "ABJ",
                    "carton_count": 2,
                    "equivalent_units": 2,
                }
            ],
            "volunteers": [
                {
                    "snapshot_id": 201,
                    "max_colis_vol": 4,
                    "availability_summary": {
                        "slots": [
                            {
                                "date": "2026-03-10",
                                "start_time": "11:00",
                                "end_time": "11:05",
                            }
                        ]
                    },
                }
            ],
            "flights": [
                {
                    "snapshot_id": 301,
                    "departure_date": "2026-03-10",
                    "departure_time": "10:00",
                    "destination_iata": "ABJ",
                    "capacity_units": 12,
                }
            ],
        }

        compatibility = compute_compatibility(payload)

        self.assertEqual(compatibility[101], [])

    def test_shipment_exceeding_equivalent_capacity_per_volunteer_is_incompatible(self):
        payload = {
            "shipments": [
                {
                    "snapshot_id": 101,
                    "destination_iata": "ABJ",
                    "carton_count": 2,
                    "equivalent_units": 23,
                }
            ],
            "volunteers": [
                {
                    "snapshot_id": 201,
                    "availability_summary": {},
                    "max_colis_vol": None,
                }
            ],
            "flights": [
                {
                    "snapshot_id": 301,
                    "departure_date": "2026-03-10",
                    "destination_iata": "ABJ",
                    "capacity_units": 30,
                }
            ],
        }

        compatibility = compute_compatibility(payload)

        self.assertEqual(compatibility[101], [])

    def test_shipment_larger_than_flight_capacity_is_incompatible(self):
        payload = {
            "shipments": [
                {
                    "snapshot_id": 101,
                    "destination_iata": "ABJ",
                    "carton_count": 2,
                    "equivalent_units": 15,
                }
            ],
            "volunteers": [
                {
                    "snapshot_id": 201,
                    "max_colis_vol": 4,
                    "availability_summary": {},
                }
            ],
            "flights": [
                {
                    "snapshot_id": 301,
                    "departure_date": "2026-03-10",
                    "destination_iata": "ABJ",
                    "capacity_units": 12,
                    "max_cartons_per_flight": 12,
                }
            ],
        }

        compatibility = compute_compatibility(payload)

        self.assertEqual(compatibility[101], [])

    def test_shipment_exceeds_destination_max_cartons_per_flight(self):
        payload = {
            "shipments": [
                {
                    "snapshot_id": 101,
                    "destination_iata": "ABJ",
                    "carton_count": 13,
                    "equivalent_units": 13,
                }
            ],
            "volunteers": [
                {
                    "snapshot_id": 201,
                    "max_colis_vol": 20,
                    "availability_summary": {},
                }
            ],
            "flights": [
                {
                    "snapshot_id": 301,
                    "departure_date": "2026-03-10",
                    "destination_iata": "ABJ",
                    "capacity_units": 20,
                    "max_cartons_per_flight": 12,
                }
            ],
        }

        compatibility = compute_compatibility(payload)

        self.assertEqual(compatibility[101], [])
