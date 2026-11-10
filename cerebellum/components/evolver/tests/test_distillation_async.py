import asyncio
import pytest
from unittest.mock import MagicMock
from evolver.distillation import DistillationEngine


@pytest.mark.asyncio
async def test_adistill_happy_path():
    """adistill should delegate to distill via asyncio.to_thread."""
    engine = DistillationEngine.__new__(DistillationEngine)
    engine.distill = MagicMock(return_value=[{"text": "distilled"}])
    result = await engine.adistill([{"text": "raw"}])
    assert result == [{"text": "distilled"}]
    engine.distill.assert_called_once()


@pytest.mark.asyncio
async def test_abuild_graph():
    """abuild_graph should delegate to build_graph."""
    engine = DistillationEngine.__new__(DistillationEngine)
    engine.build_graph = MagicMock(return_value={"nodes": 5})
    result = await engine.abuild_graph([{"text": "data"}])
    assert result == {"nodes": 5}


@pytest.mark.asyncio
async def test_abuild_links():
    """abuild_links should delegate to build_links."""
    engine = DistillationEngine.__new__(DistillationEngine)
    engine.build_links = MagicMock(return_value=[{"from": 1, "to": 2}])
    result = await engine.abuild_links([{"text": "data"}])
    assert result == [{"from": 1, "to": 2}]
