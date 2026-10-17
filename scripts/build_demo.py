"""Build a static, sample-only portfolio demo using the app's existing frontend."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    assets = ROOT / 'app' / 'static'
    html = (assets / 'index.html').read_text(encoding='utf-8')
    html = html.replace('<html lang="en">', '<html lang="en" data-demo="true">')
    html = html.replace('/static/style.css', './style.css').replace('/static/app.js', './app.js')
    html = html.replace('<title>MaintainerMate AI | Open-source issue assistant</title>',
                        '<title>Try MaintainerMate AI | Sample demo</title>')
    (output / 'index.html').write_text(html, encoding='utf-8')
    for name in ['app.js', 'style.css']:
        shutil.copyfile(assets / name, output / name)
    shutil.copyfile(ROOT / 'app' / 'demo-plan.json', output / 'demo-plan.json')
    (output / '.nojekyll').touch()


if __name__ == '__main__':
    build(ROOT / '_site')
    print('Built the sample-only demo in _site/')
