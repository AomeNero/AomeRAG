import os

import pytest

from aome_rag.providers.messages import Message
from aome_rag.session.db import open_db
from aome_rag.session.store import SessionNotFound, SessionStore

pytestmark = pytest.mark.integration


async def test_round_trip_messages(tmp_path) -> None:
    db = await open_db(os.path.join(str(tmp_path), "s.db"))
    store = SessionStore(db)
    sid = await store.create_session("alice", title="t")
    await store.append_message(sid, "alice", Message.text("user", "hi"))
    await store.append_message(sid, "alice", Message.text("assistant", "hello"))

    msgs = await store.get_messages(sid, "alice")
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[0].as_text() == "hi"
    await db.close()


async def test_isolation_user_cannot_read_others_session(tmp_path) -> None:
    db = await open_db(os.path.join(str(tmp_path), "s.db"))
    store = SessionStore(db)
    sid = await store.create_session("alice")
    await store.append_message(sid, "alice", Message.text("user", "secret"))

    # bob reads alice's session -> empty (JOIN filters by user_id)
    assert await store.get_messages(sid, "bob") == []
    # bob cannot list alice's sessions
    assert await store.list_sessions("bob") == []
    # bob cannot append to alice's session
    with pytest.raises(SessionNotFound):
        await store.append_message(sid, "bob", Message.text("user", "x"))
    # bob cannot delete alice's session
    assert await store.delete_session(sid, "bob") is False
    await db.close()


async def test_delete_session(tmp_path) -> None:
    db = await open_db(os.path.join(str(tmp_path), "s.db"))
    store = SessionStore(db)
    sid = await store.create_session("alice")
    await store.append_message(sid, "alice", Message.text("user", "hi"))
    assert await store.delete_session(sid, "alice") is True
    assert await store.get_messages(sid, "alice") == []
    await db.close()
