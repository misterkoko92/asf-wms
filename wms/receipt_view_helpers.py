def build_receipts_view_rows(receipts_qs):
    receipts = []
    for receipt in receipts_qs:
        name = receipt.source_contact.name if receipt.source_contact else "-"
        quantity = "-"
        if receipt.pallet_count:
            quantity = f"{receipt.pallet_count} palettes"
        elif receipt.carton_count:
            quantity = f"{receipt.carton_count} colis"

        hors_format_count = receipt.hors_format_count
        hors_format_desc = "; ".join(
            item.description.strip()
            for item in receipt.hors_format_items.all()
            if item.description
        )
        if hors_format_count and hors_format_desc:
            hors_format = f"{hors_format_count} : {hors_format_desc}"
        elif hors_format_count:
            hors_format = str(hors_format_count)
        elif hors_format_desc:
            hors_format = hors_format_desc
        else:
            hors_format = "-"

        carrier = receipt.carrier_contact.name if receipt.carrier_contact else "-"

        receipts.append(
            {
                "received_on": receipt.received_on,
                "name": name,
                "quantity": quantity,
                "hors_format": hors_format,
                "carrier": carrier,
            }
        )
    return receipts
