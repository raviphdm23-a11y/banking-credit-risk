"""
Cloud Storage Manager — GCS integration for persistent data
───────────────────────────────────────────────────────────

Handles downloading/uploading of:
  • bank.db (database)
  • ML models (*.pkl, metadata)
  • Reports (PDF, JSON)
  • Audit logs (governance trail)

Used by app.py on Cloud Run startup to populate /tmp with
persistent data from Google Cloud Storage buckets.
"""

import os
import json
from google.cloud import storage
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class CloudStorageManager:
    """Manage downloads/uploads to/from Google Cloud Storage buckets"""

    def __init__(self, project_id: str, bucket_name: str):
        """
        Initialize GCS manager.

        Args:
            project_id: GCP project ID
            bucket_name: GCS bucket name (without gs:// prefix)
        """
        self.project_id = project_id
        self.bucket_name = bucket_name
        try:
            self.client = storage.Client(project=project_id)
            self.bucket = self.client.bucket(bucket_name)
            self._verify_access()
        except Exception as e:
            logger.warning(f"[GCS] Failed to initialize: {e}")
            self.client = None
            self.bucket = None

    def _verify_access(self):
        """Verify bucket is accessible"""
        try:
            self.bucket.reload()
            logger.info(f"[GCS] Connected to bucket: gs://{self.bucket_name}")
        except Exception as e:
            logger.warning(f"[GCS] Cannot access bucket gs://{self.bucket_name}: {e}")
            raise

    def download_file(self, source_blob_name: str, destination_file_path: str) -> bool:
        """
        Download file from GCS to local filesystem.

        Args:
            source_blob_name: Path in bucket (e.g., 'models/pd_model_CORPORATE.pkl')
            destination_file_path: Local file path

        Returns:
            True if successful, False otherwise
        """
        if not self.bucket:
            logger.error("[GCS] Not connected to bucket")
            return False

        try:
            blob = self.bucket.blob(source_blob_name)
            blob.download_to_filename(destination_file_path)
            logger.info(f"[GCS] Downloaded gs://{self.bucket_name}/{source_blob_name} → {destination_file_path}")
            return True
        except Exception as e:
            logger.error(f"[GCS] Download failed for {source_blob_name}: {e}")
            return False

    def upload_file(self, source_file_path: str, destination_blob_name: str) -> bool:
        """
        Upload file from local filesystem to GCS.

        Args:
            source_file_path: Local file path
            destination_blob_name: Path in bucket (e.g., 'reports/RMC-123.json')

        Returns:
            True if successful, False otherwise
        """
        if not self.bucket:
            logger.error("[GCS] Not connected to bucket")
            return False

        if not os.path.exists(source_file_path):
            logger.error(f"[GCS] Source file not found: {source_file_path}")
            return False

        try:
            blob = self.bucket.blob(destination_blob_name)
            blob.upload_from_filename(source_file_path)
            logger.info(f"[GCS] Uploaded {source_file_path} → gs://{self.bucket_name}/{destination_blob_name}")
            return True
        except Exception as e:
            logger.error(f"[GCS] Upload failed for {source_file_path}: {e}")
            return False

    def upload_string(self, data: str, destination_blob_name: str) -> bool:
        """
        Upload string content to GCS as a blob.

        Args:
            data: String content to upload
            destination_blob_name: Path in bucket

        Returns:
            True if successful, False otherwise
        """
        if not self.bucket:
            logger.error("[GCS] Not connected to bucket")
            return False

        try:
            blob = self.bucket.blob(destination_blob_name)
            blob.upload_from_string(data, content_type='application/json')
            logger.info(f"[GCS] Uploaded string → gs://{self.bucket_name}/{destination_blob_name}")
            return True
        except Exception as e:
            logger.error(f"[GCS] Upload string failed for {destination_blob_name}: {e}")
            return False

    def file_exists(self, blob_name: str) -> bool:
        """
        Check if file exists in bucket.

        Args:
            blob_name: Path in bucket

        Returns:
            True if exists, False otherwise
        """
        if not self.bucket:
            return False

        try:
            blob = self.bucket.blob(blob_name)
            return blob.exists()
        except Exception as e:
            logger.warning(f"[GCS] Error checking file existence for {blob_name}: {e}")
            return False

    def list_files(self, prefix: str = '') -> List[str]:
        """
        List all files in bucket with given prefix.

        Args:
            prefix: Prefix filter (e.g., 'models/', 'reports/')

        Returns:
            List of blob names (paths) in bucket
        """
        if not self.bucket:
            return []

        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            files = [blob.name for blob in blobs]
            logger.info(f"[GCS] Listed {len(files)} files with prefix '{prefix}'")
            return files
        except Exception as e:
            logger.error(f"[GCS] Error listing files with prefix {prefix}: {e}")
            return []

    def get_file_size(self, blob_name: str) -> Optional[int]:
        """
        Get file size in bytes.

        Args:
            blob_name: Path in bucket

        Returns:
            File size in bytes, or None if not found
        """
        if not self.bucket:
            return None

        try:
            blob = self.bucket.blob(blob_name)
            blob.reload()
            return blob.size
        except Exception as e:
            logger.warning(f"[GCS] Error getting file size for {blob_name}: {e}")
            return None

    def delete_file(self, blob_name: str) -> bool:
        """
        Delete file from bucket (use with caution).

        Args:
            blob_name: Path in bucket

        Returns:
            True if successful, False otherwise
        """
        if not self.bucket:
            logger.error("[GCS] Not connected to bucket")
            return False

        try:
            blob = self.bucket.blob(blob_name)
            blob.delete()
            logger.info(f"[GCS] Deleted gs://{self.bucket_name}/{blob_name}")
            return True
        except Exception as e:
            logger.error(f"[GCS] Delete failed for {blob_name}: {e}")
            return False

    def __repr__(self):
        return f"CloudStorageManager(project={self.project_id}, bucket={self.bucket_name})"
