import os
from prompts import LLAMA_PROMPT_TEMPLATE

from llama_cloud import LlamaCloud


PARSE_CONFIGURATION = {
    "tier": "cost_effective",
    "version": "latest",
    "disable_cache": True,
    "agentic_options": {
      "custom_prompt": LLAMA_PROMPT_TEMPLATE
    },
    "output_options": {
        "markdown": {
            "tables": {
                "output_tables_as_markdown": True,
                "compact_markdown_tables": True,
                "merge_continued_tables": True,
                "markdown_table_multiline_separator": "<br />",
            }
        },
        "spatial_text": {
            "preserve_layout_alignment_across_pages": True,
            "preserve_very_small_text": True,
        },
    },
    "processing_options": {
        "ignore": {
            "ignore_diagonal_text": True,
            "ignore_text_in_image": True,
            "ignore_hidden_text": True
        }
    },
    "expand": ["markdown_full", "text_full"],
}


def parse_document(file_path, api_key=None):
    selected_api_key = api_key or os.environ.get("LLAMA_CLOUD_API_KEY")
    if not selected_api_key:
        raise RuntimeError("Set LLAMA_CLOUD_API_KEY before running the parser.")

    client = LlamaCloud(api_key=selected_api_key)
    file_obj = client.files.create(file=str(file_path), purpose="parse")
    result = client.parsing.parse(
        file_id=file_obj.id,
        **PARSE_CONFIGURATION,
    )

    return {
        "markdown": result.markdown_full or "",
        "text": result.text_full or "",
    }
