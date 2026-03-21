MENTOR_ROLE_TO_ID_DICTIONARY_DEV = {
    "frontend": 1482999081302364161,
    "backend": 1482999306196750449,
    "product": 1483991027089150114,
    "UI/UX": 1482998230013841521,
    "devops/setup": 1483991421168914452,
    "other/exec": 1483991524520890429,
    "python": 1483990953550286941,
    "javascript": 1483991876473196674,
}

MENTOR_ROLE_TO_ID_DICTIONARY_PROD = {
    "frontend mentor": 1484785989292396584,
    "backend mentor": 1484786262089924689,
    "product mentor": 1484786084478193790,
    "UI/UX mentor": 1484786956511739925,
    "devops/setup mentor": 1484786308198039573,
    "other/exec": 1484787473589735514,
    "Fetch AI": 1440489800460402899,
}

PROD_GUILD_ID = 1404646266725732492
PROD_TICKETS_CATEGORY_ID = 1482961779494486171 # Produhacks 2026


def get_mentor_role_to_id_dictionary(guild_id: int | None) -> dict[str, int]:
    """
    Resolve mentor role mapping based on the Discord server ID.

    - PROD guild ID uses PROD role IDs.
    - Any other guild ID uses DEV role IDs.
    """
    if guild_id == PROD_GUILD_ID:
        return MENTOR_ROLE_TO_ID_DICTIONARY_PROD
    return MENTOR_ROLE_TO_ID_DICTIONARY_DEV


EXEC_ROLE_IDS = [
    # Biztech
    1404646631688896604,  # BizTech Executive
    1440489800460402899,  # Fetch AI
    1484788119785046127,  # Mentor
    # Biztech Test server,
    1396397591465300098,  # Admin
    1423137037518770199,
]

MENTOR_ROLE_IDS = []

CLAIM_ALLOWED_ROLE_IDS = {*EXEC_ROLE_IDS, *MENTOR_ROLE_IDS}
