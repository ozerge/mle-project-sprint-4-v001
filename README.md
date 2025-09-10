# Подготовка виртуальной машины

## Склонируйте репозиторий

Склонируйте репозиторий проекта:

```
git clone https://github.com/yandex-praktikum/mle-project-sprint-4-v001.git
```

## Активируйте виртуальное окружение

Используйте то же самое виртуальное окружение, что и созданное для работы с уроками. Если его не существует, то его следует создать.

Создать новое виртуальное окружение можно командой:

```
python3 -m venv env_recsys_start
```

После его инициализации следующей командой

```
. env_recsys_start/bin/activate
```

установите в него необходимые Python-пакеты следующей командой

```
pip install -r requirements.txt
```

### Скачайте файлы с данными

Для начала работы понадобится три файла с данными:
- [tracks.parquet](https://storage.yandexcloud.net/mle-data/ym/tracks.parquet)
- [catalog_names.parquet](https://storage.yandexcloud.net/mle-data/ym/catalog_names.parquet)
- [interactions.parquet](https://storage.yandexcloud.net/mle-data/ym/interactions.parquet)
 
Скачайте их в директорию локального репозитория. Для удобства вы можете воспользоваться командой wget:

```
wget https://storage.yandexcloud.net/mle-data/ym/tracks.parquet

wget https://storage.yandexcloud.net/mle-data/ym/catalog_names.parquet

wget https://storage.yandexcloud.net/mle-data/ym/interactions.parquet
```

## Запустите Jupyter Lab

Запустите Jupyter Lab в командной строке

```
jupyter lab --ip=0.0.0.0 --no-browser
```

# Расчёт рекомендаций

Код для выполнения первой части проекта находится в файле `recommendations.ipynb`. Изначально, это шаблон. Используйте его для выполнения первой части проекта.


### Файлы с рекомендациями:

 - топ популярных — в `top_popular.parquet`
 - персональные (при помощи ALS) — в `personal_als.parquet`
 - похожие треки (i2i при помощи ALS) — в `similar.parquet`
 - итоговые рекомендации — в `recommendations.parquet`

# Сервис рекомендаций

[Код сервиса рекомендаций находится в файле `recommendations_service.py`.](recommendations_service.py)

Структура проекта
```bash
├── recommendations_service.py  # Основной сервис
├── test_service.py             # Тесты
├── test_service.log            # Результаты тестов
├── utils.py                    # Вспомогательные функции
├── .env                        # Переменные окружения
└── README.md                   # Документация
```
Стратегия смешивания рекомендаций:  
1.Офлайн-рекомендации  
 - Источник: Предварительно вычисленные рекомендации (CatBoost)  
 - Для: Известных пользователей - персонализированные рекомендации
 - Для: Холодных пользователей - топ-популярные треки
 
2.Онлайн-рекомендации  
 - Источник: События прослушивания в реальном времени
 - Механизм: Поиск похожих треков через similar-матрицу

3.Алгоритм смешивания  
 - Чередование: Онлайн и офлайн рекомендации чередуются
 - Дедубликация: Удаление повторяющихся треков
 - Баланс: Сохранение пропорций при наличии истории  
Формула: Для пользователя с историей - 50% онлайн, 50% офлайн рекомендаций  

API Endpoints:
 - GET /recommendations/{user_id}?k=100 - Получение рекомендаций  
 - POST /event?user_id=123&track_id=456 - Добавление события  
 - GET /events/{user_id} - История событий  
 - GET /health - Проверка здоровья  

### Необходимые шаги для запуска сервиса рекомендаций:
- Установите необходимые библиотеки:  
```bash
pip install -r requirements2.txt 
```
- Настройте переменные окружения в .env:
```bash
S3_ENDPOINT_URL=your_s3_endpoint
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
S3_BUCKET_NAME=your_bucket_name
KEY_RECOMMENDATIONS_PARQUET=path_to_the_file_recommendations.parquet
KEY_TOP_POPULAR_PARQUET=path_to_the_file_top_popular.parquet
KEY_SIMILAR_PARQUET=path_to_the_file_similar.parquet
KEY_ITEMS_PARQUET=path_to_the_file_items.parquet
```
- Запустите сервис:
```bash
uvicorn recommendations_service:app --reload 
```
Сервис поднимается по адресу http://127.0.0.1:8000 (по умолчанию)

# Инструкции для тестирования сервиса

[Код для тестирования сервиса находится в файле `test_service.py`.](test_service.py)

Тестируются 3 сценария:  
 - Холодный пользователь (только топ-популярные)
 - Пользователь с офлайн-рекомендациями (без истории)
 - Активный пользователь (смешанные рекомендации)

Запустите тесты для проверки всех сценариев::
```bash
python test_service.py
```
[Вывод тестов сохраняется в `test_service.log`](test_service.log)

Проверяем вручную:
пример для холодного пользователя
```bash
curl "http://localhost:8000/recommendations/999999999?k=3"
```
пример для пользователя с историей
```bash
# Добавляем несколько событий для пользователя 50
curl -X POST "http://localhost:8000/event?user_id=50&track_id=1000"
curl -X POST "http://localhost:8000/event?user_id=50&track_id=2000"

# Получаем рекомендации
curl "http://localhost:8000/recommendations/50?k=5"

# Посмотреть историю пользователя
curl "http://localhost:8000/events/50"
```
