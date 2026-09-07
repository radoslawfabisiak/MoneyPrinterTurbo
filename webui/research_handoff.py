import os
from uuid import UUID

import requests
import streamlit as st


def _valid_launch_id(value) -> str | None:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        return None


def _set_param(name: str, value, language: str):
    if value is None:
        return
    st.session_state[name] = value
    st.session_state[f"{name}_{language}"] = value


def _apply_restored_params(params: dict):
    language = st.session_state.get("ui_language", "en")
    terms = params.get("video_terms") or ""
    if isinstance(terms, list):
        terms = ", ".join(str(term) for term in terms)

    for name in ("video_subject", "video_script", "video_terms"):
        _set_param(name, params.get(name) or "", language)
    _set_param("paragraph_number_input", params.get("paragraph_number", 1), language)
    _set_param("video_script_prompt", params.get("video_script_prompt") or "", language)
    _set_param("custom_system_prompt", params.get("custom_system_prompt") or "", language)
    for name in (
        "video_source_select",
        "video_concat_mode_select",
        "video_transition_mode_select",
        "video_clip_duration_select",
        "video_count_select",
        "voice_mode_control",
        "bgm_type_select",
        "bgm_volume_select",
        "voice_volume_select",
        "voice_rate_select",
    ):
        source_name = {
            "video_source_select": "video_source",
            "video_concat_mode_select": "video_concat_mode",
            "video_transition_mode_select": "video_transition_mode",
            "video_clip_duration_select": "video_clip_duration",
            "video_count_select": "video_count",
            "bgm_type_select": "bgm_type",
            "bgm_volume_select": "bgm_volume",
            "voice_volume_select": "voice_volume",
            "voice_rate_select": "voice_rate",
        }.get(name)
        if source_name:
            _set_param(name, params.get(source_name), language)

    source = params.get("video_source") or "pexels"
    _set_param(
        f"video_aspect_for_{source}",
        params.get("video_aspect") or "9:16",
        language,
    )
    _set_param(
        "video_clip_speed_slider",
        params.get("video_clip_speed", 1.0),
        language,
    )
    _set_param("video_terms", terms, language)
    _set_param("script_language_select", params.get("video_language") or "", language)
    _set_param("bgm_type_select", params.get("bgm_type") or "", language)
    _set_param("custom_bgm_file_input", params.get("bgm_file") or "", language)
    _set_param(
        "sonilo_bgm_prompt_input",
        params.get("video_music_prompt") or params.get("sonilo_bgm_prompt") or "",
        language,
    )
    _set_param("elevenlabs_music_prompt_input", params.get("video_music_prompt") or "", language)
    _set_param("subtitle_enabled_checkbox", bool(params.get("subtitle_enabled", True)), language)
    _set_param("custom_position_input", str(params.get("custom_position", 70.0)), language)
    _set_param("font_name_select", params.get("font_name") or "", language)
    _set_param("subtitle_position_select", params.get("subtitle_position") or "bottom", language)
    _set_param("font_color_picker", params.get("text_fore_color") or "#FFFFFF", language)
    _set_param("font_size_slider", params.get("font_size", 60), language)
    _set_param("stroke_color_picker", params.get("stroke_color") or "#000000", language)
    _set_param("stroke_width_slider", params.get("stroke_width", 1.5), language)
    background = params.get("text_background_color", False)
    _set_param("subtitle_background_enabled_checkbox", bool(background), language)
    if isinstance(background, str):
        _set_param("subtitle_background_color_picker", background, language)
    _set_param(
        "rounded_subtitle_background_checkbox",
        bool(params.get("rounded_subtitle_background", False)),
        language,
    )
    st.session_state["match_materials_to_script"] = bool(
        params.get("match_materials_to_script", False)
    )
    st.session_state["research_params"] = dict(params)


def hydrate_research_launch() -> dict | None:
    """Consume and hydrate one launch before any generation widget is created."""
    if st.session_state.get("research_handoff_checked"):
        return st.session_state.get("research_handoff_result")

    raw_launch_id = st.query_params.get("research_launch")
    if not raw_launch_id:
        st.session_state["research_handoff_checked"] = True
        return None

    launch_id = _valid_launch_id(raw_launch_id)
    if not launch_id:
        result = {"error": "Invalid Research launch ID."}
        st.session_state["research_handoff_result"] = result
        st.session_state["research_handoff_checked"] = True
        return result

    base_url = os.getenv(
        "MONEYPRINTER_INTERNAL_API_URL",
        "http://moneyprinter-api:8080/api/v1",
    ).rstrip("/")
    api_key = os.getenv("MONEYPRINTER_API_KEY", "")
    try:
        response = requests.post(
            f"{base_url}/integrations/research/launches/{launch_id}/consume",
            headers={"x-api-key": api_key},
            timeout=(3, 10),
        )
        if response.status_code != 200:
            result = {
                "error": (
                    f"Research launch unavailable ({response.status_code}). "
                    "Create a new launch from Research & Content Studio."
                )
            }
        else:
            envelope = response.json()
            result = envelope.get("data") or {}
            _apply_restored_params(result["params"])
            st.session_state["research_reserved_task_id"] = result["task_id"]
            st.session_state["research_source"] = result["source"]
            st.session_state["research_display_context"] = result["display_context"]
            del st.query_params["research_launch"]
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        result = {
            "error": (
                "Could not import the Research handoff. Check that the local "
                f"MoneyPrinter API is running ({type(exc).__name__})."
            )
        }

    st.session_state["research_handoff_result"] = result
    st.session_state["research_handoff_checked"] = True
    return result


def render_research_handoff_banner():
    result = st.session_state.get("research_handoff_result") or {}
    if result.get("error"):
        st.error(result["error"])
        return
    context = st.session_state.get("research_display_context")
    if context:
        st.success(
            "Imported from Research & Content Studio: "
            f"{context['brief_title']} / {context['scenario_title']} / "
            f"{context['preset_name']}"
        )
