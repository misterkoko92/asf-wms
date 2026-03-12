from unittest import TestCase

from tools.planning_comm_helper.whatsapp import build_whatsapp_url, open_whatsapp_drafts


class PlanningCommunicationHelperWhatsAppTests(TestCase):
    def test_open_whatsapp_drafts_opens_urls_in_sequence(self):
        opened_urls = []

        open_whatsapp_drafts(
            [
                {"recipient_contact": "0611223344", "body": "Premier message"},
                {"recipient_contact": "0622334455", "body": "Deuxieme message"},
            ],
            opener=opened_urls.append,
        )

        self.assertEqual(
            opened_urls,
            [
                build_whatsapp_url("0611223344", "Premier message"),
                build_whatsapp_url("0622334455", "Deuxieme message"),
            ],
        )
