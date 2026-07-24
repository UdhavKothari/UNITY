import importlib.util, os
spec = importlib.util.spec_from_file_location("srv", os.path.join(os.path.dirname(__file__), "..", "server.py"))
srv = importlib.util.module_from_spec(spec); spec.loader.exec_module(srv)

def test_massplan_page_registered():
    assert "op_massplan" in srv.ALL_PAGES

def test_migrate_backfills_batch_planning_fields():
    db = {"batches": [
        {"id": "B-0001", "mcPin": "JET-2"},
        {"id": "B-0002", "mcPin": "JET-2"},
        {"id": "B-0003", "mcPin": ""},
    ]}
    srv._migrate(db)
    b = {x["id"]: x for x in db["batches"]}
    assert b["B-0001"]["machine"] == "JET-2"
    assert b["B-0003"]["machine"] == ""            # no pin -> empty, still gets planDay/seq
    for x in db["batches"]:
        assert isinstance(x["seq"], int) and x["seq"] >= 1
        assert len(x["planDay"]) == 10             # YYYY-MM-DD
    # per-machine sequence restarts at 1
    assert b["B-0001"]["seq"] == 1 and b["B-0002"]["seq"] == 2

if __name__ == "__main__":
    test_massplan_page_registered()
    test_migrate_backfills_batch_planning_fields()
    print("ok")
