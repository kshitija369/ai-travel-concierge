import vertexai
from vertexai import agent_engines # Correct import based on your deploy.py and logs

import os
import json # For debugging event structures, if needed
from dotenv import load_dotenv

def main():
    # Load environment variables from .env file
    load_dotenv()

    # --- Configuration from .env file ---
    PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
    LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
    YOUR_AGENT_RESOURCE_ID = os.getenv("REASONING_ENGINE_RESOURCE_NAME")

    if not all([PROJECT_ID, LOCATION, YOUR_AGENT_RESOURCE_ID]):
        print("ERROR: Missing one or more required environment variables.")
        print("Please ensure PROJECT_ID, LOCATION, and REASONING_ENGINE_RESOURCE_NAME are set in your .env file.")
        return

    # Initialize the Vertex AI SDK
    try:
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        print(f"Initialized Vertex AI for project '{PROJECT_ID}' in location '{LOCATION}'.")
    except Exception as e:
        print(f"ERROR: Failed to initialize Vertex AI SDK: {e}")
        return

    print(f"Attempting to get deployed agent using resource name: {YOUR_AGENT_RESOURCE_ID}")

    try:
        # Get the remote agent instance using agent_engines.get()
        remote_agent_engine = agent_engines.get(YOUR_AGENT_RESOURCE_ID)

        if not remote_agent_engine:
            # Depending on the SDK, .get() might raise an exception on failure (e.g., NotFound)
            # rather than returning None. This check is a fallback.
            print(f"ERROR: Failed to get the agent instance for {YOUR_AGENT_RESOURCE_ID}. The resource might not exist or there could be a permission issue.")
            return
        
        print(f"Successfully retrieved deployed agent. Resource name from object: {remote_agent_engine.resource_name}")

        # --- Session Management (as seen in your deploy.py) ---
        user_id_for_session = "cli_chat_user_002" # Use a unique ID or make it configurable
        session_id = None
        try:
            session_info = remote_agent_engine.create_session(user_id=user_id_for_session)
            # The structure of session_info (dict vs object) depends on the SDK version/ADK wrapper
            if isinstance(session_info, dict):
                session_id = session_info.get("id")
            elif hasattr(session_info, 'id'):
                session_id = session_info.id
            
            if not session_id:
                print(f"WARNING: Could not retrieve session_id from session_info: {session_info}. Proceeding without session if agent allows.")
            else:
                print(f"Created session: {session_id} for user: {user_id_for_session}")
        except Exception as e:
            print(f"Warning: Could not create session (agent might not use them, or an error occurred): {e}")
            # Proceeding with session_id as None
        print("---")

        # --- Interaction Loop ---
        while True:
            user_message = input("You: ")
            if user_message.lower() in ["exit", "quit"]:
                print("Exiting chat.")
                break
            if not user_message.strip():
                continue

            print("Agent: ", end="", flush=True)
            agent_spoke_text = False

            try:
                # Prepare arguments for stream_query
                # Based on your deploy.py, it uses `message`, `user_id`, and `session_id`
                query_args = {"message": user_message}
                if session_id: # Only add session_id and user_id if a session was established
                    query_args["session_id"] = session_id
                    query_args["user_id"] = user_id_for_session
                
                for event in remote_agent_engine.stream_query(**query_args):
                    # For debugging the full event structure:
                    # print(f"\nDEBUG_EVENT: {json.dumps(event, indent=2)}")

                    if isinstance(event, dict) and 'content' in event and isinstance(event['content'], dict) and 'parts' in event['content']:
                        for part in event['content']['parts']:
                            if isinstance(part, dict) and 'text' in part and part['text']:
                                print(part['text'], end="", flush=True)
                                agent_spoke_text = True
                            # Optional: Handle function calls for more detailed output
                            # elif isinstance(part, dict) and 'function_call' in part:
                            #     fc = part['function_call']
                            #     author = event.get('author', 'Agent') # Get author from event if available
                            #     print(f"\n[{author} calls function: {fc.get('name')}]", end="", flush=True)
                            #     agent_spoke_text = True 
                
                print() # Final newline after the agent's full streamed response

                if not agent_spoke_text:
                    print("[Agent may have performed an action without sending a text message this turn.]")

            except Exception as e:
                print(f"\nERROR during stream_query: {e}")
                import traceback
                traceback.print_exc()
                break # Exit loop on stream error
            
            print("---")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Query Agent Script")
    print("------------------")
    print("Make sure you have authenticated with Google Cloud: `gcloud auth application-default login`")
    print("Ensure required Python libraries are installed (e.g., google-cloud-aiplatform, python-dotenv).")
    print("Your .env file should be present in the same directory and correctly configured with:")
    print("  PROJECT_ID, LOCATION, and REASONING_ENGINE_RESOURCE_NAME.\n")
    main()
