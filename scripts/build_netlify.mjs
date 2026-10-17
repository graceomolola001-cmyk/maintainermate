// Publish only known browser assets. Environment variables and source stay private.
import {mkdir, copyFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = path.join(root, '_netlify');
await mkdir(path.join(output, 'static'), {recursive: true});
await copyFile(path.join(root, 'app/static/index.html'), path.join(output, 'index.html'));
for (const name of ['app.js', 'style.css']) {
  await copyFile(path.join(root, 'app/static', name), path.join(output, 'static', name));
}
console.log('Built Netlify browser assets in _netlify/. No API key is included.');
