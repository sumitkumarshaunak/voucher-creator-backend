import json
import os

from openai import OpenAI


def get_openai_client(api_key=None):
    selected_api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not selected_api_key:
        raise RuntimeError("Set OPENAI_API_KEY before calling the LLM.")

    return OpenAI(api_key=selected_api_key)


def build_json_instructions(system_prompt, data_schema):
    return (
        system_prompt.strip()
        + "\n\nReturn the extracted document DATA as JSON. Do not return the schema itself.\n"
        + "Never include schema-only keys such as `type`, `properties`, `required`, "
        + "`additionalProperties`, `description`, or `items` in the output unless they are "
        + "explicit business fields inside the document data.\n"
        + "The required output shape is described by this JSON Schema:\n"
        + json.dumps(data_schema, indent=2)
    )


def _extract_json_response(raw, error_context):
    try:
        return json.loads(raw.output_text)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"OpenAI returned incomplete or invalid JSON while {error_context} "
            f"at response line {error.lineno}, column {error.colno}, character {error.pos}."
        ) from error


def call_llm(
    *,
    model,
    instructions,
    input_content,
    client=None,
    api_key=None,
    json_response=True,
    error_context="calling the LLM",
):
    openai_client = client or get_openai_client(api_key=api_key)

    request = {
        "model": model,
        "instructions": instructions,
        "input": [
            {
                "role": "user",
                "content": input_content,
            }
        ],
        "store": False,
    }
    if json_response:
        request["text"] = {"format": {"type": "json_object"}}

    raw = openai_client.responses.create(**request)
    print(f"LLM tokens used: {raw.usage}")

    if not json_response:
        return raw.output_text

    return _extract_json_response(raw, error_context)
