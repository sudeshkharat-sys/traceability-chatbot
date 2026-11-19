// Copies the PDF.js worker from node_modules into public/ so the app serves it
// itself instead of loading it from a public CDN (unpkg.com).
const fs = require("fs");
const path = require("path");

const src = path.join(__dirname, "..", "node_modules", "pdfjs-dist", "build", "pdf.worker.min.mjs");
const dest = path.join(__dirname, "..", "public", "pdf.worker.min.mjs");

if (!fs.existsSync(src)) {
  console.error("copy-pdf-worker: not found: " + src + " (run npm install first)");
  process.exit(1);
}
fs.copyFileSync(src, dest);
console.log("copy-pdf-worker: copied to public/pdf.worker.min.mjs");
