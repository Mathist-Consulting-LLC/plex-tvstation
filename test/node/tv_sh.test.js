const test = require('node:test');
const assert = require('node:assert/strict');
const { execFile } = require('node:child_process');
const { promisify } = require('node:util');

const execFileAsync = promisify(execFile);

test('tv.sh prints commands for every playlist and forwards all args', async () => {
  const { stdout } = await execFileAsync('bash', ['tv.sh', '--print-commands', '-l', '--force'], {
    cwd: process.cwd()
  });

  const lines = stdout.trim().split('\n');

  assert.equal(lines.length, 11);
  assert.match(lines[0], /\.venv\/bin\/python3 .*src\/main\.py tvstation -l --force$/);
  assert.match(lines[1], /python3 .*src\/main\.py tvstation -g comedy -l --force$/);
  assert.match(lines[2], /python3 .*src\/main\.py tvstation -g action -l --force$/);
  assert.match(lines[3], /python3 .*src\/main\.py tvstation -g animation -l --force$/);
  assert.match(lines[4], /python3 .*src\/main\.py tvstation -g sci-fi -l --force$/);
  assert.match(lines[5], /python3 .*src\/main\.py tvstation -g fantasy -l --force$/);
  assert.match(lines[6], /python3 .*src\/main\.py tvstation -f star-wars -l --force$/);
  assert.match(lines[7], /python3 .*src\/main\.py tvstation -f star-trek -l --force$/);
  assert.match(lines[8], /python3 .*src\/main\.py tvstation -f marvel -l --force$/);
  assert.match(lines[9], /python3 .*src\/main\.py tvstation -f dc -l --force$/);
  assert.match(lines[10], /python3 .*src\/main\.py tvstation -g comfort -l --force$/);
});
