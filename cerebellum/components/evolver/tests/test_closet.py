from evolver.closet import ClosetIndex


def test_closet_add_and_query():
    closet = ClosetIndex()
    closet.add(memory_id=1, content="Fixed auth bug in login module", category="success")
    closet.add(memory_id=2, content="Deployed docker container", category="success")
    results = closet.query("auth")
    assert 1 in results
    assert 2 not in results


def test_closet_query_multiple_matches():
    closet = ClosetIndex()
    closet.add(memory_id=1, content="Auth fix for login", category="success")
    closet.add(memory_id=2, content="Auth token validation", category="success")
    results = closet.query("auth")
    assert 1 in results
    assert 2 in results


def test_closet_query_no_match():
    closet = ClosetIndex()
    closet.add(memory_id=1, content="Docker deploy", category="success")
    results = closet.query("nonexistent")
    assert results == []


def test_closet_remove():
    closet = ClosetIndex()
    closet.add(memory_id=1, content="Auth fix", category="success")
    closet.remove(1)
    results = closet.query("auth")
    assert 1 not in results


def test_closet_empty_query():
    closet = ClosetIndex()
    closet.add(memory_id=1, content="Auth fix", category="success")
    results = closet.query("")
    assert results == []
