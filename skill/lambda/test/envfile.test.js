const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { loadEnvFile } = require('../index.js');

function tmpJson(obj) {
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'roomcode-env-')), 'env.json');
  fs.writeFileSync(file, typeof obj === 'string' ? obj : JSON.stringify(obj));
  return file;
}

test('loadEnvFile preenche o que falta e nao sobrescreve o ambiente', () => {
  process.env.RC_TEST_SET = 'do-ambiente';
  delete process.env.RC_TEST_NEW;
  delete process.env.RC_TEST_EMPTY;
  loadEnvFile(tmpJson({ RC_TEST_SET: 'do-arquivo', RC_TEST_NEW: 'novo', RC_TEST_EMPTY: '' }));
  assert.strictEqual(process.env.RC_TEST_SET, 'do-ambiente');
  assert.strictEqual(process.env.RC_TEST_NEW, 'novo');
  assert.strictEqual(process.env.RC_TEST_EMPTY, undefined);
});

test('loadEnvFile sem arquivo nao faz nada', () => {
  assert.doesNotThrow(() => loadEnvFile(path.join(os.tmpdir(), 'roomcode-nao-existe', 'env.json')));
});

test('loadEnvFile com JSON invalido falha alto', () => {
  assert.throws(() => loadEnvFile(tmpJson('{ isto nao e json')));
});

test('env.json nao esta versionado', () => {
  assert.ok(!fs.existsSync(path.join(__dirname, '..', 'env.json')), 'skill/lambda/env.json nao pode existir no repo');
});
