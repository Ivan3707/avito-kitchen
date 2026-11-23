import json
from hashlib import sha256

from app.schemas import SyncPayload


def catalog_checksum(payload: SyncPayload) -> str:
    canonical_content = {
        "restaurant": payload.restaurant.model_dump(mode="json"),
        "branches": [
            branch.model_dump(mode="json")
            for branch in sorted(
                payload.branches,
                key=lambda branch: branch.external_id,
            )
        ],
        "menu": {
            "external_id": payload.menu.external_id,
            "name": payload.menu.name,
            "items": [
                item.model_dump(mode="json")
                for item in sorted(
                    payload.menu.items,
                    key=lambda item: item.external_id,
                )
            ],
        },
        "availability": sorted(
            (
                {
                    "branch_external_id": branch.branch_external_id,
                    **item.model_dump(mode="json"),
                }
                for branch in payload.availability
                for item in branch.items
            ),
            key=lambda relation: (
                relation["branch_external_id"],
                relation["menu_item_external_id"],
            ),
        ),
    }
    canonical_json = json.dumps(
        canonical_content,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return sha256(canonical_json.encode("utf-8")).hexdigest()
