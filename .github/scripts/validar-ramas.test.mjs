import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

const ejecutar = promisify(execFile);
const script = fileURLToPath(new URL('./validar-ramas.mjs', import.meta.url));

async function validar(env, cwd) {
  return ejecutar(process.execPath, [script], {
    cwd,
    env: { ...process.env, EVENTO: '', RAMA: '', BASE_PR: '', ORIGEN_PR: '',
      REPO_PR: '', REPO: 'equipo/revo', ...env },
  });
}

test('permite promover stating del mismo repositorio a main', async () => {
  await validar({ EVENTO: 'pull_request', BASE_PR: 'main', ORIGEN_PR: 'stating',
    REPO_PR: 'equipo/revo' });
});

for (const [origen, repo] of [
  ['WilsonCollantesAponte', 'equipo/revo'],
  ['stating', 'otro/revo'],
  ['', 'equipo/revo'],
]) {
  test(`rechaza promover ${repo}:${origen || '(sin origen)'} a main`, async () => {
    await assert.rejects(validar({ EVENTO: 'pull_request', BASE_PR: 'main',
      ORIGEN_PR: origen, REPO_PR: repo }), /main solo recibe PR desde stating/);
  });
}

test('permite PR de trabajo hacia stating', async () => {
  await validar({ EVENTO: 'pull_request', BASE_PR: 'stating',
    ORIGEN_PR: 'AlexisMH30', REPO_PR: 'equipo/revo' });
});

test('rechaza un destino de PR fuera del flujo', async () => {
  await assert.rejects(validar({ EVENTO: 'pull_request', BASE_PR: 'otra' }),
    /El PR debe apuntar a stating o main/);
});

for (const evento of ['push', 'workflow_dispatch']) {
  for (const rama of ['main', 'stating']) {
    test(`permite ${evento} en ${rama} sin buscar otra rama`, async () => {
      await validar({ EVENTO: evento, RAMA: rama }, tmpdir());
    });
  }
}

test('rechaza contexto incompleto o eventos inesperados', async () => {
  await assert.rejects(validar({ EVENTO: 'push' }), /Falta un evento o una rama/);
  await assert.rejects(validar({ EVENTO: 'schedule', RAMA: 'main' }),
    /Falta un evento o una rama/);
});

/** Crea dos repositorios desechables; nunca modifica el checkout del proyecto. */
async function repositorios(t) {
  const raiz = await mkdtemp(join(tmpdir(), 'revo-ramas-'));
  t.after(() => rm(raiz, { recursive: true, force: true }));
  const origen = join(raiz, 'origen');
  const trabajo = join(raiz, 'trabajo');
  const git = (cwd, ...args) => ejecutar('git', args, { cwd });
  await mkdir(origen);
  await git(origen, 'init', '--initial-branch=main');
  await git(origen, 'config', 'user.name', 'Pruebas REVO');
  await git(origen, 'config', 'user.email', 'pruebas@example.invalid');
  await writeFile(join(origen, 'archivo.txt'), 'base\n');
  await git(origen, 'add', 'archivo.txt');
  await git(origen, 'commit', '-m', 'base');
  await git(origen, 'branch', 'stating');
  await git(raiz, 'clone', origen, trabajo);
  await git(trabajo, 'config', 'user.name', 'Pruebas REVO');
  await git(trabajo, 'config', 'user.email', 'pruebas@example.invalid');
  await git(trabajo, 'switch', '-c', 'WilsonCollantesAponte');
  return { origen, trabajo, git };
}

test('detecta cambios compatibles sin modificar HEAD ni archivos', async (t) => {
  const { origen, trabajo, git } = await repositorios(t);
  await git(origen, 'switch', 'stating');
  await writeFile(join(origen, 'central.txt'), 'central\n');
  await git(origen, 'add', '.');
  await git(origen, 'commit', '-m', 'cambio central');
  await writeFile(join(trabajo, 'personal.txt'), 'personal\n');
  await git(trabajo, 'add', '.');
  await git(trabajo, 'commit', '-m', 'cambio personal');
  const antes = (await git(trabajo, 'rev-parse', 'HEAD')).stdout;
  await validar({ EVENTO: 'push', RAMA: 'WilsonCollantesAponte' }, trabajo);
  assert.equal((await git(trabajo, 'rev-parse', 'HEAD')).stdout, antes);
  assert.equal((await git(trabajo, 'status', '--porcelain')).stdout, '');
});

test('detecta un conflicto con los cambios mas recientes de stating', async (t) => {
  const { origen, trabajo, git } = await repositorios(t);
  await git(origen, 'switch', 'stating');
  await writeFile(join(origen, 'archivo.txt'), 'central\n');
  await git(origen, 'commit', '-am', 'cambio central posterior al clone');
  await writeFile(join(trabajo, 'archivo.txt'), 'personal\n');
  await git(trabajo, 'commit', '-am', 'cambio incompatible');
  const antes = (await git(trabajo, 'rev-parse', 'HEAD')).stdout;
  await assert.rejects(validar({ EVENTO: 'push', RAMA: 'WilsonCollantesAponte' }, trabajo),
    (error) => error.code === 1 && /CONFLICT/.test(error.stderr));
  assert.equal((await git(trabajo, 'rev-parse', 'HEAD')).stdout, antes);
  assert.equal((await git(trabajo, 'status', '--porcelain')).stdout, '');
});

test('falla si stating no existe en el remoto', async (t) => {
  const { origen, trabajo, git } = await repositorios(t);
  await git(origen, 'branch', '-D', 'stating');
  await assert.rejects(validar({ EVENTO: 'push', RAMA: 'WilsonCollantesAponte' }, trabajo),
    (error) => error.code === 1 && /stating/.test(error.stderr));
});
