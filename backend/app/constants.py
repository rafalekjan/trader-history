OPTION_CATEGORY = "Equity and Index Options"


def contract_multiplier(asset_category: str) -> int:
    """Cash multiplier per contract: options are 100 shares, everything else 1."""
    return 100 if asset_category == OPTION_CATEGORY else 1
