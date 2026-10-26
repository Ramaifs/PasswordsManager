"""State-based multi-value registers with a global causal context.

No clock wins, no tombstone expiry, no local preferences/drafts in the wire state.
Every actor is a new random ID per application session (safe when profiles are copied).
"""
from copy import deepcopy
from datetime import datetime
import uuid
import re

from .crypto import canonical
from .errors import InvalidVault, VaultError

MAX_ACTORS = 4096
MAX_REGISTERS = 50_000


def identifier(value):
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise InvalidVault()
    except (ValueError, TypeError, AttributeError):
        raise InvalidVault() from None
    return value


def empty():
    return {"vector": {}, "registers": {}}


def validate(state):
    from .model import valid_fields
    try:
        if not isinstance(state, dict) or set(state) != {"vector", "registers"}:
            raise InvalidVault()
        vector, registers = state["vector"], state["registers"]
        if not isinstance(vector, dict) or len(vector) > MAX_ACTORS or not isinstance(registers, dict) or len(registers) > MAX_REGISTERS:
            raise InvalidVault()
        for actor, counter in vector.items():
            identifier(actor)
            if type(counter) is not int or not 1 <= counter < 2**53:
                raise InvalidVault()
        all_dots = set()
        for key, variants in registers.items():
            kind, eid = key.split(":")
            identifier(eid)
            if kind not in ("entry", "category", "category_parent", "category_color") or not isinstance(variants, dict) or not 1 <= len(variants) <= MAX_ACTORS:
                raise InvalidVault()
            for dot, value in variants.items():
                actor, counter = dot.split(":")
                identifier(actor)
                number = int(counter)
                if str(number) != counter or not 1 <= number <= vector.get(actor, 0) or dot in all_dots:
                    raise InvalidVault()
                all_dots.add(dot)
                if kind == "category_color":
                    if value is not None and (not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value)):
                        raise InvalidVault()
                elif kind == "category_parent":
                    if value is not None:
                        identifier(value)
                elif kind == "category":
                    if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 256):
                        raise InvalidVault()
                elif isinstance(value, dict) and set(value) == {"purged_at"}:
                    if datetime.fromisoformat(value["purged_at"]).tzinfo is None:
                        raise InvalidVault()
                else:
                    if not valid_fields(value, {"id", "category", "deleted_at", "updated_at"}) or value["id"] != eid:
                        raise InvalidVault()
                    if not value["title"].strip():
                        raise InvalidVault()
                    if value["category"] is not None:
                        identifier(value["category"])
                    for field in ("updated_at", "deleted_at"):
                        if value[field] is not None and datetime.fromisoformat(value[field]).tzinfo is None:
                            raise InvalidVault()
        return state
    except (ValueError, TypeError, KeyError, AttributeError):
        raise InvalidVault() from None


def write(state, actor, key, value):
    identifier(actor)
    counter = state["vector"].get(actor, 0) + 1
    state["vector"][actor] = counter
    state["registers"][key] = {f"{actor}:{counter}": deepcopy(value)}
    validate(state)


def shared(document):
    return {**{f"category:{k}": v for k, v in document["categories"].items()},
            **{f"category_parent:{k}": v for k, v in document.get("category_parents", {}).items()},
            **{f"category_color:{k}": v for k, v in document["settings"].get("category_colors", {}).items() if k in document["categories"]},
            **{f"entry:{k}": v for k, v in document["entries"].items()},
            **{f"entry:{k}": {"purged_at": v} for k, v in document["tombstones"].items()}}


def seed(document, actor):
    result = empty()
    for counter, (key, value) in enumerate(sorted(shared(document).items()), 1):
        result["registers"][key] = {f"{actor}:{counter}": deepcopy(value)}
        result["vector"][actor] = counter
    return validate(result)


def migrate_category_colors(document, actor):
    """Publish pre-update local colors once; a null register is an observed reset."""
    state = document["sync"]["state"]
    for cid, color in document["settings"].get("category_colors", {}).items():
        key = f"category_color:{cid}"
        if cid in document["categories"] and key not in state["registers"]:
            write(state, actor, key, color)


def track(before, after, actor):
    if after.get("sync") is None:
        return
    state = after["sync"]["state"]
    a, b = shared(before), shared(after)
    for key in sorted(a.keys() | b.keys()):
        if a.get(key) == b.get(key):
            continue
        if is_conflicted(state["registers"].get(key, {})):
            raise VaultError("Сначала разрешите конфликт этой записи или категории.")
        write(state, actor, key, b.get(key))


def _observed(dot, vector):
    actor, count = dot.split(":")
    return vector.get(actor, 0) >= int(count)


def merge(left, right):
    validate(left)
    validate(right)
    result = empty()
    result["vector"] = {actor: max(left["vector"].get(actor, 0), right["vector"].get(actor, 0))
                        for actor in left["vector"].keys() | right["vector"].keys()}
    # A dot must have the same register/value everywhere; collisions are never guessed away.
    known = {}
    for state in (left, right):
        for key, variants in state["registers"].items():
            for dot, value in variants.items():
                fingerprint = canonical([key, value])
                if dot in known and known[dot] != fingerprint:
                    raise InvalidVault()
                known[dot] = fingerprint
    for key in left["registers"].keys() | right["registers"].keys():
        a, b = left["registers"].get(key, {}), right["registers"].get(key, {})
        variants = {dot: deepcopy(value) for dot, value in a.items() if dot in b or not _observed(dot, right["vector"])}
        variants.update({dot: deepcopy(value) for dot, value in b.items() if dot in a or not _observed(dot, left["vector"])})
        if variants:
            result["registers"][key] = variants
    return validate(result)


def conflicts(state):
    return {key: deepcopy(variants) for key, variants in state["registers"].items() if is_conflicted(variants)}


def is_conflicted(variants):
    return len({canonical(value) for value in variants.values()}) > 1


def project(document, state):
    """Keep a pre-existing local view for conflicts; all variants remain in state."""
    from .model import validate as validate_document
    result = deepcopy(document)
    result["categories"], result["category_parents"], result["entries"], result["tombstones"] = {}, {}, {}, {}
    for key, variants in state["registers"].items():
        kind, eid = key.split(":")
        if kind != "category":
            continue
        if is_conflicted(variants):
            result["categories"][eid] = document["categories"].get(eid, "Конфликт категории")
        elif (value := next(iter(variants.values()))) is not None:
            result["categories"][eid] = value
    for key, variants in state["registers"].items():
        kind, eid = key.split(":")
        if kind == "category_parent":
            parent = document.get("category_parents", {}).get(eid) if is_conflicted(variants) else next(iter(variants.values()))
            if parent is not None:
                result["category_parents"][eid] = parent
        if kind != "entry":
            continue
        if is_conflicted(variants):
            if eid in document["entries"]:
                result["entries"][eid] = deepcopy(document["entries"][eid])
            elif eid in document["tombstones"]:
                result["tombstones"][eid] = document["tombstones"][eid]
        else:
            value = next(iter(variants.values()))
            if "purged_at" in value:
                result["tombstones"][eid] = value["purged_at"]
            else:
                result["entries"][eid] = deepcopy(value)
    colors = {cid: color for cid, color in document["settings"].get("category_colors", {}).items() if cid in result["categories"]}
    for key, variants in state["registers"].items():
        kind, cid = key.split(":")
        if kind != "category_color" or cid not in result["categories"] or is_conflicted(variants):
            continue
        color = next(iter(variants.values()))
        if color is None:
            colors.pop(cid, None)
        else:
            colors[cid] = color
    if colors or "category_colors" in result["settings"]:
        result["settings"]["category_colors"] = colors
    for record in result["entries"].values():
        if record["category"] not in result["categories"]:
            record["category"] = None
    result["sync"]["state"] = deepcopy(state)
    from .model import normalize_category_parents
    normalize_category_parents(result)
    return validate_document(result)
