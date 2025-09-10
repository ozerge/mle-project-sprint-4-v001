from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging
from dotenv import load_dotenv
from utils import load_all_data, dedup_ids
import traceback

load_dotenv()
logger = logging.getLogger("uvicorn.error")

# Глобальные переменные для хранения данных
data_store = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Загрузка всех данных при старте сервиса"""
    global data_store
    logger.info("Starting service initialization...")

    try:
        data_store = load_all_data()
        logger.info("Service initialized successfully!")
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        raise

    yield
    logger.info("Stopping service...")

app = FastAPI(title="Recommendation Service", lifespan=lifespan)


class EventStore:
    """Хранилище событий пользователей (онлайн-история)"""

    def __init__(self, max_events_per_user=20):
        self.events = {}
        self.max_events = max_events_per_user

    def put(self, user_id, item_id):
        user_events = self.events.get(user_id, [])
        self.events[user_id] = [item_id] + user_events[:self.max_events-1]

    def get(self, user_id, k=10):
        return self.events.get(user_id, [])[:k]


# Глобальное хранилище событий
events_store = EventStore()


@app.get("/recommendations/{user_id}")
async def get_recommendations(user_id: int, k: int = 100):
    """
    Основной эндпоинт для получения рекомендаций
    - user_id: идентификатор пользователя (в пути)
    - k: количество рекомендаций (в query, по умолчанию 100)
    """
    try:
        # 1. Получаем готовые офлайн-рекомендации (уже проранжированные CatBoost)
        user_recs = data_store['recommendations']
        user_offline_recs = user_recs[user_recs['user_id'] == user_id]

        if not user_offline_recs.empty:
            # Берем топ-K уже проранжированных рекомендаций
            offline_recs = user_offline_recs[user_offline_recs['rank'] <= k]['track_id'].tolist(
            )
            logger.info(
                f"Found {len(offline_recs)} offline recommendations for user {user_id}")
        else:
            # Холодный пользователь - используем топ-популярные
            offline_recs = data_store['top_popular'].head(k)[
                'track_id'].tolist()
            logger.info(
                f"User {user_id} is cold, using {len(offline_recs)} top popular tracks")

        # 2. Генерируем онлайн-рекомендации на основе истории
        user_history = events_store.get(user_id, 5)
        online_recs = await generate_online_recommendations(user_history, k//2)
        logger.info(
            f"Generated {len(online_recs)} online recommendations from history: {user_history}")

        # 3. Смешиваем рекомендации
        blended_recs, rec_types = await blend_recommendations_with_types(offline_recs, online_recs, k)

        # 4. Получаем информацию о треках
        track_info = await get_track_info_with_types(blended_recs, rec_types)

        # Статистика
        offline_count = sum(
            1 for rec in track_info if rec['recommendation_type'] == 'offline')
        online_count = sum(
            1 for rec in track_info if rec['recommendation_type'] == 'online')

        logger.info(
            f"Final: {offline_count} offline, {online_count} online recommendations")

        return {
            "user_id": user_id,
            "k": k,
            "recommendations": track_info,
            "stats": {
                "offline_recommendations": offline_count,
                "online_recommendations": online_count,
                "total_recommendations": len(track_info)
            }
        }

    except Exception as e:
        logger.error(f"Error for user {user_id}: {e}")
        logger.error(traceback.format_exc())
        # Фолбэк на топ-популярные
        top_recs = data_store['top_popular'].head(k)['track_id'].tolist()
        track_info = []
        for track_id in top_recs:
            track_data = data_store['items'][data_store['items']
                                             ['track_id'] == track_id]
            if not track_data.empty:
                first_row = track_data.iloc[0]
                # Исправляем получение строковых значений (убираем списки)
                info = {
                    'track_id': int(track_id),
                    'track_name': str(first_row['track_name']).strip("[]'\"") if isinstance(first_row['track_name'], list) else str(first_row['track_name']),
                    'artist_name': str(first_row['artist_name']).strip("[]'\"") if isinstance(first_row['artist_name'], list) else str(first_row['artist_name']),
                    'genre': str(first_row['genre_name']).strip("[]'\"") if isinstance(first_row['genre_name'], list) else str(first_row['genre_name']),
                    'album_name': str(first_row['album_name']).strip("[]'\"") if isinstance(first_row['album_name'], list) else str(first_row['album_name']),
                    'recommendation_type': 'offline'
                }
            else:
                info = {
                    'track_id': int(track_id),
                    'track_name': f"Unknown track ({track_id})",
                    'artist_name': "Unknown artist",
                    'genre': "Unknown",
                    'album_name': "Unknown",
                    'recommendation_type': 'offline'
                }
            track_info.append(info)

        return {
            "user_id": user_id,
            "k": k,
            "recommendations": track_info,
            "stats": {
                "offline_recommendations": len(track_info),
                "online_recommendations": 0,
                "total_recommendations": len(track_info)
            }
        }


async def blend_recommendations_with_types(offline_recs, online_recs, k):
    """Смешивание рекомендаций с сохранением информации о типе"""
    min_length = min(len(offline_recs), len(online_recs))

    blended = []
    rec_types = []

    # Чередуем элементы из списков
    for i in range(min_length):
        blended.append(online_recs[i])
        rec_types.append('online')
        blended.append(offline_recs[i])
        rec_types.append('offline')

    # Добавляем оставшиеся элементы
    for track_id in offline_recs[min_length:]:
        if track_id not in blended:
            blended.append(track_id)
            rec_types.append('offline')

    for track_id in online_recs[min_length:]:
        if track_id not in blended:
            blended.append(track_id)
            rec_types.append('online')

    # Удаляем дубликаты (сохраняем первый тип)
    seen = set()
    final_blended = []
    final_types = []

    for i, track_id in enumerate(blended):
        if track_id not in seen:
            seen.add(track_id)
            final_blended.append(track_id)
            final_types.append(rec_types[i])

    return final_blended[:k], final_types[:k]


async def generate_online_recommendations(user_history, n_recommendations=10):
    """Генерация онлайн-рекомендаций на основе истории пользователя"""
    if not user_history:
        return []

    similar_df = data_store['similar']

    # Берем уникальные треки из similar
    all_tracks = similar_df['track_id'].unique().tolist()

    # Исключаем треки из истории
    available_tracks = [
        track for track in all_tracks if track not in user_history]

    # Возвращаем первые n_recommendations треков
    return available_tracks[:n_recommendations]


async def get_track_info_with_types(track_ids, rec_types):
    """Получение информации о треках с указанием типа рекомендации"""
    track_info = []
    items_df = data_store['items']

    for i, track_id in enumerate(track_ids):
        track_data = items_df[items_df['track_id'] == track_id]
        rec_type = rec_types[i]

        if not track_data.empty:
            # Получаем первую строку и преобразуем в dict
            first_row = track_data.iloc[0]
            # Исправляем получение строковых значений (убираем списки)
            info = {
                'track_id': int(track_id),
                'track_name': str(first_row['track_name']).strip("[]'\"") if isinstance(first_row['track_name'], list) else str(first_row['track_name']),
                'artist_name': str(first_row['artist_name']).strip("[]'\"") if isinstance(first_row['artist_name'], list) else str(first_row['artist_name']),
                'genre': str(first_row['genre_name']).strip("[]'\"") if isinstance(first_row['genre_name'], list) else str(first_row['genre_name']),
                'album_name': str(first_row['album_name']).strip("[]'\"") if isinstance(first_row['album_name'], list) else str(first_row['album_name']),
                'recommendation_type': rec_type
            }
        else:
            info = {
                'track_id': int(track_id),
                'track_name': f"Unknown track ({track_id})",
                'artist_name': "Unknown artist",
                'genre': "Unknown",
                'album_name': "Unknown",
                'recommendation_type': rec_type
            }
        track_info.append(info)
    return track_info


@app.post("/event")
async def add_event(user_id: int, track_id: int):
    """Добавление события прослушивания (онлайн-история)"""
    events_store.put(user_id, track_id)
    logger.info(f"Added event: user {user_id}, track {track_id}")
    return {"status": "ok", "message": "Event added"}


@app.get("/events/{user_id}")
async def get_events(user_id: int, limit: int = 10):
    """Получение истории событий пользователя"""
    events = events_store.get(user_id, limit)
    return {"user_id": user_id, "events": events}


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "healthy",
        "data_loaded": data_store is not None,
        "recommendations_loaded": data_store is not None and 'recommendations' in data_store,
        "top_popular_loaded": data_store is not None and 'top_popular' in data_store,
        "similar_loaded": data_store is not None and 'similar' in data_store,
        "items_loaded": data_store is not None and 'items' in data_store
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
