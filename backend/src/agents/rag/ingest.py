"""Code to ingest blob into a vectorstore.

Code is responsible for taking binary data, parsing it and then indexing it
into a vector store.

This code should be agnostic to how the blob got generated; i.e., it does not
know about server/uploading etc.
"""

import asyncio
import re
from typing import List

import ftfy
from langchain.text_splitter import TextSplitter
from langchain_community.document_loaders import Blob
from langchain_community.document_loaders.base import BaseBlobParser
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore


def _update_document_metadata(
    document: Document, user_id: str, document_id: str
) -> None:
    """Mutation in place that adds a user_id and document_id to the document metadata."""
    document.metadata["user_id"] = user_id
    document.metadata["document_id"] = document_id


def _sanitize_document_content(document: Document):
    """Sanitize the document."""
    # Without this, PDF ingestion fails with
    # "A string literal cannot contain NUL (0x00) characters".
    document.page_content = document.page_content.replace("\x00", "x")


def _clean_text(document: Document):
    document.page_content = ftfy.fix_text(document.page_content)
    document.page_content = re.sub(r"\s+", " ", document.page_content).strip()


async def ingest_blob(
    blob: Blob,
    parser: BaseBlobParser,
    text_splitter: TextSplitter,
    vectorstore: VectorStore,
    user_id: str,
    document_id: str,
    *,
    batch_size: int = 100,
) -> List[str]:
    """Ingest a document into the vectorstore."""
    docs_to_index = []
    ids = []

    # Parse documents in a separate thread to avoid blocking
    documents = await asyncio.to_thread(list, parser.lazy_parse(blob))

    for i, document in enumerate(documents):
        # Split documents in a separate thread to avoid blocking
        docs = await asyncio.to_thread(text_splitter.split_documents, [document])

        for doc in docs:
            _sanitize_document_content(doc)
            _update_document_metadata(doc, user_id, document_id)
            _clean_text(doc)
        docs_to_index.extend(docs)

        if len(docs_to_index) >= batch_size:
            ids.extend(await vectorstore.aadd_documents(docs_to_index))
            docs_to_index = []

        # Periodically yield control back to the event loop
        if i % 10 == 0:
            await asyncio.sleep(0)

    if docs_to_index:
        ids.extend(await vectorstore.aadd_documents(docs_to_index))

    return ids
