# TTM - TikTok Media

TTM (TikTok Media) - это система для автоматической нарезки вертикальных клипов из длинных YouTube-видео с веб-интерфейсом, REST API и live-логами через WebSocket.

Репозиторий разделен на два слоя:

- `backend/` - FastAPI-приложение, которое запускает пайплайн обработки, управляет заданиями и отдает клипы.
- `frontend/` - React + Vite интерфейс для запуска задач, мониторинга прогресса и просмотра результатов.

---

## Что умеет проект

- запуск задач генерации клипов по списку YouTube-каналов;
- фоновая обработка и отслеживание статуса задач (`queued`, `running`, `completed`, `failed`, `cancelled`);
- просмотр логов в реальном времени через WebSocket;
- просмотр созданных клипов и миниатюр в галерее;
- редактирование ключевых параметров `config.yaml` из UI.

---

## Архитектура

### Backend (`backend/`)

Основа: `FastAPI + ThreadPoolExecutor`.

Ключевые роли:

- API-слой (`backend/app/api/routes/*`) - маршруты `jobs`, `clips`, `config`;
- запуск пайплайна (`backend/app/core/job_runner.py`) - выполнение TTM-процессинга в фоне;
- менеджер задач (`backend/app/core/job_manager.py`) - хранение состояния задач в памяти;
- WebSocket (`backend/app/api/websocket.py`) - стрим логов и прогресса на страницу задачи;
- статическая раздача артефактов - `/output/*` монтируется из каталога `output/`.

### Frontend (`frontend/`)

Основа: `React 19 + TypeScript + Vite + TanStack Query + Tailwind`.

Основные страницы:

- `Dashboard` - сводка и активные задачи;
- `Jobs` - создание задач и таблица всех запусков;
- `JobDetail` - прогресс, live-логи, клипы конкретной задачи;
- `ClipsGallery` - единая галерея клипов по завершенным задачам;
- `Settings` - редактирование частей `config.yaml` через API.

В `vite` настроен proxy:

- `/api -> http://localhost:8000`
- `/ws -> ws://localhost:8000`
- `/output -> http://localhost:8000`

---

## Требования

- Python `3.11+`
- Node.js `18+` (рекомендуется `20+`)
- `ffmpeg` в `PATH`

---

## Быстрый старт

### 1) Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
```

API будет доступен на `http://localhost:8000`.

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

UI будет доступен на `http://localhost:5173`.

---

## REST API

Базовый префикс: `/api`.

### Health

- `GET /api/health` - проверка доступности backend.

### Jobs

- `POST /api/jobs` - создать задачу и поставить в очередь.
- `GET /api/jobs` - список всех задач.
- `GET /api/jobs/{job_id}` - данные одной задачи.
- `DELETE /api/jobs/{job_id}` - удалить задачу (для running помечает cancel и удаляет из менеджера).
- `GET /api/jobs/{job_id}/clips` - клипы конкретной задачи.

Пример тела для `POST /api/jobs`:

```json
{
  "channels": ["MrBeast", "@veritasium"],
  "num_clips": 1,
  "videos_per_channel": 2,
  "min_clip_duration": 40,
  "max_clip_duration": 65,
  "channels_limit": 2
}
```

### Clips

- `GET /api/clips/{clip_id}/download` - скачать/проиграть `mp4`.
- `GET /api/clips/{clip_id}/thumbnail` - получить `jpg` миниатюру.

### Config

- `GET /api/config` - текущий `config.yaml`.
- `PUT /api/config` - частичное обновление конфига (deep merge).

Ограничение: если есть активная задача, `PUT /api/config` вернет `409`.

---

## WebSocket API

- `WS /ws/jobs/{job_id}`

События:

- `{"type":"log","level":"INFO","message":"..."}`
- `{"type":"progress","value":50}`
- `{"type":"status","status":"running|completed|failed|cancelled"}`
- `{"type":"ping"}`

При подключении клиент получает буфер последних логов и актуальные статус/прогресс.

---

## Структура репозитория

```text
.
|-- backend/
|   |-- app/
|   |   |-- api/
|   |   |-- core/
|   |   `-- models/
|   |-- main.py
|   `-- requirements.txt
|-- frontend/
|   |-- src/
|   |-- package.json
|   `-- vite.config.ts
|-- config.yaml
|-- core/
|-- processing/
|-- utils/
`-- output/
```

---

## Поток работы

1. Пользователь создает задачу в UI (`POST /api/jobs`).
2. Backend ставит задачу в очередь и запускает пайплайн в фоне.
3. Страница `JobDetail` получает live-логи/прогресс по WebSocket.
4. После завершения API возвращает список клипов и ссылки на файл/миниатюру.
5. Результаты доступны в UI и на файловой системе в `output/`.

---

## Полезно знать

- Текущее состояние задач хранится в памяти процесса backend (не в БД).
- Выходные артефакты могут занимать много места (`output/`).
- Для локальной разработки backend и frontend запускаются отдельно.
