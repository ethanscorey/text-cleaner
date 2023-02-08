from io import BytesIO
import json
import logging

import boto3
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


SCOPES = ["https://www.googleapis.com/auth/documents.readonly"]
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def lambda_handler(event, context):
    document_url = event["document_url"]
    document_id = document_url.split("/")[-2]
    bucket = boto3.resource("s3").Bucket("google-creds-appeal")
    creds = None
    try:
        token_file = BytesIO()
        bucket.download_fileobj("token.json", token_file)
        token_file.seek(0)
        token_data = json.loads(token_file.read().decode("utf-8"))
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    except:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            credentials_file = BytesIO()
            bucket.download_fileobj("credentials.json", credentials_file)
            credentials_file.seek(0)
            credentials_data = json.loads(credentials_file.read().decode("uft-8"))
            flow = InstalledAppFlow.from_client_config(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        bucket.put_object(Key="token.json", Body=creds.to_json())
    service = build("docs", "v1", credentials=creds)
    document = service.documents().get(documentId=document_id).execute()
    grafs = get_paragraphs(document)
    text = "".join("".join(paragraph_to_text(graf)) for graf in grafs)
    return {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
            "Access-Control-Allow-Headers": "Content-Type",
        },
        "body": text,
    }


def get_paragraphs(document):
    """Extract all paragraph elements from document JSON."""
    body = document.get("body")
    content = body.get("content")
    if content is not None:
        return (
            el.get("paragraph")
            for el in content
            if el.get("paragraph") is not None
        )


def paragraph_to_text(graf):
    """Convert paragraph JSON to WP text."""
    elements = graf.get("elements")
    if elements is not None:
        for el in elements:
            text_run = el.get("textRun")
            if text_run is not None:
                content = text_run.get("content", "")
                style = text_run.get("textStyle")
                if style is not None:
                    link = style.get("link")
                    if link is not None:
                        url = link.get("url")
                        content = f'&lt;a href="{url}"&gt;{content}&lt;/a&gt;'
                    if style.get("italic"):
                        content = f"&lt;em&gt;{content}&lt;/em&gt;"
                    if style.get("bold"):
                        content = f"&lt;strong&gt;{content}&lt;/strong&gt;"
                yield content
