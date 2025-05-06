import vertexai
from vertexai import agent_engines
import os
import json
from dotenv import load_dotenv
from pathlib import Path
import argparse
from typing import Dict, Any, Optional, List, Set
import uuid
import traceback

# --- Pydantic Model Import (Optional for this script's direct use) ---
try:
    from travel_concierge.shared_libraries.types import Itinerary as PydanticItinerary
    print("Successfully imported Pydantic Itinerary model for validation (vertex_ai_client.py).")
except ImportError:
    PydanticItinerary = None
    print("Could not import Pydantic Itinerary model in vertex_ai_client.py.")
# ---

REMOTE_AGENT_ENGINE = None
IS_INITIALIZED = False

def initialize_globals_and_agent() -> bool:
    global REMOTE_AGENT_ENGINE, IS_INITIALIZED
    if IS_INITIALIZED:
        print("INFO (vertex_ai_client.py): Agent already initialized.")
        return True
    print("INFO (vertex_ai_client.py): Starting agent initialization process...")
    try:
        script_dir = Path(__file__).resolve().parent
        dotenv_path = script_dir / '.env'
        print(f"INFO (vertex_ai_client.py): Attempting to load .env file from: {dotenv_path}")
        if dotenv_path.is_file():
            load_dotenv(dotenv_path=dotenv_path, verbose=True)
            print(f"INFO (vertex_ai_client.py): Successfully called load_dotenv for {dotenv_path}.")
        else:
            print(f"WARNING (vertex_ai_client.py): .env file not found at {dotenv_path}.")
    except Exception as e:
        print(f"ERROR (vertex_ai_client.py): Exception during load_dotenv: {e}")
        traceback.print_exc()

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION")
    agent_resource_id = os.getenv("REASONING_ENGINE_RESOURCE_NAME")

    print(f"DEBUG (vertex_ai_client.py): GOOGLE_CLOUD_PROJECT: {project_id}")
    print(f"DEBUG (vertex_ai_client.py): GOOGLE_CLOUD_LOCATION: {location}")
    print(f"DEBUG (vertex_ai_client.py): REASONING_ENGINE_RESOURCE_NAME: {agent_resource_id}")
    print(f"DEBUG (vertex_ai_client.py): GOOGLE_APPLICATION_CREDENTIALS (if set): {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")

    if not all([project_id, location, agent_resource_id]):
        print("ERROR (vertex_ai_client.py): Missing one or more required environment variables.")
        IS_INITIALIZED = False
        return False
    try:
        print(f"INFO (vertex_ai_client.py): Initializing Vertex AI for project '{project_id}' in location '{location}'.")
        vertexai.init(project=project_id, location=location)
        print("INFO (vertex_ai_client.py): vertexai.init() call completed.")
        print(f"INFO (vertex_ai_client.py): Attempting to get deployed agent: {agent_resource_id}")
        REMOTE_AGENT_ENGINE = agent_engines.get(agent_resource_id)
        if not REMOTE_AGENT_ENGINE:
            print(f"ERROR (vertex_ai_client.py): agent_engines.get() returned None for resource: {agent_resource_id}.")
            IS_INITIALIZED = False
            return False
        print(f"INFO (vertex_ai_client.py): Successfully retrieved agent: {REMOTE_AGENT_ENGINE.resource_name}")
        IS_INITIALIZED = True
        return True
    except Exception as e:
        print(f"ERROR (vertex_ai_client.py): Exception during Vertex AI setup: {e}")
        print("----------- TRACEBACK (vertex_ai_client.py) -----------")
        traceback.print_exc()
        print("------------------------------------------------------")
        IS_INITIALIZED = False
        return False

def process_agent_query(user_query: str, session_id: Optional[str], user_id: str) -> Dict[str, Any]:
    if not IS_INITIALIZED or not REMOTE_AGENT_ENGINE:
        error_msg = "Agent not initialized (checked in process_agent_query)."
        print(f"ERROR (vertex_ai_client.py - process_agent_query): {error_msg}")
        return {"session_id": session_id, "display_text": error_msg, "error_message": error_msg, "full_event_log": []}

    collected_display_text_parts: List[str] = []
    collected_structured_itinerary: Optional[Dict[str, Any]] = None
    collected_suggestions: List[str] = []
    collected_active_sub_agents: Set[str] = set()
    requires_follow_up_flag: bool = False
    error_message_text: Optional[str] = None
    full_event_log: List[Dict[str, Any]] = []

    try:
        query_args: Dict[str, Any] = {"message": user_query}
        if session_id: query_args["session_id"] = session_id
        if user_id: query_args["user_id"] = user_id
        print(f"AGENT_CLIENT DEBUG: Query args for stream_query: {query_args}")
        # Inside process_agent_query function in vertex_ai_client.py

        for event in REMOTE_AGENT_ENGINE.stream_query(**query_args):
            full_event_log.append(event)
            # print(f"AGENT_CLIENT RAW_EVENT: {json.dumps(event, indent=2)}") # For deep debug

            # Initialize to keep any previously found itinerary if multiple events update it (unlikely for this key)
            current_event_itinerary = None

            # 1. Check for itinerary within function_response (tool output)
            if isinstance(event, dict) and 'content' in event and isinstance(event['content'], dict) and 'parts' in event['content']:
                for part in event['content']['parts']:
                    if isinstance(part, dict) and 'text' in part and part['text']:
                        collected_display_text_parts.append(part['text'])

                    # --- MODIFIED/ADDED BLOCK for tool_code_execution_result / function_response ---
                    # Check if this part is a function_response for the itinerary_agent
                    if isinstance(part, dict) and 'function_response' in part:
                        fn_response = part['function_response']
                        if isinstance(fn_response, dict) and fn_response.get('name') == 'itinerary_agent':
                            if 'response' in fn_response and isinstance(fn_response['response'], dict):
                                # Assuming the direct response is the itinerary object
                                current_event_itinerary = fn_response['response']
                                print("AGENT_CLIENT DEBUG: Found itinerary in function_response for itinerary_agent.")
                                break # Found it in this part

                    # Keep your existing check for 'tool_code_execution_result' just in case
                    # (though function_response seems to be what ADK uses here)
                    if isinstance(part, dict) and 'tool_code_execution_result' in part:
                        tool_output = part['tool_code_execution_result']
                        # Check if the tool_output itself IS the itinerary (if output_key promotes it)
                        # OR if it's a dict containing an "itinerary" key
                        if isinstance(tool_output, dict):
                            if "itinerary" in tool_output and isinstance(tool_output["itinerary"], dict): # Nested
                                current_event_itinerary = tool_output["itinerary"]
                                print("AGENT_CLIENT DEBUG: Found itinerary nested in tool_code_execution_result.")
                                break
                            # ADK might also place the output directly if output_key is used and schema matches
                            # This would require checking if tool_output *is* an itinerary-like dict
                            # For now, assuming it's nested or in state_delta primarily for output_key.
                if current_event_itinerary: # If found in parts, use it for this event
                    collected_structured_itinerary = current_event_itinerary


            # 2. Check for itinerary in state_delta (often the most reliable for output_key)
            if isinstance(event, dict) and 'actions' in event and isinstance(event['actions'], dict) \
                and 'state_delta' in event['actions'] and isinstance(event['actions']['state_delta'], dict):
                state_delta = event['actions']['state_delta']
                if 'itinerary' in state_delta and isinstance(state_delta['itinerary'], dict):
                    # Check if it's not empty and looks like a real itinerary
                    if state_delta['itinerary']: # Ensure it's not just an empty {}
                        current_event_itinerary = state_delta['itinerary']
                        print("AGENT_CLIENT DEBUG: Found itinerary in event['actions']['state_delta'].")

            # 3. Your existing checks for common top-level or wrapped keys (fallback)
            if not current_event_itinerary and isinstance(event, dict): # Only if not found via state_delta
                if "itinerary" in event and isinstance(event["itinerary"], dict):
                    if event["itinerary"]: # Ensure not empty
                        current_event_itinerary = event["itinerary"]
                        print("AGENT_CLIENT DEBUG: Found itinerary directly in event root.")

                if not current_event_itinerary: # Only if still not found
                    for key_to_check in ["tool_output", "tool_result", "structured_output", "output"]: # Removed "tool_code_execution_output" as it's handled above
                        if key_to_check in event and isinstance(event[key_to_check], dict) and \
                            "itinerary" in event[key_to_check] and isinstance(event[key_to_check]["itinerary"], dict):
                            if event[key_to_check]["itinerary"]: # Ensure not empty
                                current_event_itinerary = event[key_to_check]["itinerary"]
                                print(f"AGENT_CLIENT DEBUG: Found itinerary in event['{key_to_check}'].")
                                break

            if current_event_itinerary:
                collected_structured_itinerary = current_event_itinerary # Update with the latest found

            # --- Collect other data (active_sub_agents, suggestions, etc. - keep as is) ---
            if isinstance(event, dict):
                if 'author' in event and isinstance(event['author'], str): collected_active_sub_agents.add(event['author'])
                # ... (rest of your existing logic for suggestions, requires_follow_up, error_message) ...
                elif 'source_agent' in event and isinstance(event['source_agent'], str): collected_active_sub_agents.add(event['source_agent'])
                if 'suggestions' in event and isinstance(event['suggestions'], list): collected_suggestions.extend(event['suggestions'])
                if 'requires_follow_up' in event and isinstance(event['requires_follow_up'], bool): requires_follow_up_flag = event['requires_follow_up']
                if 'error' in event and isinstance(event['error'], str): error_message_text = event['error']
                elif 'error_message' in event and isinstance(event['error_message'], str): error_message_text = event['error_message']

    # ... (rest of the function: final_display_text, debug prints, return statement) ...
    except Exception as e:
        error_message_text = f"ERROR during stream_query: {e}"
        print(f"\nAGENT_CLIENT ERROR: {error_message_text}")
        traceback.print_exc()

    final_display_text = "".join(collected_display_text_parts)
    if not requires_follow_up_flag and final_display_text.strip().endswith("?"):
        requires_follow_up_flag = True

    #print(f"AGENT_CLIENT DEBUG: Collected display_text_parts: {collected_display_text_parts}")
    #print(f"AGENT_CLIENT DEBUG: Final display_text: '{final_display_text}'")
    #print(f"AGENT_CLIENT DEBUG: Full event log: '{full_event_log}'")
    #print(f"AGENT_CLIENT DEBUG: Collected structured_itinerary_raw: {collected_structured_itinerary}")

    if not final_display_text.strip() and not error_message_text:
        if not full_event_log: print("\nAGENT_CLIENT WARNING: final_display_text is empty AND full_event_log is empty. Stream_query yielded no events.")
        else:
            print("\nAGENT_CLIENT WARNING: final_display_text is empty. Printing full event log for debugging:")
            for i, evt in enumerate(full_event_log):
                try: print(f"  Event {i}: {json.dumps(evt, indent=2)}")
                except TypeError: print(f"  Event {i}: (Could not serialize to JSON) {str(evt)}")
            print("--- End of full event log ---\n")

    return {
        "session_id": session_id, # Return the session_id that was *used* for the query
        "display_text": final_display_text,
        "structured_itinerary_raw": collected_structured_itinerary, "suggestions": collected_suggestions,
        "active_sub_agents": list(collected_active_sub_agents), "requires_follow_up": requires_follow_up_flag,
        "error_message": error_message_text, "full_event_log": full_event_log
    }

def run_cli_chat_loop():
    if not IS_INITIALIZED or not REMOTE_AGENT_ENGINE:
        print("Agent not initialized. Cannot start CLI chat.")
        return
    cli_user_id = "interactive_cli_user_001"
    current_cli_session_id: Optional[str] = None

    if hasattr(REMOTE_AGENT_ENGINE, 'create_session'):
        try:
            print(f"Attempting to create session for CLI user: {cli_user_id}")
            session_info = REMOTE_AGENT_ENGINE.create_session(user_id=cli_user_id)
            returned_id = None
            if isinstance(session_info, dict): returned_id = session_info.get("id")
            elif hasattr(session_info, 'id'): returned_id = session_info.id
            if returned_id:
                current_cli_session_id = returned_id
                print(f"CLI using session: {current_cli_session_id} for user: {cli_user_id}")
            else:
                current_cli_session_id = str(uuid.uuid4())
                print(f"WARNING (CLI): SDK create_session did not return ID. Using generated: {current_cli_session_id}")
        except Exception as e:
            current_cli_session_id = str(uuid.uuid4())
            print(f"Warning (CLI): SDK create_session failed: {e}. Using generated: {current_cli_session_id}")
    else:
        current_cli_session_id = str(uuid.uuid4())
        print(f"Agent engine has no 'create_session'. Using generated ID for CLI: {current_cli_session_id}")
    print("---")
    while True:
        # ... (rest of CLI loop as before) ...
        user_message = input("You: ")
        if user_message.lower() in ["exit", "quit"]: break
        if not user_message.strip(): continue
        print("Agent: ", end="", flush=True)
        response_data = process_agent_query(user_message, current_cli_session_id, cli_user_id)
        print(response_data["display_text"])
        print("\n--- Collected Response Data (CLI) ---")
        # ... (printing details) ...
        if response_data["structured_itinerary_raw"]:
            # ...
            pass
        else: print("Structured Itinerary: Not found this turn.")
        # ...
        print("---------------------------------------\n")


def print_initial_messages():
    # ... (as before) ...
    pass

if __name__ == "__main__":
    # ... (argparse and main CLI logic as before) ...
    parser = argparse.ArgumentParser(description="Interact with the Vertex AI Travel Concierge Agent.")
    parser.add_argument(
        "--mode", type=str, default="cli", choices=["cli"],
        help="Mode to run the script in. 'cli' for interactive command-line chat."
    )
    args = parser.parse_args()
    print_initial_messages()
    if not initialize_globals_and_agent():
        print("Exiting due to agent initialization failure.")
        exit(1)
    if args.mode == "cli":
        print("Starting CLI chat mode...")
        run_cli_chat_loop()
    else:
        print(f"Unknown mode: {args.mode}")