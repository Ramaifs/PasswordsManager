import fs from 'node:fs/promises';
await fs.mkdir('dist/vendor', { recursive: true });
await fs.copyFile('node_modules/hash-wasm/dist/index.esm.js', 'dist/vendor/hash-wasm.js');
await fs.copyFile('node_modules/hash-wasm/LICENSE', 'dist/vendor/hash-wasm.LICENSE');
console.log('Vendored hash-wasm 4.12.0; no runtime CDN');
