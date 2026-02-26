/**
 * Синхронизирует версию из version.py в frontend.
 * Запускается перед сборкой (prebuild).
 * Не редактируйте version.ts вручную — он генерируется автоматически.
 */

const fs = require('fs')
const path = require('path')

const projectRoot = path.resolve(__dirname, '../..')
const versionPyPath = path.join(projectRoot, 'version.py')
const versionTsPath = path.join(projectRoot, 'frontend', 'src', 'version.ts')
const packageJsonPath = path.join(projectRoot, 'frontend', 'package.json')

const content = fs.readFileSync(versionPyPath, 'utf8')
const match = content.match(/__version__\s*=\s*["']([^"']+)["']/)
const version = match ? match[1] : '0.0.0'

const versionTs = `// Автоматически сгенерировано из version.py — не редактировать вручную
export const APP_VERSION = '${version}'
`

fs.writeFileSync(versionTsPath, versionTs, 'utf8')
console.log(`[sync-version] Версия ${version} синхронизирована в frontend/src/version.ts`)

// Обновляем version в package.json
const pkg = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'))
pkg.version = version
fs.writeFileSync(packageJsonPath, JSON.stringify(pkg, null, 2) + '\n', 'utf8')
console.log(`[sync-version] package.json обновлён: version = ${version}`)
