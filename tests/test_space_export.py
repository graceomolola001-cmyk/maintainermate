"""Deployment exports must omit local-only files and preserve existing output."""
from pathlib import Path

import pytest
from scripts import build_space


def test_space_export_contains_public_sources_only(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    for folder in ['app', 'deploy', '.venv', '.git']:
        (source / folder).mkdir(parents=True)
    for name in ['Dockerfile', '.dockerignore', 'requirements.txt', 'LICENSE',
                 'app/main.py', 'deploy/serve.py', 'deploy/README.space.md']:
        (source / name).write_text('public test fixture', encoding='utf-8')
    for name in ['.env', 'app/.env', 'app/private.key', '.venv/local.txt', '.git/config']:
        (source / name).write_text('synthetic private fixture', encoding='utf-8')
    monkeypatch.setattr(build_space, 'ROOT', source)
    output = tmp_path / 'export'
    build_space.build(output)
    assert (output / 'README.md').read_text() == 'public test fixture'
    assert (output / 'app/main.py').is_file()
    names = {str(p.relative_to(output)) for p in output.rglob('*')}
    assert not any('.env' in name or '.venv' in name or '.git/' in name
                   or name.endswith('.key') for name in names)
    with pytest.raises(FileExistsError):
        build_space.build(output)


def test_space_export_rejects_source_symlinks(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    (source / 'app').mkdir(parents=True)
    (source / 'deploy').mkdir()
    target = tmp_path / 'outside.txt'
    target.write_text('outside fixture')
    try:
        (source / 'app/link.txt').symlink_to(target)
    except OSError:
        pytest.skip('This platform does not permit creating test symlinks.')
    monkeypatch.setattr(build_space, 'ROOT', source)
    with pytest.raises(ValueError, match='symlink'):
        build_space.build(tmp_path / 'export')
