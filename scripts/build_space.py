"""Export only public deployment files for a Docker Space; never include credentials."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def build(output: Path) -> None:
    if output.exists():
        raise FileExistsError(f'{output} already exists. Choose a new directory to preserve its files.')
    for directory in ['app', 'deploy']:
        if any(path.is_symlink() for path in (ROOT / directory).rglob('*')):
            raise ValueError('Deployment sources contain a symlink; inspect it before exporting.')
    output.mkdir(parents=True)
    for name in ['Dockerfile', '.dockerignore', 'requirements.txt', 'LICENSE']:
        shutil.copyfile(ROOT / name, output / name)
    shutil.copyfile(ROOT / 'deploy' / 'README.space.md', output / 'README.md')
    for directory in ['app', 'deploy']:
        shutil.copytree(ROOT / directory, output / directory,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.log', '.env', '.env.*', '*.pem', '*.key', '.git'))


if __name__ == '__main__':
    build(ROOT / '_space')
    print('Deployment files exported to _space/. Confirm hosting eligibility before creating a Space.')
