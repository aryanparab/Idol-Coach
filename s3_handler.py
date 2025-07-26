import os
import boto3
from botocore.exceptions import ClientError
import json
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()
class StorageHandler:
    def __init__(self):
        self.is_production = os.getenv('PRODUCTION', 'false').lower() == 'true'
        print(os.getenv('PRODUCTION', 'false').lower(),os.getenv('PRODUCTION', 'false').lower()=="true")
        self.bucket_name = os.getenv('S3_BUCKET_NAME', 'your-bucket-name')
        
        if self.is_production:
            self.s3_client = boto3.client('s3',config=Config(signature_version='s3v4'),region_name=os.getenv("AWS_REGION"))
        else:
            self.s3_client = None
    
    def ensure_directory_exists(self, path):
        """Create directory if using local storage"""
        if not self.is_production:
            os.makedirs(path, exist_ok=True)
    
    def write_file(self, file_path, content, mode='w'):
        """Write file to local storage or S3"""
        if self.is_production:
            # S3 storage
            try:
                if mode == 'wb':
                    # Binary content
                    self.s3_client.put_object(
                        Bucket=self.bucket_name,
                        Key=file_path,
                        Body=content
                    )
                else:
                    # Text content
                    if isinstance(content, str):
                        content = content.encode('utf-8')
                    self.s3_client.put_object(
                        Bucket=self.bucket_name,
                        Key=file_path,
                        Body=content
                    )
                print(f"✅ Uploaded to S3: s3://{self.bucket_name}/{file_path}")
            except ClientError as e:
                print(f"❌ S3 upload failed: {e}")
                raise
        else:
            # Local storage
            directory = os.path.dirname(file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            
            with open(file_path, mode) as f:
                f.write(content)
            print(f"✅ Saved locally: {file_path}")
    
    def read_file(self, file_path, mode='r'):
        """Read file from local storage or S3"""
        if self.is_production:
            # S3 storage
            try:
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=file_path
                )
                content = response['Body'].read()
                
                if mode == 'rb':
                    return content
                else:
                    return content.decode('utf-8')
            except ClientError as e:
                print(f"❌ S3 read failed: {e}")
                raise
        else:
            # Local storage
            if 'b' in mode:
                with open(file_path, mode) as f:
                    return f.read()  # returns bytes
            else:
                with open(file_path, mode, encoding='utf-8') as f:
                    return f.read()  # returns str
    
    def file_exists(self, file_path):
        """Check if file exists in local storage or S3"""
        if self.is_production:
            # S3 storage
            try:
                self.s3_client.head_object(Bucket=self.bucket_name, Key=file_path)
                return True
            except ClientError:
                return False
        else:
            # Local storage
            return os.path.exists(file_path)
    
    def get_presigned_url(self, file_path, expiration=3600):
    # """Generate a presigned URL to share an S3 object"""
        if not self.is_production:
            # For local, just return the file path
            return f"/coach/{file_path}"

        try:
            url = self.s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={'Bucket': self.bucket_name, 'Key': file_path},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            print(f"❌ Failed to generate presigned URL: {e}")
            return None

    def get_file_url(self, file_path):
        """Get file URL/path"""
        if self.is_production:
            return f"s3://{self.bucket_name}/{file_path}"
        else:
            return file_path
    
    def write_audio_file(self, file_path, audio_data, sample_rate=44100):
        """Write audio file using soundfile"""
        import soundfile as sf
        import io
        
        if self.is_production:
            # For S3, write to bytes buffer first
            buffer = io.BytesIO()
            sf.write(buffer, audio_data, sample_rate, format='WAV')
            buffer.seek(0)
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=buffer.getvalue(),
                ContentType='audio/wav'
            )
            print(f"✅ Uploaded audio to S3: s3://{self.bucket_name}/{file_path}")
        else:
            # Local storage
            directory = os.path.dirname(file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            sf.write(file_path, audio_data, sample_rate)
            print(f"✅ Saved audio locally: {file_path}")

# Global storage handler instance
storage = StorageHandler()