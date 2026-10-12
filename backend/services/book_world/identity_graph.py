"""Clone identities and scenes into a new B; canonical claims are deliberately rechecked."""

import json
import sqlite3
from uuid import uuid4


def clone_graph(
    db: sqlite3.Connection, parent_id: str, scope: tuple[str, str, str]
) -> dict[str, str]:
    people = db.execute("SELECT * FROM book_characters WHERE build_id=?", (parent_id,)).fetchall()
    characters = {person["id"]: str(uuid4()) for person in people}
    scenes = db.execute(
        "SELECT * FROM book_scenes WHERE build_id=? ORDER BY narrative_order", (parent_id,)
    ).fetchall()
    scene_ids = {scene["id"]: str(uuid4()) for scene in scenes}
    for person in people:
        status = "needs_review" if person["agent_status"] == "needs_review" else "candidate"
        db.execute(
            "INSERT INTO book_characters(id,book_id,source_version_id,build_id,lineage_id,name,agent_status,public_profile_json) VALUES (?,?,?,?,?,?,?,?)",
            (
                characters[person["id"]],
                *scope,
                person["lineage_id"],
                person["name"],
                status,
                person["public_profile_json"],
            ),
        )
    for alias in db.execute("SELECT * FROM book_character_aliases WHERE build_id=?", (parent_id,)):
        provenance = json.loads(alias["provenance_json"])
        provenance["scene_id"] = scene_ids.get(provenance.get("scene_id"))
        db.execute(
            "INSERT INTO book_character_aliases(book_id,source_version_id,build_id,character_id,alias,normalized_alias,review_state,provenance_json) VALUES (?,?,?,?,?,?,?,?)",
            (
                *scope,
                characters[alias["character_id"]],
                alias["alias"],
                alias["normalized_alias"],
                alias["review_state"],
                json.dumps(provenance, ensure_ascii=False),
            ),
        )
    for scene in scenes:
        sid = scene_ids[scene["id"]]
        db.execute(
            "INSERT INTO book_scenes(id,book_id,source_version_id,build_id,narrative_order,story_time_json,location_label) VALUES (?,?,?,?,?,?,?)",
            (
                sid,
                *scope,
                scene["narrative_order"],
                scene["story_time_json"],
                scene["location_label"],
            ),
        )
        db.execute(
            "INSERT INTO book_scene_segments(book_id,source_version_id,build_id,scene_id,position,segment_id) SELECT ?,?,?,?,position,segment_id FROM book_scene_segments WHERE build_id=? AND scene_id=?",
            (*scope, sid, parent_id, scene["id"]),
        )
        db.executemany(
            "INSERT INTO book_scene_characters(book_id,source_version_id,build_id,scene_id,character_id,presence) VALUES (?,?,?,?,?,?)",
            [
                (*scope, sid, characters[row["character_id"]], row["presence"])
                for row in db.execute(
                    "SELECT * FROM book_scene_characters WHERE build_id=? AND scene_id=?",
                    (parent_id, scene["id"]),
                )
            ],
        )
    return characters
