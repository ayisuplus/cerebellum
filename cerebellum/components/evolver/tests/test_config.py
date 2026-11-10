from evolver.config import EvolverConfig


def test_config_defaults():
    cfg = EvolverConfig(mysql_url="mysql://root:root@localhost:3306/test")
    assert cfg.embedding_model == "BAAI/bge-m3"
    assert cfg.embedding_dim == 1024
    assert cfg.recall_top_k == 5
    assert cfg.recall_weights == (0.6, 0.15, 0.1, 0.15)
    assert cfg.skill_output_dir == "./skills"
    assert cfg.log_level == "INFO"


def test_config_custom_values():
    cfg = EvolverConfig(
        mysql_url="mysql://u:p@host:3306/db",
        embedding_model="custom/model",
        embedding_dim=768,
        recall_top_k=10,
        recall_weights=(0.5, 0.2, 0.15, 0.15),
        skill_output_dir="./out",
        log_level="DEBUG",
    )
    assert cfg.embedding_model == "custom/model"
    assert cfg.embedding_dim == 768
    assert cfg.recall_top_k == 10
    assert cfg.recall_weights == (0.5, 0.2, 0.15, 0.15)


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("EVOLVER_MYSQL_URL", "mysql://u:p@h:3306/db")
    monkeypatch.setenv("EVOLVER_EMBEDDING_MODEL", "test/model")
    cfg = EvolverConfig.from_env()
    assert cfg.mysql_url == "mysql://u:p@h:3306/db"
    assert cfg.embedding_model == "test/model"


def test_config_data_url_default_none():
    cfg = EvolverConfig(mysql_url="sqlite:///x.db")
    assert cfg.data_url is None


def test_config_from_env_reads_data_url(monkeypatch):
    monkeypatch.setenv("EVOLVER_DB_URL", "sqlite:///x.db")
    monkeypatch.setenv("EVOLVER_DATA_URL", "mysql://root:root@localhost:3306/data")
    cfg = EvolverConfig.from_env()
    assert cfg.data_url == "mysql://root:root@localhost:3306/data"
