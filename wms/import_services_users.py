from django.contrib.auth import get_user_model

from .import_services_common import _row_is_empty
from .import_utils import get_value, parse_bool, parse_str

def import_users(rows, default_password):
    created = 0
    updated = 0
    errors = []
    User = get_user_model()
    for index, row in enumerate(rows, start=2):
        if _row_is_empty(row):
            continue
        try:
            username = parse_str(get_value(row, "username", "login"))
            if not username:
                raise ValueError("Username requis.")
            email = parse_str(get_value(row, "email"))
            first_name = parse_str(get_value(row, "first_name", "prenom"))
            last_name = parse_str(get_value(row, "last_name", "nom"))
            is_staff = parse_bool(get_value(row, "is_staff", "staff"))
            is_superuser = parse_bool(get_value(row, "is_superuser", "admin"))
            is_active = parse_bool(get_value(row, "is_active", "actif"))
            password = parse_str(get_value(row, "password", "mot_de_passe"))

            user = User.objects.filter(username=username).first()
            if user is None and not password and not default_password:
                raise ValueError(
                    "Mot de passe requis (colonne password ou IMPORT_DEFAULT_PASSWORD)."
                )
            was_created = False
            if user is None:
                user = User.objects.create(username=username)
                was_created = True
            updates = {}
            if email is not None:
                updates["email"] = email
            if first_name is not None:
                updates["first_name"] = first_name
            if last_name is not None:
                updates["last_name"] = last_name
            if is_staff is not None:
                updates["is_staff"] = is_staff
            if is_superuser is not None:
                updates["is_superuser"] = is_superuser
            if is_active is not None:
                updates["is_active"] = is_active
            if updates:
                for field, value in updates.items():
                    setattr(user, field, value)
                user.save(update_fields=list(updates.keys()))
                updated += 1 if not was_created else 0
            if was_created:
                created += 1
            if password:
                user.set_password(password)
                user.save(update_fields=["password"])
            elif was_created and default_password:
                user.set_password(default_password)
                user.save(update_fields=["password"])
        except ValueError as exc:
            errors.append(f"Ligne {index}: {exc}")
    return created, updated, errors
