"""Logo pack: index parsing, manifest safety, the served view and the sync."""
import json
from unittest.mock import AsyncMock, MagicMock

from custom_components.ceny_paliv import CenyPalivLogoView
from custom_components.ceny_paliv.logos import (
    ID_RE,
    PNG_MAGIC,
    async_fetch_index,
    async_sync,
    chains_in,
    logo_dir,
    scan_logos,
)


def session_returning(text=None, body=None, status=200):
    response = MagicMock(status=status)
    response.text = AsyncMock(return_value=text)
    response.read = AsyncMock(return_value=body)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.get.return_value = context
    return session


def test_logo_ids_are_strict():
    assert ID_RE.match("robin-oil")
    for bad in ("orlen\n", "../evil", "Orlen", "", "-x", "a" * 41):
        assert not ID_RE.match(bad), bad


async def test_index_skips_malformed_items_and_reads_a_lone_match_as_one_name():
    index = {"logos": ["orlen", {"id": "omv", "match": "omv"}, {"id": "Bad!"}, {"id": "mol", "match": ["mol", 5]}]}
    result = await async_fetch_index(session_returning(text=json.dumps(index)))
    assert result == [
        {"id": "omv", "label": "omv", "match": ["omv"]},
        {"id": "mol", "label": "mol", "match": ["mol"]},
    ]
    assert chains_in(["OMV Praha", "Shell"], result) == {"omv"}
    assert await async_fetch_index(session_returning(text="not json")) is None


def test_scan_ignores_bad_manifest_entries(tmp_path):
    (tmp_path / "orlen.png").write_bytes(PNG_MAGIC)
    (tmp_path / "robin-oil.png").write_bytes(PNG_MAGIC)
    (tmp_path / "installed.json").write_text(
        json.dumps({"orlen": {"match": "orlen"}, "../evil": {"match": ["x"]}, "robin-oil": "broken"}),
        encoding="utf-8",
    )
    assert scan_logos(tmp_path) == [
        {"id": "orlen", "match": ["orlen"]},
        {"id": "robin-oil", "match": ["robin-oil", "robin oil"]},
    ]


async def test_sync_never_deletes_outside_its_folder(hass, tmp_path):
    hass.config.config_dir = str(tmp_path)
    folder = logo_dir(hass)
    folder.mkdir()
    outside = tmp_path / "evil.png"
    outside.write_bytes(PNG_MAGIC)
    (folder / "orlen.png").write_bytes(PNG_MAGIC)
    (folder / "installed.json").write_text(
        json.dumps({"orlen": {"match": ["orlen"]}, "../evil": {"match": ["x"]}}), encoding="utf-8"
    )
    await async_sync(hass, MagicMock(), [], set())
    assert outside.exists()  # a tampered manifest id is never turned into a path
    assert not (folder / "orlen.png").exists()  # a downloaded, no longer wanted logo is removed


async def test_sync_refuses_a_download_that_is_not_a_small_png(hass, tmp_path):
    hass.config.config_dir = str(tmp_path)
    index = [{"id": "orlen", "label": "Orlen", "match": ["orlen"]}]
    await async_sync(hass, session_returning(body=b"<html>"), index, {"orlen"})
    assert not (logo_dir(hass) / "orlen.png").exists()
    await async_sync(hass, session_returning(body=PNG_MAGIC + b"x"), index, {"orlen"})
    assert (logo_dir(hass) / "orlen.png").exists()


async def test_logo_view_serves_only_valid_ids(hass, tmp_path):
    hass.config.config_dir = str(tmp_path)
    logo_dir(hass).mkdir()
    (logo_dir(hass) / "orlen.png").write_bytes(PNG_MAGIC)
    view = CenyPalivLogoView(hass)
    assert (await view.get(MagicMock(), "orlen\n")).status == 404
    assert (await view.get(MagicMock(), "shell")).status == 404
    assert (await view.get(MagicMock(), "orlen")).status == 200
