def _choice_label_key(choice):
    return str(choice[1] or "").lower()


def _is_grouped_choice(choice):
    if not isinstance(choice, list | tuple) or len(choice) != 2:
        return False
    _, label = choice
    if not isinstance(label, list | tuple):
        return False
    return all(isinstance(option, list | tuple) and len(option) == 2 for option in label)


def sorted_choices(choices, *, order="asc"):
    reverse = order == "desc"
    choices = list(choices)
    placeholders = [
        choice for choice in choices if not _is_grouped_choice(choice) and choice[0] in ("", None)
    ]
    remaining = [
        choice
        for choice in choices
        if not (not _is_grouped_choice(choice) and choice[0] in ("", None))
    ]

    if any(_is_grouped_choice(choice) for choice in remaining):
        sorted_grouped = []
        for choice in remaining:
            if _is_grouped_choice(choice):
                group_label, group_choices = choice
                sorted_grouped.append(
                    (
                        group_label,
                        tuple(sorted(group_choices, key=_choice_label_key, reverse=reverse)),
                    )
                )
            else:
                sorted_grouped.append(choice)
        return placeholders + sorted_grouped

    return placeholders + sorted(remaining, key=_choice_label_key, reverse=reverse)
