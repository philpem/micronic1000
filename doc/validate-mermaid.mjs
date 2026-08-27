import fs from 'node:fs/promises';
import { JSDOM } from 'jsdom';

const dom = new JSDOM('');
globalThis.window = dom.window;
globalThis.document = dom.window.document;
const { default: mermaid } = await import('mermaid');

const inputPath = process.argv[2];
if (!inputPath) {
  console.error('usage: node validate-mermaid.mjs DIAGRAM.mmd');
  process.exit(2);
}

try {
  await mermaid.parse(await fs.readFile(inputPath, 'utf8'));
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
} finally {
  dom.window.close();
}
