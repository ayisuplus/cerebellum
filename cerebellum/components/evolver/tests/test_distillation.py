import json
import pytest
from unittest.mock import MagicMock, patch

from evolver.distillation import DistillationEngine


@pytest.fixture
def mock_archive():
    archive = MagicMock()
    archive.list_recent.return_value = [
        {"id": 1, "content": "Debugged memory leak in worker pool. Root cause: unclosed connections.",
         "kind": "debug", "tags": ["memory", "workers"], "source": "dev"},
        {"id": 2, "content": "Implementing cache eviction policy. LRU works best for our access pattern.",
         "kind": "feature", "tags": ["cache"], "source": "dev"},
        {"id": 3, "content": "Short note", "kind": "note", "tags": [], "source": "dev"},
    ]
    return archive


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.insert_memory.side_effect = [101, 102, 103]
    return storage


@pytest.fixture
def mock_graph():
    graph = MagicMock()
    graph.build_from_text.side_effect = [
        [201, 202],
        [203],
        [],
    ]
    return graph


@pytest.fixture
def mock_link():
    link = MagicMock()
    return link


@pytest.fixture
def engine(mock_archive, mock_storage, mock_graph, mock_link):
    return DistillationEngine(
        archive_store=mock_archive,
        storage=mock_storage,
        graph_engine=mock_graph,
        link_engine=mock_link,
        lang="en",
    )


class TestDistill:
    def test_distill_processes_records(self, engine, mock_storage):
        result = engine.distill(limit=10)
        assert result["processed"] == 3
        assert result["stored"] == 2
        assert result["skipped"] == 1
        assert result["memory_ids"] == [101, 102]
        assert mock_storage.insert_memory.call_count == 2

    def test_distill_skips_short_content(self, engine, mock_storage):
        result = engine.distill(limit=10)
        mems = [c.args[0] for c in mock_storage.insert_memory.call_args_list]
        assert all(len(m.content) >= 20 for m in mems)

    def test_distill_no_records(self, engine, mock_archive):
        mock_archive.list_recent.return_value = []
        result = engine.distill(limit=10)
        assert result["processed"] == 0
        assert result["stored"] == 0

    def test_distill_sets_lifecycle_distilled(self, engine, mock_storage):
        engine.distill(limit=10)
        for call in mock_storage.insert_memory.call_args_list:
            mem = call.args[0]
            assert mem.lifecycle == "distilled"

    def test_distill_sets_category_from_record_kind(self, engine, mock_storage):
        engine.distill(limit=10)
        mems = [c.args[0] for c in mock_storage.insert_memory.call_args_list]
        assert mems[0].category == "debug"
        assert mems[1].category == "feature"

    def test_distill_forwards_tags(self, engine, mock_storage):
        engine.distill(limit=10)
        mems = [c.args[0] for c in mock_storage.insert_memory.call_args_list]
        assert mems[0].tags == ["memory", "workers"]
        assert mems[1].tags == ["cache"]

    def test_distill_with_kind_filter(self, engine, mock_archive):
        mock_archive.search_archive.return_value = [
            {"id": 10, "content": "Filtered archive record content for testing purposes.",
             "kind": "log", "tags": [], "source": "test"},
        ]
        result = engine.distill(kind="log", limit=5)
        assert result["processed"] == 1
        mock_archive.search_archive.assert_called_with("log", limit=5)

    def test_distill_with_llm(self, mock_archive, mock_storage, mock_graph, mock_link):
        llm = MagicMock()
        llm.available = True
        llm.call_llm.return_value = json.dumps({
            "experiences": [{
                "content": "Use LRU cache eviction for optimal memory usage.",
                "category": "optimization",
                "tags": ["cache", "LRU"],
            }]
        })
        llm.extract_final_answer.return_value = json.dumps({
            "experiences": [{
                "content": "Use LRU cache eviction for optimal memory usage.",
                "category": "optimization",
                "tags": ["cache", "LRU"],
            }]
        })
        mock_archive.list_recent.return_value = [
            {"id": 5, "content": "LRU eviction policy worked best for our workload.",
             "kind": "note", "tags": ["cache"], "source": "dev"},
        ]
        engine = DistillationEngine(
            archive_store=mock_archive, storage=mock_storage,
            graph_engine=mock_graph, link_engine=mock_link,
            llm_client=llm, lang="en",
        )
        result = engine.distill(limit=5)
        assert result["stored"] == 1
        mem = mock_storage.insert_memory.call_args[0][0]
        assert "LRU" in mem.content
        assert mem.category == "optimization"

    def test_distill_storage_failure(self, engine, mock_storage):
        mock_storage.insert_memory.side_effect = [101, None, Exception("DB error")]
        result = engine.distill(limit=10)
        assert result["stored"] == 1
        assert result["skipped"] == 2


class TestBuildGraph:
    def test_build_graph_creates_nodes_and_links(self, engine, mock_storage):
        result = engine.build_graph([101, 102], ["worker pool memory leak", "LRU cache eviction"])
        assert result["node_count"] == 3
        assert result["link_count"] == 3
        assert mock_storage.insert_link.call_count == 3

    def test_build_graph_empty_text_skipped(self, engine, mock_storage):
        result = engine.build_graph([101], [""])
        assert result["node_count"] == 0
        assert result["link_count"] == 0

    def test_build_graph_no_texts(self, engine, mock_storage):
        result = engine.build_graph([], [])
        assert result["node_count"] == 0


class TestBuildLinks:
    def test_build_links_calls_auto_link(self, engine, mock_link):
        result = engine.build_links([101, 102], ["text a", "text b"])
        assert result["total_linked"] == 2
        assert mock_link.auto_link_memory.call_count == 2

    def test_build_links_skips_empty(self, engine, mock_link):
        result = engine.build_links([101], [""])
        assert result["total_linked"] == 0
        mock_link.auto_link_memory.assert_not_called()

    def test_build_links_empty(self, engine, mock_link):
        result = engine.build_links([], [])
        assert result["total_linked"] == 0

    def test_build_links_handles_exception(self, engine, mock_link):
        mock_link.auto_link_memory.side_effect = [None, Exception("link error")]
        result = engine.build_links([101, 102], ["text a", "text b"])
        assert result["total_linked"] == 1


class TestArchiveListRecent:
    def test_list_recent_all(self, mock_conn):
        from evolver.archive_store import ArchiveStore
        conn, cursor = mock_conn
        cursor.fetchall.return_value = (
            {"id": 1, "content": "test", "kind": "log", "ref": None,
             "tags": None, "source": None, "meta": None, "created_at": "2025-01-01"},
        )
        with patch("evolver.archive_store.pymysql") as mock_pymysql:
            mock_pymysql.connect.return_value = conn
            store = ArchiveStore("mysql://root:root@localhost:3306/data", pool_size=1)
            rows = store.list_recent(limit=10)
            assert len(rows) == 1
            assert rows[0]["content"] == "test"

    def test_list_recent_by_kind(self, mock_conn):
        from evolver.archive_store import ArchiveStore
        conn, cursor = mock_conn
        cursor.fetchall.return_value = (
            {"id": 2, "content": "filtered", "kind": "debug", "ref": None,
             "tags": None, "source": None, "meta": None, "created_at": "2025-01-01"},
        )
        with patch("evolver.archive_store.pymysql") as mock_pymysql:
            mock_pymysql.connect.return_value = conn
            store = ArchiveStore("mysql://root:root@localhost:3306/data", pool_size=1)
            rows = store.list_recent(limit=5, kind="debug")
            assert len(rows) == 1
