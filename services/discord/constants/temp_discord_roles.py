import os
import subprocess

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
    "Fetch AI":1440489800460402899,
}


def _resolve_branch_name() -> str:
    branch_from_env = (
        os.getenv("GITHUB_REF_NAME")
        or os.getenv("BRANCH_NAME")
        or os.getenv("GIT_BRANCH")
        or os.getenv("CI_COMMIT_REF_NAME")
    )
    if branch_from_env:
        return branch_from_env.replace("refs/heads/", "")

    github_ref = os.getenv("GITHUB_REF")
    if github_ref:
        return github_ref.replace("refs/heads/", "")

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


MENTOR_ROLE_TO_ID_DICTIONARY = (
    MENTOR_ROLE_TO_ID_DICTIONARY_PROD
    if _resolve_branch_name().lower() == "main"
    else MENTOR_ROLE_TO_ID_DICTIONARY_DEV
)

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
