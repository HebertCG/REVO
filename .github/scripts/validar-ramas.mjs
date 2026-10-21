import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const ejecutar = promisify(execFile);

try {
  const { EVENTO, RAMA, BASE_PR, ORIGEN_PR, REPO_PR, REPO } = process.env;

  if (EVENTO === 'pull_request') {
    if (!['stating', 'main'].includes(BASE_PR)) {
      throw new Error('El PR debe apuntar a stating o main.');
    }
    if (BASE_PR === 'main' &&
        (ORIGEN_PR !== 'stating' || !REPO || REPO_PR !== REPO)) {
      throw new Error('main solo recibe PR desde stating de este repositorio.');
    }
    console.log('Origen del PR correcto; las pruebas usan la combinacion propuesta por GitHub.');
  } else {
    if (!['push', 'workflow_dispatch'].includes(EVENTO) || !RAMA) {
      throw new Error('Falta un evento o una rama de trabajo valida.');
    }
    if (!['main', 'stating'].includes(RAMA)) {
      // Compara arboles en el runner sin cambiar ramas, archivos ni hacer un merge.
      await ejecutar('git', [
        'fetch', '--no-tags', 'origin',
        '+refs/heads/stating:refs/remotes/origin/stating',
      ]);
      await ejecutar('git', ['merge-tree', '--write-tree', 'origin/stating', 'HEAD']);
      console.log('La rama se puede combinar con la version actual de stating sin conflictos.');
    } else {
      console.log('Rama central: ejecutar todas las puertas de pruebas.');
    }
  }
} catch (error) {
  console.error(error.message);
  if (error.stdout) console.error(error.stdout.trim());
  if (error.stderr) console.error(error.stderr.trim());
  process.exitCode = 1;
}
