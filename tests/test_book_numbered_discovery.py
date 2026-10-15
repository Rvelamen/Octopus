"""Numbered wire data cannot change source, identity or canonical authority."""

import copy
import json

import pytest
from test_book_discovery import story

from backend.core.providers.base import LLMResponse
from backend.services.book_world.discovery import BookDiscoveryService, DiscoveryConfig
from backend.services.book_world.discovery_numbered import assemble_numbered, prepare_numbered
from backend.services.book_world.storage import connect


def input_data():
    return {"unit_key":"0","segments":[{"id":"segment-a","ordinal":0,"text":"人物甲说：\"这不是秘密\"。"},{"id":"segment-b","ordinal":1,"text":"人物乙经过，人物甲安坐。"}],"known_characters":[{"id":"known-a","name":"人物甲","aliases":[{"alias":"人物甲","review_state":"candidate"}]}]}


def numbered_reply():
    return {"people":[{"i":0,"k":0,"state":"existing"},{"i":1,"state":"uncertain"}],"scenes":[{"s":[0],"c":[{"p":0,"kn":0,"e":0,"at":"active"}]},{"s":[1],"c":[{"p":0,"kn":0,"e":1,"at":"silent"},{"p":1,"n":"人物乙","e":1,"at":"active"}]}]}


def test_numbered_sources_preserve_exact_quotes_and_one_identity_binding():
    data = input_data()
    packet = prepare_numbered(data)
    expanded = assemble_numbered(json.dumps(numbered_reply()),packet)
    result = BookDiscoveryService._validate_result(json.dumps(expanded),data)
    assert result.scenes[0].characters[0].existing_character_id == "known-a"
    assert result.scenes[1].characters[0].existing_character_id == "known-a"
    assert result.scenes[0].characters[0].evidence.quote == data["segments"][0]["text"]
    assert result.scenes[0].characters[0].evidence.local_start == 0
    assert result.scenes[0].characters[0].evidence.local_end == len(data["segments"][0]["text"])
    assert result.scenes[1].characters[1].identity == "uncertain"
    assert "segment-a" not in json.dumps(packet["input"]) and "known-a" not in json.dumps(packet["input"])


@pytest.mark.parametrize("defect",["foreign_anchor","foreign_known","foreign_segment","foreign_person","duplicate_known","duplicate_person","unused_person","wrong_scene","name_outside_quote","missing_segment","identity_mismatch"])
def test_numbered_wires_fail_closed_for_invalid_references_and_bindings(defect):
    data = input_data()
    reply = numbered_reply()
    if defect == "foreign_anchor":
        reply["scenes"][0]["c"][0]["e"] = 1000
    elif defect == "foreign_known":
        reply["people"][0]["k"] = 1000
    elif defect == "foreign_segment":
        reply["scenes"][0]["s"] = [1000]
    elif defect == "foreign_person":
        reply["scenes"][0]["c"][0]["p"] = 1000
    elif defect == "duplicate_known":
        reply["people"][1].update(k=0,state="existing")
    elif defect == "duplicate_person":
        reply["scenes"][0]["c"].append(copy.deepcopy(reply["scenes"][0]["c"][0]))
    elif defect == "unused_person":
        reply["people"].append({"i":2})
    elif defect == "wrong_scene":
        reply["scenes"][0]["c"][0]["e"] = 1
    elif defect == "name_outside_quote":
        reply["scenes"][0]["c"][0]["n"] = "未出现的角色"
    elif defect == "missing_segment":
        reply["scenes"].pop()
    elif defect == "identity_mismatch":
        reply["people"][0]["state"] = "uncertain"
    with pytest.raises(ValueError):
        expanded = assemble_numbered(json.dumps(reply),prepare_numbered(data))
        BookDiscoveryService._validate_result(json.dumps(expanded),data)


def test_numbered_windows_cover_long_names_and_unicode_without_partial_source_reads():
    name = "名字" * 40
    text = "😀" * 340 + name + "走" * 510
    data = {"segments":[{"id":"long-source","text":text,"ordinal":0}],"known_characters":[]}
    packet = prepare_numbered(data)
    assert any(name in anchor["t"] for anchor in packet["anchors"])
    covered = set()
    for anchor in packet["anchors"]:
        span = anchor["span"]
        assert span["quote"] == text[span["local_start"]:span["local_end"]]
        assert len(span["quote"]) <= 384
        covered.update(range(span["local_start"],span["local_end"]))
    assert covered == set(range(len(text)))


@pytest.mark.parametrize("repeated", [False, True])
def test_numbered_registry_preserves_original_multiscene_capacity_above_256_people(repeated):
    data = {"segments":[],"known_characters":[]}
    people, scenes = [], []
    for scene_index in range(4):
        first = scene_index * 70
        names = [f"候选{index:03d}" for index in range(first,min(257,first+70))]
        text = "、".join(names)
        data["segments"].append({"id":f"segment-{scene_index}","text":text + ("、" + text if repeated else ""),"ordinal":scene_index})
        scenes.append({"s":[scene_index],"c":[]})
        for index,name in enumerate(names,first):
            people.append({"i":index})
            scenes[-1]["c"].append({"p":index,"n":name,"e":0,"at":"referenced"})
    packet = prepare_numbered(data)
    for scene_index,scene in enumerate(scenes):
        for appearance in scene["c"]:
            appearance["e"] = next(anchor["e"] for anchor in packet["anchors"] if anchor["s"] == scene_index and appearance["n"] in anchor["t"])
            if repeated:
                appearance["o"] = 0
    expanded = assemble_numbered(json.dumps({"people":people,"scenes":scenes}),packet)
    validated = BookDiscoveryService._validate_result(json.dumps(expanded, ensure_ascii=False, separators=(",",":")),data)
    assert sum(len(scene.characters) for scene in validated.scenes) == 257


@pytest.mark.parametrize("occurrence",[0,1,2])
def test_numbered_repeated_names_require_exact_explicit_occurrence(occurrence):
    data = {"segments":[{"id":"source","text":"人物甲行走。人物甲安坐。","ordinal":0}],"known_characters":[]}
    reply = {"people":[{"i":0}],"scenes":[{"s":[0],"c":[{"p":0,"n":"人物甲","e":0,"o":occurrence,"at":"active"}]}]}
    if occurrence == 2:
        with pytest.raises(ValueError,match="occurrence"):
            assemble_numbered(json.dumps(reply),prepare_numbered(data))
    else:
        expanded = assemble_numbered(json.dumps(reply),prepare_numbered(data))
        proof = expanded["scenes"][0]["characters"][0]["evidence"]
        assert proof["quote"] == data["segments"][0]["text"][proof["local_start"]:proof["local_end"]]
        assert BookDiscoveryService._validate_result(json.dumps(expanded),data)


def test_numbered_dense_registry_and_anonymous_literal_preserve_exact_source_ability():
    names = [f"人{index:03d}" for index in range(320)]
    data = {"segments":[{"id":f"source-{scene_index}","text":"、".join(names[scene_index*80:(scene_index+1)*80]),"ordinal":scene_index} for scene_index in range(4)],"known_characters":[]}
    packet = prepare_numbered(data)
    reply = {"people":[{"i":index} for index in range(320)],"scenes":[]}
    for scene_index in range(4):
        reply["scenes"].append({"s":[scene_index],"c":[{"p":index,"n":names[index],"e":next(anchor["e"] for anchor in packet["anchors"] if anchor["s"] == scene_index and names[index] in anchor["t"]),"at":"referenced"} for index in range(scene_index*80,(scene_index+1)*80)]})
    expanded = assemble_numbered(json.dumps(reply),packet)
    serialized = json.dumps(expanded,ensure_ascii=False,separators=(",",":"))
    assert len(serialized) < 100000
    assert len(BookDiscoveryService._validate_result(serialized,data).scenes) == 4
    data = {"segments":[{"id":"source","text":"他走来，他又走开。","ordinal":0}],"known_characters":[]}
    reply = {"people":[{"i":0,"anonymous":True,"kind":"unknown","state":"uncertain"}],"scenes":[{"s":[0],"c":[{"p":0,"n":"他","e":0,"o":1,"at":"active"}]}]}
    expanded = assemble_numbered(json.dumps(reply),prepare_numbered(data))
    assert BookDiscoveryService._validate_result(json.dumps(expanded),data).scenes[0].characters[0].anonymous


@pytest.mark.asyncio
@pytest.mark.parametrize("action", [None,"cancel","delete"])
async def test_numbered_invalid_appearance_uses_one_scoped_repair_and_late_results_are_fenced(book_library, action):
    import asyncio

    item, source = story(book_library,"人物甲说：\"这不是秘密\"。\n\n人物乙经过，人物甲安坐。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(provider_id=1,model="fixture",prompt_version="character-discovery-v13")
    build = service.create_build(item,source,config)
    entered, release = asyncio.Event(), asyncio.Event()
    seen = []

    class Provider:
        async def chat(self,messages,**kwargs):
            data = json.loads(messages[-1]["content"])
            seen.append(data)
            if len(seen) == 1:
                reply = numbered_reply()
                reply["people"][0].pop("k")
                reply["people"][0]["state"] = "new"
                for scene in reply["scenes"]:
                    for appearance in scene["c"]:
                        if appearance["p"] == 0:
                            appearance.pop("kn")
                            appearance["n"] = "人物甲"
                reply["scenes"][1]["c"][1]["e"] = 0
            else:
                assert data["phase"] == "discovery_repair_choices"
                assert len(data["repair_targets"]) == 1
                target = data["repair_targets"][0]
                choice = next(option for option in target["choices"] if option["name"] == "人物乙")
                entered.set()
                if action is not None:
                    await release.wait()
                reply = {"repairs":[{"scene_index":1,"character_index":1,"identity":"preserve","presence":"active","evidence_choice":choice["id"]}]}
            return LLMResponse(content=json.dumps(reply))

    worker = asyncio.create_task(service.run(build["build_id"],Provider(),config))
    try:
        if action is not None:
            await asyncio.wait_for(entered.wait(),10)
            if action == "cancel":
                service.cancel_build(item,build["build_id"])
            else:
                assert book_library.delete_item(item)
            release.set()
        await worker
    finally:
        release.set()
        if not worker.done():
            worker.cancel()
            await asyncio.gather(worker,return_exceptions=True)
    assert len(seen) == 2
    if action is None:
        assert service.get_build(item,build["build_id"])["stage"] == "discovery_complete"
    else:
        with connect(service.db_path) as database:
            assert not database.execute("SELECT 1 FROM book_build_steps WHERE build_id=? AND status='validated'",(build["build_id"],)).fetchone()
            assert not database.execute("SELECT 1 FROM book_characters WHERE build_id=?",(build["build_id"],)).fetchone()


@pytest.mark.asyncio
async def test_numbered_service_persists_existing_shape_and_keeps_uncertainty(book_library):
    item, source = story(book_library,"人物甲说：\"这不是秘密\"。\n\n人物乙经过，人物甲安坐。")
    service = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(provider_id=1,model="fixture",prompt_version="character-discovery-v13")
    build = service.create_build(item,source,config)
    seen = []

    class Provider:
        async def chat(self,messages,**kwargs):
            data = json.loads(messages[-1]["content"])
            seen.append(data)
            assert data["phase"] == "discovery_numbered"
            reply = numbered_reply()
            reply["people"][0].pop("k")
            reply["people"][0]["state"] = "new"
            for scene in reply["scenes"]:
                for appearance in scene["c"]:
                    if appearance["p"] == 0:
                        appearance.pop("kn")
                        appearance["n"] = "人物甲"
            return LLMResponse(content=json.dumps(reply))

    await service.run(build["build_id"],Provider(),config)
    assert len(seen) == 1
    assert service.get_build(item,build["build_id"])["stage"] == "discovery_complete"
    people = service.list_characters(item,build["build_id"])["characters"]
    assert next(person for person in people if person["name"] == "人物乙")["agent_status"] == "needs_review"
    with connect(service.db_path) as database:
        saved = json.loads(database.execute("SELECT result_json FROM book_build_steps WHERE build_id=?",(build["build_id"],)).fetchone()[0])["result"]
        assert "people" not in saved
        assert saved["scenes"][0]["characters"][0]["evidence"]["segment_id"]
