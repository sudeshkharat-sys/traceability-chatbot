const fs   = require('fs');
const path = require('path');

const src = path.resolve(__dirname, '../node_modules/three/examples/jsm/libs/draco');
const dst = path.resolve(__dirname, '../public/draco');

if (!fs.existsSync(src)) {
  console.warn('Draco source not found at', src, '— skipping copy');
  process.exit(0);
}

if (!fs.existsSync(dst)) fs.mkdirSync(dst, { recursive: true });

fs.readdirSync(src).forEach(file => {
  fs.copyFileSync(path.join(src, file), path.join(dst, file));
  console.log('Copied', file);
});

console.log('Draco decoder ready at public/draco/');
