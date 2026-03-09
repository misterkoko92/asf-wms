from datetime import date, time

import pandas as pd
from django.test import SimpleTestCase

from wms.planning.reference_case_builder import build_reference_case_payload


class LegacyReferenceCaseBuilderTests(SimpleTestCase):
    def test_build_reference_case_payload_normalizes_legacy_frames(self):
        payload = build_reference_case_payload(
            case_name="legacy_session_sample",
            df_be=pd.DataFrame(
                [
                    {
                        "BE_Numero": "250722",
                        "BE_Expediteur": "AR MADA",
                        "Destination": "RUN",
                        "Priorite": 2,
                        "BE_Nb_Colis": 10,
                        "Equiv_Colis": 10,
                        "BE_Type": "MM",
                        "BE_Destinataire": "AR MADA",
                    }
                ]
            ),
            df_vols=pd.DataFrame(
                [
                    {
                        "Date_Vol_dt": pd.Timestamp("2026-03-11"),
                        "Heure_Vol_dt": pd.Timestamp("1900-01-01 18:20:00"),
                        "Numero_Vol": "AF 652",
                        "IATA": "RUN",
                        "Routing": "[CDG,RUN]",
                        "Route_Pos": 1,
                        "Max_Colis": 20,
                        "Source": "excel",
                    }
                ]
            ),
            df_benev=pd.DataFrame(
                [
                    {
                        "ID": 5,
                        "Benevole": "PIERSON Gilles",
                        "Date_dt": pd.Timestamp("2026-03-11"),
                        "Heure_Arrivee_time": time(7, 0),
                        "Heure_Depart_time": time(20, 0),
                    }
                ]
            ),
            df_param_benev=pd.DataFrame(
                [
                    {
                        "ID": 5,
                        "Benevole": "PIERSON Gilles",
                        "Max_Colis_Vol": 30,
                        "Telephone": "0600000000",
                    }
                ]
            ),
            planning_df=pd.DataFrame(
                [
                    {
                        "Date_Vol": date(2026, 3, 11),
                        "Numero_Vol": "652",
                        "Destination": "RUN",
                        "BE_Numero": "250722",
                        "Benevole": "PIERSON Gilles",
                    }
                ]
            ),
            stats={
                "nb_vols_total": 1,
                "nb_vols_sans_benevole_compatible": 0,
            },
        )

        self.assertEqual(payload["week_start"], "2026-03-11")
        self.assertEqual(payload["week_end"], "2026-03-11")
        self.assertEqual(
            payload["shipments"],
            [
                {
                    "reference": "250722",
                    "shipper_name": "AR MADA",
                    "destination_iata": "RUN",
                    "priority": 2,
                    "carton_count": 10,
                    "equivalent_units": 10,
                    "payload": {
                        "legacy_case_name": "legacy_session_sample",
                        "legacy_type": "MM",
                        "legacy_destinataire": "AR MADA",
                    },
                }
            ],
        )
        self.assertEqual(
            payload["volunteers"],
            [
                {
                    "label": "PIERSON Gilles",
                    "max_colis_vol": 30,
                    "availability_summary": {
                        "slot_count": 1,
                        "slots": [
                            {
                                "date": "2026-03-11",
                                "start_time": "07:00",
                                "end_time": "20:00",
                            }
                        ],
                    },
                    "payload": {
                        "legacy_id": 5,
                        "legacy_phone": "0600000000",
                    },
                }
            ],
        )
        self.assertEqual(
            payload["flights"],
            [
                {
                    "flight_number": "AF652",
                    "departure_date": "2026-03-11",
                    "destination_iata": "RUN",
                    "capacity_units": 20,
                    "payload": {
                        "departure_time": "18:20",
                        "origin_iata": "CDG",
                        "routing": "CDG-RUN",
                        "route_pos": 1,
                        "legacy_source": "excel",
                    },
                }
            ],
        )
        self.assertEqual(
            payload["expected_assignments"],
            [["250722", "AF652", "PIERSON Gilles"]],
        )
        self.assertEqual(
            payload["expected_result"],
            {
                "assignment_count": 1,
                "nb_vols_total": 1,
                "nb_vols_sans_benevole_compatible": 0,
            },
        )

    def test_build_reference_case_payload_respects_explicit_week_bounds(self):
        payload = build_reference_case_payload(
            case_name="legacy_session_filtered",
            week_start="2026-03-09",
            week_end="2026-03-15",
            df_be=pd.DataFrame(
                [
                    {
                        "BE_Numero": "250722",
                        "BE_Expediteur": "AR MADA",
                        "Destination": "RUN",
                        "Priorite": 2,
                        "BE_Nb_Colis": 10,
                        "Equiv_Colis": 10,
                        "BE_Type": "MM",
                        "BE_Destinataire": "AR MADA",
                    }
                ]
            ),
            df_vols=pd.DataFrame(
                [
                    {
                        "Date_Vol_dt": pd.Timestamp("2026-01-03"),
                        "Heure_Vol_dt": pd.Timestamp("1900-01-01 10:00:00"),
                        "Numero_Vol": "AF 111",
                        "IATA": "RUN",
                        "Routing": "[CDG,RUN]",
                        "Route_Pos": 1,
                        "Max_Colis": 20,
                        "Source": "excel",
                    },
                    {
                        "Date_Vol_dt": pd.Timestamp("2026-03-11"),
                        "Heure_Vol_dt": pd.Timestamp("1900-01-01 18:20:00"),
                        "Numero_Vol": "AF 652",
                        "IATA": "RUN",
                        "Routing": "[CDG,RUN]",
                        "Route_Pos": 1,
                        "Max_Colis": 20,
                        "Source": "excel",
                    },
                ]
            ),
            df_benev=pd.DataFrame(
                [
                    {
                        "ID": 5,
                        "Benevole": "PIERSON Gilles",
                        "Date_dt": pd.Timestamp("2026-01-03"),
                        "Heure_Arrivee_time": time(7, 0),
                        "Heure_Depart_time": time(20, 0),
                    },
                    {
                        "ID": 5,
                        "Benevole": "PIERSON Gilles",
                        "Date_dt": pd.Timestamp("2026-03-11"),
                        "Heure_Arrivee_time": time(7, 0),
                        "Heure_Depart_time": time(20, 0),
                    },
                ]
            ),
            df_param_benev=pd.DataFrame(
                [
                    {
                        "ID": 5,
                        "Benevole": "PIERSON Gilles",
                        "Max_Colis_Vol": 30,
                        "Telephone": "0600000000",
                    }
                ]
            ),
            planning_df=pd.DataFrame(
                [
                    {
                        "Date_Vol": date(2026, 3, 11),
                        "Numero_Vol": "652",
                        "Destination": "RUN",
                        "BE_Numero": "250722",
                        "Benevole": "PIERSON Gilles",
                    }
                ]
            ),
            stats={},
        )

        self.assertEqual(payload["week_start"], "2026-03-09")
        self.assertEqual(payload["week_end"], "2026-03-15")
        self.assertEqual(len(payload["flights"]), 1)
        self.assertEqual(payload["flights"][0]["flight_number"], "AF652")
        self.assertEqual(
            payload["volunteers"][0]["availability_summary"]["slots"],
            [
                {
                    "date": "2026-03-11",
                    "start_time": "07:00",
                    "end_time": "20:00",
                }
            ],
        )

    def test_build_reference_case_payload_omits_incomparable_legacy_flight_metrics(self):
        payload = build_reference_case_payload(
            case_name="legacy_session_incomparable_stats",
            df_be=pd.DataFrame(
                [
                    {
                        "BE_Numero": "250722",
                        "BE_Expediteur": "AR MADA",
                        "Destination": "RUN",
                        "Priorite": 2,
                        "BE_Nb_Colis": 10,
                        "Equiv_Colis": 10,
                        "BE_Type": "MM",
                        "BE_Destinataire": "AR MADA",
                    }
                ]
            ),
            df_vols=pd.DataFrame(
                [
                    {
                        "Date_Vol_dt": pd.Timestamp("2026-03-11"),
                        "Heure_Vol_dt": pd.Timestamp("1900-01-01 18:20:00"),
                        "Numero_Vol": "AF 652",
                        "IATA": "RUN",
                        "Routing": "[CDG,RUN]",
                        "Route_Pos": 1,
                        "Max_Colis": 20,
                        "Source": "excel",
                    }
                ]
            ),
            df_benev=pd.DataFrame(
                [
                    {
                        "ID": 5,
                        "Benevole": "PIERSON Gilles",
                        "Date_dt": pd.Timestamp("2026-03-11"),
                        "Heure_Arrivee_time": time(7, 0),
                        "Heure_Depart_time": time(20, 0),
                    }
                ]
            ),
            df_param_benev=pd.DataFrame(
                [
                    {
                        "ID": 5,
                        "Benevole": "PIERSON Gilles",
                        "Max_Colis_Vol": 30,
                        "Telephone": "0600000000",
                    }
                ]
            ),
            planning_df=pd.DataFrame(
                [
                    {
                        "Date_Vol": date(2026, 3, 11),
                        "Numero_Vol": "652",
                        "Destination": "RUN",
                        "BE_Numero": "250722",
                        "Benevole": "PIERSON Gilles",
                    }
                ]
            ),
            stats={
                "nb_vols_total": 3,
                "nb_vols_sans_be_compatible": 2,
                "nb_vols_sans_benevole_compatible": 1,
                "nb_vols_sans_compatibilite_complete": 2,
            },
        )

        self.assertEqual(
            payload["expected_result"],
            {
                "assignment_count": 1,
            },
        )
