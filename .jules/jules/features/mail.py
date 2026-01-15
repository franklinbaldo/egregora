import mailbox
import os
import uuid
import boto3
import email
from email import policy
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol
from abc import ABC, abstractmethod
import requests

from botocore.config import Config

# Default root for local mail storage
MAIL_ROOT = Path(".jules/mail")
# Default S3 config
BUCKET_NAME = os.environ.get("JULES_MAIL_BUCKET", "jules-mail")
S3_ENDPOINT = os.environ.get("AWS_S3_ENDPOINT_URL")

class MailboxBackend(ABC):
    @abstractmethod
    def send_message(self, from_id: str, to_id: str, subject: str, body: str, attachments: Optional[List[str]] = None) -> str:
        pass

    @abstractmethod
    def list_inbox(self, persona_id: str, unread_only: bool = False) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_message(self, persona_id: str, key: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def mark_read(self, persona_id: str, key: str) -> None:
        pass

class LocalMaildirBackend(MailboxBackend):
    def _get_maildir(self, persona_id: str) -> mailbox.Maildir:
        # Resolve path to .jules/personas/<persona_id>/mail
        # We assume .jules is in the current working directory or resolvable relative to it
        persona_path = Path(".jules/personas") / persona_id
        mail_path = persona_path / "mail"
        
        if not persona_path.exists():
            persona_path.mkdir(parents=True, exist_ok=True)

        # Ensure mail directory exists
        mail_path.mkdir(parents=True, exist_ok=True)

        # Explicitly create Maildir subdirectories to match mailbox requirements
        # mailbox.Maildir(create=True) can sometimes be flaky if dir exists but subdirs don't
        (mail_path / "tmp").mkdir(exist_ok=True)
        (mail_path / "new").mkdir(exist_ok=True)
        (mail_path / "cur").mkdir(exist_ok=True)

        return mailbox.Maildir(str(mail_path), create=True)

    def send_message(self, from_id: str, to_id: str, subject: str, body: str, attachments: Optional[List[str]] = None) -> str:
        dest_maildir = self._get_maildir(to_id)
        msg = mailbox.MaildirMessage()
        msg["Subject"] = subject
        msg["From"] = from_id
        msg["To"] = to_id
        content = body
        if attachments:
            content += "\n\nAttachments: " + ", ".join(attachments)
        msg.set_payload(content)
        return dest_maildir.add(msg)

    def list_inbox(self, persona_id: str, unread_only: bool = False) -> List[Dict[str, Any]]:
        maildir = self._get_maildir(persona_id)
        results = []
        for key in maildir.keys():
            msg = maildir.get(key)
            is_seen = "S" in msg.get_flags()
            if unread_only and is_seen:
                continue
            results.append({
                "key": key,
                "subject": msg["Subject"],
                "from": msg["From"],
                "read": is_seen,
                "date": msg["Date"]
            })
        return results

    def get_message(self, persona_id: str, key: str) -> Dict[str, Any]:
        maildir = self._get_maildir(persona_id)
        msg = maildir.get(key)
        if msg is None: raise ValueError(f"Message not found: {key}")
        payload = msg.get_payload(decode=True)
        body = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else str(payload)
        return {
            "key": key, "subject": msg["Subject"], "from": msg["From"],
            "to": msg["To"], "body": body.strip(), "date": msg["Date"]
        }

    def mark_read(self, persona_id: str, key: str) -> None:
        maildir = self._get_maildir(persona_id)
        msg = maildir.get(key)
        if msg:
            msg.add_flag("S")
            maildir[key] = msg

class S3MailboxBackend(MailboxBackend):
    def _get_s3_client(self):
        # Specific configuration for Internet Archive S3 compatibility
        my_config = Config(
            s3={'addressing_style': 'path', 'payload_signing_enabled': False},
            retries={'max_attempts': 3}
        )
        kwargs = {"config": my_config}
        if S3_ENDPOINT: kwargs["endpoint_url"] = S3_ENDPOINT
        return boto3.client("s3", **kwargs)

    def send_message(self, from_id: str, to_id: str, subject: str, body: str, attachments: Optional[List[str]] = None) -> str:
        s3 = self._get_s3_client()
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_id
        msg["To"] = to_id
        content = body
        if attachments: content += "\n\nAttachments: " + ", ".join(attachments)
        msg.set_content(content)
        message_id = str(uuid.uuid4())
        key = f"{to_id}/{message_id}.eml"
        
        # Metadata is more widely supported than Tagging (e.g. Internet Archive)
        metadata = {
            "subject": subject[:100], 
            "from-id": from_id,
            "seen": "0"
        }
        
        body_bytes = msg.as_bytes()
        
        # Internet Archive S3 is extremely picky about Content-Length and 100-continue.
        # requests handles this more reliably than boto3's default behavior for some endpoints.
        from urllib.parse import urlparse
        if S3_ENDPOINT and urlparse(S3_ENDPOINT).hostname == "archive.org":
            import base64
            auth = base64.b64encode(f"{s3._request_signer._credentials.access_key}:{s3._request_signer._credentials.secret_key}".encode()).decode()
            headers = {
                "Content-Length": str(len(body_bytes)),
                "Authorization": f"Lowry {s3._request_signer._credentials.access_key}:{s3._request_signer._credentials.secret_key}", # IA specific auth style sometimes
                "Content-Type": "message/rfc822"
            }
            # IA S3 also supports standard S3 auth via headers if we use the correct signer
            # But let's try the most robust way: boto3 s3.put_object but force content-length
            # Actually, let's try boto3 one more time with a very specific param:
            try:
                s3.put_object(
                    Bucket=BUCKET_NAME, Key=key, Body=body_bytes,
                    Metadata=metadata, ContentLength=len(body_bytes),
                    ContentType="message/rfc822"
                )
            except Exception as e:
                if "411" in str(e) or "403" in str(e):
                    # Fallback to requests with IA-specific Lowry auth
                    url = f"{S3_ENDPOINT}/{BUCKET_NAME}/{key}"
                    creds = s3._request_signer._credentials
                    headers = {
                        "Content-Length": str(len(body_bytes)),
                        "Authorization": f"Lowry {creds.access_key}:{creds.secret_key}",
                        "Content-Type": "message/rfc822",
                        "x-archive-meta-mediatype": "texts",
                        "x-archive-meta-collection": "opensource",
                        "x-amz-auto-make-bucket": "1"
                    }
                    # Add metadata as x-amz-meta-* headers for IA
                    for k, v in metadata.items():
                        headers[f"x-amz-meta-{k}"] = v

                    resp = requests.put(url, data=body_bytes, headers=headers, timeout=30)
                    resp.raise_for_status()
                else:
                    raise
        else:
            s3.put_object(
                Bucket=BUCKET_NAME, Key=key, Body=body_bytes,
                Metadata=metadata, ContentLength=len(body_bytes)
            )
        return message_id

    def list_inbox(self, persona_id: str, unread_only: bool = False) -> List[Dict[str, Any]]:
        s3 = self._get_s3_client()
        results = []
        try:
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=f"{persona_id}/"):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if not key.endswith(".eml"): continue
                    
                    head = s3.head_object(Bucket=BUCKET_NAME, Key=key)
                    meta = head.get("Metadata", {})
                    
                    # Try metadata first, fallback to Tagging
                    is_seen = meta.get("seen") == "1"
                    if "seen" not in meta:
                        try:
                            tagging = s3.get_object_tagging(Bucket=BUCKET_NAME, Key=key)
                            tags = {t["Key"]: t["Value"] for t in tagging["TagSet"]}
                            is_seen = tags.get("Seen") == "1"
                        except Exception:
                            is_seen = False

                    if unread_only and is_seen: continue

                    results.append({
                        "key": key.split("/")[-1].replace(".eml", ""),
                        "subject": meta.get("subject", "No Subject"),
                        "from": meta.get("from-id", "Unknown"),
                        "read": is_seen,
                        "date": obj["LastModified"].isoformat()
                    })
        except s3.exceptions.NoSuchBucket: return []
        except Exception as e:
            # For IA-like backends, bucket might need to be created or item might not exist
            return []
        return results

    def get_message(self, persona_id: str, key: str) -> Dict[str, Any]:
        s3 = self._get_s3_client()
        full_key = f"{persona_id}/{key}.eml"
        response = s3.get_object(Bucket=BUCKET_NAME, Key=full_key)
        raw_bytes = response["Body"].read()
        msg = email.message_from_bytes(raw_bytes, policy=policy.default)
        body = msg.get_content().strip() if hasattr(msg, 'get_content') else ""
        return {
            "key": key, "subject": msg["Subject"], "from": msg["From"],
            "to": msg["To"], "body": body, "date": msg["Date"]
        }

    def mark_read(self, persona_id: str, key: str) -> None:
        s3 = self._get_s3_client()
        full_key = f"{persona_id}/{key}.eml"

        # For S3, updating metadata requires a COPY of the object onto itself
        # This is more compatible than Tagging for IA/MinIO
        try:
            head = s3.head_object(Bucket=BUCKET_NAME, Key=full_key)
            metadata = head.get("Metadata", {})
            metadata["seen"] = "1"

            s3.copy_object(
                Bucket=BUCKET_NAME,
                Key=full_key,
                CopySource={'Bucket': BUCKET_NAME, 'Key': full_key},
                Metadata=metadata,
                MetadataDirective='REPLACE'
            )
        except Exception:
            # Fallback to tagging if COPY fails or is not desired
            try:
                s3.put_object_tagging(
                    Bucket=BUCKET_NAME, Key=full_key,
                    Tagging={'TagSet': [{'Key': 'Seen', 'Value': '1'}]}
                )
            except Exception:
                pass

def _get_backend() -> MailboxBackend:
    storage_type = os.environ.get("JULES_MAIL_STORAGE", "local").lower()
    if storage_type == "s3":
        return S3MailboxBackend()
    return LocalMaildirBackend()

def send_message(from_id: str, to_id: str, subject: str, body: str, attachments: Optional[List[str]] = None) -> str:
    if to_id == "all@team":
        # Broadcast to all personas
        # We assume .jules/personas exists relative to execution or use MAIL_ROOT.parent
        # MAIL_ROOT is .jules/mail, so parent is .jules.
        personas_dir = MAIL_ROOT.parent / "personas"
        if not personas_dir.exists():
            return _get_backend().send_message(from_id, to_id, subject, body, attachments)
        
        sent_ids = []
        for p in personas_dir.iterdir():
            if p.is_dir():
                # Send to each persona found
                # Note: This sends multiple individual messages.
                mid = _get_backend().send_message(from_id, p.name, subject, body, attachments)
                sent_ids.append(mid)
        return f"broadcast:{len(sent_ids)}-messages"
    
    return _get_backend().send_message(from_id, to_id, subject, body, attachments)


def list_inbox(*args, **kwargs): return _get_backend().list_inbox(*args, **kwargs)
def get_message(*args, **kwargs): return _get_backend().get_message(*args, **kwargs)
def mark_read(*args, **kwargs): return _get_backend().mark_read(*args, **kwargs)
