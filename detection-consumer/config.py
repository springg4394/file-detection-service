import os

class Config:
    # MinIO 관련 환경 변수
    MINIO_SERVER_ACCESS_KEY = os.getenv('MINIO_SERVER_ACCESS_KEY')
    MINIO_SERVER_SECRET_KEY = os.getenv('MINIO_SERVER_SECRET_KEY')
    MINIO_SERVER_URL = os.getenv('MINIO_SERVER_URL')
    
    # Elasticsearch 관련 환경 변수
    ES_HOST = os.getenv('ES_HOST')
    ES_INDEX_NAME = os.getenv('ES_INDEX_NAME')
    
    # Kafka 관련 환경 변수
    KAFKA_HOST = os.getenv('KAFKA_HOST')
    KAFKA_TOPIC = os.getenv('KAFKA_TOPIC')
    KAFKA_GROUP = os.getenv('KAFKA_GROUP')
