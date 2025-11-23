from core.indexing.index_pipeline import IndexPipeline

if __name__ == "__main__":
    pipeline = IndexPipeline()
    pipeline.run_for_source("cis_ubuntu_24_04")
