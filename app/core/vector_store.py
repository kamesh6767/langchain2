import shutil
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma

from app.config import CHROMA_DIR
from app.core.model_factory import get_embeddings

COLLECTION_NAME = "documents_rag"


class VectorStoreManager:
    def __init__(self):
        self._vector_store: Optional[Chroma] = None

    def get_vector_store(self, reset_cache: bool = False) -> Chroma:
        if self._vector_store is None or reset_cache:
            embeddings = get_embeddings()
            try:
                self._vector_store = Chroma(
                    collection_name=COLLECTION_NAME,
                    embedding_function=embeddings,
                    persist_directory=str(CHROMA_DIR)
                )
            except Exception as e:
                if "dimension" in str(e).lower():
                    self.clear_all()
                    self._vector_store = Chroma(
                        collection_name=COLLECTION_NAME,
                        embedding_function=embeddings,
                        persist_directory=str(CHROMA_DIR)
                    )
                else:
                    raise e
        return self._vector_store

    def add_documents(self, documents: List[Document]) -> int:
        if not documents:
            return 0
        vs = self.get_vector_store()
        vs.add_documents(documents)
        return len(documents)

    def search(self, query: str, k: int = 4) -> List[Document]:
        try:
            vs = self.get_vector_store()
            return vs.similarity_search(query, k=k)
        except Exception as e:
            print(f"Vector search error: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        try:
            vs = self.get_vector_store()
            collection = vs._collection
            count = collection.count()
            
            # Fetch all metadata to group by source file
            files_map: Dict[str, Dict[str, Any]] = {}
            if count > 0:
                results = collection.get(include=["metadatas"])
                metas = results.get("metadatas", [])
                for meta in metas:
                    if meta and "source" in meta:
                        source = meta["source"]
                        filename = meta.get("filename", source.split("/")[-1].split("\\")[-1])
                        if filename not in files_map:
                            files_map[filename] = {
                                "filename": filename,
                                "chunks": 0,
                                "file_type": meta.get("file_type", "unknown"),
                                "uploaded_at": meta.get("uploaded_at", "")
                            }
                        files_map[filename]["chunks"] += 1

            return {
                "total_chunks": count,
                "total_documents": len(files_map),
                "documents": list(files_map.values())
            }
        except Exception as e:
            return {
                "total_chunks": 0,
                "total_documents": 0,
                "documents": [],
                "error": str(e)
            }

    def delete_document(self, filename: str) -> bool:
        try:
            vs = self.get_vector_store()
            collection = vs._collection
            # Delete where metadata filename or source matches
            collection.delete(where={"filename": filename})
            return True
        except Exception as e:
            print(f"Error deleting document {filename}: {e}")
            return False

    def clear_all(self) -> bool:
        try:
            if CHROMA_DIR.exists():
                shutil.rmtree(CHROMA_DIR)
                CHROMA_DIR.mkdir(parents=True, exist_ok=True)
            self._vector_store = None
            return True
        except Exception as e:
            print(f"Error clearing vector store: {e}")
            return False


vector_store_manager = VectorStoreManager()
