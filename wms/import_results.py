def normalize_import_result(result):
    if len(result) == 4:
        return result
    created, updated, errors = result
    return created, updated, errors, []
