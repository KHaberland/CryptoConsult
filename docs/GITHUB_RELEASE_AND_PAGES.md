# Публикация CryptoConsult на GitHub Release и GitHub Pages

Пошаговая инструкция по настройке релизов и лендинга на GitHub.

---

## Часть 1: GitHub Pages (лендинг)

### Шаг 1.1. Включить GitHub Pages

1. Откройте репозиторий: `https://github.com/KHaberland/CryptoConsult`
2. Перейдите в **Settings** → **Pages**
3. В разделе **Build and deployment**:
   - **Source**: `GitHub Actions` (рекомендуется) или `Deploy from a branch`
   - Если выбрали **Deploy from a branch**:
     - **Branch**: `main`
     - **Folder**: `/docs`
     - Сохраните

### Шаг 1.2. Если используете GitHub Actions (рекомендуется)

Workflow `.github/workflows/pages.yml` уже настроен. При каждом пуше в `main` лендинг из `docs/` будет публиковаться автоматически.

Сайт будет доступен по адресу:
```
https://KHaberland.github.io/CryptoConsult/
```

### Шаг 1.3. Если используете Deploy from a branch

Убедитесь, что в репозитории есть папка `docs/` с файлом `index.html`. После сохранения настроек GitHub автоматически соберёт и опубликует сайт.

---

## Часть 2: GitHub Release (установщик)

### Шаг 2.1. Подготовка к релизу

1. Обновите версию в `version.py`:
   ```python
   __version__ = "1.0.1"
   ```

2. Синхронизируйте версию во frontend:
   ```powershell
   cd frontend
   npm run prebuild
   ```

3. Обновите версию в `installer/CryptoConsult.iss`:
   ```
   #define MyAppVersion "1.0.1"
   ```

4. Закоммитьте изменения:
   ```powershell
   git add version.py frontend/package.json frontend/src/version.ts installer/CryptoConsult.iss
   git commit -m "Версия 1.0.1"
   ```

### Шаг 2.2. Создание релиза вручную

1. Соберите установщик локально:
   ```powershell
   cd installer
   .\build-installer.ps1
   ```

2. Создайте тег и запушьте:
   ```powershell
   git tag -a v1.0.1 -m "Релиз 1.0.1"
   git push origin v1.0.1
   ```

3. На GitHub: **Releases** → **Create a new release**
4. Выберите тег `v1.0.1`
5. Заголовок: `Релиз 1.0.1` (или скопируйте из `RELEASE_NOTES_TEMPLATE.md`)
6. Описание: вставьте шаблон из `docs/RELEASE_NOTES_TEMPLATE.md`
7. Загрузите файл: `dist\installer\CryptoConsult-Setup-1.0.1.exe`
8. Нажмите **Publish release**

### Шаг 2.3. Создание релиза через GitHub Actions (автоматически)

Workflow `.github/workflows/release.yml` настроен на автоматическую сборку при пуше тега `v*`.

**Важно:** Сборка выполняется на Windows runner. Inno Setup устанавливается автоматически.

1. Обновите версию (как в шаге 2.1)
2. Закоммитьте и создайте тег:
   ```powershell
   git add .
   git commit -m "Версия 1.0.1"
   git tag -a v1.0.1 -m "Релиз 1.0.1"
   git push origin main
   git push origin v1.0.1
   ```

3. Перейдите в **Actions** на GitHub — workflow запустится
4. После успешной сборки перейдите в **Releases** → откройте черновик → добавьте описание и опубликуйте

---

## Часть 3: Структура файлов

```
CryptoConsult/
├── .github/
│   └── workflows/
│       ├── release.yml      # Сборка установщика при пуше тега v*
│       └── pages.yml      # Публикация лендинга на GitHub Pages
├── docs/
│   ├── GITHUB_RELEASE_AND_PAGES.md   # Эта инструкция
│   ├── RELEASE_NOTES_TEMPLATE.md     # Шаблон описания релиза
│   └── index.html                   # HTML-лендинг для GitHub Pages
└── ...
```

---

## Часть 4: Проверка

| Действие | Результат |
|---------|-----------|
| Push в `main` | Лендинг обновляется на GitHub Pages |
| Push тега `v1.0.0` | Запускается сборка установщика |
| Ручной релиз | Загружаете .exe вручную |

---

## Часть 5: Частые проблемы

### GitHub Pages показывает 404

- Подождите 1–2 минуты после первого деплоя
- Проверьте, что в **Settings** → **Pages** выбран правильный источник
- URL: `https://<username>.github.io/<repo>/` (для репозиториев с именем репо в URL)

### Сборка установщика падает в Actions

- Проверьте логи workflow
- Убедитесь, что `version.py`, `package.json` и `CryptoConsult.iss` содержат одну и ту же версию
- Inno Setup устанавливается через Chocolatey автоматически

### Версия отображается неправильно

- Запустите `npm run prebuild` в `frontend/` перед сборкой
- Проверьте, что `version.py` — единственный источник версии
