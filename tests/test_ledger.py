from services.contracts import LedgerEvent
from services.ledger import SqliteLedger


def test_ledger_is_append_only_and_ordered() -> None:
    ledger = SqliteLedger()
    ledger.append(LedgerEvent(event_id="1", project_id="p", kind="first", payload={"n": 1}))
    ledger.append(LedgerEvent(event_id="2", project_id="p", kind="second", payload={"n": 2}))
    assert [event.kind for event in ledger.recent_events("p")] == ["first", "second"]
