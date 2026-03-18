def sorted_choices(choices):
    return sorted(choices, key=lambda choice: str(choice[1] or "").lower())
