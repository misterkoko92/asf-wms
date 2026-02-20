# Setup email Brevo sur PythonAnywhere (messmed, pas a pas)

Objectif: configurer un envoi reel (pas console), avec fallback SMTP, sans utiliser un `.env` versionne.

Note: les notifications de nouvelle commande (portail/public) sont envoyees en direct.
Si l'envoi direct echoue, elles sont automatiquement mises en queue.

## 1) Ouvrir une console Bash sur PythonAnywhere

Tout se fait sur le serveur PythonAnywhere, avec ton user `messmed`.

## 2) Creer le fichier secrets `/home/messmed/.asf-wms.env`

```bash
cp /home/messmed/asf-wms/deploy/pythonanywhere/asf-wms.messmed.env.template /home/messmed/.asf-wms.env
chmod 600 /home/messmed/.asf-wms.env
nano /home/messmed/.asf-wms.env
```

Tu remplis au minimum:
- `DJANGO_SECRET_KEY`
- `EMAIL_HOST_PASSWORD`
- `BREVO_API_KEY` (ou vide pour SMTP only)
- `ORDER_NOTIFICATION_GROUP_NAME` (laisser `Mail_Order_Staff`, ou `''` pour superusers uniquement)

Important:
- `EMAIL_HOST` doit rester `smtp-relay.brevo.com`
- `EMAIL_HOST_USER` doit rester `9f2ab8001@smtp-brevo.com`
- Ne pas utiliser la cle MCP pour `BREVO_API_KEY`

## 3) Installer le WSGI qui charge ce fichier secrets

```bash
cp /home/messmed/asf-wms/deploy/pythonanywhere/wsgi.messmed.pythonanywhere.py /var/www/messmed_pythonanywhere_com_wsgi.py
```

## 4) Verifier les variables en console

```bash
source /home/messmed/.asf-wms.env
echo "EMAIL_BACKEND=$EMAIL_BACKEND"
echo "EMAIL_HOST=$EMAIL_HOST"
echo "EMAIL_HOST_USER=$EMAIL_HOST_USER"
echo "BREVO_API_KEY_SET=$([ -n "$BREVO_API_KEY" ] && echo yes || echo no)"
```

Attendu:
- `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`
- `EMAIL_HOST` et `EMAIL_HOST_USER` non vides

## 5) Tester un envoi direct + un flux queue

```bash
cd /home/messmed/asf-wms
./deploy/pythonanywhere/test_email_setup.sh edouard.gonnu@aviation-sans-frontieres-fr.org
```

Attendu:
- test direct: `True`
- queue: `enqueue=True` puis `processed` > 0

## 6) Recharger l'app web

PythonAnywhere -> onglet **Web** -> bouton **Reload**.

## 7) Planifier le worker queue mail (Scheduler)

```bash
mkdir -p /home/messmed/asf-wms/logs
```

Dans Scheduler (toutes les minutes):

```bash
cd /home/messmed/asf-wms && source /home/messmed/.asf-wms.env && python manage.py process_email_queue --limit=100 >> /home/messmed/asf-wms/logs/email_queue.log 2>&1
```

## 8) Vider la queue si besoin

Pending/processing/failed uniquement:

```bash
cd /home/messmed/asf-wms
./deploy/pythonanywhere/flush_email_queue.sh active
```

Tout l'historique email:

```bash
cd /home/messmed/asf-wms
./deploy/pythonanywhere/flush_email_queue.sh all
```

## 9) Si tu as encore `Brevo email failed: HTTP Error 401: Unauthorized`

Ca veut dire que `BREVO_API_KEY` est invalide pour l'API Brevo.

Tu as 2 options:
1. Mettre une vraie cle API Brevo v3 dans `BREVO_API_KEY`.
2. Laisser `BREVO_API_KEY=''` pour bypass API et envoyer via SMTP uniquement.
