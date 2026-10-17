"""Check the standalone demo artifact without requiring an AI backend."""
import json
from pathlib import Path

from scripts.build_demo import build


def test_demo_build_supports_project_site_paths(tmp_path):
    output = tmp_path / 'maintainermate'
    build(output)
    html = (output / 'index.html').read_text(encoding='utf-8')
    assert 'data-demo="true"' in html
    assert 'href="./style.css"' in html
    assert 'src="./app.js"' in html
    assert '/static/' not in html
    assert 'Interactive portfolio demo' in html
    assert 'No AI model runs here' in html
    for name in ['index.html', 'style.css', 'app.js', 'demo-plan.json', '.nojekyll']:
        assert (output / name).is_file()
    sample = json.loads((output / 'demo-plan.json').read_text(encoding='utf-8'))
    assert 'DEMO ONLY' in sample['model']
    assert sample['issue_source'] == 'Fixed sample issue'
    assert 'IMPLEMENTATION PLAN' in sample['analysis']
    # Rebuilding into an existing directory is safe and reproducible.
    initial = {p.name: p.read_bytes() for p in output.iterdir()}
    build(output)
    assert initial == {p.name: p.read_bytes() for p in output.iterdir()}
