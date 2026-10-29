import urllib3
import json
import boto3
import certifi

from boto3.s3.transfer import TransferConfig


from oss.sts_token_error import StsTokenError
from utils.coros_oss_credients_utils import decode

class AwsOssClient:
  def __init__(self, bucket="coros-s3", service="aws", app_id="1660188068672619112", sign="877571111A1EE5316E4B590103D4B5B3", v=2, access_token=None):
    self.bucket = bucket
    self.service = service
    self.app_id = app_id
    self.sign = sign
    self.access_token = access_token
    self.credentials = None
    self.access_key_id = None
    self.access_key_secret = None
    self.req = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
    self.v = v
    self.client = None
    self.initClient()
  
  def initClient(self):
        if not self.access_token:
            raise StsTokenError("AWS OSS STS requires a COROS login access token")

        sts_token_url = (
            "https://training.coros.com/api/proxy/oss/sts"
            f"?bucket={self.bucket}&service={self.service}&v={self.v}"
        )

        headers = {}
        if self.access_token:
            headers["Cookie"] = f"CPL-coros-token={self.access_token}"

        response = self.req.request(
            "GET",
            sts_token_url,
            headers=headers,
        )

        print(
            f"DEBUG: AWS STS HTTP status={response.status}, "
            f"content-type={response.headers.get('Content-Type')}, "
            f"response-bytes={len(response.data)}",
            flush=True,
        )

        try:
            sts_token_response = json.loads(response.data)
        except (ValueError, TypeError):
            raise StsTokenError(
                f"AWS OSS STS returned invalid JSON (HTTP {response.status})"
            )

        if response.status != 200 or sts_token_response.get("code") != 200:
            raise StsTokenError(
                f"AWS OSS STS request failed (HTTP {response.status}, "
                f"code={sts_token_response.get('code')})"
            )

        credentials = sts_token_response["data"]["credentials"]
        self.v = sts_token_response["data"]["v"]
        self.credentials = credentials
        credients_json = decode(credentials)

        self.client = boto3.client(
            "s3",
            aws_access_key_id=credients_json["AccessKeyId"],
            aws_secret_access_key=credients_json["SecretAccessKey"],
            aws_session_token=credients_json["SessionToken"],
            endpoint_url="https://s3.us-west-1.amazonaws.com",
            region_name="us-west-1",
        )

  def multipart_upload(self, filePath, fileName):
      # 配置上传选项
      config = TransferConfig(
          multipart_threshold=1024 * 1024 * 5,  # 分片上传的阈值（5MB）
          max_concurrency=4,                   # 并发数
          multipart_chunksize=1024 * 1024 * 5,  # 分片大小（5MB）
          use_threads=True                     # 使用多线程
      )

      # 执行上传
      try:
          self.client.upload_file(
              filePath,
              Bucket=self.bucket,
              Key=f"fit_zip/{fileName}",
              Config=config
          )
          print(f"File {fileName} uploaded successfully!")
      except Exception as e:
          print(f"Upload failed: {e}")



