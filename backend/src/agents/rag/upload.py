from __future__ import annotations

import mimetypes
from functools import lru_cache
from typing import BinaryIO, List, Optional

import numpy as np
import redis
import structlog
from agents.rag.ingest import ingest_blob
from agents.rag.parsing import MIMETYPE_BASED_PARSER
from langchain.schema import Document
from langchain_core.document_loaders.blob_loaders import Blob
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import (
    ConfigurableField,
    RunnableConfig,
    RunnableSerializable,
)
from langchain_redis import RedisVectorStore
from langchain_sambanova import SambaNovaCloudEmbeddings, SambaStudioEmbeddings
from langchain_text_splitters import TextSplitter, TokenTextSplitter
from pydantic import BaseModel, ConfigDict
from redisvl.index import SearchIndex
from redisvl.query import HybridQuery

logger = structlog.get_logger(__name__)


class RedisHybridRetriever(BaseRetriever, BaseModel):
    """
    Hybrid retriever combining vector similarity with keyword filtering
    via RediSearch KNN + BM25 keyword search.
    """

    search_index: SearchIndex
    embedding_model: SambaNovaCloudEmbeddings
    filter_expr: str

    class Config:
        arbitrary_types_allowed = True

    def get_relevant_documents(self, query: str) -> List[Document]:
        embedding = self.embedding_model.embed_query(query)
        vector = np.array(embedding, dtype=np.float32).tobytes()

        hybrid_query = HybridQuery(
            text=query,
            text_field_name="text",
            vector=vector,
            vector_field_name="embedding",
            return_fields=["text", "user_id", "document_id"],
            filter_expression=self.filter_expr,
        )

        results = self.search_index.query(hybrid_query)

        docs: List[Document] = []
        for doc in results:
            content = doc.get("text", "")
            metadata = {k: v for k, v in doc.items() if k not in ("text",)}
            docs.append(Document(page_content=content, metadata=metadata))
        return docs


@lru_cache(maxsize=100)
def create_user_vector_store(
    api_key: str, redis_client: redis.Redis
) -> RedisVectorStore:
    # Initialize vector store with shared Redis client
    vstore = RedisVectorStore(
        embeddings=SambaNovaCloudEmbeddings(
            model="E5-Mistral-7B-Instruct",
            sambanova_api_key=api_key,
            batch_size=32,
        ),
        index_name="sambanova-rag-index",
        metadata_schema=[
            {"name": "user_id", "type": "tag"},
            {"name": "document_id", "type": "tag"},
        ],
    )
    return vstore


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


class IngestRunnable(RunnableSerializable[BinaryIO, List[str]]):
    """Runnable for ingesting files into a vectorstore."""

    text_splitter: TextSplitter
    user_id: Optional[str] = None
    document_id: Optional[str] = None
    api_key: Optional[str] = None
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

        if self.api_key:
            vectorstore = create_user_vector_store(self.api_key)

            out = await ingest_blob(
                blob=blob,
                parser=MIMETYPE_BASED_PARSER,
                text_splitter=self.text_splitter,
                vectorstore=vectorstore,
                user_id=self.user_id,
                document_id=self.document_id,
            )
            return out
        else:
            raise ValueError("API key is required")


ingest_runnable = IngestRunnable(
    text_splitter=TokenTextSplitter(chunk_size=512, chunk_overlap=128),
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
    api_key=ConfigurableField(
        id="api_key",
        annotation=Optional[str],
        name="API Key",
    ),
)
