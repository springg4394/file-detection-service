import io
from elasticsearch import Elasticsearch
from ultralytics import YOLO
from kafka import KafkaConsumer
from minio import Minio
from minio.error import S3Error
from PIL import Image
import numpy as np
import json
import torch
import cv2
from config import Config

env_config = Config()

# MinIO 클라이언트 설정
minio_client = Minio(
    env_config.MINIO_SERVER_URL,
    access_key=env_config.MINIO_SERVER_ACCESS_KEY,
    secret_key=env_config.MINIO_SERVER_SECRET_KEY,
    secure=False
)

# Kafka Consumer 설정 
consumer = KafkaConsumer(
    env_config.KAFKA_TOPIC,
    bootstrap_servers=env_config.KAFKA_HOST,
    group_id=env_config.KAFKA_GROUP
)

# Elasticsearch 클라이언트 연결
es = Elasticsearch([env_config.ES_HOST])

# 훈련 전에 불필요한 메모리 해제
torch.cuda.empty_cache()

# YOLO 모델 로드
model = YOLO("yolo11n.pt")

# 이미지 다운로드
def download_image_from_minio(bucket_name, file_name):
    try:
        # MinIO에서 객체 다운로드
        data = minio_client.get_object(bucket_name, file_name)
        # 이미지 파일을 메모리로 로드
        image_data = data.read()
        image = Image.open(io.BytesIO(image_data))

        # 이미지가 RGBA일 경우 RGB로 변환
        if image.mode == 'RGBA':
            image = image.convert('RGB')

        return np.array(image)
    except S3Error as e:
        print(f"Error downloading image: {e}")
        return None

# 이미지를 리사이즈하고, 색상 변환, 차원 변경 및 정규화를 수행하여 YOLO 모델에 입력할 수 있는 텐서를 반환하는 함수
def preprocess_image(image, target_size=(640, 640)):
    # 이미지 리사이즈
    image_resized = cv2.resize(image, target_size)  # 이미지 리사이즈
    image_rgb = image_resized[..., ::-1]  # BGR to RGB

    # 배열의 차원 확인 (디버깅용)
    print("image_rgb shape:", image_rgb.shape)

    # image_rgb가 2D인 경우, 3채널을 추가하여 (height, width, 3) 형태로 변환
    if len(image_rgb.shape) == 2:
        image_rgb = np.stack([image_rgb] * 3, axis=-1)  # 2D를 3채널로 변환

    # 차원 변경: (height, width, channels) -> (channels, height, width)
    image_input = image_rgb.transpose((2, 0, 1))  # 채널 순서 변경

    # 정규화: 픽셀 값을 0-1 사이로 변환
    image_input = image_input / 255.0  # 0-1 사이로 정규화

    # 텐서로 변환
    image_input = torch.from_numpy(image_input.copy()).float()  # 배열을 복사한 후 텐서로 변환
    image_input = image_input.unsqueeze(0)  # 배치 차원 추가

    return image_input


# 객체 위치 추출 및 JSON으로 변환
def extract_objects_info(imgage_path, results, file_id):
    # 결과에서 클래스 이름, 클래스 ID, 확신도, 객체 위치 추출
    object_list = []

    result = results[0]  # 첫 번째 이미지에 대한 예측 결과

    # 예측 결과에서 객체 정보 추출
    boxes = result.boxes  # bounding boxes
    cls = boxes.cls.cpu().numpy()  # 클래스 ID
    conf = boxes.conf.cpu().numpy()  # 확신도 (confidence score)
    xywh = boxes.xywh.cpu().numpy()  # 좌표 정보 (x_center, y_center, width, height)
    class_names = result.names  # 클래스 이름

    # 각 객체의 정보 저장
    for i in range(len(xywh)):
        if conf[i] >= 0.6:  # 확신도가 0.6 이상인 경우만 저장
            class_name = class_names[int(cls[i])]  # 클래스 이름
            object_info = {
                'class_id': int(cls[i]),
                'class_name': class_name,
                'confidence': float(conf[i]),
                'bbox': xywh[i].tolist()  # 객체의 bounding box
            }
            object_list.append(object_info)

    # 객체 정보를 포함한 최종 JSON 구조 생성
    json_output = {
        "file_id": file_id,
        "image_path": imgage_path,
        "predictions": object_list
    }

    return json_output

def process_message(message):
    print(f"Received path: {message}")
    
    # 메시지에서 bucketName/fileName 추출
    parsed_message = json.loads(message)
    
    detect_flag = parsed_message.get('detect')

    if detect_flag == "true":

        bucket_name = parsed_message.get('bucketName')
        file_name = parsed_message.get('objectName')
        file_id = parsed_message.get('fileId')

        if file_name is None or file_name == "":
            print("Error: file_name is missing or empty!")
        else:
            if file_name.startswith('/'):
                file_name = file_name[1:]
                path = f"{bucket_name}/{file_name}"
            else:
                path = f"{bucket_name}/{file_name}"


        # MinIO에서 이미지 다운로드
        image = download_image_from_minio(bucket_name, file_name)

        if image is not None:
            # YOLO 모델에 이미지 전달하여 예측 수행
            image_input = preprocess_image(image)

            # YOLO 모델에 이미지 전달하여 예측 수행
            results = model(image_input)

            # 객체 정보 추출 및 JSON 생성
            json_output = extract_objects_info(path, results, file_id)

            # JSON 형식으로 출력
            json_string = json.dumps(json_output, indent=4)  # pretty-printing
            print(json_string)

            # Elasticsearch에 데이터 삽입
            index_name = env_config.ES_INDEX_NAME
            response = es.index(index=index_name, body=json_output)

            # 삽입된 결과 확인
            print(f"Document ID: {response['_id']}")
            
    else:
        print("[detect] detection not use")


# 메세지 처리 및 학습 시작
print("[image-model] Kafka Consumer is starting...")
for message in consumer:
    process_message(message.value)