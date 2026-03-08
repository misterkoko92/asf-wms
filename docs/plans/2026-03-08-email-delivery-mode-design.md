# Email Delivery Mode Design

## Context
`asf-wms` dispose aujourd'hui de deux chemins d'envoi email:
- `send_or_enqueue_email_safe(...)`: envoi direct puis fallback queue
- `enqueue_email_safe(...)`: queue directe via `IntegrationEvent`

Sur PythonAnywhere gratuit, le `Scheduler` n'est pas disponible pour traiter la queue mail en continu. Cela casse les flux qui passent par `enqueue_email_safe(...)`, notamment les approbations de compte `portal` et `benevole`, qui restent en `pending` jusqu'a un traitement manuel.

Objectif valide:
- conserver le comportement actuel par defaut pour les environnements existants
- permettre a PythonAnywhere de tout envoyer en direct sans dependre de `process_email_queue`
- garder la queue disponible pour les environnements qui veulent encore du retry asynchrone

## Decision Summary
Decision retenue:
- introduire un reglage `EMAIL_DELIVERY_MODE`
- valeur par defaut: `direct_or_queue`
- valeur PythonAnywhere: `direct_only`

Decision technique:
- centraliser la decision dans `wms/emailing.py`
- ne pas modifier les call sites metier existants
- conserver `process_email_queue` et les `IntegrationEvent` pour les environnements qui gardent la queue

## Delivery Modes
### `direct_or_queue`
Comportement par defaut, identique a l'existant:
- `send_or_enqueue_email_safe(...)` tente l'envoi direct puis cree un evenement si echec
- `enqueue_email_safe(...)` cree un evenement en queue

### `direct_only`
Comportement cible pour PythonAnywhere:
- `send_or_enqueue_email_safe(...)` tente l'envoi direct sans changement
- `enqueue_email_safe(...)` tente lui aussi l'envoi direct
- aucun `IntegrationEvent` n'est cree en cas de succes
- si l'envoi direct echoue, la fonction retourne `False`

## Scope
### In Scope
- ajout du reglage `EMAIL_DELIVERY_MODE` dans `settings`
- adaptation de `wms/emailing.py`
- mise a jour des tests email
- mise a jour des templates env PythonAnywhere
- mise a jour de la doc de deploiement/mail

### Out Of Scope
- suppression de la queue mail
- refonte des templates email
- changement des flux `portal` et `benevole` cote UX
- ajout d'un backend de retry alternatif

## Technical Approach
Ajouter un helper central dans `wms/emailing.py` pour normaliser la strategie:
- lire `EMAIL_DELIVERY_MODE`
- normaliser les valeurs invalides vers `direct_or_queue`
- exposer un point de decision utilise par `enqueue_email_safe(...)`

Pseudo-code:

```python
def _email_delivery_mode():
    value = str(getattr(settings, "EMAIL_DELIVERY_MODE", "direct_or_queue") or "").strip().lower()
    if value == "direct_only":
        return "direct_only"
    return "direct_or_queue"


def enqueue_email_safe(...):
    if _email_delivery_mode() == "direct_only":
        return send_email_safe(...)
    ...
    IntegrationEvent.objects.create(...)
    return True
```

## Impact
Avec `EMAIL_DELIVERY_MODE=direct_only`, les flux suivants n'auront plus besoin du scheduler:
- approbation de demande portail
- approbation de demande benevole
- creation/reinitialisation d'acces benevole
- autres flux metier qui appellent `enqueue_email_safe(...)`

Le comportement public reste identique; seul le transport change.

## Risks
Risque principal:
- en `direct_only`, un echec SMTP/Brevo perd le mail au lieu de le retenir en queue

Trade-off assume:
- acceptable sur PythonAnywhere gratuit pour supprimer la dependance au Scheduler

Mesures de reduction:
- garder `direct_or_queue` par defaut
- conserver les tests sur les deux modes
- documenter explicitement le risque dans la doc ops
