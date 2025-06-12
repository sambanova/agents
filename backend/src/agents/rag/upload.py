"""API to deal with file uploads via a runnable.

For now this code assumes that the content is a base64 encoded string.

The details here might change in the future.

For the time being, upload and ingestion are coupled
"""

from __future__ import annotations

import asyncio
import mimetypes
from typing import BinaryIO, List, Optional

from fastapi import UploadFile
from langchain_redis import RedisVectorStore


from langchain_core.document_loaders.blob_loaders import Blob
from langchain_core.runnables import (
    ConfigurableField,
    RunnableConfig,
    RunnableSerializable,
)
from langchain_core.vectorstores import VectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_sambanova import SambaNovaCloudEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter, TextSplitter
from pydantic import ConfigDict


from agents.rag.parsing import MIMETYPE_BASED_PARSER
from agents.rag.ingest import ingest_blob


async def _guess_mimetype(file_name: str, file_bytes: bytes) -> str:
    """Guess the mime-type of a file based on its name or bytes."""
    # Guess based on the file extension
    mime_type, _ = mimetypes.guess_type(file_name)

    # Return detected mime type from mimetypes guess, unless it's None
    if mime_type:
        return mime_type

    # Signature-based detection for common types
    if file_bytes.startswith(b"%PDF"):
        return "application/pdf"
    elif file_bytes.startswith(
        (b"\x50\x4b\x03\x04", b"\x50\x4b\x05\x06", b"\x50\x4b\x07\x08")
    ):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif file_bytes.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "application/msword"
    elif file_bytes.startswith(b"\x09\x00\xff\x00\x06\x00"):
        return "application/vnd.ms-excel"

    # Check for CSV-like plain text content (commas, tabs, newlines)
    try:
        decoded = file_bytes[:1024].decode("utf-8", errors="ignore")
        if all(char in decoded for char in (",", "\n")) or all(
            char in decoded for char in ("\t", "\n")
        ):
            return "text/csv"
        elif decoded.isprintable() or decoded == "":
            return "text/plain"
    except UnicodeDecodeError:
        pass

    return "application/octet-stream"


async def convert_ingestion_input_to_blob(file_data: bytes, file_name: str) -> Blob:
    """Convert ingestion input to blob."""

    mimetype = await _guess_mimetype(file_name, file_data)
    return Blob.from_data(
        data=file_data,
        path=file_name,
        mime_type=mimetype,
    )


def get_embeddings() -> OpenAIEmbeddings:
    return SambaNovaCloudEmbeddings(
        model="E5-Mistral-7B-Instruct",
        sambanova_api_key="f9c2c30f-faa3-464f-a8fd-e7d10160c4b1",
    )


class IngestRunnable(RunnableSerializable[BinaryIO, List[str]]):
    """Runnable for ingesting files into a vectorstore."""

    text_splitter: TextSplitter
    vectorstore: VectorStore
    user_id: Optional[str] = None
    document_id: Optional[str] = None
    """Ingested documents will be associated with user_id and document_id.
    
    ID is used as the namespace, and is filtered on at query time.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def invoke(self, blob: Blob, config: Optional[RunnableConfig] = None) -> List[str]:
        """
        Synchronous wrapper around the async `ainvoke`.
        """
        raise NotImplementedError(
            "The synchronous `invoke` method is not supported. "
            "Please use the asynchronous `ainvoke` method instead."
        )

    async def ainvoke(
        self, blob: Blob, config: Optional[RunnableConfig] = None
    ) -> List[str]:
        if self.user_id is None:
            raise ValueError("User ID is required")
        if self.document_id is None:
            raise ValueError("Document ID is required")

        out = await ingest_blob(
            blob=blob,
            parser=MIMETYPE_BASED_PARSER,
            text_splitter=self.text_splitter,
            vectorstore=self.vectorstore,
            user_id=self.user_id,
            document_id=self.document_id,
        )
        return out


vstore = RedisVectorStore(
    embeddings=get_embeddings(),
    # TODO: remove hardcoded redis url
    redis_url="redis://localhost:6379",
)


ingest_runnable = IngestRunnable(
    text_splitter=RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200),
    vectorstore=vstore,
).configurable_fields(
    user_id=ConfigurableField(
        id="user_id",
        annotation=Optional[str],
        name="User ID",
    ),
    document_id=ConfigurableField(
        id="document_id",
        annotation=Optional[str],
        name="Document ID",
    ),
)
