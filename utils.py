import pandas as pd
import boto3
import os
import io
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger("uvicorn.error")


def get_s3_client():
    """Создание S3 клиента"""
    return boto3.session.Session().client(
        service_name="s3",
        endpoint_url=os.environ.get("S3_ENDPOINT_URL"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )


def load_from_s3(bucket_name, key):
    """Загрузка parquet файла из S3"""
    s3 = get_s3_client()
    try:
        logger.info(f"Loading {key} from S3...")
        obj = s3.get_object(Bucket=bucket_name, Key=key)

        # Читаем данные в память
        content = obj["Body"].read()
        logger.info(f"Downloaded {len(content)} bytes from {key}")

        # Конвертируем в DataFrame
        df = pd.read_parquet(io.BytesIO(content))
        logger.info(
            f"Loaded {key}: shape={df.shape}, memory={df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")

        return df

    except Exception as e:
        logger.error(f"Error loading {key} from S3: {e}")
        raise  # Пробрасываем исключение дальше


def load_all_data():
    """Загрузка всех необходимых данных из S3"""
    bucket_name = os.environ.get("S3_BUCKET_NAME")

    logger.info("Starting data loading from S3...")

    # Загружаем данные
    recommendations = load_from_s3(
        bucket_name, os.environ.get("KEY_RECOMMENDATIONS_PARQUET"))
    top_popular = load_from_s3(
        bucket_name, os.environ.get("KEY_TOP_POPULAR_PARQUET"))
    similar = load_from_s3(bucket_name, os.environ.get("KEY_SIMILAR_PARQUET"))
    items = load_from_s3(bucket_name, os.environ.get("KEY_ITEMS_PARQUET"))

    logger.info("All data loaded successfully from S3!")

    return {
        'recommendations': recommendations,
        'top_popular': top_popular,
        'similar': similar,
        'items': items
    }


def dedup_ids(ids):
    """Дедубликация списка ID с сохранением порядка"""
    seen = set()
    return [id for id in ids if not (id in seen or seen.add(id))]
