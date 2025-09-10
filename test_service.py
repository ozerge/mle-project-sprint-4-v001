import requests
import os
import logging
from dotenv import load_dotenv

# Настройка логирования в файл и консоль
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("test_service.log", mode='w'),
        logging.StreamHandler()
    ]
)

load_dotenv()
BASE_URL = os.getenv("SERVICE_URL", "http://localhost:8000")
logger = logging.getLogger(__name__)


def test_health():
    """Тест здоровья сервиса"""
    logger.info("=== Testing Health Endpoint ===")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        assert response.status_code == 200
        health_data = response.json()
        logger.info(f"Health status: {health_data}")
        assert health_data["status"] == "healthy"
        logger.info("✓ Health test passed\n")
        return True
    except Exception as e:
        logger.error(f"Health test failed: {e}")
        return False


def test_events():
    """Тест работы с событиями"""
    logger.info("=== Testing Events Endpoint ===")
    try:
        test_user_id = 100
        test_track_id = 500

        # Добавляем событие
        response = requests.post(
            f"{BASE_URL}/event", params={"user_id": test_user_id, "track_id": test_track_id}, timeout=10)
        assert response.status_code == 200
        logger.info(f"Added event: user {test_user_id}, track {test_track_id}")

        # Получаем события
        response = requests.get(
            f"{BASE_URL}/events/{test_user_id}", timeout=10)
        assert response.status_code == 200
        events_data = response.json()
        logger.info(f"Events data: {events_data}")
        assert events_data["user_id"] == test_user_id
        assert test_track_id in events_data["events"]

        logger.info("✓ Events test passed\n")
        return True
    except Exception as e:
        logger.error(f"Events test failed: {e}")
        return False


def test_case_1():
    """Тест 1: Пользователь без персональных рекомендаций (холодный)"""
    logger.info("=== Test Case 1: Cold User (no personal recommendations) ===")
    try:
        user_id = 999999999
        response = requests.get(
            f"{BASE_URL}/recommendations/{user_id}?k=3", timeout=10)
        assert response.status_code == 200
        data = response.json()

        logger.info(f"User ID: {data['user_id']}")
        logger.info(f"Requested k: {data['k']}")
        logger.info(f"Stats: {data['stats']}")
        logger.info("Recommendations:")
        for rec in data['recommendations']:
            logger.info(
                f"  [{rec['recommendation_type'].upper()}] Track ID: {rec['track_id']}")
            logger.info(f"    Name: {rec['track_name']}")
            logger.info(f"    Artist: {rec['artist_name']}")
            logger.info(f"    Genre: {rec['genre']}")
            logger.info("    ---")

        assert len(data["recommendations"]) == 3
        assert data['stats']['offline_recommendations'] > 0
        logger.info(
            "✓ Test 1 passed: Cold user received top popular recommendations\n")
        return True
    except Exception as e:
        logger.error(f"Test 1 failed: {e}")
        return False


def test_case_2():
    """Тест 2: Пользователь с персональными рекомендациями, но без истории"""
    logger.info("=== Test Case 2: User with offline recs, no history ===")
    try:
        user_id = 47
        response = requests.get(
            f"{BASE_URL}/recommendations/{user_id}?k=4", timeout=10)
        assert response.status_code == 200
        data = response.json()

        logger.info(f"User ID: {data['user_id']}")
        logger.info(f"Requested k: {data['k']}")
        logger.info(f"Stats: {data['stats']}")
        logger.info("Recommendations:")
        for rec in data['recommendations']:
            logger.info(
                f"  [{rec['recommendation_type'].upper()}] Track ID: {rec['track_id']}")
            logger.info(f"    Name: {rec['track_name']}")
            logger.info(f"    Artist: {rec['artist_name']}")
            logger.info(f"    Genre: {rec['genre']}")
            logger.info("    ---")

        assert len(data["recommendations"]) == 4
        logger.info(
            "✓ Test 2 passed: User with offline recs received recommendations\n")
        return True
    except Exception as e:
        logger.error(f"Test 2 failed: {e}")
        return False


def test_case_3():
    """Тест 3: Пользователь с персональными рекомендациями и историей"""
    logger.info("=== Test Case 3: User with both offline recs and history ===")
    try:
        user_id = 4

        # Очищаем историю
        requests.post(f"{BASE_URL}/event",
                      params={"user_id": user_id, "track_id": 0}, timeout=10)

        test_tracks = [97241633, 65457108, 59523137, 69063591, 96366184]
        for track_id in test_tracks:
            response = requests.post(
                f"{BASE_URL}/event",
                params={"user_id": user_id, "track_id": track_id},
                timeout=10
            )
            assert response.status_code == 200
            logger.info(f"Added event: user {user_id}, track {track_id}")

        # Получаем рекомендации
        response = requests.get(
            f"{BASE_URL}/recommendations/{user_id}?k=10", timeout=10)
        assert response.status_code == 200
        data = response.json()

        logger.info(f"User ID: {data['user_id']}")
        logger.info(f"Requested k: {data['k']}")
        logger.info(f"Stats: {data['stats']}")
        logger.info("Blended Recommendations:")
        for rec in data['recommendations']:
            logger.info(
                f"  [{rec['recommendation_type'].upper()}] Track ID: {rec['track_id']}")
            logger.info(f"    Name: {rec['track_name']}")
            logger.info(f"    Artist: {rec['artist_name']}")
            logger.info(f"    Genre: {rec['genre']}")
            logger.info("    ---")

        assert len(data["recommendations"]) == 10
        logger.info(
            "✓ Test 3 passed: User with history received recommendations\n")
        return True
    except Exception as e:
        logger.error(f"Test 3 failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("Starting recommendation service tests...")

    try:
        # Проверяем здоровье сервиса
        if not test_health():
            logger.error("Service is not healthy. Exiting.")
            exit(1)

        # Тестируем работу с событиями
        test_events()

        # Запускаем основные тесты рекомендаций
        test_case_1()
        test_case_2()
        test_case_3()

        logger.info("All tests completed successfully!")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        exit(1)
